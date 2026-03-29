# Contributing Guide

Welcome! This guide helps you contribute to the Tibber Prices integration.

## Getting Started

### Prerequisites

- Git
- VS Code with Remote Containers extension
- Docker Desktop

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/hass.tibber_prices.git
   cd hass.tibber_prices
   ```
3. Open in VS Code
4. Click "Reopen in Container" when prompted

The DevContainer will set up everything automatically.

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-123-description
```

**Branch naming:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code restructuring
- `test/` - Test improvements

### 2. Make Changes

Edit code, following [Coding Guidelines](coding-guidelines.md).

**Run checks frequently:**
```bash
./scripts/type-check  # Pyright type checking
./scripts/lint        # Ruff linting (auto-fix)
./scripts/test        # Run tests
```

### 3. Test Locally

```bash
./scripts/develop     # Start HA with integration loaded
```

Access at http://localhost:8123

### 4. Write Tests

Add tests in `/tests/` for new features:

```python
@pytest.mark.unit
async def test_your_feature(hass, coordinator):
    """Test your new feature."""
    # Arrange
    coordinator.data = {...}

    # Act
    result = your_function(coordinator.data)

    # Assert
    assert result == expected_value
```

Run your test:
```bash
./scripts/test tests/test_your_feature.py -v
```

### 5. Commit Changes

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git add .
git commit -m "feat(sensors): add volatility trend sensor

Add new sensor showing 3-hour volatility trend direction.
Includes attributes with historical volatility data.

Impact: Users can predict when prices will stabilize or continue fluctuating."
```

**Commit types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `refactor:` - Code restructuring
- `test:` - Test changes
- `chore:` - Maintenance

**Add scope when relevant:**
- `feat(sensors):` - Sensor platform
- `fix(coordinator):` - Data coordinator
- `docs(user):` - User documentation

### 6. Push and Create PR

```bash
git push origin your-branch-name
```

Then open Pull Request on GitHub.

## Pull Request Guidelines

### PR Template

Title: Short, descriptive (50 chars max)

Description should include:
```markdown
## What
Brief description of changes

## Why
Problem being solved or feature rationale

## How
Implementation approach

## Testing
- [ ] Manual testing in Home Assistant
- [ ] Unit tests added/updated
- [ ] Type checking passes
- [ ] Linting passes

## Breaking Changes
(If any - describe migration path)

## Related Issues
Closes #123
```

### PR Checklist

Before submitting:
- [ ] Code follows [Coding Guidelines](coding-guidelines.md)
- [ ] All tests pass (`./scripts/test`)
- [ ] Type checking passes (`./scripts/type-check`)
- [ ] Linting passes (`./scripts/lint-check`)
- [ ] Documentation updated (if needed)
- [ ] AGENTS.md updated (if patterns changed)
- [ ] Commit messages follow Conventional Commits

### Review Process

1. **Automated checks** run (CI/CD)
2. **Maintainer review** (usually within 3 days)
3. **Address feedback** if requested
4. **Approval** → Maintainer merges

## Code Review Tips

### What Reviewers Look For

✅ **Good:**
- Clear, self-explanatory code
- Appropriate comments for complex logic
- Tests covering edge cases
- Type hints on all functions
- Follows existing patterns

❌ **Avoid:**
- Large PRs (>500 lines) - split into smaller ones
- Mixing unrelated changes
- Missing tests for new features
- Breaking changes without migration path
- Copy-pasted code (refactor into shared functions)

### Responding to Feedback

- Don't take it personally - we're improving code together
- Ask questions if feedback unclear
- Push additional commits to address comments
- Mark conversations as resolved when fixed

## Finding Issues to Work On

Good first issues are labeled:
- `good first issue` - Beginner-friendly
- `help wanted` - Maintainers welcome contributions
- `documentation` - Docs improvements

Comment on issue before starting work to avoid duplicates.

## Communication

- **GitHub Issues** - Bug reports, feature requests
- **Pull Requests** - Code discussion
- **Discussions** - General questions, ideas

Be respectful, constructive, and patient. We're all volunteers! 🙏

---

💡 **Related:**
- [Setup Guide](setup.md) - DevContainer setup
- [Coding Guidelines](coding-guidelines.md) - Style guide
- [Testing](testing.md) - Writing tests
- [Release Management](release-management.md) - How releases work
