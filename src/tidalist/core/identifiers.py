"""Strong identifier aliases for the domain."""

from typing import NewType

ISRC = NewType("ISRC", str)        # International Standard Recording Code
MBID = NewType("MBID", str)        # MusicBrainz Recording ID
TrackId = NewType("TrackId", str)  # catalog (Tidal) track id
PlaylistId = NewType("PlaylistId", str)
