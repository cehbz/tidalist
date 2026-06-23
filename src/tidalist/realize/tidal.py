"""TidalRealizer: the Realizer port for Tidal, built on the Platform port.

It composes a Platform (TidalPlatform in production), so all tidalapi specifics stay in
the Platform adapter. resolve() matches a recording to a track ISRC-first, then by
closeness; emit() creates a playlist and adds the resolved tracks.
"""

from ..core.ports import Platform
from ..core.identifiers import TrackId
from ..core.recording import Recording, Performance
from ..core.catalog import Track
from ..core.realize import PlatformItem, MatchQuality
from ..core.fidelity import (
    PlatformCandidate, IdentityFacet, EditionFacet, PerformanceFacet, choose,
    recording_artist_match, Compromise,
)
from ..core.edition import EditionPreference
from ..core.album import Album


class TidalRealizer:
    def __init__(self, platform: Platform):
        self._platform = platform

    def resolve(self, recording: Recording) -> tuple[PlatformItem | None, tuple[Compromise, ...]]:
        if recording.isrc is not None:
            track = self._platform.track_by_isrc(recording.isrc)
            if track is not None:
                return _item(track, MatchQuality.ISRC), ()
        hits = self._platform.search_tracks(_query(recording))
        candidates = [_track_candidate(t) for t in hits]
        if not candidates:
            return None, ()
        chosen, comps = choose(recording, candidates, [IdentityFacet(), PerformanceFacet()])
        if chosen is None:
            return None, ()
        return _item_from_candidate(chosen, _quality_for(recording, chosen)), comps

    def resolve_album(
        self,
        album: Album,
        preference: EditionPreference,
    ) -> tuple[list[PlatformItem], tuple]:
        survivors = self._search_survivors(album)
        if not survivors:
            return [], ()
        anchor = survivors[0]
        # The discography gives the full edition set; fall back to the search
        # survivors when it's empty (so `editions` is always non-empty here).
        editions = self._platform.album_editions(anchor.id) or survivors
        candidates = [self._candidate(e, with_tracks=bool(album.tracklist)) for e in editions]
        facets = [IdentityFacet(), EditionFacet(preference)]
        chosen, comps = choose(album, candidates, facets)
        if chosen is None:
            return [], ()
        tracks = chosen.tracks or tuple(self._platform.album_tracks(TrackId(chosen.ref)))
        items = [_item(t, MatchQuality.STRONG) for t in tracks]
        return items, comps

    def _candidate(self, edition, with_tracks: bool) -> PlatformCandidate:
        tracks = tuple(self._platform.album_tracks(edition.id)) if with_tracks else ()
        return PlatformCandidate(ref=str(edition.id), title=edition.title,
                                 artists=edition.artists, year=edition.year, tracks=tracks)

    def _search_survivors(self, album: Album):
        for query in _anchor_queries(album):
            hits = self._platform.search_albums(query)
            survivors = [
                c for c in hits
                if _artist_match_album(album.artist, c.artists)
                and _title_match_album(album.title, c.title)
            ]
            if survivors:
                return survivors
        return []

    def emit(self, name: str, items: list[PlatformItem]) -> str:
        playlist = self._platform.create_playlist(name)
        self._platform.add_tracks(playlist, [TrackId(i.ref) for i in items])
        return str(playlist)


def _query(recording: Recording) -> str:
    return f"{recording.artist} {recording.title}".strip()


def _strip_leading_the(s: str) -> str:
    return s[4:] if s.casefold().startswith("the ") else s


def _anchor_queries(album: Album):
    """Yield de-duplicated search queries for album, from most to least specific."""
    seen: set[str] = set()
    candidates = [
        f"{album.artist} {album.title}",
        f"{_strip_leading_the(album.artist)} {album.title}",
        album.title,
    ]
    for q in candidates:
        if q not in seen:
            seen.add(q)
            yield q


def _item(track: Track, quality: MatchQuality) -> PlatformItem:
    return PlatformItem(ref=str(track.id), title=track.title, artists=track.artists,
                        isrc=track.isrc, quality=quality)


def _norm(s: str | None) -> str:
    return (s or "").casefold().strip()


def _artist_match_album(artist: str, catalog_artists: tuple[str, ...]) -> bool:
    a = artist.casefold()
    return any(a in ca.casefold() or ca.casefold() in a for ca in catalog_artists)


def _title_match_album(title: str, catalog_title: str) -> bool:
    t = title.casefold()
    ct = catalog_title.casefold()
    return t in ct or ct in t


_LIVE_MARKERS = ("(live", "[live", " live at ", " - live", "live in ", "live from", "unplugged")


def _observe_performance(title: str) -> Performance:
    t = title.casefold()
    return Performance.LIVE if any(m in t for m in _LIVE_MARKERS) else Performance.UNKNOWN


def _track_candidate(track: Track) -> PlatformCandidate:
    return PlatformCandidate(
        ref=str(track.id), title=track.title, artists=track.artists,
        isrc=track.isrc, duration_s=track.duration_s,
        performance=_observe_performance(track.title),
    )


def _item_from_candidate(cand: PlatformCandidate, quality: MatchQuality) -> PlatformItem:
    return PlatformItem(ref=cand.ref, title=cand.title, artists=cand.artists,
                        isrc=cand.isrc, quality=quality)


def _quality_for(recording: Recording, cand: PlatformCandidate) -> MatchQuality:
    title_ok = _norm(recording.title) == _norm(cand.title)
    artist_ok = recording_artist_match(recording, cand.artists)
    return MatchQuality.STRONG if title_ok and artist_ok else MatchQuality.WEAK
