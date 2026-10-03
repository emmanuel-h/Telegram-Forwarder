"""Automatically forward every new message from Telegram channels to other chats.

Runs as your own Telegram user account (via Telethon / MTProto), so it works for
any channel you can read, even ones where you are not an admin.
"""

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import ChatForwardsRestrictedError, FloodWaitError, RPCError

log = logging.getLogger("forwarder")


def parse_chats(value):
    """Turn "@channel, -1001234567890, me" into ["@channel", -1001234567890, "me"]."""
    chats = []
    for item in (value or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            chats.append(int(item))
        except ValueError:
            chats.append(item)
    return chats


def load_config():
    load_dotenv()
    missing = [k for k in ("API_ID", "API_HASH") if not os.getenv(k)]
    if missing:
        sys.exit(f"Missing required setting(s): {', '.join(missing)} (see .env.example)")

    mode = os.getenv("FORWARD_MODE", "forward").strip().lower()
    if mode not in ("forward", "copy"):
        sys.exit(f"FORWARD_MODE must be 'forward' or 'copy', got {mode!r}")

    return {
        "api_id": int(os.environ["API_ID"]),
        "api_hash": os.environ["API_HASH"],
        "session": os.getenv("SESSION_NAME", "forwarder"),
        "sources": parse_chats(os.getenv("SOURCE_CHATS")),
        "destinations": parse_chats(os.getenv("DESTINATION_CHATS")),
        "drop_author": mode == "copy",
    }


async def list_chats(client):
    """Print every chat the account can see, with the ID to put in .env."""
    async for dialog in client.iter_dialogs():
        kind = "channel" if dialog.is_channel and not dialog.is_group else (
            "group" if dialog.is_group else "user"
        )
        username = getattr(dialog.entity, "username", None)
        print(f"{dialog.id:>16}  {kind:<8} {dialog.name}" + (f"  (@{username})" if username else ""))


async def resolve(client, chats, label):
    entities = []
    for chat in chats:
        try:
            entities.append(await client.get_input_entity(chat))
        except (ValueError, RPCError) as e:
            sys.exit(f"Could not find {label} chat {chat!r}: {e}\n"
                     "Run `python forwarder.py --list-chats` to see valid IDs.")
    return entities


async def forward(client, destinations, messages, drop_author):
    for dest in destinations:
        for attempt in range(2):
            try:
                await client.forward_messages(dest, messages, drop_author=drop_author)
                break
            except FloodWaitError as e:
                log.warning("Rate limited by Telegram, waiting %s s", e.seconds)
                await asyncio.sleep(e.seconds + 1)
            except ChatForwardsRestrictedError:
                log.error("Source chat has 'Restrict saving content' enabled; "
                          "Telegram does not allow forwarding or copying its messages")
                return
            except RPCError as e:
                log.error("Failed to forward to %s: %s", dest, e)
                break


async def run(cfg):
    if not cfg["sources"] or not cfg["destinations"]:
        sys.exit("SOURCE_CHATS and DESTINATION_CHATS must both be set (see .env.example)")

    client = TelegramClient(cfg["session"], cfg["api_id"], cfg["api_hash"])
    # The first run asks for your phone number and login code, then stores the
    # session in <SESSION_NAME>.session so later runs log in silently.
    await client.start()

    # Load the dialog list so numeric chat IDs can be resolved.
    await client.get_dialogs()
    sources = await resolve(client, cfg["sources"], "source")
    destinations = await resolve(client, cfg["destinations"], "destination")
    drop_author = cfg["drop_author"]

    # Albums (several photos/videos sent together) arrive as one message per
    # item; handle them as a group so they are forwarded as a single album.
    @client.on(events.NewMessage(chats=sources))
    async def on_message(event):
        if event.message.grouped_id:
            return
        log.info("New message %s in %s", event.message.id, event.chat_id)
        await forward(client, destinations, event.message, drop_author)

    @client.on(events.Album(chats=sources))
    async def on_album(event):
        log.info("New album (%d items) in %s", len(event.messages), event.chat_id)
        await forward(client, destinations, event.messages, drop_author)

    log.info("Watching %d source chat(s), forwarding to %d destination(s) in %s mode",
             len(sources), len(destinations), "copy" if drop_author else "forward")
    await client.run_until_disconnected()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list-chats", action="store_true",
                        help="print the chats this account can see, with their IDs, and exit")
    args = parser.parse_args()

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()

    if args.list_chats:
        async def _list():
            async with TelegramClient(cfg["session"], cfg["api_id"], cfg["api_hash"]) as client:
                await list_chats(client)
        asyncio.run(_list())
    else:
        asyncio.run(run(cfg))


if __name__ == "__main__":
    main()
