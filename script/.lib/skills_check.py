"""
Validate the agent skills under .agents/skills/.

Checks conformance with the Agent Skills open standard (https://agentskills.io/specification)
plus the conventions this repository adds on top of it:

- frontmatter parses and only uses spec-defined fields
- ``name`` matches the directory and the spec's naming rules
- ``description`` is present and within the 1024 character limit
- SKILL.md body stays within the recommended 500 lines
- reference files sit exactly one level below SKILL.md
- relative markdown links resolve, in the skills and in every file that points into them
- every skill is listed in the catalogues that template sync can update
- no concrete project identifiers leak in (they must stay template-sync safe)
- the marker blocks initialize.sh strips or rewrites are intact

Invoked by script/skills-check; not intended to be run directly.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys

SKILLS_DIR = Path(".agents/skills")
INSTRUCTIONS_DIR = Path(".agents/instructions")

# https://agentskills.io/specification#frontmatter
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_MAX_LENGTH = 64
DESCRIPTION_MAX_LENGTH = 1024
BODY_MAX_LINES = 500

# Identifiers that initialize.sh rewrites. Skills must use the <domain> and {ClassPrefix}
# placeholders instead, otherwise template sync would overwrite an initialized repository
# with the blueprint's own names.
FORBIDDEN_IDENTIFIERS = ("ha_integration_domain", "IntegrationBlueprint")

# Instructions files that are meant to load in every session, so they carry no `paths`.
UNCONDITIONAL_INSTRUCTIONS = {"blueprint.commit-message.instructions.md"}

# AGENTS.md is a blueprint catalogue, but initialized repositories own and exclude it from
# template sync. Their synchronized catalogue is the skills README.
SKILLS_CATALOGUE = SKILLS_DIR / "README.md"
AGENTS_CATALOGUE = Path("AGENTS.md")

LINK_PATTERN = re.compile(r"\[[^\]]*\]\((?!https?:|mailto:|#)([^)]+)\)")

# Sections initialize.sh strips when a project is initialised from the template.
MARKER_START = "<!-- blueprint-only:start -->"
MARKER_END = "<!-- blueprint-only:end -->"

# The repository-role block initialize.sh rewrites, rather than strips.
ROLE_FILE = Path("AGENTS.md")
ROLE_MARKER_START = "<!-- repo-role:start -->"
ROLE_MARKER_END = "<!-- repo-role:end -->"


@dataclass
class Report:
    """Collected problems for a single skill."""

    skill: str
    errors: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        """Record a problem."""
        self.errors.append(message)


def parse_frontmatter(text: str, report: Report) -> tuple[dict[str, object], int]:
    """
    Extract the YAML frontmatter as a mapping and the line where the body starts.

    Parsed with a real YAML parser on purpose. Descriptions contain colons, quotes and
    backticks, so a naive ``key: value`` split silently accepts frontmatter that agents
    would fail to load.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        report.error("SKILL.md must start with a '---' frontmatter delimiter")
        return {}, 0

    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        report.error("frontmatter is never closed with '---'")
        return {}, 0

    try:
        import yaml  # noqa: PLC0415  (optional; only needed here)
    except ImportError:
        report.error("PyYAML is unavailable — run script/setup/bootstrap so frontmatter can be validated")
        return {}, end + 1

    try:
        parsed = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as err:
        report.error(f"frontmatter is not valid YAML: {err}")
        return {}, end + 1

    if not isinstance(parsed, dict):
        report.error("frontmatter must be a YAML mapping")
        return {}, end + 1

    return parsed, end + 1


def check_frontmatter(skill_dir: Path, fields: Mapping[str, object], report: Report) -> None:
    """Validate the frontmatter fields against the spec."""
    unknown = sorted(set(fields) - SPEC_FIELDS)
    if unknown:
        report.error(f"frontmatter has non-spec fields (reduces portability): {', '.join(unknown)}")

    name = fields.get("name") or ""
    if not isinstance(name, str):
        report.error(f"name must be a string, got {type(name).__name__}")
    elif not name:
        report.error("frontmatter is missing the required 'name' field")
    else:
        if len(name) > NAME_MAX_LENGTH:
            report.error(f"name is {len(name)} characters, the limit is {NAME_MAX_LENGTH}")
        if not NAME_PATTERN.match(name):
            report.error(f"name {name!r} must be lowercase alphanumeric with single hyphens between segments")
        if name != skill_dir.name:
            report.error(f"name {name!r} does not match the directory name {skill_dir.name!r}")

    description = fields.get("description") or ""
    if not isinstance(description, str):
        report.error(f"description must be a string, got {type(description).__name__}")
    elif not description:
        report.error("frontmatter is missing the required 'description' field")
    elif len(description) > DESCRIPTION_MAX_LENGTH:
        report.error(f"description is {len(description)} characters, the limit is {DESCRIPTION_MAX_LENGTH}")


