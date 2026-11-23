---
id: 20261123-cards-plain-es-modules
status: accepted
rule: .agents/instructions/tibber.cards.instructions.md
migrated-from: AGENTS.md@0f00a56
---

# Dashboard cards ship as plain ES modules with gzip copies, no bundler

## Context

The dashboard cards are plain JavaScript web components in `frontend/cards/`, served by the integration itself as a
static directory and loaded into every frontend. They import each other by relative path. Their size on the wire was
the reason to look at a build step: bundling and minifying, or compression alone.

## Decision

The cards stay native ES modules without a bundler or minifier. Only the release zip adds a gzip copy of every module
(`<module>.js.gz`, built by `script/hooks/build.post.sh`), which aiohttp's file response sends when the browser
accepts gzip. The repository carries no copies, so an edit during development is never hidden behind a stale one, and
`_drop_stale_copies()` in `frontend/__init__.py` deletes a copy that no longer matches its module on start.

Compression alone removes most of the transfer size. The rest would cost a build tool from npm in the release and
source maps for reading a user's error report.

## Consequences

- The release build has no Node dependency; the code users run is the code in the repository.
- A build tool for the cards needs a measurement against the gzip copies first, not a size argument on its own.
- Module layering has to be kept by hand: no bundler resolves an import cycle.
