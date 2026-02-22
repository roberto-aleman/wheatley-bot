# Hourglass Bot

A Discord bot for coordinating gaming sessions on a private server. Users save their game lists and weekly availability, then use `/ready-to-play` to find who's online and shares their games.

## Features

- **Game lists** — add, remove, and browse games with autocomplete suggestions
- **Weekly availability** — set time windows per day of the week (supports late-night sessions past midnight)
- **Timezone support** — all IANA timezones supported; availability is stored in local time and converted for matching
- **Matchmaking** — `/ready-to-play` finds users who are available *right now* and share your games
- **Setup hints** — new users get guided through setup when they first try matchmaking commands
- **SQLite storage** — persistent data stored in `data/state.db`

## Commands

| Command | Description |
|---|---|
| `/hourglass` | Show all available commands |
| `/add-game <game>` | Add a game to your list (autocompletes from all known games) |
| `/remove-game <game>` | Remove a game by name (autocompletes from your games) |
| `/remove-game-menu` | Remove a game using a dropdown menu |
| `/list-games` | Show your saved games |
| `/common-games <user>` | Show games you share with another user |
| `/who-plays <game>` | List all users who have a specific game |
| `/set-timezone <timezone>` | Set your timezone (autocompletes from abbreviations and IANA timezones) |
| `/my-timezone` | Show your saved timezone |
| `/set-availability <day> <start> <end>` | Add a time slot for a weekday (autocomplete with 15-min intervals) |
| `/clear-availability <day>` | Clear all time slots for a weekday |
| `/my-availability` | Show your weekly availability summary |
| `/ready-to-play [game]` | Find available players who share your games, optionally filtered by game |
| `/next-available [user]` | Show when a user is next available (defaults to yourself) |
| `/snooze <until>` | Temporarily hide from matchmaking until a time today |
| `/unsnooze` | Cancel your snooze and show as available again |

## Setup

1. Create a bot at the [Discord Developer Portal](https://discord.com/developers/applications) and copy the token.

2. *(Optional)* For instant command updates during development, get your test server's Guild ID (enable Developer Mode in Discord settings, then right-click the server name → Copy Server ID).

3. Create a `.env` file in the project root:

   ```
   DISCORD_TOKEN=your_token_here
   TEST_GUILD_ID=your_guild_id_here  # optional, for instant command sync during dev
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
hourglass-bot/
├── bot.py                      # Bot setup and entrypoint (commands.Bot)
├── state.py                    # Database class (SQLite), versioned migrations, and pure logic
├── commands/
│   ├── helpers.py              # BotClient protocol, shared autocomplete helpers, and setup hints
│   ├── games.py                # Game list commands (Cog)
│   ├── availability.py         # Timezone and availability commands (Cog)
│   ├── matchmaking.py          # /ready-to-play and /next-available commands (Cog)
│   └── help.py                 # /hourglass help command (Cog)
├── tests/
│   └── test_state.py           # Unit tests for state logic
├── data/                       # Runtime data (gitignored)
│   └── state.db
├── requirements.txt
└── pyproject.toml
```

## Running Tests

```bash
python -m pytest tests/ -v
```
