#!/bin/bash
set -e

# Cleanup old documentation versions based on versioning strategy:
# - Pre-1.0 (0.x.y): Keep only last 5 versions
# - Post-1.0 (≥1.0.0): Keep last 3 MINOR versions per MAJOR (only latest PATCH per MINOR)

KEEP_PRE_1_0=5
KEEP_POST_1_0_MINORS=3

echo "🧹 Cleaning up old documentation versions..."

for doc_type in "user" "developer"; do
  VERSIONS_FILE="${doc_type}_versions.json"
  VERSIONED_DOCS_DIR="${doc_type}_versioned_docs"

  if [ ! -f "$VERSIONS_FILE" ]; then
    echo "⚠️  No $VERSIONS_FILE found, skipping $doc_type docs"
    continue
  fi

  # Read current versions from JSON (remove brackets and quotes)
  CURRENT_VERSIONS=$(jq -r '.[]' "$VERSIONS_FILE" 2>/dev/null || echo "")

  if [ -z "$CURRENT_VERSIONS" ]; then
    echo "✓ No versions found in $VERSIONS_FILE"
    continue
  fi

  echo ""
  echo "📋 Current $doc_type versions:"
  echo "$CURRENT_VERSIONS"

  # Separate pre-1.0 and post-1.0 versions
  PRE_1_0_VERSIONS=$(echo "$CURRENT_VERSIONS" | grep '^v0\.' || true)
  POST_1_0_VERSIONS=$(echo "$CURRENT_VERSIONS" | grep -v '^v0\.' || true)

  VERSIONS_TO_KEEP=()

  # Handle pre-1.0 versions: keep last N
  if [ -n "$PRE_1_0_VERSIONS" ]; then
    echo ""
    echo "🔍 Processing pre-1.0 versions (keep last $KEEP_PRE_1_0):"
    PRE_1_0_SORTED=$(echo "$PRE_1_0_VERSIONS" | sort -V -r)
    PRE_1_0_KEEP=$(echo "$PRE_1_0_SORTED" | head -n "$KEEP_PRE_1_0")

    while IFS= read -r version; do
      [ -n "$version" ] && VERSIONS_TO_KEEP+=("$version")
    done <<< "$PRE_1_0_KEEP"

    echo "$PRE_1_0_KEEP"
  fi

  # Handle post-1.0 versions: keep last N MINOR per MAJOR (latest PATCH only)
  if [ -n "$POST_1_0_VERSIONS" ]; then
    echo ""
    echo "🔍 Processing post-1.0 versions (keep last $KEEP_POST_1_0_MINORS MINOR per MAJOR):"

    # Get unique MAJOR versions
    MAJORS=$(echo "$POST_1_0_VERSIONS" | sed 's/^v\([0-9]*\)\..*/\1/' | sort -u -n)

    for major in $MAJORS; do
      # Get all versions for this MAJOR
      MAJOR_VERSIONS=$(echo "$POST_1_0_VERSIONS" | grep "^v${major}\.")

      # Group by MINOR version and keep only latest PATCH
      MINORS=$(echo "$MAJOR_VERSIONS" | sed 's/^v[0-9]*\.\([0-9]*\)\..*/\1/' | sort -u -n -r)

      MINOR_COUNT=0
      for minor in $MINORS; do
        if [ $MINOR_COUNT -ge $KEEP_POST_1_0_MINORS ]; then
          break
        fi

        # Get latest PATCH for this MINOR
        LATEST_PATCH=$(echo "$MAJOR_VERSIONS" | grep "^v${major}\.${minor}\." | sort -V -r | head -n 1)

        if [ -n "$LATEST_PATCH" ]; then
          VERSIONS_TO_KEEP+=("$LATEST_PATCH")
          echo "  v${major}.${minor}.x → $LATEST_PATCH"
          MINOR_COUNT=$((MINOR_COUNT + 1))
        fi
      done
    done
  fi

  # Convert array to newline-separated list for comparison
  KEEP_LIST=$(printf "%s\n" "${VERSIONS_TO_KEEP[@]}" | sort -V)

  echo ""
  echo "✅ Versions to keep for $doc_type:"
  echo "$KEEP_LIST"

  # Find versions to delete
  VERSIONS_TO_DELETE=()
  while IFS= read -r version; do
    if ! echo "$KEEP_LIST" | grep -q "^${version}$"; then
      VERSIONS_TO_DELETE+=("$version")
    fi
  done <<< "$CURRENT_VERSIONS"

  if [ ${#VERSIONS_TO_DELETE[@]} -eq 0 ]; then
    echo ""
    echo "✓ No old versions to delete for $doc_type"
    continue
  fi

  echo ""
  echo "🗑️  Deleting old $doc_type versions:"
  for version in "${VERSIONS_TO_DELETE[@]}"; do
    echo "  - $version"

    # Remove versioned docs directory
    VERSION_DIR="${VERSIONED_DOCS_DIR}/version-${version}"
    if [ -d "$VERSION_DIR" ]; then
      rm -rf "$VERSION_DIR"
      echo "    Removed: $VERSION_DIR"
    fi
  done

  # Update versions.json with only kept versions
  echo "$KEEP_LIST" | jq -R -s 'split("\n") | map(select(length > 0))' > "$VERSIONS_FILE"
  echo ""
  echo "✓ Updated $VERSIONS_FILE"
done

echo ""
echo "✨ Cleanup complete!"
