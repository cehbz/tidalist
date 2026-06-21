"""Draft a set of proposals from a brief, publish accepted ones."""

from .ports import Catalog
from .recording import Candidate
from .brief import Brief
from .proposal import Proposal, Provenance
from .resolve import Resolver
from .identifiers import PlaylistId
from .errors import CatalogError


class Curator:
    def __init__(self, resolver: Resolver):
        self._resolver = resolver

    def draft(self, brief: Brief, candidates: list[Candidate], source: str) -> list[Proposal]:
        provenance = Provenance(source)
        return [self._resolver.resolve(c, brief, provenance) for c in candidates]


class Publisher:
    def __init__(self, catalog: Catalog):
        self._catalog = catalog

    def publish(self, name: str, proposals: list[Proposal]) -> PlaylistId:
        ids: list = []
        seen: set = set()
        for p in proposals:
            if p.admissible and p.track.id not in seen:
                seen.add(p.track.id)
                ids.append(p.track.id)
        if not ids:
            raise CatalogError(f"nothing admissible to publish for playlist '{name}'")
        playlist = self._catalog.create_playlist(name)
        self._catalog.add_tracks(playlist, ids)
        return playlist
