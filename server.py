#!/usr/bin/env python3
"""
OPERATION CIPHERFALL — local scoreboard server (zero dependencies, Python 3 stdlib only).

Run:   python3 server.py
Then open http://localhost:8000  (others on your network can use http://<your-ip>:8000)

- Flags are checked SERVER-SIDE by SHA-256. They never leave this file, so players
  cannot read them from the page source.
- Scoring: sum of solved-challenge points, minus 1 point for every wrong submission.
- State persists to data.json in this folder. Delete that file to reset the event.
"""

import json, hashlib, threading, os, sys, re, mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
INDEX_FILE = os.path.join(HERE, "index.html")
CHAL_DIR = os.path.join(HERE, "challenges")
PORT = int(os.environ.get("PORT", "8000"))

def load_artifacts():
    """Map challenge id -> [filenames] from challenges/manifest.json (if present)."""
    out = {}
    try:
        with open(os.path.join(CHAL_DIR, "manifest.json")) as f:
            data = json.load(f)
        for cid, info in data.items():
            files = [fn for fn in info.get("files", [])
                     if os.path.isfile(os.path.join(CHAL_DIR, f"{int(cid):02d}", fn))]
            if files:
                out[str(int(cid))] = files
    except Exception as e:
        print("NOTE: no challenge artifacts loaded:", e)
    return out

ARTIFACTS = load_artifacts()

# ---------------------------------------------------------------------------
# Challenge catalogue (metadata sent to clients; points used for scoring)
# ---------------------------------------------------------------------------
TIERS = {"Warm-Up": 100, "Easy": 200, "Medium": 300, "Hard": 500, "Expert": 750}
CHALLENGES = [
    {"id": 1,  "t": "Welcome to Base Camp",       "c": "Cryptography",        "tier": "Warm-Up"},
    {"id": 2,  "t": "Hail Caesar",                 "c": "Cryptography",        "tier": "Warm-Up"},
    {"id": 3,  "t": "First Steps in the Shell",    "c": "Linux Fundamentals",  "tier": "Warm-Up"},
    {"id": 4,  "t": "Eavesdropper",                "c": "Networking",          "tier": "Warm-Up"},
    {"id": 5,  "t": "Picture Perfect",             "c": "Digital Forensics",   "tier": "Warm-Up"},
    {"id": 6,  "t": "Reading Between the Lines",   "c": "Digital Forensics",   "tier": "Warm-Up"},
    {"id": 7,  "t": "Spin the Wheel",              "c": "Cryptography",        "tier": "Easy"},
    {"id": 8,  "t": "Locked Out",                  "c": "Digital Forensics",   "tier": "Easy"},
    {"id": 9,  "t": "Login Loophole",              "c": "Web Exploitation",    "tier": "Easy"},
    {"id": 10, "t": "What Robots Know",            "c": "Web / OSINT",         "tier": "Easy"},
    {"id": 11, "t": "Packet Detective",            "c": "Networking",          "tier": "Easy"},
    {"id": 12, "t": "Where Was This Taken?",       "c": "OSINT / Forensics",   "tier": "Easy"},
    {"id": 13, "t": "Ghost Hunt",                  "c": "OSINT",               "tier": "Medium"},
    {"id": 14, "t": "Token of Trust",              "c": "Web Exploitation",    "tier": "Medium"},
    {"id": 15, "t": "Hidden in Plain Sight",       "c": "Web Exploitation",    "tier": "Medium"},
    {"id": 16, "t": "XOR Marks the Spot",          "c": "Cryptography",        "tier": "Medium"},
    {"id": 17, "t": "Needle in the Logstack",      "c": "Programming",         "tier": "Medium"},
    {"id": 18, "t": "Snapshot",                    "c": "Digital Forensics",   "tier": "Medium"},
    {"id": 19, "t": "Truth or Dare",               "c": "Web Exploitation",    "tier": "Hard"},
    {"id": 20, "t": "Stack Overflow (Literally)",  "c": "Reverse Engineering", "tier": "Hard"},
    {"id": 21, "t": "Layers of the Onion",         "c": "Digital Forensics",   "tier": "Hard"},
    {"id": 22, "t": "Patient Zero",                "c": "Forensics / RE",      "tier": "Hard"},
    {"id": 23, "t": "Domain of Shadows",           "c": "Networking",          "tier": "Hard"},
    {"id": 24, "t": "Crackme",                     "c": "Reverse Engineering", "tier": "Hard"},
    {"id": 25, "t": "Chain Reaction",              "c": "Web Exploitation",    "tier": "Expert"},
    {"id": 26, "t": "The Cipher's Apprentice",     "c": "Crypto / Programming","tier": "Expert"},
    {"id": 27, "t": "Deep Cuts",                   "c": "Reverse Engineering", "tier": "Expert"},
    {"id": 28, "t": "Total Recall",                "c": "Digital Forensics",   "tier": "Expert"},
    {"id": 29, "t": "Climbing the Ladder",         "c": "Linux / Privesc",     "tier": "Expert"},
    {"id": 30, "t": "The Long Con",                "c": "Networking",          "tier": "Expert"},
]
POINTS = {c["id"]: TIERS[c["tier"]] for c in CHALLENGES}

