"""
Validate source-level architecture guardrails from AGENTS.md.

The checks focus on idiomatic source patterns that can be identified conservatively without
importing the integration or requiring Home Assistant to start:

- EntityDescription constructors and subclasses do not set ``name=`` or ``icon=`` directly.
- The integration does not ship frozen device automation platform files.
- DeviceRegistry instances use entry-scoped device lookups instead of ``async_get_device()``.

The checker deliberately does not claim to prove arbitrary dynamic code. Import aliases, local
subclasses, direct aliases, and literal ``**{...}`` metadata are resolved; factories and values
assembled through general data flow remain review concerns.

Invoked by script/architecture-check; not intended to be run directly.
"""

import ast
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

BANNED_FILENAMES = {
    "device_trigger.py": "device triggers are frozen upstream — use a trigger platform (trigger.py) instead",
    "device_condition.py": "device conditions are frozen upstream — use a condition platform (condition.py) instead",
    "device_action.py": "device actions are frozen upstream — expose a service action instead",
}
DESCRIPTION_SUFFIX = "EntityDescription"
DESCRIPTION_METADATA_FIELDS = {"icon", "name"}
DEVICE_REGISTRY_MODULE = "homeassistant.helpers.device_registry"


@dataclass(frozen=True, slots=True)
class Finding:
    """One rule violation, anchored to a file and line."""

    file: str
    line: int
    message: str


@dataclass(frozen=True, slots=True)
class SourceSymbols:
    """Bindings relevant to architecture checks in one source module."""

    description_classes: frozenset[str]
    description_modules: frozenset[str]
    device_registry_factories: frozenset[str]
    device_registry_instances: frozenset[tuple[int, str]]
    device_registry_modules: frozenset[str]
    device_registry_types: frozenset[str]


def integration_python_files() -> list[Path]:
    """Return tracked and untracked, non-ignored integration Python files."""
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            "custom_components/*.py",
        ],
        capture_output=True,
        check=True,
    )
    return sorted({Path(os.fsdecode(path)) for path in result.stdout.split(b"\0") if path})


def check_banned_filenames(files: list[Path]) -> list[Finding]:
    """Flag device automation platforms, which this project never ships."""
    return [Finding(str(file), 1, BANNED_FILENAMES[file.name]) for file in files if file.name in BANNED_FILENAMES]


def _bound_name(alias: ast.alias) -> str:
    """Return the local name introduced by an import alias."""
    return alias.asname or alias.name.split(".", maxsplit=1)[0]


def _dotted_name(node: ast.expr) -> str | None:
    """Return a dotted representation for a name or attribute expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and (parent := _dotted_name(node.value)):
        return f"{parent}.{node.attr}"
    return None


def _is_description_reference(
    node: ast.expr,
    description_classes: set[str],
    description_modules: set[str],
) -> bool:
    """Return whether an expression resolves to a known EntityDescription class."""
    if isinstance(node, ast.Name):
        return node.id in description_classes
    if not isinstance(node, ast.Attribute) or not node.attr.endswith(DESCRIPTION_SUFFIX):
        return False
    root = _dotted_name(node.value)
    return root is not None and root.split(".", maxsplit=1)[0] in description_modules


def _is_device_registry_type(node: ast.expr, registry_modules: set[str], registry_types: set[str]) -> bool:
    """Return whether an annotation names Home Assistant's DeviceRegistry type."""
    if isinstance(node, ast.Name):
        return node.id in registry_types
    if isinstance(node, ast.Attribute) and node.attr == "DeviceRegistry":
        root = _dotted_name(node.value)
        return root is not None and root.split(".", maxsplit=1)[0] in registry_modules
    return False


def _is_device_registry_factory_call(
    node: ast.expr,
    registry_modules: set[str],
    registry_factories: set[str],
) -> bool:
    """Return whether an expression obtains Home Assistant's device registry."""
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id in registry_factories
    if isinstance(node.func, ast.Attribute) and node.func.attr == "async_get":
        root = _dotted_name(node.func.value)
        return root is not None and root.split(".", maxsplit=1)[0] in registry_modules
    return False


def _assigned_names(node: ast.expr) -> set[str]:
    """Return simple and dotted targets assigned by an expression."""
    if isinstance(node, (ast.Name, ast.Attribute)) and (name := _dotted_name(node)):
        return {name}
    if isinstance(node, (ast.List, ast.Tuple)):
        return {name for item in node.elts for name in _assigned_names(item)}
    return set()


