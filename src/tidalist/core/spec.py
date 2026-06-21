"""PlaylistSpec: serializable, JSON-pure hand-off between agent, human, and tool.

Criteria and ranking are a closed discriminated union (a `type` tag), so the agent
emits only known rule types, we validate by tag, and we never eval model output.
"""

from .identifiers import ISRC, TrackId
from .recording import Candidate, Credit, Recording, Performance
from .catalog import Edition, Track
from .criteria import PerformedBy, Studio, Criterion, Verdict
from .ranking import PreferOriginal, Ranking
from .brief import Brief
from .proposal import Proposal, Provenance


# --- criteria (discriminated union) ------------------------------------------

def _criterion_to_dict(c: Criterion) -> dict:
    if isinstance(c, PerformedBy):
        return {"type": "performed_by", "artist": c.artist}
    if isinstance(c, Studio):
        return {"type": "studio"}
    raise ValueError(f"unserializable criterion: {type(c).__name__}")


def _criterion_from_dict(d: dict) -> Criterion:
    kind = d["type"]
    if kind == "performed_by":
        return PerformedBy(d["artist"])
    if kind == "studio":
        return Studio()
    raise ValueError(f"unknown criterion type: {kind!r}")


def _ranking_to_dict(r: Ranking) -> dict:
    if isinstance(r, PreferOriginal):
        return {"type": "prefer_original"}
    raise ValueError(f"unserializable ranking: {type(r).__name__}")


def _ranking_from_dict(d: dict) -> Ranking:
    kind = d.get("type", "prefer_original")
    if kind == "prefer_original":
        return PreferOriginal()
    raise ValueError(f"unknown ranking type: {kind!r}")


# --- value objects -----------------------------------------------------------

def _candidate_to_dict(c: Candidate) -> dict:
    return {"artist": c.artist, "title": c.title, "album": c.album,
            "year": c.year, "isrc": c.isrc, "whole_album": c.whole_album}


def _candidate_from_dict(d: dict) -> Candidate:
    return Candidate(d["artist"], d["title"], d.get("album"), d.get("year"),
                     _isrc(d.get("isrc")), d.get("whole_album", False))


def _track_to_dict(t: Track | None) -> dict | None:
    if t is None:
        return None
    return {"id": t.id, "title": t.title, "artists": list(t.artists), "isrc": t.isrc,
            "album": t.album, "year": t.year, "edition": t.edition.value,
            "duration_s": t.duration_s}


def _track_from_dict(d: dict | None) -> Track | None:
    if d is None:
        return None
    return Track(id=TrackId(d["id"]), title=d["title"], artists=tuple(d["artists"]),
                 isrc=_isrc(d.get("isrc")), album=d.get("album"), year=d.get("year"),
                 edition=Edition(d.get("edition", Edition.UNKNOWN.value)),
                 duration_s=d.get("duration_s"))


def _recording_to_dict(r: Recording | None) -> dict | None:
    if r is None:
        return None
    return {"isrc": r.isrc, "performance": r.performance.value,
            "credits": [{"artist": c.artist, "role": c.role} for c in r.credits],
            "first_released": r.first_released}


def _recording_from_dict(d: dict | None) -> Recording | None:
    if d is None:
        return None
    return Recording(_isrc(d.get("isrc")), Performance(d["performance"]),
                     tuple(Credit(c["artist"], c["role"]) for c in d.get("credits", [])),
                     d.get("first_released"))


def _isrc(value):
    return ISRC(value) if value is not None else None


# --- top level ---------------------------------------------------------------

def to_spec(brief: Brief, proposals: list[Proposal]) -> dict:
    return {
        "name": brief.name,
        "criteria": [_criterion_to_dict(c) for c in brief.criteria],
        "ranking": _ranking_to_dict(brief.ranking),
        "proposals": [{
            "candidate": _candidate_to_dict(p.candidate),
            "provenance": {"source": p.provenance.source, "note": p.provenance.note},
            "track": _track_to_dict(p.track),
            "recording": _recording_to_dict(p.recording),
            "verdict": {"admitted": p.verdict.admitted,
                        "violations": list(p.verdict.violations)},
        } for p in proposals],
    }


def from_spec(data: dict) -> tuple[Brief, list[Proposal]]:
    brief = Brief(
        data["name"],
        tuple(_criterion_from_dict(c) for c in data.get("criteria", [])),
        _ranking_from_dict(data.get("ranking", {})),
    )
    proposals = []
    for pd in data.get("proposals", []):
        v = pd["verdict"]
        prov = pd["provenance"]
        proposals.append(Proposal(
            _candidate_from_dict(pd["candidate"]),
            _track_from_dict(pd.get("track")),
            _recording_from_dict(pd.get("recording")),
            Verdict(v["admitted"], tuple(v.get("violations", []))),
            Provenance(prov["source"], prov.get("note", "")),
        ))
    return brief, proposals
