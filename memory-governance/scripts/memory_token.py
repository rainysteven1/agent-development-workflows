#!/usr/bin/env python3
"""Print the workspace Memory bearer token for Codex provider auth."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path


DEFAULT_CREDENTIAL = Path.home() / ".config/surveying/team-knowledge-memory.json"


def load_token(path: Path) -> str:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise ValueError("Memory credential loading requires O_NOFOLLOW support")
    try:
        descriptor = os.open(path, os.O_RDONLY | no_follow | getattr(os, "O_CLOEXEC", 0))
    except OSError as error:
        raise ValueError("Memory credential path must be a regular, non-symlink file") from error
    with os.fdopen(descriptor, encoding="utf-8") as credential:
        metadata = os.fstat(credential.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Memory credential path must be a regular file")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise ValueError("Memory credential file must have mode 0600")
        if metadata.st_uid != os.getuid():
            raise ValueError("Memory credential file must be owned by the current user")
        payload = json.load(credential)
    token = payload.get("codex_user_key") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token or "\n" in token or "\r" in token:
        raise ValueError("Memory credential record has no valid codex_user_key")
    return token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-file", type=Path, default=DEFAULT_CREDENTIAL)
    args = parser.parse_args()
    print(load_token(args.credential_file))


if __name__ == "__main__":
    main()