def _collect_import_symbols(
    tree: ast.Module,
) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
    """Collect architecture-relevant symbols introduced by imports."""
    description_classes: set[str] = set()
    description_modules: set[str] = set()
    registry_factories: set[str] = set()
    registry_modules: set[str] = set()
    registry_types: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = _bound_name(alias)
                if alias.name == DEVICE_REGISTRY_MODULE:
                    registry_modules.add(local_name)
                if alias.name.startswith(("homeassistant.", "custom_components.")):
                    description_modules.add(local_name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                local_name = alias.asname or alias.name
                description_source = node.level > 0 or module.startswith(("homeassistant.", "custom_components."))
                if description_source and alias.name.endswith(DESCRIPTION_SUFFIX):
                    description_classes.add(local_name)
                elif description_source:
                    description_modules.add(local_name)
                if module == "homeassistant.helpers" and alias.name == "device_registry":
                    registry_modules.add(local_name)
                elif module == DEVICE_REGISTRY_MODULE:
                    if alias.name == "async_get":
                        registry_factories.add(local_name)
                    elif alias.name == "DeviceRegistry":
                        registry_types.add(local_name)

    return description_classes, description_modules, registry_factories, registry_modules, registry_types


def _collect_description_aliases(
    tree: ast.Module,
    description_classes: set[str],
    description_modules: set[str],
) -> None:
    """Add local EntityDescription subclasses and direct aliases to the known classes."""
    changed = True
    while changed:
        changed = False
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name not in description_classes:
                if any(
                    _is_description_reference(base, description_classes, description_modules) for base in node.bases
                ):
                    description_classes.add(node.name)
                    changed = True
            elif isinstance(node, ast.Assign) and _is_description_reference(
                node.value, description_classes, description_modules
            ):
                for target in node.targets:
                    for name in _assigned_names(target):
                        if name not in description_classes:
                            description_classes.add(name)
                            changed = True
            elif (
                isinstance(node, ast.AnnAssign)
                and node.value is not None
                and _is_description_reference(node.value, description_classes, description_modules)
            ):
                for name in _assigned_names(node.target):
                    if name not in description_classes:
                        description_classes.add(name)
                        changed = True


def _function_arguments(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    """Return every declared argument of a function."""
    arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg is not None:
        arguments.append(node.args.vararg)
    if node.args.kwarg is not None:
        arguments.append(node.args.kwarg)
    return arguments


def _scope_ids(tree: ast.Module) -> dict[ast.AST, int]:
    """Map each node to its nearest module, class, function, or lambda scope."""

    class ScopeVisitor(ast.NodeVisitor):
        """Record lexical scopes while walking the tree."""

        def __init__(self) -> None:
            self.scope: ast.AST = tree
            self.scopes: dict[ast.AST, int] = {}

        def generic_visit(self, node: ast.AST) -> None:
            self.scopes[node] = id(self.scope)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                outer_scope = self.scope
                self.scope = node
                super().generic_visit(node)
                self.scope = outer_scope
                return
            super().generic_visit(node)

    visitor = ScopeVisitor()
    visitor.visit(tree)
    return visitor.scopes


def _collect_registry_instances(
    tree: ast.Module,
    registry_modules: set[str],
    registry_factories: set[str],
    registry_types: set[str],
) -> set[tuple[int, str]]:
    """Return expressions known to hold Home Assistant's DeviceRegistry."""
    scope_ids = _scope_ids(tree)
    registry_instances: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for argument in _function_arguments(node):
                if argument.annotation is not None and _is_device_registry_type(
                    argument.annotation, registry_modules, registry_types
                ):
                    registry_instances.add((id(node), argument.arg))
        elif isinstance(node, ast.Assign) and _is_device_registry_factory_call(
            node.value, registry_modules, registry_factories
        ):
            for target in node.targets:
                registry_instances.update((scope_ids[node], name) for name in _assigned_names(target))
        elif isinstance(node, ast.AnnAssign):
            if _is_device_registry_type(node.annotation, registry_modules, registry_types) or (
                node.value is not None
                and _is_device_registry_factory_call(node.value, registry_modules, registry_factories)
            ):
                registry_instances.update((scope_ids[node], name) for name in _assigned_names(node.target))
    return registry_instances


def collect_source_symbols(tree: ast.Module) -> SourceSymbols:
    """Collect imported, inherited, and assigned symbols used by the checks."""
    (
        description_classes,
        description_modules,
        registry_factories,
        registry_modules,
        registry_types,
    ) = _collect_import_symbols(tree)
    _collect_description_aliases(tree, description_classes, description_modules)
    registry_instances = _collect_registry_instances(
        tree,
        registry_modules,
        registry_factories,
        registry_types,
    )

    return SourceSymbols(
        description_classes=frozenset(description_classes),
        description_modules=frozenset(description_modules),
        device_registry_factories=frozenset(registry_factories),
        device_registry_instances=frozenset(registry_instances),
        device_registry_modules=frozenset(registry_modules),
        device_registry_types=frozenset(registry_types),
    )


def _metadata_items(call: ast.Call) -> list[tuple[str, ast.expr]]:
    """Return explicit and literal-unpacked metadata keywords from a call."""
    items: list[tuple[str, ast.expr]] = []
    for keyword in call.keywords:
        if keyword.arg is not None:
            items.append((keyword.arg, keyword.value))
            continue
        if not isinstance(keyword.value, ast.Dict):
            continue
        for key, value in zip(keyword.value.keys, keyword.value.values, strict=True):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                items.append((key.value, value))
    return items


def _metadata_finding(file: Path, line: int, description: str, field: str, value: ast.expr) -> Finding | None:
    """Return a finding for one forbidden metadata field, except literal ``name=None``."""
    if field not in DESCRIPTION_METADATA_FIELDS:
        return None
    if field == "name" and isinstance(value, ast.Constant) and value.value is None:
        return None
    hint = "translation_key and icons.json" if field == "icon" else "translation_key"
    return Finding(str(file), line, f"{description} sets `{field}=` directly — use {hint} instead")


def check_entity_description_metadata(
    tree: ast.Module,
    file: Path,
    symbols: SourceSymbols,
) -> list[Finding]:
    """Flag forbidden metadata on known EntityDescription constructors and subclasses."""
    findings: list[Finding] = []
    description_classes = set(symbols.description_classes)
    description_modules = set(symbols.description_modules)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_description_reference(
            node.func, description_classes, description_modules
        ):
            description = _dotted_name(node.func) or DESCRIPTION_SUFFIX
            for field, value in _metadata_items(node):
                if finding := _metadata_finding(file, node.lineno, f"{description}(...)", field, value):
                    findings.append(finding)
        elif isinstance(node, ast.ClassDef) and node.name in description_classes:
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    field = statement.target.id
                    value = statement.value
                elif (
                    isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                ):
                    field = statement.targets[0].id
                    value = statement.value
                else:
                    continue
                if value is not None and (
                    finding := _metadata_finding(file, statement.lineno, node.name, field, value)
                ):
                    findings.append(finding)
    return findings


def check_unscoped_device_lookup(tree: ast.Module, file: Path, symbols: SourceSymbols) -> list[Finding]:
    """Flag unscoped lookups on expressions known to be Home Assistant's DeviceRegistry."""
    findings: list[Finding] = []
    registry_instances = set(symbols.device_registry_instances)
    registry_modules = set(symbols.device_registry_modules)
    registry_factories = set(symbols.device_registry_factories)
    scope_ids = _scope_ids(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "async_get_device":
            continue
        receiver = _dotted_name(node.func.value)
        known_instance = receiver is not None and (scope_ids[node], receiver) in registry_instances
        direct_factory = _is_device_registry_factory_call(node.func.value, registry_modules, registry_factories)
        if not known_instance and not direct_factory:
            continue
        findings.append(
            Finding(
                str(file),
                node.lineno,
                "DeviceRegistry.async_get_device() is unscoped — use async_get_device_by_identifier() or "
                "async_get_device_by_connection() instead",
            )
        )
    return findings


def check_file(file: Path) -> list[Finding]:
    """Run every AST-based check against one source file."""
    if not file.is_file():
        return []
    try:
        source = file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [Finding(str(file), getattr(exc, "lineno", 0) or 0, f"could not parse file: {exc}")]
    symbols = collect_source_symbols(tree)
    return [
        *check_entity_description_metadata(tree, file, symbols),
        *check_unscoped_device_lookup(tree, file, symbols),
    ]


def main() -> int:
    """Run every architecture check and print a summary."""
    files = integration_python_files()
    if not files:
        print("No tracked or untracked integration Python files — nothing to check.")
        return 0

    findings = check_banned_filenames(files)
    for file in files:
        findings.extend(check_file(file))

    findings.sort(key=lambda finding: (finding.file, finding.line, finding.message))

    for finding in findings:
        location = f"{finding.file}:{finding.line}" if finding.line else finding.file
        print(f"  ✗ {location}  {finding.message}")

    print()
    if findings:
        print(f"{len(findings)} architecture finding(s) in {len(files)} file(s).")
        return 1
    print(f"{len(files)} file(s) checked, no architecture findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
