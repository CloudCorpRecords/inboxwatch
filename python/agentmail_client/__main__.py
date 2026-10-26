"""inboxwatch CLI. Run with: python -m agentmail_client <command> [args]
(the Python module keeps its original name; inboxwatch is the product name).

Every command prints JSON to stdout, so agents can parse it. Errors print a
JSON object with success:false to stderr and exit non-zero.
"""
import argparse
import json
import os
import sys

from . import __version__, client
from .client import MailError


def out(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))


def fail(msg):
    print(json.dumps({"success": False, "error": msg}, indent=2), file=sys.stderr)
    sys.exit(1)


def cmd_status(args):
    out({**client.status(), "version": __version__})


def cmd_claim(args):
    out(client.claim(args.name, relay=args.relay))


def cmd_lookup(args):
    try:
        out(client.lookup(args.address))
    except MailError as e:
        fail(str(e))


def cmd_send(args):
    try:
        out(client.send(args.to, args.text, subject=args.subject, kind=args.kind, thread=args.thread))
    except MailError as e:
        fail(str(e))


def cmd_check(args):
    out(client.check())


def cmd_inbox(args):
    out(client.list_messages(args.box))


def cmd_read(args):
    m = client.get_message(args.id)
    if not m:
        fail(f"No message {args.id}.")
    out(m)


def cmd_threads(args):
    out(client.threads(args.box))


def cmd_contacts(args):
    out(client.contacts())


def cmd_trust(args):
    out({"success": client.set_trust(args.address, args.trust)})


def cmd_accept_keys(args):
    try:
        out(client.accept_new_keys(args.address))
    except MailError as e:
        fail(str(e))


def cmd_selfhost(args):
    out(client.selfhost_lookup(args.address))


def cmd_register_selfhost(args):
    out(client.register_selfhost(args.endpoint))


def cmd_heartbeat(args):
    out(client.heartbeat())


def main(argv=None):
    p = argparse.ArgumentParser(prog="inboxwatch",
                                description="InboxWatch: an E2E encrypted mailbox for AI agents (Agent Mail protocol).")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--relay", default=None, help="relay domain (default: INBOXWATCH_RELAY)")
    p.add_argument("--home", default=None, help="state dir (default: INBOXWATCH_HOME or ~/.inboxwatch)")
    # The same two flags on every subcommand: the documented shape is
    # `inboxwatch claim sam --relay post.example.com`, with the flag
    # after the subcommand, and argparse only accepts a flag where it
    # is defined. Before this, that documented form exited 2 with
    # "unrecognized arguments" (found by the dogfood pass,
    # tests/test_dogfood.py).
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS defaults: a subparser default would clobber a value
    # given in the top-level position (`inboxwatch --relay X claim
    # sam`) when the subcommand itself carries no flag.
    common.add_argument("--relay", default=argparse.SUPPRESS, help="relay domain (default: INBOXWATCH_RELAY)")
    common.add_argument("--home", default=argparse.SUPPRESS, help="state dir (default: INBOXWATCH_HOME or ~/.inboxwatch)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("claim", parents=[common], help="claim an address on the relay, e.g. claim sam --relay post.example.com")
    s.add_argument("name"); s.set_defaults(f=cmd_claim)

    s = sub.add_parser("lookup", parents=[common], help="look up an address's public keys")
    s.add_argument("address"); s.set_defaults(f=cmd_lookup)

    s = sub.add_parser("send", parents=[common], help="seal and send a message now")
    s.add_argument("to", help="recipient address, or comma separated list")
    s.add_argument("text", help="message text")
    s.add_argument("--subject", default=""); s.add_argument("--kind", default="message")
    s.add_argument("--thread", default=None); s.set_defaults(f=cmd_send)

    s = sub.add_parser("check", parents=[common], help="pick up new mail from the relay"); s.set_defaults(f=cmd_check)

    s = sub.add_parser("inbox", parents=[common], help="list messages (boxes: inbox, requests, sent, held)")
    s.add_argument("--box", default="inbox"); s.set_defaults(f=cmd_inbox)

    s = sub.add_parser("read", parents=[common], help="read one message by id")
    s.add_argument("id"); s.set_defaults(f=cmd_read)

    s = sub.add_parser("threads", parents=[common], help="list threads")
    s.add_argument("--box", default="inbox"); s.set_defaults(f=cmd_threads)

    s = sub.add_parser("contacts", parents=[common], help="list pinned contacts"); s.set_defaults(f=cmd_contacts)

    s = sub.add_parser("trust", parents=[common], help="set a contact's trust: unknown, known, mine, blocked")
    s.add_argument("address"); s.add_argument("trust"); s.set_defaults(f=cmd_trust)

    s = sub.add_parser("accept-keys", parents=[common], help="pin a contact's new keys after checking the safety number")
    s.add_argument("address"); s.set_defaults(f=cmd_accept_keys)

    s = sub.add_parser("register-selfhost", parents=[common], help="register your self-hosted endpoint on the relay directory")
    s.add_argument("endpoint"); s.set_defaults(f=cmd_register_selfhost)

    s = sub.add_parser("heartbeat", parents=[common], help="tell the relay your address is alive"); s.set_defaults(f=cmd_heartbeat)

    s = sub.add_parser("selfhost-lookup", parents=[common], help="look up an address's self-hosted endpoint")
    s.add_argument("address"); s.set_defaults(f=cmd_selfhost)

    s = sub.add_parser("status", parents=[common], help="show setup state"); s.set_defaults(f=cmd_status)

    args = p.parse_args(argv)
    if args.home:
        os.environ["INBOXWATCH_HOME"] = args.home
    if args.relay:
        os.environ["INBOXWATCH_RELAY"] = args.relay
    try:
        args.f(args)
    except MailError as e:
        fail(str(e))
    except BrokenPipeError:
        pass


if __name__ == "__main__":
    main()
