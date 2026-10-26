"""Dogfood pass: the packaged entry points, end to end (fleet wave 2).

The client suite (test_client.py) imports the Python client and drives
it in-process. Nothing exercised the surfaces a user or an agent host
actually runs: the Node launcher (bin/inboxwatch.js), the Python CLI
behind it (python -m agentmail_client), and the MCP stdio server.
This file is a recorded dogfood pass over those surfaces against the
same local fake relay fixture: two agents claim addresses through the
real launcher, trade one sealed message, and pick it up, with the
relay-side assertions a production claim needs (the relay never sees
the plaintext, pickup deletes the envelope, a second pickup is
empty). Recorded results live in DOGFOOD.md next to the README.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "bin" / "inboxwatch.js"
CANARY = "canary plaintext 7f3d9 must never reach the relay"

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node launcher dogfood needs node")


def run_cli(home_dir, *args, expect_ok=True):
    env = dict(os.environ)
    env["INBOXWATCH_HOME"] = str(home_dir)
    env["INBOXWATCH_PYTHON"] = sys.executable
    p = subprocess.run(["node", str(LAUNCHER), *args], capture_output=True, text=True, env=env, timeout=60)
    if expect_ok:
        assert p.returncode == 0, f"{args} rc={p.returncode} stderr={p.stderr[:400]}"
        return json.loads(p.stdout)
    return p


@requires_node
def test_cli_two_agents_trade_sealed_mail(home, relay, tmp_path):
    alice_home = home
    bob_home = tmp_path / "bob"

    a = run_cli(alice_home, "claim", "alice", "--relay", relay.domain)
    assert a["success"] and a["address"] == f"alice@{relay.domain}"
    b = run_cli(bob_home, "claim", "bob", "--relay", relay.domain)
    assert b["success"] and b["address"] == f"bob@{relay.domain}"

    st = run_cli(alice_home, "status")
    assert st["set_up"] and st["address"] == f"alice@{relay.domain}" and st["unread"] == 0

    sent = run_cli(alice_home, "send", f"bob@{relay.domain}", CANARY, "--subject", "dogfood")
    assert sent["success"] and sent["sent_to"] == [f"bob@{relay.domain}"]

    # The relay holds exactly one sealed envelope, and neither the
    # canary text nor the subject appears anywhere in what it holds.
    held = relay.mail.get("bob") or []
    assert len(held) == 1
    held_json = json.dumps(held)
    assert CANARY not in held_json and "dogfood" not in held_json

    got = run_cli(bob_home, "check")
    assert got["success"] and got["new"] == 1
    m = got["messages"][0]
    assert m["peer"] == f"alice@{relay.domain}" and m["status"] == "new" and m["trust"] == "unknown"

    # A stranger's mail waits in Requests until trusted, via the CLI.
    assert run_cli(bob_home, "inbox") == []
    requests = run_cli(bob_home, "inbox", "--box", "requests")
    assert len(requests) == 1
    assert run_cli(bob_home, "trust", f"alice@{relay.domain}", "known") == {"success": True}
    inbox = run_cli(bob_home, "inbox")
    assert len(inbox) == 1 and inbox[0]["id"] == m["id"]

    read = run_cli(bob_home, "read", m["id"])
    assert read["text"] == CANARY and read["subject"] == "dogfood" and read["verified"]

    # Pickup deleted the envelope at the relay; a second check is empty.
    assert relay.mail.get("bob") == []
    assert run_cli(bob_home, "check")["new"] == 0


def _frame(obj):
    body = json.dumps(obj).encode()
    return b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


def _read_frames(raw):
    out = []
    while raw:
        head, _, rest = raw.partition(b"\r\n\r\n")
        length = int(head.decode().split(":", 1)[1].strip())
        out.append(json.loads(rest[:length].decode()))
        raw = rest[length:]
    return out


@requires_node
def test_mcp_server_through_the_launcher(home, relay):
    env = dict(os.environ)
    env["INBOXWATCH_HOME"] = str(home)
    env["INBOXWATCH_PYTHON"] = sys.executable
    payload = b"".join([
        _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        _frame({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
        _frame({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        _frame({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "claim_address", "arguments": {"name": "carol", "relay": relay.domain}}}),
        _frame({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "check_inbox", "arguments": {}}}),
    ])
    p = subprocess.run(["node", str(LAUNCHER)], input=payload, capture_output=True, env=env, timeout=60)
    assert p.returncode == 0, p.stderr.decode()[:400]
    responses = {r["id"]: r for r in _read_frames(p.stdout)}
    assert responses[1]["result"]["serverInfo"]["name"] == "inboxwatch"
    tools = [t["name"] for t in responses[2]["result"]["tools"]]
    assert tools == ["claim_address", "lookup", "send_message", "check_inbox",
                     "read_message", "register_selfhost", "heartbeat"], tools
    claim = json.loads(responses[3]["result"]["content"][0]["text"])
    assert claim["success"] and claim["address"] == f"carol@{relay.domain}", claim
    check = json.loads(responses[4]["result"]["content"][0]["text"])
    assert check["success"] and check["new"] == 0, check
