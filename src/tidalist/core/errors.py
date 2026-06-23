"""Domain error hierarchy."""


class TidalistError(Exception):
    """Base for all tidalist domain errors."""


class PlatformError(TidalistError):
    """A platform (streaming service) operation failed or is impossible."""


class MetadataError(TidalistError):
    """A metadata provider lookup failed."""


class ResolutionError(TidalistError):
    """A candidate could not be resolved to a platform track."""