def check_body(path: Path, body_start: int, report: Report) -> None:
    """Validate the markdown body length."""
    body_lines = len(path.read_text().split("\n")) - body_start
    if body_lines > BODY_MAX_LINES:
        report.error(f"SKILL.md body is {body_lines} lines, the recommended limit is {BODY_MAX_LINES} — split it")


def check_layout(skill_dir: Path, report: Report) -> None:
    """Validate that supporting files sit exactly one level below SKILL.md."""
    for sub in ("references", "scripts", "assets"):
        directory = skill_dir / sub
        if not directory.is_dir():
            continue
        for nested in directory.iterdir():
            if nested.is_dir():
                report.error(f"{sub}/{nested.name}/ is nested too deeply — keep reference files one level deep")


def check_identifiers(path: Path, report: Report) -> None:
    """Reject concrete project identifiers that template sync would clobber."""
    text = path.read_text()
    for identifier in FORBIDDEN_IDENTIFIERS:
        if identifier in text:
            placeholder = "<domain>" if identifier.islower() else "{ClassPrefix}"
            report.error(f"{path} contains {identifier!r} — use the {placeholder} placeholder instead")


def check_links(path: Path, report: Report) -> None:
    """Verify that every relative markdown link resolves to an existing file."""
    for target in LINK_PATTERN.findall(path.read_text()):
        resolved = (path.parent / target.split("#", 1)[0]).resolve()
        if not resolved.exists():
            report.error(f"{path} links to a missing file: {target}")


def check_skill(skill_dir: Path) -> Report:
    """Run every check against one skill directory."""
    report = Report(skill=skill_dir.name)
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        report.error("directory has no SKILL.md")
        return report

    fields, body_start = parse_frontmatter(skill_file.read_text(), report)
    if fields:
        check_frontmatter(skill_dir, fields, report)
        check_body(skill_file, body_start, report)
    check_layout(skill_dir, report)
    for markdown in sorted(skill_dir.rglob("*.md")):
        check_identifiers(markdown, report)
        check_links(markdown, report)
    return report


def check_blueprint_only_markers() -> list[Report]:
    """
    Verify that every blueprint-only marker is balanced and ordered.

    initialize.sh strips these blocks with a sed range. An unmatched start marker makes
    that range run to end of file and silently truncates the document in every repository
    initialised from the template.
    """
    reports: list[Report] = []
    for path in sorted(Path(".agents").rglob("*.md")):
        text = path.read_text()
        starts = text.count(MARKER_START)
        ends = text.count(MARKER_END)
        if not starts and not ends:
            continue
        report = Report(skill=str(path))
        if starts != ends:
            report.error(f"blueprint-only markers are unbalanced ({starts} start, {ends} end) — sed would over-delete")
        elif text.index(MARKER_START) > text.index(MARKER_END):
            report.error("blueprint-only end marker precedes its start marker")
        reports.append(report)
    return reports


def check_repo_role_markers() -> Report:
    """
    Verify that AGENTS.md still carries exactly one repo-role block.

    initialize.sh rewrites this block to say the repository is an initialised integration.
    Unlike the blueprint-only markers, losing these fails silently in both directions: the
    rewrite becomes a no-op, and every repository initialised from the template keeps a
    block claiming it has not been initialised yet. Nothing surfaces that downstream, so
    this check is the only thing standing between an edit here and wrong instructions in
    every generated repository.
    """
    report = Report(skill=str(ROLE_FILE))
    if not ROLE_FILE.is_file():
        report.error(f"{ROLE_FILE} is missing — initialize.sh rewrites its repo-role block")
        return report

    text = ROLE_FILE.read_text()
    starts = text.count(ROLE_MARKER_START)
    ends = text.count(ROLE_MARKER_END)
    if starts != 1 or ends != 1:
        report.error(
            f"expected exactly one repo-role block, found {starts} start and {ends} end marker(s) — "
            "initialize.sh would silently leave the wrong role in place downstream"
        )
    elif text.index(ROLE_MARKER_START) > text.index(ROLE_MARKER_END):
        report.error("repo-role end marker precedes its start marker")
    return report


