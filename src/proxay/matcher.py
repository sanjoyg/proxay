import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set
from urllib.parse import parse_qs, urlparse

from deepdiff import DeepDiff
from thefuzz import fuzz

from .http import HttpRequest
from .rewrite import RewriteRules
from .tape import TapeRecord

DEFAULT_HEADERS_TO_IGNORE = [
    "accept",
    "accept-encoding",
    "age",
    "cache-control",
    "clear-site-data",
    "connection",
    "expires",
    "from",
    "host",
    "postman-token",
    "pragma",
    "referer",
    "referer-policy",
    "te",
    "trailer",
    "transfer-encoding",
    "user-agent",
    "warning",
    "x-datadog-trace-id",
    "x-datadog-parent-id",
    "traceparent",
]


@dataclass
class Match:
    record: TapeRecord
    similarity: float
    exact: bool
    debug_info: Dict[str, Any] = field(default_factory=dict)


def _compare_urls(req_url: str, rec_url: str) -> float:
    return fuzz.ratio(req_url, rec_url) / 100.0


def _compare_bodies(req_body: bytes, rec_body: bytes) -> float:
    try:
        # Try to compare as JSON objects for more semantic comparison
        req_json = json.loads(req_body)
        rec_json = json.loads(rec_body)
        diff = DeepDiff(req_json, rec_json, ignore_order=True)
        # Higher similarity for fewer differences
        return 1.0 - (len(diff.get("values_changed", {})) / (len(req_json) or 1))
    except (json.JSONDecodeError, TypeError):
        # Fallback to string similarity
        return fuzz.ratio(req_body.decode("utf-8", "ignore"), rec_body.decode("utf-8", "ignore")) / 100.0


def _compare_queries(
    req_query: Dict, rec_query: Dict, debug: bool
) -> tuple[bool, dict]:
    diff = DeepDiff(req_query, rec_query, ignore_order=True)
    is_match = not diff
    debug_info = diff.to_dict() if debug and not is_match else {}
    return is_match, debug_info


def _compare_headers(
    req_headers: Dict, rec_headers: Dict, ignore: List[str], debug: bool
) -> tuple[bool, dict]:
    ignore_lower = [h.lower() for h in ignore] + DEFAULT_HEADERS_TO_IGNORE

    def filter_headers(headers: Dict) -> Dict:
        return {k: v for k, v in headers.items() if k.lower() not in ignore_lower}

    filtered_req = filter_headers(req_headers)
    filtered_rec = filter_headers(rec_headers)

    diff = DeepDiff(filtered_req, filtered_rec, ignore_order=True, ignore_case=True)
    is_match = not diff
    debug_info = diff.to_dict() if debug and not is_match else {}
    return is_match, debug_info


def find_record_matches(
    request: HttpRequest,
    tape_records: List[TapeRecord],
    rewrite_before_diff_rules: RewriteRules,
    exact: bool,
    debug_matcher_fails: bool,
    ignore_headers: List[str],
) -> List[Match]:
    matches: List[Match] = []

    req_parse_result = urlparse(request.path)
    req_query = parse_qs(req_parse_result.query)

    for record in tape_records:
        rec_parse_result = urlparse(record.request.path)

        # Rewrite paths before comparison if rules are provided
        req_path_to_compare = rewrite_before_diff_rules.rewrite(req_parse_result.path)
        rec_path_to_compare = rewrite_before_diff_rules.rewrite(rec_parse_result.path)

        if request.method != record.request.method or req_path_to_compare != rec_path_to_compare:
            continue

        rec_query = parse_qs(rec_parse_result.query)
        query_match, query_diff = _compare_queries(req_query, rec_query, debug_matcher_fails)

        headers_match, headers_diff = _compare_headers(
            request.headers, record.request.headers, ignore_headers, debug_matcher_fails
        )

        is_exact_match = query_match and headers_match

        if exact:
            if is_exact_match:
                matches.append(Match(record=record, similarity=1.0, exact=True))
            elif debug_matcher_fails:
                debug_info = {"query": query_diff, "headers": headers_diff}
                # Log this info or attach it somewhere
                print(f"DEBUG MATCHER FAILS for {request.path}: {debug_info}")

        else: # Best effort matching
            body_similarity = _compare_bodies(request.body, record.request.body)
            # A simple weighted average. Can be tuned.
            similarity = (body_similarity * 0.6) + (float(query_match) * 0.2) + (float(headers_match) * 0.2)
            matches.append(Match(record=record, similarity=similarity, exact=is_exact_match))

    return sorted(matches, key=lambda m: m.similarity, reverse=True)


def find_next_record_to_replay(
    matches: List[Match], replayed_tapes: Set[TapeRecord]
) -> TapeRecord | None:
    for match in matches:
        if match.record not in replayed_tapes:
            return match.record
    return None
