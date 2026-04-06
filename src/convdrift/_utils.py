from __future__ import annotations

from pathlib import Path

from watchfiles import Change


def transcript_was_updated(
    changes: set[tuple[Change, str]], transcript_path: Path
) -> bool:
    for change, changed_path in changes:
        if Path(changed_path) != transcript_path:
            continue
        if change in {Change.added, Change.modified}:
            return True
    return False