# SHA-256(flag). Plaintext flags are NOT in this file.
FLAG_HASHES = {
    1:"2e457e8ef3102f7a0074fb2632fe5e26451c5d68047cd2c69bb8c7c8e0e79a89",
    2:"17bbfbf07db780d914ad23c47a2f0700db95ec4b1d21730f249ff88d1efae833",
    3:"89a0690fa4f73d1f064cef2def4b5e8c677fb8fdba988fbcbcdf6f8d752eda72",
    4:"24b7d954dab356a4c5e1a0c1a9a033fb509edec6ae1473d1ace417a59ab37498",
    5:"e9e0823f90f3078273bc7033199ec5f0b75ce46ee51dd4544d7629baedd029e1",
    6:"fabc3b6e66672897d6473c21ea70807d003ec132417fc2f90b7df254b1156184",
    7:"c8c3fc6ee45acb1958a5fdbddc6665527de6e9e2f45cd59af155f8983d6e2996",
    8:"a73368ebacc390be3bf76d7c9fdb935eea048a04f57294431887ebe98ff8d7e4",
    9:"ee61fe537830c61bc3e3bd323df950621765c6789780dfa92c20029b4f76953c",
    10:"2fca6a6e9ae4989e3204d3158e8609e84f1c4c51a0277d9c64b04f83058dba33",
    11:"373957bd6de80454c320655e27efbcb38f616e3723751da0bc57750562d3a67e",
    12:"4de8e3260760801405cc5ecfcfb923f3d70797b6dbb9c6d96eb0216503baa7e9",
    13:"ac2486b7b854172e07d3a506feee6471476f27173840611e13ab4e76ca3070e9",
    14:"dcb0aac0b641f9285e6cac9d2d4418a609d421aa9546e4402799889b1f78e432",
    15:"412d8d111c8225bc61233467349a67243ab4e3e238b20e5782756e95c09f04da",
    16:"e4418ead745f295533c5d631e31e962b2cad60c5c905eeaafcbd8b0384715edb",
    17:"51a24965c654e0029c2111397ecec18217766fcf21dcf3ebafe14acb59da655b",
    18:"0ef0a59d0a3ab3f47f9fc7458c59c25ddbb91873372f6ba94b3ac5bdee2c552b",
    19:"3555f3210afb5d1054015b67a230df9f5343efc822668e67333118e96ae7f99a",
    20:"d2b8e7f7837cee796dd1bce20aefd81a09d32ffcf23234f60a15d61445bb9937",
    21:"d31d426e15d1a8d909712274b172adf363ef19840fa14160a68d0dd2ba8f5706",
    22:"e8b2a4a930ab766d1132b28419b365ac1287a41911caeb8d90d1d88af6442a4b",
    23:"86fd03f5a6725fe0584efc16de7ce504c5ec2604b14cbbe6717bde057dcd0a5c",
    24:"09b8fde5ef75ceaba9dde5bee8ee8ae11f37b02b19c2223f18accb8bb967cb21",
    25:"f65236bb365a83e0c169a7bcb46b1bea0097035913f48038efe1b31a01bb7cd9",
    26:"877c259d4c91cdf29869c14ee624636b4febf87f22b430987233708010e2ff93",
    27:"72e6356abbcd0317bd27307211845aef57d1976afd95a02d7bfba212a0832551",
    28:"c062774f310a93a4ba905125cfdd10bef4f1487fb149c06cd2274bacef3c062d",
    29:"7bb6ce86af044475cef0c2a0af72d3205d41389d2805a378479a2535de2d9fad",
    30:"10aaf387478eb320de922a8720a40574650fe1c71a37cb08c8c4f0ec281c0850",
}

# ---------------------------------------------------------------------------
# State (thread-safe, persisted to data.json)
# ---------------------------------------------------------------------------
LOCK = threading.Lock()
STATE = {"teams": {}}  # teams: { id: {id,name,solved:{cid:ts},wrong,lastSolve,created} }

