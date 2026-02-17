# Wheatley Bot

A Discord bot for coordinating gaming sessions on a private server. Users save their game lists and weekly availability, then use `/ready-to-play` to find who's online and shares their games.

## Features

- **Game lists** — add, remove, and browse games with autocomplete suggestions
- **Weekly availability** — set time windows per day of the week (supports late-night sessions past midnight)
- **Timezone support** — availability is stored in local time and converted for matching
- **Matchmaking** — `/ready-to-play` finds users who are available *right now* and share your games
- **SQLite storage** — persistent data stored in `data/state.db`

## Commands

| Command | Description |
|---|---|
| `/add-game <game>` | Add a game to your list (autocompletes from all known games) |
| `/remove-game <game>` | Remove a game by name (autocompletes from your games) |
| `/remove-game-menu` | Remove a game using a dropdown menu |
| `/list-games` | Show your saved games |
| `/common-games <user>` | Show games you share with another user |
| `/set-timezone <tz>` | Set your timezone (US timezone dropdown) |
| `/my-timezone` | Show your saved timezone |
| `/set-availability <day> [start] [end]` | Set or clear availability for a weekday (HH:MM format) |
| `/my-availability` | Show your weekly availability summary |
| `/ready-to-play [game]` | Find available players who share your games, optionally filtered by game |

## Setup

1. Create a bot at the [Discord Developer Portal](https://discord.com/developers/applications) and copy the token.

2. Get your server's Guild ID (enable Developer Mode in Discord settings, then right-click the server name → Copy Server ID).

3. Create a `.env` file in the project root:

   ```
   DISCORD_TOKEN=your_token_here
   GUILD_ID=your_guild_id_here
   ```

4. Install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

5. Run the bot:

   ```bash
   python bot.py
   ```

## Project Structure

```
wheatley-bot/
├── bot.py                      # Client setup and entrypoint
├── state.py                    # Database class (SQLite) and pure logic
├── commands/
│   ├── helpers.py              # BotClient protocol for type-safe access
│   ├── games.py                # Game list commands
│   ├── availability.py         # Timezone and availability commands
│   └── matchmaking.py          # /ready-to-play command
├── tests/
│   └── test_games_state.py     # Unit tests for state logic
├── data/                       # Runtime data (gitignored)
│   └── state.db
├── requirements.txt
└── pyproject.toml
```

## Running Tests

```bash
python -m pytest tests/ -v
```
