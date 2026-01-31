"""Logging setup.

Keeps console output readable while you iterate locally and in Docker/systemd.
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger.

    Args:
        level: e.g. 'DEBUG', 'INFO', 'WARNING'
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
