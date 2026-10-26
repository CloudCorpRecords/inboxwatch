# Dogfood pass, 2026-10-25 (fleet wave 2)

First end-to-end pass over the packaged surfaces, run against a
local mailbox fixture (the in-process fake relay in
tests/conftest.py, which implements the real relay protocol with
real signature checks). Until this pass, inboxwatch was not
production-claimed in Greenlight sweeps. The Python client had
in-process coverage and the CLI had a status and version smoke
test, but the Node launcher (the surface `npx @reneturcios/inboxwatch`
runs) and a two-agent trade through the packaged entry points had
never been exercised end to end.

Automated form: tests/test_dogfood.py (2 tests, in the suite).

## What ran

- `inboxwatch claim alice --relay <local relay>` and the same for
  bob, through the real Node launcher (bin/inboxwatch.js) as
  subprocesses with separate INBOXWATCH_HOME state dirs.
- `inboxwatch status`, `send`, `check`, `inbox` (inbox and requests
  boxes), `trust`, and `read`, all through the launcher.
- The MCP server through the launcher with no arguments: initialize,
  tools/list, tools/call claim_address, tools/call check_inbox,
  spoken as Content-Length framed JSON-RPC over stdio.

## Results

- Claim, send, and pickup work end to end through the launcher.
  The relay held exactly 1 sealed envelope for bob; the message
  text and the subject appear nowhere in the envelope JSON the
  relay stored (sealing verified from the relay side, not just the
  client side).
- Pickup deleted the envelope at the relay; a second check
  reported 0 new messages.
- Mail from an untrusted sender landed in Requests, moved to the
  inbox after `trust ... known`, and `read` returned the exact
  text with verified true.
- MCP: initialize answered with serverInfo name inboxwatch;
  tools/list returned the 7 documented tools; claim_address and
  check_inbox round-tripped through the framed stdio transport.

## Bug found and fixed by this pass

- The documented CLI shape `inboxwatch claim sam --relay
  post.example.com` exited 2 with "unrecognized arguments: --relay".
  The --relay and --home flags were defined only on the top-level
  parser, so they were accepted only before the subcommand, while
  the README shows them after it. Both flags are now defined on
  every subcommand as well (with SUPPRESS defaults, so the
  top-level position keeps working). Fixed in
  python/agentmail_client/__main__.py; the dogfood tests pin the
  documented shape.

## Suite counts

- Before: 28 tests passing (test_client.py, test_crypto.py).
- After: 30 tests passing, including the 2 dogfood tests.
