"""Authenticate a tidalapi Session: reuse a cached session, else OAuth and cache it."""

from pathlib import Path

import tidalapi

from ..core.errors import PlatformError


def authenticate(session_file: Path, *, session_factory=tidalapi.Session) -> tidalapi.Session:
    session = session_factory()
    if _load_cached(session, session_file):
        return session
    session.login_oauth_simple()  # interactive: prints a link.tidal.com URL
    if not session.check_login():
        raise PlatformError("Tidal OAuth login failed")
    session.save_session_to_file(session_file)
    return session


def _load_cached(session: tidalapi.Session, session_file: Path) -> bool:
    if not session_file.exists():
        return False
    try:
        return bool(session.load_session_from_file(session_file)) and session.check_login()
    except Exception:
        return False  # corrupt or stale cache: fall back to a fresh login
