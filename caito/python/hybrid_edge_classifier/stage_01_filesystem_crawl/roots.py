"""Cross-platform, project-local roots for explicitly invoked lab workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Final


DEFAULT_LAB_CORPUS_DIRECTORY: Final = "corpus"
DEFAULT_LAB_CORPUS_ROOT: Final = (
    Path(__file__).resolve().parents[3] / DEFAULT_LAB_CORPUS_DIRECTORY
)


def default_lab_corpus_root() -> Path:
    """Return the project-local corpus root without reading or creating it.

    Resolving from this package location avoids a macOS/Windows-specific
    absolute path and avoids treating the caller's working directory or home
    directory as an implicit collection root.
    """

    return DEFAULT_LAB_CORPUS_ROOT
