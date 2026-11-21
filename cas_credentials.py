"""Local credential management for CAS Monster."""

import argparse
import getpass
import json
import os
import re

import keyring
from keyring.errors import KeyringError, PasswordDeleteError


SERVICE = "CAS Monster MCP"
ENTRY = "WFLA school account"
DEFAULT_PROFILE = "default"


def profile_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", value):
        raise argparse.ArgumentTypeError("Use 1–32 letters, digits, hyphens or underscores, starting with a letter or digit.")
    return value.lower()


def credential_entry(profile: str) -> str:
    return ENTRY if profile == DEFAULT_PROFILE else f"{ENTRY} / {profile}"


def school_credentials(*, profile: str = DEFAULT_PROFILE) -> tuple[str, str]:
    profile = profile_name(profile)
    # Preserve the original environment login for the default instance.
    if profile == DEFAULT_PROFILE:
        username = os.environ.get("CAS_MONSTER_USERNAME")
        password = os.environ.get("CAS_MONSTER_PASSWORD")
        if username or password:
            if username and password:
                return username, password
            raise ValueError("Set both CAS_MONSTER_USERNAME and CAS_MONSTER_PASSWORD.")
    try:
        stored = keyring.get_password(SERVICE, credential_entry(profile))
    except KeyringError:
        raise ValueError("Could not open the OS credential store.") from None
    if not stored:
        raise ValueError(
            f"CAS profile {profile!r} has no school login. "
            f"Run python -m cas_credentials set --profile {profile} in your terminal."
        )
    login = json.loads(stored)
    return login["username"], login["password"]


def save_credentials(username: str, password: str, *, profile: str = DEFAULT_PROFILE) -> None:
    if not username.strip() or not password:
        raise ValueError("Both username and password are required.")
    keyring.set_password(SERVICE, credential_entry(profile_name(profile)), json.dumps({
        "username": username.strip(),
        "password": password,
    }))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("set", "forget"))
    parser.add_argument("--profile", type=profile_name, default=DEFAULT_PROFILE, help="Local school account alias")
    args = parser.parse_args()
    if args.action == "set":
        save_credentials(input("School username: "), getpass.getpass("School password: "), profile=args.profile)
        print(f"School login saved for profile {args.profile!r} in the OS credential store.")
    else:
        try:
            keyring.delete_password(SERVICE, credential_entry(args.profile))
        except PasswordDeleteError:
            pass
        print(f"School login removed for profile {args.profile!r}.")


if __name__ == "__main__":
    main()
