# Release Process

This page describes the release process used for the open-source documentation package.

## Versioning

Use semantic version tags:

```text
vMAJOR.MINOR.PATCH
```

The first public documentation release is `v0.1.0`.

## Pre-Release Checklist

1. Confirm the worktree is clean except for intended release files.
2. Run the harness validator:

   ```bash
   scripts/.venv/bin/python scripts/serenity_harness.py validate
   ```

3. Verify documentation paths and required references:

   ```bash
   test -s README.md
   test -s LICENSE
   test -s CHANGELOG.md
   test -s docs/wiki/README.md
   rg "serenity_pipeline.py" README.md docs/wiki
   ```

4. Review the staged diff and confirm only release-scope files changed.

## Commit

Follow the repository's existing Conventional Commit style:

```bash
git add README.md LICENSE CHANGELOG.md docs/wiki docs/releases
git commit -m "docs(release): publish open-source project docs"
```

## Push

```bash
git push origin main
```

## Create The GitHub Release

```bash
gh release create v0.1.0 \
  --title "Harness of Serenity v0.1.0" \
  --notes-file docs/releases/v0.1.0.md
```

Verify it:

```bash
gh release view v0.1.0 --json tagName,name,url,isDraft,isPrerelease,targetCommitish
```

The release is valid when:

- `tagName` is `v0.1.0`
- `isDraft` is `false`
- `isPrerelease` is `false`
- `url` points to the repository release page

## Rollback

If a release was created with the wrong notes or target commit:

```bash
gh release delete v0.1.0
git tag -d v0.1.0
git push origin :refs/tags/v0.1.0
```

Only run rollback commands when the release is actually wrong and the repository owner accepts the history impact.