def load_state():
    global STATE
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                STATE = json.load(f)
                STATE.setdefault("teams", {})
        except Exception as e:
            print("WARN: could not read data.json, starting fresh:", e)
            STATE = {"teams": {}}

def save_state():
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(STATE, f)
    os.replace(tmp, DATA_FILE)  # atomic

def score_of(team):
    earned = sum(POINTS.get(int(cid), 0) for cid in team.get("solved", {}))
    return earned - team.get("wrong", 0)

def public_team(team):
    return {
        "id": team["id"], "name": team["name"],
        "solved": list(team.get("solved", {}).keys()),
        "wrong": team.get("wrong", 0),
        "score": score_of(team),
        "lastSolve": team.get("lastSolve", 0),
    }

def now_ms():
    import time
    return int(time.time() * 1000)

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quieter console
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode() or "{}")
        except Exception:
            return {}

    # ---- GET ----
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            try:
                with open(INDEX_FILE, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._json({"error": "index.html missing — keep it next to server.py"}, 500)
            return
        if path == "/api/state":
            with LOCK:
                teams = [public_team(t) for t in STATE["teams"].values()]
            self._json({
                "challenges": CHALLENGES,
                "tiers": TIERS,
                "points": POINTS,
                "artifacts": ARTIFACTS,
                "teams": teams,
            })
            return
        if path.startswith("/files/"):
            self._serve_artifact(path[len("/files/"):])
            return
        self._json({"error": "not found"}, 404)

    def _serve_artifact(self, rel):
        # rel like "01/briefing.txt" — strict allowlist, no path traversal
        parts = rel.split("/")
        if (len(parts) != 2 or not parts[0].isdigit()
                or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", parts[1])):
            self._json({"error": "not found"}, 404); return
        fp = os.path.abspath(os.path.join(CHAL_DIR, parts[0], parts[1]))
        if (not fp.startswith(os.path.abspath(CHAL_DIR) + os.sep)
                or not os.path.isfile(fp)):
            self._json({"error": "not found"}, 404); return
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        try:
            with open(fp, "rb") as f:
                body = f.read()
        except OSError:
            self._json({"error": "not found"}, 404); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % parts[1])
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    # ---- POST ----
    def do_POST(self):
        path = urlparse(self.path).path
        data = self._read_json()

        if path == "/api/team":
            name = (data.get("name") or "").strip()
            if not name:
                self._json({"error": "name required"}, 400); return
            if len(name) > 28:
                name = name[:28]
            with LOCK:
                if any(t["name"].lower() == name.lower() for t in STATE["teams"].values()):
                    self._json({"error": "name taken"}, 409); return
                tid = hashlib.sha1((name + str(now_ms())).encode()).hexdigest()[:12]
                STATE["teams"][tid] = {
                    "id": tid, "name": name, "solved": {},
                    "wrong": 0, "lastSolve": 0, "created": now_ms(),
                }
                save_state()
            self._json({"ok": True, "id": tid})
            return

        if path == "/api/submit":
            tid = data.get("teamId")
            cid = data.get("challengeId")
            flag = (data.get("flag") or "").strip()
            try:
                cid = int(cid)
            except Exception:
                self._json({"error": "bad challengeId"}, 400); return
            if cid not in FLAG_HASHES:
                self._json({"error": "no such challenge"}, 404); return
            with LOCK:
                team = STATE["teams"].get(tid)
                if not team:
                    self._json({"error": "unknown team — register first"}, 404); return
                if str(cid) in team.get("solved", {}):
                    self._json({"result": "locked", "score": score_of(team)}); return
                if not flag:
                    self._json({"result": "empty", "score": score_of(team)}); return

                digest = hashlib.sha256(flag.encode()).hexdigest()
                if digest == FLAG_HASHES[cid]:
                    team.setdefault("solved", {})[str(cid)] = now_ms()
                    team["lastSolve"] = now_ms()
                    save_state()
                    self._json({"result": "correct", "points": POINTS[cid], "score": score_of(team)})
                else:
                    team["wrong"] = team.get("wrong", 0) + 1
                    save_state()
                    self._json({"result": "wrong", "penalty": 1, "score": score_of(team)})
            return

        self._json({"error": "not found"}, 404)


def main():
    load_state()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 60)
    print("  OPERATION CIPHERFALL — scoreboard running")
    print(f"  Local:    http://localhost:{PORT}")
    print(f"  Network:  http://<your-ip>:{PORT}   (same Wi-Fi/LAN)")
    print("  Reset:    stop server, delete data.json, restart")
    print("  Stop:     Ctrl+C")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down. Scores saved to data.json.")
        server.shutdown()


if __name__ == "__main__":
    main()
