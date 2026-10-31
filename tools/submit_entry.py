"""
Runs the official, unmodified contest-submit.py for this entry.

    LAB_SUBMISSION_TOKEN=… python3 -I tools/submit_entry.py [--entry <uuid>]   (or --token-file <mode-600 file>)

- The token is read from a mode-600 file outside the repo and passed only as LAB_SUBMISSION_TOKEN in this
  process's environment: never in arguments, URLs, logs or files.
- Cloudflare in front of the Lab API answers 403 to Python's default "Python-urllib" user agent (checked on
  2026-10-30). The wrapper only sets an honest user agent naming the official client; the client's code runs
  as published (SHA-256 recorded below and checked before running).
"""

import argparse
import hashlib
import os
import runpy
import stat
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENT = ROOT / "vendor" / "contest-submit" / "contest-submit.py"
CLIENT_SHA256 = "7599c1c09b9cf0358ad359dddfbcfd61d2ca72675caf2af5c542efa17933ba14"
USER_AGENT = "contest-submit.py (official SandBase Lab client; python urllib)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token-file", help="mode-600 file with the token; omit when LAB_SUBMISSION_TOKEN is already in the environment")
    ap.add_argument("--entry", default="a43da048-c1e7-429f-9306-005dabcd638b")
    args = ap.parse_args()
    if hashlib.sha256(CLIENT.read_bytes()).hexdigest() != CLIENT_SHA256:
        print("contest-submit.py does not match the reviewed version; stopping")
        return 2
    if args.token_file:
        tf = Path(args.token_file)
        if tf.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            print("token file must be readable by its owner only (chmod 600)")
            return 2
        os.environ["LAB_SUBMISSION_TOKEN"] = tf.read_text().strip()
    elif not os.environ.get("LAB_SUBMISSION_TOKEN"):
        print("LAB_SUBMISSION_TOKEN is not set")
        return 2
    for f in ("final/entry.json", "final/film.mp4", "final/cover.jpg"):
        if not (ROOT / f).is_file():
            print(f"missing {f}; nothing uploaded")
            return 2

    original = urllib.request.OpenerDirector.__init__

    def init(self, *a, **k):
        original(self, *a, **k)
        self.addheaders = [("User-agent", USER_AGENT)]

    urllib.request.OpenerDirector.__init__ = init
    sys.argv = [str(CLIENT), "--contest", "city-life", "--entry", args.entry,
                "--metadata", str(ROOT / "final/entry.json"), "--video", str(ROOT / "final/film.mp4"),
                "--cover", str(ROOT / "final/cover.jpg")]
    try:
        runpy.run_path(str(CLIENT), run_name="__main__")
    except SystemExit as e:
        return int(e.code or 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
