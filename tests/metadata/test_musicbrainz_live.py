import pytest
import musicbrainzngs

from tidalist.config import AppConfig
from tidalist.core.recording import Candidate
from tidalist.metadata.musicbrainz import MusicBrainzMetadata


@pytest.mark.integration
def test_traffic_glad_excludes_traffic_sound_live():
    cfg = AppConfig.load()
    if not cfg.musicbrainz_contact:
        pytest.skip("no musicbrainz.contact configured")
    musicbrainzngs.set_useragent("tidalist", "1.0", cfg.musicbrainz_contact)
    recs = MusicBrainzMetadata(musicbrainzngs).recordings_for(Candidate("Traffic", "Glad"))
    assert recs, "expected Traffic 'Glad' recordings"
    artists = {r.artist for r in recs}
    assert all("Traffic Sound" not in a for a in artists)   # the identity bug we fixed
    assert any(a == "Traffic" for a in artists)
