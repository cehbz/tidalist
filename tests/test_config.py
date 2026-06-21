from tidalist.config import AppConfig


def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(text)
    return p


def test_loads_discogs_and_musicbrainz(tmp_path):
    p = _write(tmp_path, "discogs:\n  token: TOK\n  rate_limit: 30\n"
                         "musicbrainz:\n  contact: me@example.com\n")
    cfg = AppConfig.load(p)
    assert cfg.discogs_token == "TOK"
    assert cfg.discogs_rate_limit == 30
    assert cfg.musicbrainz_contact == "me@example.com"


def test_defaults_when_file_missing(tmp_path):
    cfg = AppConfig.load(tmp_path / "nope.yaml")
    assert cfg.discogs_token is None
    assert cfg.discogs_rate_limit == 60
    assert cfg.musicbrainz_contact is None


def test_session_file_lives_in_config_dir(tmp_path):
    p = _write(tmp_path, "discogs:\n  token: X\n")
    assert AppConfig.load(p).session_file == tmp_path / "tidal_session.json"


def test_defaults_when_sections_absent(tmp_path):
    cfg = AppConfig.load(_write(tmp_path, "{}\n"))
    assert cfg.discogs_token is None and cfg.discogs_rate_limit == 60
