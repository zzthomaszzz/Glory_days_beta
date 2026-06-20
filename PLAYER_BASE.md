# Building a Player Base

Current status: itch.io published, Reddit posted, server live.

---

## One-Time Setup

- [ ] Create a Discord server
- [ ] Add Discord invite link to itch.io page description
- [ ] Add Discord link to Reddit bio and future posts
- [ ] Pin a #find-a-game channel so players can coordinate

---

## Weekly (15–30 min)

- Post one short gameplay clip or update to Discord
  - A funny moment, close fight, something you're testing
  - Keeps the server feeling alive even with few members
- Respond to any comments on itch.io or Reddit

---

## Every 2–3 Weeks

**itch.io devlog**
- Post whenever you make balance changes, fix bugs, or add content
- Even 3–4 bullet points counts — itch.io notifies followers automatically
- Format: what changed, why, what's next

**Reddit update**
- Only post when you have something new to show
- Good triggers: new hero, balance patch, funny clip, milestone (X downloads)
- Don't post empty "still working on it" updates
- Subreddits: r/indiegaming, r/MOBA, r/gamedev (frame as "what I learned")
- Always declare AI usage per r/indiegaming rules

---

## Monthly

**YouTube devlog**
- 3–5 minutes, casual, no editing skills needed
- Just screen record and talk through what changed
- Good video ideas:
  - "I added a new hero — here's how I balanced it"
  - "How the mineral system works and why I stole it from StarCraft"
  - "X things I learned building a MOBA from scratch"
  - "GloryDay devlog #X — patch notes and what's next"

---

## Content Ideas (when stuck)

- How a specific ability works under the hood
- "We just hit X downloads — here's what I learned"
- Hero spotlight — 30 second clip showing a hero's full kit
- "Someone found a bug and it was hilarious"
- Balance patch notes with reasoning behind each change
- Behind the scenes — show the code, the map, the thought process

---

## Platforms

| Platform | Purpose | Frequency |
|----------|---------|-----------|
| Discord | Community home, find-a-game, bug reports | Daily/weekly |
| itch.io devlog | Patch notes, announcements | Every 2–3 weeks |
| r/indiegaming | New players discovery | Monthly or on big updates |
| r/MOBA | Targeted audience | Monthly or on big updates |
| YouTube | Devlogs, longer reach | Monthly |

---

## The One Rule

**Don't go silent for more than 2 weeks.**

A small consistent drip beats a big launch followed by nothing.
Even a one-liner Discord post counts as activity.

---

## Milestones to Post About

- First 50 / 100 / 500 downloads
- First Discord member who isn't a friend
- New hero added
- Major balance patch
- Steam page submission (Phase 3)
- Steam launch (Phase 4)

---

## Release Checklist (when pushing a new version)

- [ ] Bump `GAME_VERSION` in `shared/constants.py`
- [ ] Commit and push to GitHub
- [ ] Build with PyInstaller (`main.spec`, `console=False`)
- [ ] Copy assets into `dist/`
- [ ] Zip and create GitHub release
- [ ] `butler push GloryDay_vX.X.zip thomasng/glory-days:windows --userversion "X.X"`
- [ ] Post itch.io devlog with patch notes
- [ ] Post Discord update

See `CLAUDE.md` for full build steps.
