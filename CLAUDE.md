# GloryDay

## Two build targets

| Target | Channel | How it deploys |
|--------|---------|---------------|
| **Windows `.exe`** | `windows` on itch.io | Manual — create a GitHub release on `Glory_days_beta` |
| **HTML5 (browser)** | `html5` on itch.io | Automatic — every push to `main` triggers `pygbag.yml` |

---

## Before every push to `main`

The HTML5 workflow fires on **every push**. Make sure `client/net.py` is in the right mode:

```python
# client/net.py — top of file
DEV_MODE = True   # True = ws://localhost:5555  (local testing)
                  # False = wss://YOUR_PLAYIT_URL  (production browser build)
SERVER_URL = "ws://localhost:5555" if DEV_MODE else "wss://YOUR_PLAYIT_URL_HERE"
```

- Leave `DEV_MODE = True` while iterating — the HTML5 build will deploy but players will need a server running locally (fine for testing).
- Flip to `DEV_MODE = False` and paste the playit.gg `wss://` URL when you want the public browser build to actually connect.

---

## Releasing a new version (Windows exe)

### Step 0 — Bump the version (REQUIRED)

Update `GAME_VERSION` in `shared/constants.py` to match the new release tag **before building**. The server rejects clients whose version string doesn't match.

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

### Step 5 — Create GitHub release on Glory_days_beta → auto-deploys Windows channel

Creating a release on the `zzthomaszzz/Glory_days_beta` repo triggers `deploy.yml`, which downloads the zip and pushes it to itch.io via butler.

```
gh release create vX.X "GloryDay_vX.X.zip" --repo zzthomaszzz/Glory_days_beta --title "GloryDay Beta vX.X" --notes "..."
```

itch.io game page: https://thomasng.itch.io/glory-days
Releases: https://github.com/zzthomaszzz/Glory_days_beta/releases

---

## HTML5 deploy (automatic)

Pushing to `main` runs `.github/workflows/pygbag.yml`, which:
1. Installs Python 3.11 + `pip install -r requirements.txt pygbag`
2. Runs `pygbag --build main.py` (entry point is the root `main.py` shim → `client/main.py`)
3. Downloads butler and pushes `build/web/` to itch.io channel `html5`

Required GitHub secrets (Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `BUTLER_API_KEY` | itch.io API key from itch.io → Account settings → API keys |
| `ITCH_USERNAME` | `thomasng` |
| `ITCH_GAME` | `glory-days` |

---

## Commit message checklist

When writing the release commit message, include any balance changes made since the last release:

- **Hero stat changes** — check `shared/heroes.py` diff for changes to hp, mana, attack_damage, attack_speed, armor, etc.
- **Item stat changes** — check `shared/items.py` diff for changes to item stats
- **Ability stat changes** — check `ABILITY_STATS` in `server/abilities.py` for cooldown, damage, or range tweaks
