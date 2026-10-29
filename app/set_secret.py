"""Prompt for a secret without echo and update only its assignment in the project .env."""
import argparse
from getpass import GetPassWarning, getpass
from pathlib import Path
import warnings

from dotenv import set_key

from .config import ROOT

SECRET_NAMES = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "APP_ACCESS_TOKEN", "OWNER_WEBHOOK_URL")


def main(argv=None, *, path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=SECRET_NAMES)
    name = parser.parse_args(argv).name
    try:
        # Refuse getpass's echoing fallback when a suitable terminal is unavailable.
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            value = getpass(f"Enter {name} (hidden): ")
            confirmation = getpass("Confirm value (hidden): ")
        if not value or any(char in value for char in ("\r", "\n", "\x00")):
            print("ERROR: enter a non-empty, single-line value. Nothing was written.")
            return 1
        if value != confirmation:
            print("ERROR: values do not match. Nothing was written.")
            return 1
        set_key(path or ROOT / ".env", name, value, quote_mode="always", encoding="utf-8")
    except (Exception, KeyboardInterrupt):
        print("ERROR: secret was not saved. Use a terminal with hidden input and check file access.")
        return 1
    print(f"Saved {name} in the project .env. The value is not shown.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
