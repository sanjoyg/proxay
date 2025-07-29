import argparse
import re
import sys

from termcolor import cprint

from .rewrite import RewriteRule, RewriteRules
from .server import RecordReplayServer


def rewrite_rule_type(value: str) -> RewriteRule:
    RE_SED_INPUT_VALIDATION = r"s/(.+?)/(.*?)/([gims]*)"
    match = re.fullmatch(RE_SED_INPUT_VALIDATION, value)
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid rewrite rule format: {value}. Expected s/find/replace/flags."
        )

    find_str, replace_str, flags_str = match.groups()

    py_flags = 0
    if "i" in flags_str:
        py_flags |= re.IGNORECASE
    if "m" in flags_str:
        py_flags |= re.MULTILINE
    if "s" in flags_str:
        py_flags |= re.DOTALL

    try:
        find_regex = re.compile(find_str, py_flags)
    except re.error as e:
        raise argparse.ArgumentTypeError(f"Invalid regex '{find_str}': {e}")

    replace_str_py = re.sub(r"\\([1-9]\d*)", r"\\g<\1>", replace_str)

    return RewriteRule(find=find_regex, replace=replace_str_py)


def main():
    parser = argparse.ArgumentParser(
        description="A proxy server for recording and replaying HTTP interactions.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-m", "--mode", type=str, required=True,
        choices=["record", "replay", "mimic", "passthrough"],
        help="Operating mode."
    )
    parser.add_argument(
        "--default-tape", type=str, default="default",
        help="Name of the default tape to use."
    )
    parser.add_argument(
        "--host", type=str,
        help="Host to proxy (e.g., https://api.example.com). Not required in replay mode."
    )
    parser.add_argument(
        "-p", "--port", type=int, default=3000,
        help="Local port to serve on."
    )
    parser.add_argument(
        "--redis-host", type=str, default="localhost", help="Redis server host."
    )
    parser.add_argument(
        "--redis-port", type=int, default=6379, help="Redis server port."
    )

    # Other options
    parser.add_argument(
        "--send-proxy-port", action="store_true",
        help="Sends proxy's port to the proxied host in the Host header."
    )
    parser.add_argument(
        "--exact-request-matching", action="store_true",
        help="Perform exact request matching during replay."
    )
    parser.add_argument(
        "--debug-matcher-fails", action="store_true",
        help="Show debug info for failed matches in exact mode."
    )
    parser.add_argument(
        "-r", "--redact-headers", type=lambda s: s.split(","), default=[],
        help="Comma-separated list of request headers to redact."
    )

    prevent_group = parser.add_mutually_exclusive_group()
    prevent_group.add_argument(
        "--drop-conditional-request-headers", action="store_true", dest="prevent_conditional_requests", default=True,
        help="Drop If-* headers from requests in record mode (default)."
    )
    prevent_group.add_argument(
        "--no-drop-conditional-request-headers", action="store_false", dest="prevent_conditional_requests",
        help="Disable dropping of If-* headers."
    )

    parser.add_argument(
        "--rewrite-before-diff", action="append", type=rewrite_rule_type, default=[],
        help="sed-style rewrite rule (s/find/replace/flags) applied before matching."
    )
    parser.add_argument(
        "--ignore-headers", type=lambda s: s.split(","), default=[],
        help="Comma-separated list of headers to ignore during matching."
    )

    args = parser.parse_args()

    # --- Validations ---
    if args.mode not in ["replay", "passthrough"] and not args.host:
        cprint("Error: --host is required for record and mimic modes.", "red", file=sys.stderr)
        sys.exit(1)
    if args.host and "://" not in args.host:
        cprint("Error: Please include the scheme (http:// or https://) in the host.", "red", file=sys.stderr)
        sys.exit(1)
    if args.debug_matcher_fails and not args.exact_request_matching:
        cprint("Error: --debug-matcher-fails can only be used with --exact-request-matching.", "red", file=sys.stderr)
        sys.exit(1)

    rewrite_rules = RewriteRules(args.rewrite_before_diff)

    server = RecordReplayServer(
        initial_mode=args.mode,
        default_tape_name=args.default_tape,
        host=args.host,
        proxy_port_to_send=args.port if args.send_proxy_port else None,
        redact_headers=args.redact_headers,
        prevent_conditional_requests=args.prevent_conditional_requests,
        rewrite_before_diff_rules=rewrite_rules,
        ignore_headers=args.ignore_headers,
        exact_request_matching=args.exact_request_matching,
        debug_matcher_fails=args.debug_matcher_fails,
        redis_host=args.redis_host,
        redis_port=args.redis_port,
    )

    cprint(f"Starting Proxay in {args.mode} mode on port {args.port}.", "green")
    if args.mode != "replay":
        cprint(f"Proxying to: {args.host}", "blue")

    server.start(port=args.port)

if __name__ == "__main__":
    main()
