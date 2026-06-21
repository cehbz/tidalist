"""PlaylistSpec: serializable, JSON-pure hand-off between agent, human, and tool.

Criteria and ranking are a closed discriminated union (a `type` tag), so the agent
emits only known rule types, we validate by tag, and we never eval model output.
"""

from .identifiers import ISRC, MBID, TrackId
from .recording import Candidate, Credit, Recording, Performance
from .catalog import Edition, Track
from .criteria import PerformedBy, Studio, Criterion, Verdict
from .ranking import PreferOriginal, Ranking
from .brief import Brief
from .proposal import Proposal, Provenance
from .golden import GoldenPlaylist, GoldenEntry


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
    return {"artist": r.artist, "title": r.title, "mbid": r.mbid, "isrc": r.isrc,
            "album": r.album, "first_released": r.first_released,
            "duration_s": r.duration_s, "performance": r.performance.value,
            "credits": [{"artist": c.artist, "role": c.role} for c in r.credits]}


def _recording_from_dict(d: dict | None) -> Recording | None:
    if d is None:
        return None
    return Recording(
        artist=d["artist"], title=d["title"], mbid=_mbid(d.get("mbid")),
        isrc=_isrc(d.get("isrc")), album=d.get("album"),
        first_released=d.get("first_released"), duration_s=d.get("duration_s"),
        performance=Performance(d["performance"]),
        credits=tuple(Credit(c["artist"], c["role"]) for c in d.get("credits", [])))


def _isrc(value):
    return ISRC(value) if value is not None else None


def _mbid(value):
    return MBID(value) if value is not None else None


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
    brief = _brief_from_dict(data["name"], data)
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


# --- golden artifact (the durable, portable product) -------------------------

def _brief_from_dict(name: str, d: dict) -> Brief:
    return Brief(name,
                 tuple(_criterion_from_dict(c) for c in d.get("criteria", [])),
                 _ranking_from_dict(d.get("ranking", {})))


def _provenance_to_dict(p: Provenance) -> dict:
    return {"source": p.source, "note": p.note}


def _verdict_to_dict(v: Verdict) -> dict:
    return {"admitted": v.admitted, "violations": list(v.violations)}


def _golden_entry_to_dict(e: GoldenEntry) -> dict:
    r = e.recording
    return {
        "mbid": r.mbid, "isrc": r.isrc, "artist": r.artist, "title": r.title,
        "album": r.album, "year": r.first_released, "duration_s": r.duration_s,
        "performance": r.performance.value,
        "credits": [{"artist": c.artist, "role": c.role} for c in r.credits],
        "provenance": _provenance_to_dict(e.provenance),
        "verdict": _verdict_to_dict(e.verdict),
    }


def _golden_entry_from_dict(d: dict) -> GoldenEntry:
    rec = Recording(
        artist=d["artist"], title=d["title"], mbid=_mbid(d.get("mbid")),
        isrc=_isrc(d.get("isrc")), album=d.get("album"),
        first_released=d.get("year"), duration_s=d.get("duration_s"),
        performance=Performance(d["performance"]),
        credits=tuple(Credit(c["artist"], c["role"]) for c in d.get("credits", [])))
    prov, v = d["provenance"], d["verdict"]
    return GoldenEntry(rec, Provenance(prov["source"], prov.get("note", "")),
                       Verdict(v["admitted"], tuple(v.get("violations", []))))


def to_golden(golden: GoldenPlaylist) -> dict:
    return {
        "name": golden.name,
        "brief": {"criteria": [_criterion_to_dict(c) for c in golden.brief.criteria],
                  "ranking": _ranking_to_dict(golden.brief.ranking)},
        "entries": [_golden_entry_to_dict(e) for e in golden.entries],
    }


def from_golden(data: dict) -> GoldenPlaylist:
    brief = _brief_from_dict(data["name"], data.get("brief", {}))
    entries = tuple(_golden_entry_from_dict(e) for e in data.get("entries", []))
    return GoldenPlaylist(data["name"], brief, entries)
