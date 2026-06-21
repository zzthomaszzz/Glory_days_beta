# GloryDay

## Releasing a new version

### Step 0 — Bump the version (REQUIRED)

Update `GAME_VERSION` in `shared/constants.py` to match the new release tag **before building**. The server rejects clients whose version string doesn't match, so a mismatch will prevent anyone from joining.

```python
# shared/constants.py
GAME_VERSION = "1.X"   # ← change this to the new version number
```

### Step 1 — Build with PyInstaller
```
C:\Users\Thomas\AppData\Local\Programs\Python\Python312\Scripts\pyinstaller.exe main.spec
```

### Step 2 — Copy assets into dist (PyInstaller does NOT do this automatically)
```powershell
Remove-Item -Path "dist\asset" -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "dist\asset" | Out-Null
Get-ChildItem "asset" | Copy-Item -Destination "dist\asset" -Recurse -Force
```

### Step 3 — Zip dist folder
```powershell
Compress-Archive -Path "dist\main.exe", "dist\asset" -DestinationPath "GloryDay_vX.X.zip" -Force
```

### Step 4 — Commit code changes to this repo

Stage and commit all changed source files (NOT the zip — it is gitignored).

### Step 5 — Create GitHub release on Glory_days_beta → auto-deploys to itch.io

Creating a release on the `zzthomaszzz/Glory_days_beta` repo triggers the `deploy.yml` workflow, which downloads the zip and pushes it to itch.io via butler automatically.

```
gh release create vX.X "GloryDay_vX.X.zip" --repo zzthomaszzz/Glory_days_beta --title "GloryDay Beta vX.X" --notes "..."
```

itch.io game page: https://thomasng.itch.io/glory-days
Releases: https://github.com/zzthomaszzz/Glory_days_beta/releases

### Commit message checklist

When writing the release commit message, include any balance changes made since the last release:

- **Hero stat changes** — check `shared/heroes.py` diff for changes to hp, mana, attack_damage, attack_speed, armor, etc.
- **Item stat changes** — check `shared/items.py` diff for changes to item stats
- **Ability stat changes** — check `ABILITY_STATS` in `server/abilities.py` for cooldown, damage, or range tweaks
