# Telegram Forwarder

Automatically forwards every new message posted in one or more Telegram channels
to another recipient: a person, a group, another channel, or your own Saved Messages.

It logs in as **your own Telegram account** (using [Telethon](https://docs.telethon.dev/)),
so it works for any channel you can read, even channels you only subscribe to.
A regular Telegram bot would only see channel posts if the channel owner adds it
as an admin.

## Features

- Several source channels and several destinations
- Two modes:
  - `forward`: keeps the "Forwarded from …" header
  - `copy`: re-sends the message without the header, as if you posted it
- Albums (several photos or videos sent together) stay grouped
- Text, photos, videos, documents, polls and so on are all supported
- Waits out Telegram rate limits automatically

## Setup

1. **Get API credentials.** Log in at <https://my.telegram.org>, open
   *API development tools*, and create an app. Note the `api_id` and `api_hash`.

2. **Install:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. **Fill in `.env`** with `API_ID` and `API_HASH`.

4. **Log in and find the chat IDs:**

   ```bash
   python forwarder.py --list-chats
   ```

   The first run asks for your phone number, the login code Telegram sends you,
   and your 2FA password if you set one. The session is then saved in
   `forwarder.session`, so you only log in once. **Keep that file private:**
   anyone who has it can use your account.

   The command prints every chat with its ID, for example:

   ```
     -1001234567890  channel  Crypto News  (@cryptonews)
          123456789  user     Alice  (@alice)
   ```

5. **Set `SOURCE_CHATS` and `DESTINATION_CHATS`** in `.env`. Use `@usernames` or the
   numeric IDs above, separated by commas. Use `me` to send to your Saved Messages.

6. **Run it:**

   ```bash
   python forwarder.py
   ```

   It keeps running and forwards each new message as it arrives. Stop it with Ctrl+C.

## Running it 24/7

The forwarder only works while it is running, so host it on a machine that stays on,
like a small VPS or a Raspberry Pi.

### With Docker

```bash
cp .env.example .env    # then edit it
mkdir -p data
docker compose run --rm forwarder python forwarder.py --list-chats   # one-time interactive login
docker compose up -d --build
docker compose logs -f
```

The session is stored in `./data/forwarder.session`.

### With systemd

Create `/etc/systemd/system/telegram-forwarder.service`, adjusting the paths and user:

```ini
[Unit]
Description=Telegram Forwarder
After=network-online.target
Wants=network-online.target

[Service]
User=youruser
WorkingDirectory=/home/youruser/Telegram-Forwarder
ExecStart=/home/youruser/Telegram-Forwarder/.venv/bin/python forwarder.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Log in once by hand (step 4), then run:

```bash
sudo systemctl enable --now telegram-forwarder
journalctl -u telegram-forwarder -f
```

## Limitations and good practice

- **Protected channels:** if a channel has *Restrict saving content* turned on,
  Telegram blocks forwarding and copying its messages. The forwarder logs an error
  for those messages and skips them.
- **New messages only:** messages posted while the forwarder was stopped are not
  sent afterwards.
- **Use it reasonably:** this automates your personal account. Forwarding to a
  handful of recipients is fine. Mass-forwarding to many people, or sending to
  people who never contacted you, can get the account limited by Telegram's
  anti-spam system.
- Respect the copyright and wishes of the channels you forward from.
