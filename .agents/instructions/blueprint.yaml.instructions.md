---
name: "YAML Files"
description: "Formatting rules, HA conventions, and yamllint validation"
applyTo: "**/*.yaml, **/*.yml"
paths:
  - "**/*.yaml"
  - "**/*.yml"
---

# YAML Instructions

**Applies to:** All YAML files

## Formatting Standards

2 spaces, never tabs. Prefer `>` for folded multi-line strings, `|` where the newlines matter.

## Schema Validation

YAML schema files are available in `/schemas/yaml/`:

- `configuration_schema.yaml` — Validates Home Assistant `configuration.yaml`
- `services_schema.yaml` — Validates `services.yaml` (service action definitions)

Consult the relevant schema when editing YAML files to ensure correct structure.

## Home Assistant YAML Conventions

- Use modern HA configuration syntax (no legacy `platform:` style)
- Prefer `!include` for splitting large configurations
- Use `!secret` for sensitive values (passwords, API keys, tokens)
- Boolean values: `true`/`false` (lowercase)

## Validation

Run `script/yaml-check` after editing YAML files. Neither tool auto-fixes here — all
errors require manual fixes.

```bash
script/yaml-check   # yamllint against integration YAML, schemas, .github/;
                    # zizmor --pedantic against .github/workflows/
```

GitHub Actions workflows carry extra rules zizmor enforces: pin every `uses:` to a commit SHA with the version in a
trailing comment, give the workflow a `permissions:` block and every job the narrowest one it needs with a trailing
comment saying why, set `concurrency:`, and pass `persist-credentials: false` to `actions/checkout` unless the job
pushes with those credentials.

Configuration: `.yamllint.yml` at the project root. Key rules:

- Line length: 120 chars (warning, not error)
- `document-start` (`---`): not required
- `truthy.check-keys: false`: allows GitHub Actions `on:` key

**Suppressing yamllint for a single line** (use sparingly):

```yaml
some_long_key: some_very_long_value_that_exceeds_120_chars # yamllint disable-line rule:line-length
```