def check_instruction_paths() -> list[Report]:
    """
    Verify the frontmatter contract of every instructions file.

    Copilot and VS Code read ``applyTo`` as one comma-separated string; Claude Code reads
    ``paths`` as a YAML list, through the .claude/rules/instructions symlink. The two must
    describe the same set, so ``paths`` has to equal ``applyTo`` split on commas.

    ``name`` and ``description`` are documented Copilot keys — the display name and the
    hover text in the Chat view. Claude Code ignores them, which is harmless, but they are
    required here so the two agents present the same set consistently.

    ``paths`` is the only key Claude Code recognises. An unknown key is not rejected — the
    file is simply treated as unscoped and loaded into every session, which is why a wrong
    key here is invisible without this check. Files in UNCONDITIONAL_INSTRUCTIONS want that
    behaviour and therefore declare no ``paths`` at all.
    """
    reports: list[Report] = []
    for path in sorted(INSTRUCTIONS_DIR.glob("*.instructions.md")):
        report = Report(skill=str(path))
        fields, _ = parse_frontmatter(path.read_text(), report)
        if report.errors:
            reports.append(report)
            continue

        apply_to = fields.get("applyTo")
        paths = fields.get("paths")
        unconditional = path.name in UNCONDITIONAL_INSTRUCTIONS

        if "globs" in fields:
            report.error(
                "'globs' is Cursor's key and is ignored by Claude Code — use 'paths' (see the module docstring)"
            )
        for label in ("name", "description"):
            value = fields.get(label)
            if not isinstance(value, str) or not value.strip():
                report.error(f"frontmatter is missing '{label}' (Copilot shows it in the Chat view)")
        if not isinstance(apply_to, str) or not apply_to.strip():
            report.error("frontmatter is missing 'applyTo' (Copilot and VS Code need it)")
        elif unconditional:
            if paths is not None:
                report.error(f"{path.name} is listed as unconditional — it must not declare 'paths'")
        elif paths is None:
            report.error("frontmatter is missing 'paths' — Claude Code would load this file into every session")
        elif not isinstance(paths, list) or not all(isinstance(p, str) and p.strip() for p in paths):
            report.error("'paths' must be a YAML list of non-empty pattern strings, not a comma-separated string")
        elif [p.strip() for p in paths] != [p.strip() for p in apply_to.split(",")]:
            report.error("'paths' and 'applyTo' describe different patterns — 'paths' is 'applyTo' split on commas")
        reports.append(report)
    return reports


def _pointer_files() -> list[Path]:
    """
    Return the markdown outside .agents/skills/ that points into it.

    Each instructions file with a partner skill opens with a ``**Procedure:**`` link, and
    both catalogues link every skill. check_skill() only walks the skill directories, so
    without this list a removed skill leaves dangling pointers in exactly the files agents
    rely on to find their way to a skill in the first place.
    """
    return [*sorted(INSTRUCTIONS_DIR.glob("*.md")), SKILLS_CATALOGUE, AGENTS_CATALOGUE]


def _required_catalogue_files() -> tuple[Path, ...]:
    """Return catalogues that can receive the same update as synchronized skills."""
    if Path("initialize.sh").is_file():
        return (SKILLS_CATALOGUE, AGENTS_CATALOGUE)
    return (SKILLS_CATALOGUE,)


def check_pointer_links() -> list[Report]:
    """Verify that the links from those files still resolve."""
    reports: list[Report] = []
    for path in _pointer_files():
        report = Report(skill=str(path))
        if not path.is_file():
            report.error("file is missing — it carries the pointers into .agents/skills/")
        else:
            check_links(path, report)
        reports.append(report)
    return reports


