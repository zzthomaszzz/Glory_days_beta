# GloryDay

## Releasing a new version

### Step 0 — Bump the version (REQUIRED)

Update `GAME_VERSION` in `shared/constants.py` to match the new release tag **before building**. The server rejects clients whose version string doesn't match, so a mismatch will prevent anyone from joining.

```python
# shared/constants.py
GAME_VERSION = "1.X"   # ← change this to the new version number
```

Also update the zip filename and GitHub release tag in the commands below to match.

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

### Step 3 — Zip the dist folder
```powershell
Compress-Archive -Path "dist\main.exe", "dist\asset" -DestinationPath "GloryDay_vX.X.zip" -Force
```

### Step 4 — Create GitHub release
```
gh release create vX.X "GloryDay_vX.X.zip" --repo zzthomaszzz/Glory_days_beta --title "GloryDay Beta vX.X" --notes "..."
```

### Step 5 — Push to itch.io via butler

itch.io game page: https://thomasng.itch.io/glory-days
itch.io game slug: `thomasng/glory-days`

Set your API key first (never paste the key in chat):
```powershell
$env:BUTLER_API_KEY = 'your-key-here'
```

Then push:
```
butler push GloryDay_vX.X.zip thomasng/glory-days:windows --userversion X.X
```

Get your API key at: https://itch.io/user/settings/api-keys
butler is installed at: `C:\Users\Thomas\bin\butler.exe`
Get your API key at: https://itch.io/user/settings/api-keys

### Commit message checklist

When writing the release commit message, include any balance changes made since the last release:

- **Hero stat changes** — check `shared/heroes.py` diff for changes to hp, mana, attack_damage, attack_speed, armor, etc.
- **Item stat changes** — check `shared/items.py` diff for changes to item stats
- **Ability stat changes** — check `ABILITY_STATS` in `server/abilities.py` for cooldown, damage, or range tweaks

Releases: https://github.com/zzthomaszzz/Glory_days_beta/releases
