"""
Site-specific parsers for different ransomware leak sites.

Each parser implements the BaseParser interface and handles the unique
authentication, directory listing, and download logic for its site.

Registry
--------
Parsers register themselves by SITE_NAME.  Use ``get_parser()`` to
instantiate the right one:

    >>> from parsers import get_parser
    >>> parser = get_parser("lockbit", session)
"""

from .base import BaseParser
from .lockbit import LockbitParser
from .dragonforce import DragonForceParser
from .incransom import INCRansomParser

__all__ = [
    "BaseParser",
    "LockbitParser",
    "DragonForceParser",
    "INCRansomParser",
    "get_parser",
    "list_parsers",
    "PARSER_REGISTRY",
]

# ─── Registry ───────────────────────────────────────────────────────

PARSER_REGISTRY = {
    "lockbit": LockbitParser,
    "dragonforce": DragonForceParser,
    "incransom": INCRansomParser,
}


def get_parser(site_type: str, session, **kwargs) -> BaseParser:
    """
    Factory: return a parser instance for the given site type.

    Args:
        site_type: One of the keys in PARSER_REGISTRY
        session: requests.Session with Tor proxy configured
        **kwargs: Forwarded to parser constructor (e.g. cookies_file)

    Raises:
        ValueError: If site_type is not recognised
    """
    cls = PARSER_REGISTRY.get(site_type)
    if cls is None:
        valid = ", ".join(sorted(PARSER_REGISTRY))
        raise ValueError(f"Unknown site type '{site_type}'. Valid: {valid}")
    return cls(session, **kwargs)


def list_parsers():
    """Return dict of {site_name: parser_class} for all registered parsers."""
    return dict(PARSER_REGISTRY)
