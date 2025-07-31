import difflib
from typing import List, Set

from .models import HttpRequest, TapeRecord


class MatchResult:
    """Represents the result of a match between a request and a tape record."""

    def __init__(self, record: TapeRecord, score: float):
        self.record = record
        self.score = score

    def __repr__(self) -> str:
        return f"MatchResult(score={self.score}, record={self.record.request.path})"


def _calculate_similarity(a: str, b: str) -> float:
    """Calculates the similarity between two strings."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def find_record_matches(
    request: HttpRequest, tape_records: List[TapeRecord]
) -> List[MatchResult]:
    """
    Finds all records on the tape that match the given request, and scores them.
    This is a simplified version of the original's similarity matching.
    """
    matches: List[MatchResult] = []
    for record in tape_records:
        # Score is a combination of method, path, and body similarity.
        # Method match is binary: 1 for match, 0 for mismatch.
        method_score = 1 if request.method.lower() == record.request.method.lower() else 0

        # Path similarity
        path_score = _calculate_similarity(request.path, record.request.path)

        # Body similarity
        # A proper implementation would compare JSON structures, etc.
        # For now, we compare the raw byte strings.
        body_score = _calculate_similarity(
            request.body.decode("utf-8", "ignore"),
            record.request.body.decode("utf-8", "ignore"),
        )

        # Simple weighted average for the final score.
        # We weigh method and path higher than the body.
        final_score = (method_score * 0.4) + (path_score * 0.4) + (body_score * 0.2)

        if final_score > 0.5: # Only consider matches with a reasonable score
            matches.append(MatchResult(record, final_score))

    # Sort matches from best to worst
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def find_next_record_to_replay(
    matches: List[MatchResult], replayed_tapes: Set[TapeRecord]
) -> TapeRecord | None:
    """
    Finds the best matching record that has not been replayed yet.
    """
    for match in matches:
        if match.record not in replayed_tapes:
            return match.record
    return None
