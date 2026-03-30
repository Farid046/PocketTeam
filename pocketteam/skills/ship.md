---
name: ship
description: "Ship feature to production via full pipeline. Use when feature is ready to release."
---

# Ship

You are preparing a release. Follow this process strictly. STAGING FIRST, ALWAYS.

## Step 1: Pre-Flight Check

```bash
# All tests must pass
python -m pytest tests/ -q
# No uncommitted changes
git status
# Check what's being released
git log --oneline origin/main..HEAD
```

If tests fail → STOP. Fix first, then ship.

## Step 2: Version Bump

Determine version bump (semver):
- **patch** (0.0.X): bug fixes, minor changes
- **minor** (0.X.0): new features, backwards-compatible
- **major** (X.0.0): breaking changes

Update version in `pyproject.toml` (or `package.json`).

## Step 3: CHANGELOG

Update CHANGELOG.md:
```markdown
## [version] - YYYY-MM-DD

### Added
- [new feature]

### Changed
- [modification]

### Fixed
- [bug fix]
```

## Step 4: Create PR

```bash
git add -A
git commit -m "release: v[version]"
gh pr create --title "Release v[version]" --body "[changelog excerpt]"
```

## Step 5: Deploy

1. Deploy to **staging** first
2. Run smoke tests on staging
3. Ask CEO: "Staging looks good. Deploy to production?"
4. If approved → deploy to production
5. Monitor for 15 minutes post-deploy

## Rollback Plan

Always have a rollback ready:
```bash
git revert HEAD --no-edit
# Redeploy previous version
```
