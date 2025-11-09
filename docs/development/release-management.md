# Release Notes Generation

This project supports **three ways** to generate release notes from conventional commits, plus **automatic version management**.

## 🚀 Quick Start: Preparing a Release

**Recommended workflow (automatic & foolproof):**

```bash
# 1. Use the helper script to prepare release
./scripts/prepare-release 0.3.0

# This will:
#   - Update manifest.json version to 0.3.0
#   - Create commit: "chore(release): bump version to 0.3.0"
#   - Create tag: v0.3.0
#   - Show you what will be pushed

# 2. Review and push when ready
git push origin main v0.3.0

# 3. CI/CD automatically:
#   - Detects the new tag
#   - Generates release notes (excluding version bump commit)
#   - Creates GitHub release
```

**If you forget to bump manifest.json:**

```bash
# Just edit manifest.json manually and commit
vim custom_components/tibber_prices/manifest.json  # "version": "0.3.0"
git commit -am "chore(release): bump version to 0.3.0"
git push

# Auto-Tag workflow detects manifest.json change and creates tag automatically!
# Then Release workflow kicks in and creates the GitHub release
```

---

## 📋 Release Options

### 1. GitHub UI Button (Easiest)

Use GitHub's built-in release notes generator:

1. Go to [Releases](https://github.com/jpawlowski/hass.tibber_prices/releases)
2. Click "Draft a new release"
3. Select your tag
4. Click "Generate release notes" button
5. Edit if needed and publish

**Uses:** `.github/release.yml` configuration
**Best for:** Quick releases, works with PRs that have labels
**Note:** Direct commits appear in "Other Changes" category

---

### 2. Local Script (Intelligent)

Run `./scripts/generate-release-notes` to parse conventional commits locally.

**Automatic backend detection:**

```bash
# Generate from latest tag to HEAD
./scripts/generate-release-notes

# Generate between specific tags
./scripts/generate-release-notes v1.0.0 v1.1.0

# Generate from tag to HEAD
./scripts/generate-release-notes v1.0.0 HEAD
```

**Force specific backend:**

```bash
# Use AI (GitHub Copilot CLI)
RELEASE_NOTES_BACKEND=copilot ./scripts/generate-release-notes

# Use git-cliff (template-based)
RELEASE_NOTES_BACKEND=git-cliff ./scripts/generate-release-notes

# Use manual parsing (grep/awk fallback)
RELEASE_NOTES_BACKEND=manual ./scripts/generate-release-notes
```

**Disable AI** (useful for CI/CD):

```bash
USE_AI=false ./scripts/generate-release-notes
```

#### Backend Priority

The script automatically selects the best available backend:

1. **GitHub Copilot CLI** - AI-powered, context-aware (best quality)
2. **git-cliff** - Fast Rust tool with templates (reliable)
3. **Manual** - Simple grep/awk parsing (always works)

In CI/CD (`$CI` or `$GITHUB_ACTIONS`), AI is automatically disabled.

#### Installing Optional Backends

**In DevContainer (automatic):**

git-cliff is automatically installed when the DevContainer is built:
- **Rust toolchain**: Installed via `ghcr.io/devcontainers/features/rust:1` (minimal profile)
- **git-cliff**: Installed via cargo in `scripts/setup`

Simply rebuild the container (VS Code: "Dev Containers: Rebuild Container") and git-cliff will be available.

**Manual installation (outside DevContainer):**

**git-cliff** (template-based):
```bash
# See: https://git-cliff.org/docs/installation

# macOS
brew install git-cliff

# Cargo (all platforms)
cargo install git-cliff

# Manual binary download
wget https://github.com/orhun/git-cliff/releases/latest/download/git-cliff-x86_64-unknown-linux-gnu.tar.gz
tar -xzf git-cliff-*.tar.gz
sudo mv git-cliff-*/git-cliff /usr/local/bin/
```

---

### 3. CI/CD Automation

Automatic release notes on tag push.

**Workflow:** `.github/workflows/release.yml`

**Triggers:** Version tags (`v1.0.0`, `v2.1.3`, etc.)

```bash
# Create and push a tag to trigger automatic release
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions will:
# 1. Detect the new tag
# 2. Generate release notes using git-cliff
# 3. Create a GitHub release automatically
```

**Backend:** Uses `git-cliff` (AI disabled in CI for reliability)

---

## 📝 Output Format

All methods produce GitHub-flavored Markdown with emoji categories:

```markdown
## 🎉 New Features

- **scope**: Description ([abc1234](link-to-commit))

## 🐛 Bug Fixes

- **scope**: Description ([def5678](link-to-commit))

## 📚 Documentation

- **scope**: Description ([ghi9012](link-to-commit))

## 🔧 Maintenance & Refactoring

- **scope**: Description ([jkl3456](link-to-commit))

## 🧪 Testing

- **scope**: Description ([mno7890](link-to-commit))
```

---

## 🎯 When to Use Which

| Method | Use Case | Pros | Cons |
|--------|----------|------|------|
| **Helper Script** | Normal releases | Foolproof, automatic | Requires script |
| **Auto-Tag Workflow** | Forgot script | Safety net, automatic tagging | Still need manifest bump |
| **GitHub Button** | Manual quick release | Easy, no script | Limited categorization |
| **Local Script** | Testing release notes | Preview before release | Manual process |
| **CI/CD** | After tag push | Fully automatic | Needs tag first |

---

## 🔄 Complete Release Workflows

### Workflow A: Using Helper Script (Recommended)

```bash
# Step 1: Prepare release (all-in-one)
./scripts/prepare-release 0.3.0

# Step 2: Review changes
git log -1 --stat
git show v0.3.0

# Step 3: Push when ready
git push origin main v0.3.0

# Done! CI/CD creates the release automatically
```

**What happens:**
1. Script bumps manifest.json → commits → creates tag locally
2. You push commit + tag together
3. Release workflow sees tag → generates notes → creates release

---

### Workflow B: Manual (with Auto-Tag Safety Net)

```bash
# Step 1: Bump version manually
vim custom_components/tibber_prices/manifest.json
# Change: "version": "0.3.0"

# Step 2: Commit
git commit -am "chore(release): bump version to 0.3.0"
git push

# Step 3: Wait for Auto-Tag workflow
# GitHub Actions automatically creates v0.3.0 tag
# Then Release workflow creates the release
```

**What happens:**
1. You push manifest.json change
2. Auto-Tag workflow detects change → creates tag automatically
3. Release workflow sees new tag → creates release

---

### Workflow C: Manual Tag (Old Way)

```bash
# Step 1: Bump version
vim custom_components/tibber_prices/manifest.json
git commit -am "chore(release): bump version to 0.3.0"

# Step 2: Create tag manually
git tag v0.3.0
git push origin main v0.3.0

# Release workflow creates release
```

**What happens:**
1. You create and push tag manually
2. Release workflow creates release
3. Auto-Tag workflow skips (tag already exists)

---

## ⚙️ Configuration Files

- `scripts/prepare-release` - Helper script to bump version + create tag
- `.github/workflows/auto-tag.yml` - Automatic tag creation on manifest.json change
- `.github/workflows/release.yml` - Automatic release on tag push
- `.github/release.yml` - GitHub UI button configuration
- `cliff.toml` - git-cliff template (filters out version bumps)

---

## 🛡️ Safety Features

### 1. **Version Validation**
Both helper script and auto-tag workflow validate version format (X.Y.Z).

### 2. **No Duplicate Tags**
- Helper script checks if tag exists (local + remote)
- Auto-tag workflow checks if tag exists before creating

### 3. **Atomic Operations**
Helper script creates commit + tag locally. You decide when to push.

### 4. **Version Bumps Filtered**
Release notes automatically exclude `chore(release): bump version` commits.

### 5. **Rollback Instructions**
Helper script shows how to undo if you change your mind.

---

## 🐛 Troubleshooting

**"Tag already exists" error:**

```bash
# Local tag
git tag -d v0.3.0

# Remote tag (only if you need to recreate)
git push origin :refs/tags/v0.3.0
```

**Manifest version doesn't match tag:**

This shouldn't happen with the new workflows, but if it does:

```bash
# 1. Fix manifest.json
vim custom_components/tibber_prices/manifest.json

# 2. Amend the commit
git commit --amend -am "chore(release): bump version to 0.3.0"

# 3. Move the tag
git tag -f v0.3.0
git push -f origin main v0.3.0
```

**Auto-tag didn't create tag:**

Check workflow runs in GitHub Actions. Common causes:
- Tag already exists remotely
- Invalid version format in manifest.json
- manifest.json not in the commit that was pushed

---

## 🔍 Format Requirements

**HACS:** No specific format required, uses GitHub releases as-is
**Home Assistant:** No specific format required for custom integrations
**Markdown:** Standard GitHub-flavored Markdown supported
**HTML:** Can include `<ha-alert>` tags if needed

---

## 💡 Tips

1. **Conventional Commits:** Use proper commit format for best results:
   ```
   feat(scope): Add new feature

   Detailed description of what changed.

   Impact: Users can now do X and Y.
   ```

2. **Impact Section:** Add `Impact:` in commit body for user-friendly descriptions

3. **Test Locally:** Run `./scripts/generate-release-notes` before creating release

4. **AI vs Template:** GitHub Copilot CLI provides better descriptions, git-cliff is faster and more reliable

5. **CI/CD:** Tag push triggers automatic release - no manual intervention needed
