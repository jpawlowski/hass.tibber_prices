"""
Put rewritten release notes into a release-please pull request body without breaking it.

release-please reads the body back when the release pull request is merged: the notes sit between the first and the
last line that is exactly ``---``, and start with a heading that names the version. A body without the delimiters
makes it skip the release; one without the heading gives a release without notes. This keeps both and replaces only
what follows the heading. The parsing mirrors ``splitBody`` and ``extractSingleRelease`` in release-please's
``src/util/pull-request-body.ts``.

Usage: release_notes_body.py PR_BODY_FILE NOTES_FILE — prints the new body, or fails with a message.
"""

from pathlib import Path
import re
import sys

DELIMITER = "---"
VERSION_HEADING = re.compile(r"^#{2,} \[?(?P<version>\d+\.\d+\.\d+[^\]\s]*)\]?")


class BodyError(ValueError):
    """The pull request body is not one release-please can read back."""


def _split(body: str) -> tuple[list[str], list[str], list[str]]:
    lines = body.strip().replace("\r\n", "\n").split("\n")
    if DELIMITER not in lines:
        raise BodyError("the body has no '---' line, so it is not a release-please body")
    first = lines.index(DELIMITER)
    last = len(lines) - 1 - lines[::-1].index(DELIMITER)
    if last == first:
        last = len(lines) - 1
    return lines[:first], lines[first + 1 : last], lines[last + 1 :]


def version_of(body: str) -> str | None:
    """Return the version release-please would read from this body, or None."""
    try:
        _, content, _ = _split(body)
    except BodyError:
        return None
    match = VERSION_HEADING.match("\n".join(content).strip())
    return match["version"] if match else None


def merge(pr_body: str, notes: str) -> str:
    """Return ``pr_body`` with the notes under its version heading replaced by ``notes``."""
    header, content, footer = _split(pr_body)
    heading = "\n".join(content).strip().split("\n", 1)[0]
    if not VERSION_HEADING.match(heading):
        raise BodyError("the body names no version, so release-please would publish a release without notes")
    lines = notes.strip().replace("\r\n", "\n").split("\n")
    own = "\n".join(line for line in lines if line != DELIMITER and not VERSION_HEADING.match(line)).strip()
    if not own:
        raise BodyError("the rewritten notes are empty, so the release would have no notes")
    parts = ["\n".join(header), DELIMITER, "", heading, "", own, "", DELIMITER]
    return "\n".join(parts) + ("\n" + "\n".join(footer) if footer else "") + "\n"


def main(argv: list[str]) -> int:
    """Print the merged body for the two files given."""
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    try:
        sys.stdout.write(merge(Path(argv[0]).read_text(encoding="utf-8"), Path(argv[1]).read_text(encoding="utf-8")))
    except BodyError as error:
        print(f"release_notes_body: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
