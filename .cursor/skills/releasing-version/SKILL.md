---
name: releasing-version
description: Use when cutting a version, writing CHANGELOG, packing the portable Windows dist, creating a release/* branch, or publishing a zip to GitHub Releases. Also use when the user says 打包、发版、绿色版 zip、010、release 页签, or asks to follow the pack-and-release flow.
---

# Releasing a portable version

**Violating the letter of the order is violating the spirit of the order.**

Every release uses this sequence. Do not skip, swap, or parallelize past a failed step.

```
1. Read this skill
2. If this skill or pack scripts changed: commit those alone, then continue
3. Branch release/<version>
4. VERSION + CHANGELOG
5. Commit those (and any remaining ship code)
6. Pack
7. Zip
8. Push branch
9. GitHub Release + zip
```

## Version

Three digits, no dots: `010`, `011`. Not `0.1.0`.

| Thing | Value |
| --- | --- |
| File | `VERSION` (one line, no `v`) |
| Branch | `release/010` |
| Tag | `v010` |
| Zip | `dist/MapleStoryExpStats-010.zip` (gitignored) |

User supplies the number. Do not invent the next one.

## Branch

From the current HEAD (usually `main`):

```
git checkout -b release/<version>
```

Ship from this branch. Do not tag `main` and skip `release/*`.

## CHANGELOG

Repo-root `CHANGELOG.md`, Chinese, newest section first. Write for players, not a `git log` dump.

Since last `v*` tag (`git tag --sort=-v:refname`). No tags → this is the first section; summarize user-facing work on the branch.

```markdown
# 更新日志

## 010 — YYYY-MM-DD

### 新增
- …

### 变更
- …

### 修复
- …
```

Omit empty `###` headings. Date is today.

## Commit

Chinese message, why in 1–2 sentences. Stage `VERSION`, `CHANGELOG.md`, and ship code only.

Never stage `dist/`, `build/`, `*.zip`, `data/*.jsonl`, `data/window.json`, `data/crash.log`.

## Pack and zip

```
python scripts/pack.py
```

Then:

```
python -c "import shutil; shutil.make_archive('dist/MapleStoryExpStats-VERSION', 'zip', 'dist', 'MapleStoryExpStats')"
```

Replace `VERSION` with the digits. Smoke: start `dist/MapleStoryExpStats/MapleStoryExpStats.exe`, wait ~15s, no `data/crash.log`, then stop it.

## GitHub Release

```
git push -u origin release/<version>
gh auth status
gh release create v<version> --target release/<version> --title "<version>" --notes-file CHANGELOG.md dist/MapleStoryExpStats-<version>.zip
```

`--notes-file CHANGELOG.md` is OK when the file is short. If it grows, pass only this version's section via a temp notes file.

If `gh` is not logged in: stop after zip, print the zip path, ask the user to run `gh auth login`. Do not invent a token.

No `--force` push. No draft unless the user asks.

## Red flags — STOP

| Excuse | Reality |
| --- | --- |
| "CHANGELOG later" | No zip on GitHub without a written section. |
| "Tag main, skip release/*" | Branch is `release/<version>`. |
| "Commit the dist folder" | Only upload the zip on the Release. |
| "Release first, pack if CI fails" | Pack and smoke before `gh release create`. |
| "Version is 0.1.0" | Three digits: `010`. |

**All of these mean: go back to the step you skipped.**
