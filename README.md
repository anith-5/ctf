# Operation Cipherfall — Local Scoreboard

A self-contained CTF scoreboard you can run on your own machine. Flags are checked
**server-side** (they never reach the browser), wrong submissions cost **−1 point**,
and the leaderboard is **shared** across every device pointed at the server.

## Requirements
- Python 3.7+ (already on macOS/Linux; on Windows install from python.org).
- **No pip installs.** It uses only the Python standard library.

## Run it
```bash
cd cipherfall_localhost
python3 server.py
```
Then open **http://localhost:8000** in your browser.

You'll see:
```
============================================================
  OPERATION CIPHERFALL — scoreboard running
  Local:    http://localhost:8000
  Network:  http://<your-ip>:8000   (same Wi-Fi/LAN)
============================================================
```

## Multiple teams / multiple computers
Everyone on the same network opens **http://<your-ip>:8000** (find your IP with
`ipconfig` on Windows or `ifconfig`/`ip a` on macOS/Linux). Each browser registers
its own team; the leaderboard updates for all of them every few seconds.

## How scoring works
- Solve a challenge → you earn its tier points (100/200/300/500/750).
- Every **wrong** submission → **−1 point** (scores can go negative).
- Solved challenges lock and can't be resubmitted.
- Tie-break: highest score → fewest penalties → earliest last solve.

## Quick self-test (optional)
With the server running, in another terminal:
```bash
# correct flag for challenge 1 -> +100
curl -s -X POST http://localhost:8000/api/submit -H 'Content-Type: application/json' \
  -d '{"teamId":"<your-id>","challengeId":1,"flag":"FLAG{w3lc0me_t0_th3_gam3}"}'
```
(Register a team in the browser first; your team id is stored by the page.)

## Reset the competition
Stop the server (Ctrl+C), delete `data.json`, start again.

## Change the port
```bash
PORT=9000 python3 server.py
```

## Files
- `server.py`  — the web server + API + flag checking (SHA-256 hashes live here).
- `index.html` — the scoreboard UI (talks to the API via fetch).
- `data.json`  — created at runtime; holds team scores. Delete to reset.
- `challenges/` — downloadable challenge artifacts, one folder per challenge id.
- `tools/make_artifacts.py` — regenerates the challenge artifacts (deterministic).

## Challenge files
File-based challenges serve their artifacts straight from the scoreboard: each
challenge card shows a download link, served from `challenges/<id>/` via `/files/…`.

15 challenges ship as downloadable files (all Warm-Up/Easy/Medium file challenges,
plus a few others). The remaining challenges are **service-based** (hosted web apps,
SSH boxes), **compiled binaries**, or **captured images** — see the design document /
answer key for how to stand those up (CTFd + Docker is the recommended path). The
scoreboard already scores all 30; only the file downloads for these 15 are wired in.

### Rebuilding the artifacts
Two large files (`challenges/17/access.log`, `challenges/18/mini.dmp`) are gitignored
because they're big and regenerable. After cloning, rebuild every artifact with:

```bash
pip install pillow piexif pyzipper scapy
python tools/make_artifacts.py
```

Generation is deterministic (fixed seed), so rebuilt files match the committed ones.

## Security note
Flags are stored as SHA-256 hashes and verified server-side, so players can't read
them from the page or the API. This is solid for a classroom or club event. For a
large public competition, put it behind HTTPS and consider per-team rate limiting on
`/api/submit`. The flag values themselves are in your separate answer-key document.
