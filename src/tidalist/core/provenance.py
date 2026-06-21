"""Provenance: where a candidate came from (a scaruffi line, an nl rationale)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str        # "scaruffi" | "nl"
    note: str = ""
