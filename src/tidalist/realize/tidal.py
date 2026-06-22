"""TidalRealizer: the Realizer port for Tidal, built on the Catalog port.

It composes a Catalog (TidalCatalog in production), so all tidalapi specifics stay in
the Catalog adapter. resolve() matches a recording to a track ISRC-first, then by
closeness; emit() creates a playlist and adds the resolved tracks.
"""

from ..core.ports import Catalog
from ..core.identifiers import TrackId
from ..core.recording import Recording
from ..core.catalog import Track
from ..core.realize import PlatformItem, MatchQuality, EditionOption, choose_edition
from ..core.edition import EditionPreference
from ..core.album import Album


class TidalRealizer:
    def __init__(self, catalog: Catalog):
        self._catalog = catalog

    def resolve(self, recording: Recording) -> PlatformItem | None:
        if recording.isrc is not None:
            track = self._catalog.track_by_isrc(recording.isrc)
            if track is not None:
                return _item(track, MatchQuality.ISRC)
        hits = self._catalog.search_tracks(_query(recording))
        if not hits:
            return None
        best = min(hits, key=lambda t: _closeness(recording, t))
        return _item(best, _quality(recording, best))

    def resolve_album(
        self,
        album: Album,
        preference: EditionPreference,
    ) -> tuple[list[PlatformItem], str | None]:
        survivors = self._search_survivors(album)
        if not survivors:
            return [], None
        anchor = survivors[0]
        # The discography gives the full edition set; fall back to the search
        # survivors when it's empty (so `editions` is always non-empty here).
        editions = self._catalog.album_editions(anchor.id) or survivors
        if album.tracklist:
            options = [
                EditionOption(
                    ref=str(e.id),
                    title=e.title,
                    year=e.year,
                    tracks=tuple(self._catalog.album_tracks(e.id)),
                )
                for e in editions
            ]
        else:
            options = [
                EditionOption(ref=str(e.id), title=e.title, year=e.year)
                for e in editions
            ]
        chosen, compromise = choose_edition(options, preference, album)
        if chosen is None:
            return [], None
        tracks = chosen.tracks or tuple(self._catalog.album_tracks(TrackId(chosen.ref)))
        items = [_item(t, MatchQuality.STRONG) for t in tracks]
        return items, compromise

    def _search_survivors(self, album: Album):
        for query in _anchor_queries(album):
            hits = self._catalog.search_albums(query)
            survivors = [
                c for c in hits
                if _artist_match_album(album.artist, c.artists)
                and _title_match_album(album.title, c.title)
            ]
            if survivors:
                return survivors
        return []

    def emit(self, name: str, items: list[PlatformItem]) -> str:
        playlist = self._catalog.create_playlist(name)
        self._catalog.add_tracks(playlist, [TrackId(i.ref) for i in items])
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


def _closeness(recording: Recording, track: Track) -> tuple:
    """Sort key, lower is closer: title, then artist, then album, then duration delta."""
    title = 0 if _norm(recording.title) == _norm(track.title) else 1
    artist = 0 if _artist_match(recording, track) else 1
    album = 0 if _album_match(recording, track) else 1
    dur = abs((recording.duration_s or 0) - (track.duration_s or 0))
    return (title, artist, album, dur)


def _artist_match(recording: Recording, track: Track) -> bool:
    performers = {_norm(c.artist) for c in recording.credits if c.role == "performer"}
    performers.add(_norm(recording.artist))
    return any(p and any(p in _norm(a) or _norm(a) in p for a in track.artists)
               for p in performers)


def _album_match(recording: Recording, track: Track) -> bool:
    return bool(recording.album and track.album
                and _norm(recording.album) in _norm(track.album))


def _artist_match_album(artist: str, catalog_artists: tuple[str, ...]) -> bool:
    a = artist.casefold()
    return any(a in ca.casefold() or ca.casefold() in a for ca in catalog_artists)


def _title_match_album(title: str, catalog_title: str) -> bool:
    t = title.casefold()
    ct = catalog_title.casefold()
    return t in ct or ct in t


def _quality(recording: Recording, track: Track) -> MatchQuality:
    title, artist, _, _ = _closeness(recording, track)
    return MatchQuality.STRONG if title == 0 and artist == 0 else MatchQuality.WEAK
