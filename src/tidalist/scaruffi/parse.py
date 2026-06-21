"""Parse Scaruffi's classical HTML page into the intent triple (candidates, provenances, brief).

Each entry is "Composer: Work" + "Recommended recording: <performer> (<year|label>)" with
optional "(also …)" / "X or Y" alternates. The primary recommendation becomes a Candidate
(artist = performer, title = "Composer: Work", whole_album); the alternates ride in the
provenance note. The brief carries no hard criteria — Scaruffi's pick is the discrimination.
"""

import re

from bs4 import BeautifulSoup

from ..core.recording import Candidate
from ..core.provenance import Provenance
from ..core.brief import Brief
from ..core.ranking import PreferOriginal


def parse_scaruffi(html: str, *, name: str = "Scaruffi Classical"
                   ) -> tuple[list[Candidate], list[Provenance], Brief]:
    candidates: list[Candidate] = []
    provenances: list[Provenance] = []
    for composer, work, recording_text in _entries(html):
        performer, year, alternates = _primary(recording_text)
        if not performer:
            continue
        candidates.append(Candidate(artist=performer, title=f"{composer}: {work}",
                                    year=year, whole_album=True))
        note = f"{composer}: {work} — {performer}"
        if alternates:
            note += f" (also {', '.join(alternates)})"
        provenances.append(Provenance("scaruffi", note))
    return candidates, provenances, Brief(name, (), PreferOriginal())


def _entries(html: str):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return
    block: list[str] = []
    for raw in table.get_text().split("\n"):
        line = raw.strip()
        if line:
            block.append(line)
        else:
            yield from _entry(block)
            block = []
    yield from _entry(block)


def _entry(block: list[str]):
    if len(block) < 2 or ":" not in block[0] or not block[1].startswith("Recommended recording:"):
        return
    composer, work = (s.strip() for s in block[0].split(":", 1))
    if composer and work:
        yield composer, work, block[1].replace("Recommended recording:", "").strip()


def _primary(text: str) -> tuple[str | None, int | None, list[str]]:
    alternates: list[str] = []
    if " or " in text and "(also" not in text:
        head, *rest = text.split(" or ")
        alternates = [_performer_year(p.strip())[0] for p in rest]
    elif "(also" in text:
        head, tail = text.split("(also", 1)
        tail = tail.rstrip(")").strip()
        alternates = [_performer_year(p.strip())[0] for p in re.split(r"[,;]", tail) if p.strip()]
    else:
        head = text
    performer, year = _performer_year(head.strip())
    return performer, year, [a for a in alternates if a]


def _performer_year(text: str) -> tuple[str | None, int | None]:
    text = text.strip()
    if not text:
        return None, None
    if " on " in text:                       # "Andras Schiff on ECM"
        return text.split(" on ")[0].strip(), None
    paren = re.search(r"\(([^)]+)\)", text)
    if paren is None:
        return text, None
    performer = text[:paren.start()].strip()
    year = re.match(r"^(\d{4})(?:\s*[-&]\s*\d{2,4})?$", paren.group(1).strip())
    return performer, (int(year.group(1)) if year else None)