def linked_skills(path: Path) -> set[str]:
    """Return the names of the skill directories a markdown file links into."""
    skills_root = SKILLS_DIR.resolve()
    linked: set[str] = set()
    for target in LINK_PATTERN.findall(path.read_text()):
        resolved = (path.parent / target.split("#", 1)[0]).resolve()
        if resolved == skills_root:
            continue
        try:
            relative = resolved.relative_to(skills_root)
        except ValueError:
            continue
        linked.add(relative.parts[0])
    return linked


def check_catalogue(skill_dirs: list[Path]) -> list[Report]:
    """
    Verify that every skill is listed in every synchronized catalogue.

    There is no generator behind them, so a new skill is only ever added by hand and is
    silently undiscoverable until it is. The reverse direction — a catalogue entry for a
    skill that no longer exists — is covered by check_pointer_links().

    Matching is by link target rather than by table row on purpose: the same skill appears
    as a routing-table row in AGENTS.md, as a "Use when" row in the README, and as prose in
    both, and all three forms are legitimate.
    """
    expected = {d.name for d in skill_dirs}
    reports: list[Report] = []
    for path in _required_catalogue_files():
        report = Report(skill=str(path))
        if not path.is_file():
            report.error("catalogue file is missing")
        else:
            for name in sorted(expected - linked_skills(path)):
                report.error(f"{name} is not linked from this catalogue — an unlisted skill is never discovered")
        reports.append(report)
    return reports


def check_project_instructions_routed() -> list[Report]:
    """
    Verify that AGENTS.md names every instructions file the project wrote itself.

    Codex and OpenCode load no instructions file on their own; the routing table in
    AGENTS.md is the only way they find one. The shipped blueprint.* files are listed there
    already, so only the project's own files are checked.
    """
    if not AGENTS_CATALOGUE.is_file():
        return []
    rows = [line for line in AGENTS_CATALOGUE.read_text(encoding="utf-8").splitlines() if line.startswith("|")]
    reports: list[Report] = []
    for path in sorted(INSTRUCTIONS_DIR.glob("*.instructions.md")):
        if path.name.startswith("blueprint."):
            continue
        report = Report(skill=str(path))
        name = path.name.removesuffix(".instructions.md")
        if not any(f"`{name}`" in row for row in rows):
            report.error(f"{AGENTS_CATALOGUE} does not name {name} — Codex and OpenCode find it only there")
        reports.append(report)
    return reports


def main() -> int:
    """Validate every skill and print a summary."""
    if not SKILLS_DIR.is_dir():
        print(f"No {SKILLS_DIR}/ directory — nothing to validate.")
        return 0

    skill_dirs = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith("."))
    if not skill_dirs:
        print(f"No skills found in {SKILLS_DIR}/.")
        return 0

    reports = [check_skill(d) for d in skill_dirs]
    instruction_reports = check_instruction_paths()
    pointer_reports = [*check_pointer_links(), *check_catalogue(skill_dirs), *check_project_instructions_routed()]
    marker_reports = [*check_blueprint_only_markers(), check_repo_role_markers()]

    for report in reports:
        if report.errors:
            print(f"  ✗ {report.skill}")
            for error in report.errors:
                print(f"      {error}")
        else:
            print(f"  ✓ {report.skill}")

    broken_instructions = [r for r in instruction_reports if r.errors]
    if instruction_reports:
        print()
        for report in broken_instructions:
            print(f"  ✗ {report.skill}")
            for error in report.errors:
                print(f"      {error}")
        if not broken_instructions:
            print(f"  ✓ {len(instruction_reports)} instruction files: applyTo and paths agree")

    broken_pointers = [r for r in pointer_reports if r.errors]
    if broken_pointers:
        print()
        for report in broken_pointers:
            print(f"  ✗ {report.skill}")
            for error in report.errors:
                print(f"      {error}")
    else:
        print(
            f"  ✓ {len(_pointer_files())} pointer files: every skill link resolves and "
            f"{len(_required_catalogue_files())} synchronized catalogue(s) are complete"
        )

    broken_markers = [r for r in marker_reports if r.errors]
    for report in broken_markers:
        print(f"  ✗ {report.skill}")
        for error in report.errors:
            print(f"      {error}")

    failed = [r for r in reports if r.errors] + broken_instructions + broken_pointers + broken_markers
    print()
    if failed:
        print(f"{len(failed)} file(s) have problems.")
        return 1
    print(f"{len(reports)} skills and {len(instruction_reports)} instruction files validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
