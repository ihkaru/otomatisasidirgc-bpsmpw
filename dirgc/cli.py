import argparse

from playwright.sync_api import sync_playwright

from .browser import ActivityMonitor, ensure_on_dirgc, install_user_activity_tracking
from .credentials import load_credentials
from .processor import process_excel_rows
from .settings import (
    DEFAULT_CREDENTIALS_FILE,
    DEFAULT_EXCEL_FILE,
    DEFAULT_IDLE_TIMEOUT_MS,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Login, process Excel rows, and stop after filling GC fields."
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (may not work for SSO).",
    )
    parser.add_argument(
        "-m",
        "--manual-only",
        action="store_true",
        help="Skip auto-fill and always use manual login.",
    )
    parser.add_argument(
        "-c",
        "--credentials-file",
        help=(
            "Path to JSON credentials file with username/password. "
            f"Defaults to {DEFAULT_CREDENTIALS_FILE} if present."
        ),
    )
    parser.add_argument(
        "-e",
        "--excel-file",
        help=(
            "Path to Excel file. "
            f"Defaults to {DEFAULT_EXCEL_FILE} if present."
        ),
    )
    parser.add_argument(
        "-start",
        "--start",
        dest="start_row",
        type=int,
        help="Start row (1-based) to process from the Excel file.",
    )
    parser.add_argument(
        "-end",
        "--end",
        dest="end_row",
        type=int,
        help="End row (1-based, inclusive) to process from the Excel file.",
    )
    parser.add_argument(
        "-t",
        "--idle-timeout-ms",
        type=int,
        default=DEFAULT_IDLE_TIMEOUT_MS,
        help="Stop if no user input or bot action for this long.",
    )
    parser.add_argument(
        "-k",
        "--keep-open",
        action="store_true",
        help="Keep the browser open until you press Enter.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.start_row is not None and args.start_row < 1:
        parser.error("--start must be >= 1.")
    if args.end_row is not None and args.end_row < 1:
        parser.error("--end must be >= 1.")
    if (
        args.start_row is not None
        and args.end_row is not None
        and args.start_row > args.end_row
    ):
        parser.error("--start must be <= --end.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context()
        page = context.new_page()

        monitor = ActivityMonitor(page, args.idle_timeout_ms)
        install_user_activity_tracking(page, monitor.mark_activity)

        credentials = None
        if not args.manual_only:
            credentials = load_credentials(args.credentials_file)

        ensure_on_dirgc(
            page,
            monitor=monitor,
            use_saved_credentials=not args.manual_only,
            credentials=credentials,
        )
        process_excel_rows(
            page,
            monitor=monitor,
            excel_file=args.excel_file,
            use_saved_credentials=not args.manual_only,
            credentials=credentials,
            start_row=args.start_row,
            end_row=args.end_row,
        )

        if args.keep_open:
            input("Press Enter to close the browser...")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
