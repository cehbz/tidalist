"""JSON-pure (de)serialization of the durable golden artifact and the intent hand-off.

Criteria are a closed discriminated union (a `type` tag), so a front-end emits only
known rule types, we validate by tag, and we never eval model output.
"""

from .identifiers import ISRC, MBID
from .recording import Candidate, Credit, Recording, Performance, Kind
from .album import Album
from .criteria import PerformedBy, Studio, NotCompilation, NotLive, Criterion, Verdict
from .brief import Brief
from .provenance import Provenance
from .golden import GoldenPlaylist, GoldenEntry


# --- criteria (discriminated union) ------------------------------------------

def _criterion_to_dict(c: Criterion) -> dict:
    if isinstance(c, PerformedBy):
        return {"type": "performed_by", "artist": c.artist}
    if isinstance(c, Studio):
        return {"type": "studio"}
    if isinstance(c, NotCompilation):
        return {"type": "not_compilation"}
    if isinstance(c, NotLive):
        return {"type": "not_live"}
    raise ValueError(f"unserializable criterion: {type(c).__name__}")


def _criterion_from_dict(d: dict) -> Criterion:
    kind = d["type"]
    if kind == "performed_by":
        return PerformedBy(d["artist"])
    if kind == "studio":
        return Studio()
    if kind == "not_compilation":
        return NotCompilation()
    if kind == "not_live":
        return NotLive()
    raise ValueError(f"unknown criterion type: {kind!r}")


# --- value objects -----------------------------------------------------------

def _candidate_to_dict(c: Candidate) -> dict:
    return {"artist": c.artist, "title": c.title, "album": c.album,
            "year": c.year, "isrc": c.isrc, "kind": c.kind.value}


def _candidate_from_dict(d: dict) -> Candidate:
    return Candidate(d["artist"], d["title"], d.get("album"), d.get("year"),
                     _isrc(d.get("isrc")), Kind(d.get("kind", "track")))


def _brief_to_dict(b: Brief) -> dict:
    return {"criteria": [_criterion_to_dict(c) for c in b.criteria]}


def _brief_from_dict(name: str, d: dict) -> Brief:
    return Brief(name, tuple(_criterion_from_dict(c) for c in d.get("criteria", [])))


def _provenance_to_dict(p: Provenance) -> dict:
    return {"source": p.source, "note": p.note}


def _verdict_to_dict(v: Verdict) -> dict:
    return {"admitted": v.admitted, "violations": list(v.violations)}


def _isrc(value):
    return ISRC(value) if value is not None else None


def _mbid(value):
    return MBID(value) if value is not None else None


# --- golden artifact (the durable, portable product) -------------------------

def _golden_entry_to_dict(e: GoldenEntry) -> dict:
    prov_verdict = {
        "provenance": _provenance_to_dict(e.provenance),
        "verdict": _verdict_to_dict(e.verdict),
    }
    if isinstance(e.item, Album):
        a = e.item
        return {"kind": "album", "mbid": a.mbid, "artist": a.artist,
                "title": a.title, "year": a.first_released,
                "primary_type": a.primary_type,
                "secondary_types": list(a.secondary_types),
                **prov_verdict}
    r = e.item
    return {
        "kind": "track",
        "mbid": r.mbid, "isrc": r.isrc, "artist": r.artist, "title": r.title,
        "album": r.album, "year": r.first_released, "duration_s": r.duration_s,
        "performance": r.performance.value,
        "credits": [{"artist": c.artist, "role": c.role} for c in r.credits],
        **prov_verdict,
    }


def _golden_entry_from_dict(d: dict) -> GoldenEntry:
    prov, v = d["provenance"], d["verdict"]
    provenance = Provenance(prov["source"], prov.get("note", ""))
    verdict = Verdict(v["admitted"], tuple(v.get("violations", [])))
    if d.get("kind", "track") == "album":
        item = Album(artist=d["artist"], title=d["title"],
                     mbid=_mbid(d.get("mbid")), first_released=d.get("year"),
                     primary_type=d.get("primary_type"),
                     secondary_types=tuple(d.get("secondary_types") or ()))
    else:
        item = Recording(
            artist=d["artist"], title=d["title"], mbid=_mbid(d.get("mbid")),
            isrc=_isrc(d.get("isrc")), album=d.get("album"),
            first_released=d.get("year"), duration_s=d.get("duration_s"),
            performance=Performance(d["performance"]),
            credits=tuple(Credit(c["artist"], c["role"]) for c in d.get("credits", [])))
    return GoldenEntry(item, provenance, verdict)


def to_golden(golden: GoldenPlaylist) -> dict:
    return {
        "name": golden.name,
        "brief": _brief_to_dict(golden.brief),
        "entries": [_golden_entry_to_dict(e) for e in golden.entries],
    }


def from_golden(data: dict) -> GoldenPlaylist:
    brief = _brief_from_dict(data["name"], data.get("brief", {}))
    entries = tuple(_golden_entry_from_dict(e) for e in data.get("entries", []))
    return GoldenPlaylist(data["name"], brief, entries)


# --- intent artifact (front-end hand-off: candidates + per-line notes + brief) -

def to_intent(brief: Brief, candidates: list[Candidate],
              provenances: list[Provenance]) -> dict:
    return {
        "name": brief.name,
        "brief": _brief_to_dict(brief),
        "candidates": [{**_candidate_to_dict(c), "note": p.note}
                       for c, p in zip(candidates, provenances)],
    }


def from_intent(data: dict, source: str = "nl") -> tuple[list[Candidate], list[Provenance], Brief]:
    brief = _brief_from_dict(data["name"], data.get("brief", {}))
    candidates, provenances = [], []
    for cd in data.get("candidates", []):
        candidates.append(_candidate_from_dict(cd))
        provenances.append(Provenance(source, cd.get("note", "")))
    return candidates, provenances, brief
