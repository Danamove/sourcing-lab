#!/usr/bin/env python3
"""Offline smoke tests for Sourcing Lab. No Apify token or network needed.

  python tests/smoke_test.py

1. All .py files compile.
2. build.py renders a dashboard from fixture data (in a temp copy).
3. serve.py admin API answers /api/state and /api/schedule (in a temp copy).
4. Static sanity: branding + cron strings are consistent.
"""
import json
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_FILES = ["build.py", "refresh.py", "serve.py", "configure.py", "extract_clips.py"]
TEST_PORT = 4799

passed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  PASS  {label}")


def fail(label, detail=""):
    print(f"  FAIL  {label}  {detail}")
    sys.exit(1)


def make_fixture(tmp):
    """Copy the project into tmp with a 2-creator config + fake scrape data."""
    for f in PY_FILES + ["admin.html", "index.html"]:
        shutil.copy2(ROOT / f, tmp / f)
    wf = tmp / ".github" / "workflows"
    wf.mkdir(parents=True)
    shutil.copy2(ROOT / ".github" / "workflows" / "refresh.yml", wf / "refresh.yml")

    handles = ["test_recruiter_a", "test_sourcer_b"]
    (tmp / "config.json").write_text(json.dumps({
        "creators": [
            {"handle": h, "name": h, "followers": 1000, "posts": 10,
             "verified": False, "private": False, "profilePic": ""}
            for h in handles
        ]
    }), encoding="utf-8")

    data = tmp / "data"
    data.mkdir()
    now = datetime.now(timezone.utc)
    for i, h in enumerate(handles):
        posts = []
        for j in range(4):
            ts = (now - timedelta(days=j * 3 + 1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            posts.append({
                "shortCode": f"SC{i}{j}",
                "url": f"https://www.instagram.com/reel/SC{i}{j}/",
                "caption": f"Caption {j} about hiring great engineers",
                "timestamp": ts,
                "videoDuration": 30 + j,
                "videoPlayCount": 1000 * (10 if j == 0 else 1),  # j==0 is a 10x outlier
                "likesCount": 50, "commentsCount": 5,
                "transcript": f"Stop sending boring outreach messages, recruiter tip {j}.",
                "ownerUsername": h, "ownerFullName": h,
            })
        (data / f"{h}_posts.json").write_text(json.dumps({"items": posts}), encoding="utf-8")
        details = {"dataset": {"previewItems": [{
            "username": h, "fullName": h.replace("_", " ").title(),
            "followersCount": 1234, "postsCount": 10, "verified": False,
        }]}}
        (data / f"{h}_details.json").write_text(json.dumps(details), encoding="utf-8")
    (tmp / "thumbs").mkdir()
    (tmp / "clips").mkdir()
    return handles


def http_get(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{TEST_PORT}{path}", timeout=10) as r:
        return r.status, json.load(r)


def main():
    print("1) py_compile")
    for f in PY_FILES:
        try:
            py_compile.compile(str(ROOT / f), doraise=True)
        except py_compile.PyCompileError as e:
            fail(f"compile {f}", str(e))
    ok(f"all {len(PY_FILES)} python files compile")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        handles = make_fixture(tmp)

        print("2) build.py on fixture data")
        env = {"PYTHONIOENCODING": "utf-8"}
        import os
        env = {**os.environ, **env}
        r = subprocess.run([sys.executable, str(tmp / "build.py")],
                           cwd=tmp, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=120)
        if r.returncode != 0:
            fail("build.py exited non-zero", r.stdout[-500:] + r.stderr[-500:])
        ok("build.py exits 0 (Windows-safe date formatting + utf-8 write)")

        html = (tmp / "index.html").read_text(encoding="utf-8")
        for needle, label in [
            ("Sourcing Lab", "branding present"),
            (f"@{handles[0]}", "creator handle rendered"),
            ("Stop sending boring outreach messages", "spoken hook rendered"),
            ("Breakout", "outlier bands rendered"),
        ]:
            if needle not in html:
                fail(f"dashboard missing: {label}", f"needle={needle!r}")
        ok("dashboard HTML contains creators, hooks, outlier bands")

        rows = html.count('"shortCode"')
        if rows < 8:
            fail("expected 8 reels in payload", f"found {rows}")
        ok("all 8 fixture reels present in payload")

        print("3) serve.py admin API")
        runner = (
            "import serve, sys;"
            f"httpd = serve.ReusableTCPServer(('127.0.0.1', {TEST_PORT}), serve.AdminHandler);"
            "httpd.serve_forever()"
        )
        proc = subprocess.Popen([sys.executable, "-c", runner], cwd=tmp,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        try:
            state = None
            for _ in range(40):
                try:
                    status, state = http_get("/api/state")
                    break
                except OSError:
                    time.sleep(0.25)
            if state is None:
                fail("admin server did not come up")
            if state["tokenSet"] is not False:
                fail("/api/state tokenSet should be false without .env")
            if len(state["creators"]) != 2:
                fail("/api/state creators", f"expected 2, got {len(state['creators'])}")
            ok("/api/state → 200, no token, 2 creators")

            status, sched = http_get("/api/schedule")
            if sched.get("cron") != "0 4 * * 0":
                fail("/api/schedule default cron", f"got {sched}")
            ok("/api/schedule → weekly Sunday 04:00 UTC (Israel morning)")
        finally:
            proc.kill()

    print("4) static sanity")
    admin = (ROOT / "admin.html").read_text(encoding="utf-8")
    wf = (ROOT / ".github" / "workflows" / "refresh.yml").read_text(encoding="utf-8")
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if "Outlier Lab" in admin or "0 11 " in admin:
        fail("admin.html still has old branding/cron")
    if '"0 4 * * 0"' not in wf or "sourcing-lab-bot" not in wf:
        fail("workflow cron/bot not adapted")
    if not (ROOT / ".nojekyll").exists():
        fail(".nojekyll missing (GitHub Pages would drop _profile_* thumbs)")
    if len(cfg["creators"]) < 5:
        fail("config.json starter list too small")
    ok("branding, cron, .nojekyll, starter creator list all in place")

    print(f"\nAll smoke tests passed ({passed} checks).")


if __name__ == "__main__":
    main()
