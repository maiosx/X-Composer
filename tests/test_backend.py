#!/usr/bin/env python3
"""Deterministic stdlib regression test for the x.composer backend.

Runs the real backend.py as a subprocess inside a throwaway sandbox with
a private HOME, XDG_RUNTIME_DIR and PATH, so no real config, browser,
network or X API is ever touched: the fake xdg-open found on the sandbox
PATH records its argv instead of opening anything, and the API result
classification checks run against an in-memory copy of the backend with
urllib fully mocked. Backend path is repository-relative.

Usage:  python3 tests/test_backend.py   (from the plugin root)

Prints "backend regression: PASS" and exits 0 on success; the first
failed assertion aborts with full subprocess output.
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend.py"
TERMINAL = {"posted", "handoff", "rejected", "unknown"}
PY = sys.executable


def run(env, *args, payload=None, ok=True):
    p = subprocess.run(
        [PY, str(BACKEND), *args],
        input=None if payload is None else json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )
    data = json.loads(p.stdout)
    if ok is True:
        assert p.returncode == 0 and data.get("ok") is True, (p.returncode, data, p.stderr)
    if ok is False:
        assert p.returncode != 0 and data.get("ok") is False, (p.returncode, data, p.stderr)
    return p.returncode, data


def wait(env, jid):
    for _ in range(100):
        _, st = run(env, "status", jid, ok=True)
        if st.get("state") in TERMINAL:
            return st
        time.sleep(0.05)
    raise AssertionError("job did not terminate")


with tempfile.TemporaryDirectory(prefix="xtweet-reg-") as td:
    root = Path(td)
    home = root / "home"
    runtime = root / "run"
    bin = root / "bin"
    count = root / "opens"
    arg = root / "open-arg"
    for p in (home, runtime, bin):
        p.mkdir(mode=0o700)
    (bin / "xdg-open").write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f"printf x >> {count}",
                f"printf '%s' \"$1\" > {arg}",
                "sleep 1",
                "exit 0",
                "",
            ]
        )
    )
    os.chmod(bin / "xdg-open", 0o755)
    env = os.environ.copy()
    env.update(
        HOME=str(home),
        XDG_RUNTIME_DIR=str(runtime),
        PATH=f"{bin}:{env['PATH']}",
    )

    # First run provisions the config; mode defaults to the free Web Intent
    # and the provisioned paths keep owner-only permission bits.
    run(env, "mode", ok=True)
    cfg_dir = home / ".config" / "xtweet"
    cfg_file = cfg_dir / "config.toml"
    assert os.lstat(cfg_dir).st_mode & 0o777 == 0o700, "config dir is not 0700"
    assert os.lstat(cfg_file).st_mode & 0o777 == 0o600, "config.toml is not 0600"

    # Paid API mode is strictly opt-in: all four credentials enable it,
    # partial credentials fall back to the free Web Intent with a warning.
    cfg_file.write_text(
        "paid_api = true\n"
        'api_key = "k"\n'
        'api_key_secret = "s"\n'
        'access_token = "t"\n'
        'access_token_secret = "ts"\n'
    )
    _, m = run(env, "mode", ok=True)
    assert m["mode"] == "api" and m["paid"] is True, m
    cfg_file.write_text('paid_api = true\napi_key = "k"\n')
    _, m = run(env, "mode", ok=True)
    assert m["mode"] == "intent" and m["paid"] is False and m.get("warning"), m
    cfg_file.write_text("paid_api = false\n")
    rc, drift = run(
        env,
        "enqueue",
        payload={"text": "mode drift", "expectedMode": "api"},
        ok=False,
    )
    assert drift["kind"] == "mode-changed" and drift["mode"] == "intent", drift

    # Detached worker: exactly one claim, replay is refused as busy, and the
    # draft-bearing intent URL lives in a private redirect document — never
    # in xdg-open's argv. Ack removes all draft-bearing job material.
    _, q = run(env, "enqueue", payload={"text": "one worker only"}, ok=True)
    jid = q["jobId"]
    worker_claim = runtime / "x.composer" / "jobs" / jid / "worker.json"
    for _ in range(50):
        if worker_claim.exists():
            break
        time.sleep(0.02)
    assert worker_claim.exists(), "detached worker never claimed the job"
    replay = subprocess.run(
        [PY, str(BACKEND), "_worker", jid],
        text=True,
        capture_output=True,
        env=env,
        timeout=5,
    )
    if replay.stdout.strip():
        replay_obj = json.loads(replay.stdout)
        assert replay.returncode != 0 or replay_obj.get("kind") == "busy"
    st = wait(env, jid)
    assert st["state"] == "handoff", st
    assert count.read_text() == "x", count.read_text()
    opened_arg = arg.read_text()
    assert opened_arg.startswith("file://") and "one%20worker%20only" not in opened_arg, opened_arg
    redirect = Path(urllib.parse.unquote(urllib.parse.urlparse(opened_arg).path))
    redirect_html = redirect.read_text()
    assert "https://x.com/intent/tweet?" in redirect_html and "one%20worker%20only" in redirect_html
    run(env, "ack", jid, ok=True)
    assert not redirect.exists(), "ack retained draft-bearing redirect"

    worker_files = list((runtime / "x.composer" / "jobs").glob("*/worker.json"))
    assert not worker_files, worker_files

    # Draft flow: enqueue pins the draft revision it submitted, a second
    # enqueue while the terminal result is unacked is refused as busy, and
    # clearing with a stale revision is a CAS conflict that preserves the
    # saved draft.
    count.write_text("")
    _, d1 = run(env, "draft", "set", payload={"text": "A"}, ok=True)
    rev1 = d1["revision"]
    assert os.lstat(cfg_dir / "draft.json").st_mode & 0o777 == 0o600, "draft.json is not 0600"
    _, q = run(env, "enqueue", payload={"text": "A"}, ok=True)
    jid = q["jobId"]
    assert q["draftRevision"] == rev1
    run(env, "draft", "set", payload={"text": "B"}, ok=True)
    _, d3 = run(env, "draft", "set", payload={"text": "A"}, ok=True)
    rev3 = d3["revision"]
    assert rev3 > rev1
    st = wait(env, jid)
    assert st["state"] == "handoff" and st["draftRevision"] == rev1, st
    rc, busy = run(env, "enqueue", payload={"text": "duplicate"}, ok=False)
    assert busy["kind"] == "busy" and busy["jobId"] == jid, busy
    rc, conflict = run(env, "draft", "clear", str(rev1), ok=False)
    assert conflict["kind"] == "conflict", conflict
    _, saved = run(env, "draft", "get", ok=True)
    assert saved["text"] == "A" and saved["revision"] == rev3, saved
    run(env, "ack", jid, ok=True)

    # Concurrent clear vs set on the same revision: the draft lock
    # serializes them, the set always survives, and the clear either wins
    # its compare-and-swap or is refused with a conflict.
    for i in range(20):
        _, base = run(env, "draft", "set", payload={"text": "A"}, ok=True)
        rev = base["revision"]
        clear = subprocess.Popen(
            [PY, str(BACKEND), "draft", "clear", str(rev)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        setter = subprocess.Popen(
            [PY, str(BACKEND), "draft", "set"],
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        set_out, set_err = setter.communicate(json.dumps({"text": "B"}), timeout=5)
        clear_out, clear_err = clear.communicate(timeout=5)
        assert setter.returncode == 0, (set_out, set_err)
        assert clear.returncode in (0, 1), (clear_out, clear_err)
        _, saved = run(env, "draft", "get", ok=True)
        assert saved["text"] == "B", saved

    # Planted FIFOs on predictable paths must not block; oversized local
    # files and stdin must be refused instead of being slurped unbounded.
    cfg_file.write_text("paid_api = false\n")
    os.chmod(cfg_file, 0o600)

    def quick(*args, payload=None, input_bytes=None):
        p = subprocess.run(
            [PY, str(BACKEND), *args],
            input=(
                input_bytes
                if input_bytes is not None
                else (None if payload is None else json.dumps(payload))
            ),
            text=input_bytes is None,
            capture_output=True,
            env=env,
            timeout=2,
        )
        data = json.loads(p.stdout.decode() if isinstance(p.stdout, bytes) else p.stdout)
        return p.returncode, data

    saved_cfg = cfg_file.read_text()
    cfg_file.unlink()
    os.mkfifo(cfg_file, 0o600)
    os.chmod(cfg_file, 0o600)
    rc, fifo_cfg = quick("mode")
    os.unlink(cfg_file)
    cfg_file.write_text(saved_cfg)
    os.chmod(cfg_file, 0o600)
    assert rc != 0 and fifo_cfg.get("ok") is False, fifo_cfg
    assert "regular file" in fifo_cfg.get("message", ""), fifo_cfg

    draft_path = cfg_dir / "draft.json"
    if draft_path.exists() or draft_path.is_fifo():
        draft_path.unlink()
    os.mkfifo(draft_path)
    rc, fifo_draft = quick("draft", "get")
    os.unlink(draft_path)
    assert rc == 0 and fifo_draft.get("ok") is True, fifo_draft
    assert fifo_draft.get("text") == "", fifo_draft

    rt = runtime / "x.composer"
    assert rt.is_dir()
    active = rt / "active"
    if active.exists() or active.is_fifo():
        active.unlink()
    os.mkfifo(active)
    rc, fifo_active = quick("active")
    os.unlink(active)
    assert rc == 0 and fifo_active.get("ok") is True and fifo_active.get("active") is None, fifo_active

    lock_path = rt / "lock"
    if lock_path.exists() or lock_path.is_fifo():
        lock_path.unlink()
    os.mkfifo(lock_path)
    rc, fifo_lock = quick("active")
    os.unlink(lock_path)
    assert rc != 0 and fifo_lock.get("ok") is False, fifo_lock
    assert "regular file" in fifo_lock.get("message", ""), fifo_lock

    huge_cfg = "paid_api = false\n" + ("# " + "x" * 80 + "\n") * 900
    assert len(huge_cfg.encode()) > 64 * 1024
    cfg_file.write_text(huge_cfg)
    os.chmod(cfg_file, 0o600)
    rc, huge = quick("mode")
    cfg_file.write_text("paid_api = false\n")
    os.chmod(cfg_file, 0o600)
    assert rc != 0 and huge.get("ok") is False, huge
    assert "exceeds" in huge.get("message", ""), huge

    rc, huge_in = quick(
        "enqueue",
        input_bytes=b'{"text":"' + b"A" * (128 * 1024) + b'"}',
    )
    assert rc != 0 and huge_in.get("ok") is False, huge_in
    assert huge_in.get("kind") == "input" and "exceeds" in huge_in.get("message", ""), huge_in

# API result classification with the network fully mocked: a confirmed
# post ID is "posted", a 4xx is a clean "rejected", and anything ambiguous
# (5xx, empty body, network error) is "unknown" — never silently retried.
spec = importlib.util.spec_from_file_location("xt_backend", BACKEND)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Resp:
    def __init__(self, status, body):
        self.status = status
        self.body = body
        self._offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        if n is None or n < 0:
            out = self.body[self._offset :]
            self._offset = len(self.body)
            return out
        out = self.body[self._offset : self._offset + n]
        self._offset += len(out)
        return out


mod.urllib.request.urlopen = lambda req, timeout: Resp(
    201, json.dumps({"data": {"id": "1"}}).encode()
)
assert mod.api_post_tweet("x", "a", "b", "c", "d")["state"] == "posted"
mod.urllib.request.urlopen = lambda req, timeout: Resp(201, b"{}")
assert mod.api_post_tweet("x", "a", "b", "c", "d")["state"] == "unknown"


def http(code):
    def fail(req, timeout):
        raise urllib.error.HTTPError(req.full_url, code, "err", {}, io.BytesIO(b"{}"))

    return fail


mod.urllib.request.urlopen = http(401)
assert mod.api_post_tweet("x", "a", "b", "c", "d")["state"] == "rejected"
mod.urllib.request.urlopen = http(503)
assert mod.api_post_tweet("x", "a", "b", "c", "d")["state"] == "unknown"
mod.urllib.request.urlopen = lambda req, timeout: (_ for _ in ()).throw(
    urllib.error.URLError("connection reset")
)
assert mod.api_post_tweet("x", "a", "b", "c", "d")["state"] == "unknown"
mod.urllib.request.urlopen = lambda req, timeout: Resp(
    201, json.dumps({"data": {"id": "1"}}).encode() + b"x" * (mod.MAX_HTTP_BODY_BYTES + 1)
)
assert mod.api_post_tweet("x", "a", "b", "c", "d")["state"] == "unknown"


def http_body(code, body):
    def fail(req, timeout):
        raise urllib.error.HTTPError(req.full_url, code, "err", {}, io.BytesIO(body))

    return fail


mod.urllib.request.urlopen = http_body(401, b"x" * (mod.MAX_HTTP_BODY_BYTES + 1))
rejected = mod.api_post_tweet("x", "a", "b", "c", "d")
assert rejected["state"] == "rejected", rejected
assert "HTTP 401" in rejected["message"], rejected
print("backend regression: PASS")
