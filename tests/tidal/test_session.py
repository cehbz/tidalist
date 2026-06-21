import pytest

from tidalist.tidal.session import authenticate
from tidalist.core.errors import CatalogError


class _FakeSession:
    def __init__(self, *, loads=False, logged_in=False, login_succeeds=True):
        self._loads = loads
        self._logged_in = logged_in
        self._login_succeeds = login_succeeds
        self.oauth_called = False
        self.saved_to = None

    def load_session_from_file(self, path):
        return self._loads

    def check_login(self):
        return self._logged_in

    def login_oauth_simple(self):
        self.oauth_called = True
        self._logged_in = self._login_succeeds

    def save_session_to_file(self, path):
        self.saved_to = path


def test_uses_valid_cached_session_without_oauth(tmp_path):
    sf = tmp_path / "tidal_session.json"
    sf.write_text("{}")
    session = _FakeSession(loads=True, logged_in=True)
    out = authenticate(sf, session_factory=lambda: session)
    assert out is session
    assert session.oauth_called is False


def test_oauth_and_save_when_no_cached_file(tmp_path):
    sf = tmp_path / "missing.json"
    session = _FakeSession(loads=False)
    authenticate(sf, session_factory=lambda: session)
    assert session.oauth_called is True
    assert session.saved_to == sf


def test_oauth_when_cached_session_invalid(tmp_path):
    sf = tmp_path / "tidal_session.json"
    sf.write_text("{}")
    session = _FakeSession(loads=False)  # file present but unloadable
    authenticate(sf, session_factory=lambda: session)
    assert session.oauth_called is True


def test_raises_when_login_fails(tmp_path):
    session = _FakeSession(loads=False, login_succeeds=False)
    with pytest.raises(CatalogError):
        authenticate(tmp_path / "missing.json", session_factory=lambda: session)
