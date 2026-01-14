import json
import os

from .settings import DEFAULT_CREDENTIALS_FILE, LEGACY_CREDENTIALS_FILE


def resolve_credentials_path(credentials_file):
    if credentials_file:
        return os.path.expanduser(credentials_file)

    candidates = [
        os.path.join(os.getcwd(), DEFAULT_CREDENTIALS_FILE),
        os.path.join(os.getcwd(), LEGACY_CREDENTIALS_FILE),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def load_credentials(credentials_file):
    username = os.environ.get("DIRGC_USERNAME")
    password = os.environ.get("DIRGC_PASSWORD")

    path = resolve_credentials_path(credentials_file)
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        username = data.get("username") or username
        password = data.get("password") or password

    return username, password
