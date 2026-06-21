import pytest

from tidalist.core.recording import Performance, Credit, Recording, Candidate


def _recording(performance=Performance.STUDIO,
               credits=(Credit("Steve Winwood", "performer"),)):
    return Recording(isrc=None, performance=performance, credits=credits,
                     first_released=1970)


def test_live_recording_is_live():
    assert _recording(performance=Performance.LIVE).is_live() is True


def test_studio_recording_is_not_live():
    assert _recording(performance=Performance.STUDIO).is_live() is False


def test_performs_matches_performer_case_insensitively():
    assert _recording().performs("steve winwood") is True


def test_performs_rejects_someone_not_credited():
    assert _recording().performs("Eric Clapton") is False


def test_performs_ignores_non_performer_roles():
    rec = _recording(credits=(Credit("Steve Winwood", "composer"),))
    assert rec.performs("Steve Winwood") is False


def test_candidate_search_query_combines_artist_and_title():
    assert Candidate("Traffic", "John Barleycorn").search_query() == "Traffic John Barleycorn"


def test_candidate_search_query_is_broad_artist_and_title_only():
    # album is a resolver pin, not a search term, so a slightly-off album name
    # never narrows the broad search and drops the track.
    c = Candidate("Traffic", "John Barleycorn", album="John Barleycorn Must Die")
    assert c.search_query() == "Traffic John Barleycorn"


def test_candidate_requires_artist_and_title():
    with pytest.raises(ValueError):
        Candidate("", "x")
    with pytest.raises(ValueError):
        Candidate("x", "  ")
