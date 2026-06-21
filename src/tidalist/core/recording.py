"""Recording: a performance's identity. Candidate: a request to find one."""

from dataclasses import dataclass
from enum import StrEnum

from .identifiers import ISRC


class Performance(StrEnum):
    """How a recording was made (a live take is a distinct ISRC). Distinct from Edition."""
    STUDIO = "studio"
    LIVE = "live"
    SESSION = "session"
    DEMO = "demo"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Credit:
    artist: str
    role: str  # "performer", "vocals", "guitar", "composer", ...


@dataclass(frozen=True, slots=True)
class Recording:
    isrc: ISRC | None
    performance: Performance
    credits: tuple[Credit, ...]
    first_released: int | None

    def is_live(self) -> bool:
        return self.performance is Performance.LIVE

    def performs(self, artist: str) -> bool:
        """Whether `artist` is among the performer credits (so: not a cover)."""
        a = artist.casefold()
        return any(a in c.artist.casefold() or c.artist.casefold() in a
                   for c in self.credits if c.role == "performer")


@dataclass(frozen=True, slots=True)
class Candidate:
    """A described item to find in the catalog: one track, or a whole album."""
    artist: str
    title: str
    album: str | None = None
    year: int | None = None
    isrc: ISRC | None = None
    whole_album: bool = False

    def __post_init__(self):
        if not self.artist.strip() or not self.title.strip():
            raise ValueError("Candidate requires a non-empty artist and title")

    def search_query(self) -> str:
        # Broad: artist + title. album is a resolver pin, not a search term.
        return f"{self.artist} {self.title}".strip()
