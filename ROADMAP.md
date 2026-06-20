# GloryDay — Public Launch Roadmap

Estimated timeline: 6–9 months. Phases are sequential — don't skip ahead.

---

## Phase 1 — Alpha Polish (Now → ~4 weeks)

Make the game solid enough to hand to strangers without it falling apart.
Focus on stability and first impressions.

### Stability
- **Graceful disconnect handling** — client shows "connection lost" and returns to menu instead of hanging
- **Game-over → lobby flow** — victory screen auto-returns players to menu after a few seconds
- **Server crash recovery** — playit.gg tunnel auto-restarts; server logs errors to file

### Onboarding
- **In-game keybind overlay** — toggleable panel (Tab or ?) showing WASD, Q/E/R/B, left-click, shop key
- **Loading tooltip on first connect** — brief "waiting for players" hint so new players don't think it's broken

### Distribution
- **itch.io page** — screenshots, GIF of gameplay, short description, working download link
- **Simple install instructions** — unzip → run main.exe, one paragraph, no Python required

---

## Phase 2 — Community Beta (~1–3 months)

Get real players, build a feedback loop, and start growing an audience.
Everything here feeds back into balance and content decisions.

### Community
- **Discord server** — bug reports, balance feedback, find-a-game channel, announcements
- **YouTube devlog #1** — show the game, explain the concept, link itch.io — first external audience

### Infrastructure
- **Dedicated VPS** — replace playit.gg with a cheap VPS (e.g. Hetzner ~€4/mo); always-on server
- **Server-side logging** — log kills, disconnects, and errors to file so you can debug issues from reports

### Content
- **1–2 new heroes** — expand to 8 heroes; gives players more to discover and revisit
- **Balance pass from player feedback** — watch Discord, adjust `ABILITY_STATS` / `HERO_STATS`, push patch updates

---

## Phase 3 — Content Expansion (~3–6 months)

Grow the game's depth and prepare for a wider launch.
This is where the game starts feeling like a real product.

### Content
- **Expand to 10 heroes** — target 5 per team for a varied draft; hero-swapping system becomes meaningful
- **Second map** — different layout changes rotations and capture-point strategy
- **More items (10→15)** — especially mana, lifesteal, and CDR options to widen build variety

### UX & Retention
- **End-of-match stats screen** — KDA, damage dealt, gold earned — gives players something to talk about
- **Spectator / observer mode** — let community members watch matches; good for YouTube content too

### Steam Prep
- **Steam Direct submission** — $100 fee; takes 2–4 weeks review; start this early — approval isn't instant
- **Steam page assets** — capsule art, trailer, screenshots — these take real time to make well

---

## Phase 4 — Launch (~6–9 months)

Go wide. This phase is mostly marketing and scaling, not features.
The game should be solid well before this point.

### Marketing
- **Steam launch (Early Access or v1.0)** — Early Access is fine; it sets expectations and lets you keep updating publicly
- **YouTube launch trailer** — gameplay highlight reel, 60–90 seconds, link to Steam page
- **Streamer / content creator outreach** — small-to-mid streamers who play indie multiplayer games; offer keys
- **Reddit / indie game communities** — r/indiegaming, r/gamedev, r/MOBA — post a gameplay clip, not a sales pitch

### Scaling
- **Multiple server regions** — if player count justifies it; EU + NA at minimum
- **Matchmaking queue** — auto-pair players instead of relying on Discord find-a-game

---

## Key Callouts

- **Phase 1 is the most important.** The rest collapses without it — strangers need to download, run, and connect without hitting a dead end.
- **Fix disconnect/crash flow first.** If the server hiccups and players are stuck on a black screen, that kills word of mouth.
- **itch.io page before any marketing.** Every link you share needs somewhere to land.
- **Discord before YouTube.** You need somewhere to send viewers and a feedback channel before going wide.
- **VPS before Phase 3.** playit.gg is fine for testing but not for a real community.
- **Steam takes weeks to approve.** Submit the page early in Phase 3 — don't wait until you feel "ready."
