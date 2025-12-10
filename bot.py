# bot.py
import json
import os
from pathlib import Path
from typing import Any, cast

import discord
from discord import app_commands
from dotenv import load_dotenv

# Load environment variables from .env into os.environ
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

if TOKEN is None:
    raise RuntimeError("DISCORD_TOKEN is not set in .env")

if GUILD_ID is None:
    raise RuntimeError("GUILD_ID is not set in .env")

# Lightweight guild object used for command registration / sync
GUILD = discord.Object(id=int(GUILD_ID))

# Path to the JSON state file: ./data/state.json next to this script
STATE_PATH = Path(__file__).parent / "data" / "state.json"


def _empty_availability() -> dict[str, list[dict[str, str]]]:
    return {day: [] for day in DAY_KEYS}


def load_state() -> dict[str, Any]:
    """
    Load bot state from data/state.json.

    Returns a dict shaped like:
        {"users": { "<user_id_str>": { "games": [..] }, ... }}

    If the file is missing, invalid, or doesn't match this shape,
    returns {"users": {}}.
    """
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"users": {}}
    except json.JSONDecodeError:
        # Corrupted or empty file; treat as fresh
        return {"users": {}}

    # Ensure required top-level key exists
    if not isinstance(data, dict) or "users" not in data:
        return {"users": {}}

    # Make sure "users" is at least a dict
    if not isinstance(data["users"], dict):
        data["users"] = {}

    return data


def save_state(state: dict[str, Any]) -> None:
    """
    Save bot state back to data/state.json as pretty JSON.
    """
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def normalize_game_name(name: str) -> str:
    """Lowercase the name and remove all whitespace."""
    return "".join(name.split()).lower()


def add_game_to_state(state: dict[str, Any], user_id: int, game_name: str) -> None:
    """
    Add or update a game for this user in `state`.

    Matching is case- and whitespace-insensitive:
    if a normalized match exists, replace it with `game_name`;
    otherwise, append `game_name`.
    """
    user_key = str(user_id)
    users = state["users"]

    if user_key not in users:
        users[user_key] = {"games": []}

    games = users[user_key]["games"]
    normalized_new = normalize_game_name(game_name)

    for idx, existing in enumerate(games):
        if normalize_game_name(existing) == normalized_new:
            games[idx] = game_name
            break
    else:
        # Loop finished with no break: game not present yet
        games.append(game_name)


def remove_game_from_state(state: dict[str, Any], user_id: int, game_name: str) -> bool:
    """
    Remove a game for this user in `state`.

    Matching is case- and whitespace-insensitive:
    if a normalized match exists, remove it and return True;
    otherwise, return False.
    """
    user_key = str(user_id)
    users = state["users"]

    if user_key not in users:
        return False

    user = users[user_key]
    if "games" not in user:
        return False

    games = user["games"]
    if not games:
        return False

    normalized_query = normalize_game_name(game_name)
    for game in games:
        if normalize_game_name(game) == normalized_query:
            games.remove(game)
            return True

    return False


def list_games_from_state(state: dict[str, Any], user_id: int) -> list[str]:
    """
    Return a list of this user's games from `state`.

    If the user or games list is missing, returns an empty list.
    """
    user_key = str(user_id)
    users = state["users"]

    if user_key not in users:
        return []

    user = users[user_key]
    if "games" not in user:
        return []

    games = user["games"]
    # Return a copy so callers can't accidentally mutate state
    return list(games)


def get_common_games(
    state: dict[str, Any],
    user_id_a: int,
    user_id_b: int,
) -> list[str]:
    games_a = list_games_from_state(state, user_id_a)
    games_b = list_games_from_state(state, user_id_b)

    normalized_b = {normalize_game_name(name) for name in games_b}
    common: list[str] = []

    for name_a in games_a:
        norm_a = normalize_game_name(name_a)
        if norm_a in normalized_b:
            common.append(name_a)

    return common


def set_timezone_in_state(state: dict[str, Any], user_id: int, tz: str) -> None:
    """
    Set or update the user's timezone string in `state`.
    """
    user_key = str(user_id)
    users = state["users"]

    if user_key not in users:
        users[user_key] = {"games": [], "timezone": tz}
    else:
        user = users[user_key]
        # Ensure games key exists for consistency
        if "games" not in user:
            user["games"] = []
        user["timezone"] = tz


def get_timezone_from_state(state: dict[str, Any], user_id: int) -> str | None:
    user_key = str(user_id)
    users = state["users"]

    if user_key not in users:
        return None

    user = users[user_key]
    tz = user.get("timezone")
    if isinstance(tz, str) and tz:
        return tz

    return None


def set_day_availability_in_state(
    state: dict[str, Any],
    user_id: int,
    day: str,
    start: str | None,
    end: str | None,
) -> None:
    """
    Set or clear availability for a single weekday in the user's local time.

    - `day` is one of: "mon", "tue", "wed", "thu", "fri", "sat", "sun".
    - If `start` or `end` is falsy (None or ""), the day's availability is cleared.
    - Otherwise, availability[day] is set to a single interval: [{"start": start, "end": end}].
    """
    user_key = str(user_id)
    users = state["users"]

    if user_key not in users:
        users[user_key] = {
            "games": [],
            "availability": _empty_availability(),
        }

    user = users[user_key]

    if "availability" not in user or not isinstance(user["availability"], dict):
        user["availability"] = _empty_availability()

    availability = user["availability"]

    # Ensure all day keys exist
    for d in DAY_KEYS:
        if d not in availability:
            availability[d] = []

    # Clear if start/end not provided
    if not start or not end:
        availability[day] = []
    else:
        availability[day] = [{"start": start, "end": end}]


def get_availability_from_state(
    state: dict[str, Any],
    user_id: int,
) -> dict[str, list[dict[str, str]]]:
    """
    Return the user's availability dict, normalized to have all 7 days.

    The returned dict has keys "mon".."sun" and lists of {"start": "...", "end": "..."}
    in local time. The returned structure is a copy; mutating it will not change `state`.
    """
    user_key = str(user_id)
    users = state["users"]

    if user_key not in users:
        return _empty_availability()

    user = users[user_key]
    availability = user.get("availability")

    if not isinstance(availability, dict):
        return _empty_availability()

    # Normalize: ensure all day keys exist
    for day in DAY_KEYS:
        availability.setdefault(day, [])

    # Return a copy so callers can't mutate state via the result
    return {day: list(slots) for day, slots in availability.items() if day in DAY_KEYS}


def format_user_availability(state: dict[str, Any], user_id: int) -> str:
    """Return a human-readable weekly availability summary for this user.

    Uses get_availability_from_state and get_timezone_from_state.

    Output format (exact and deterministic):

    - First line: 'timezone: <tz>' or 'timezone: not set'
    - Then one line per day in DAY_KEYS order:
      '<day>: none' if that day's list is empty
      '<day>: HH:MM-HH:MM' if there is exactly one interval

    For v1 we ignore any extra intervals beyond the first if they somehow exist.
    Relies on get_availability_from_state to return a normalized availability dict.
    """
    tz = get_timezone_from_state(state, user_id)
    lines: list[str] = []

    if tz:
        lines.append(f"timezone: {tz}")
    else:
        lines.append("timezone: not set")

    availability = get_availability_from_state(state, user_id)

    for day in DAY_KEYS:
        slots = availability[day]
        if not slots:
            lines.append(f"{day}: none")
        else:
            slot = slots[0]
            lines.append(f"{day}: {slot['start']}-{slot['end']}")

    return "\n".join(lines)


class WheatleyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents) -> None:
        super().__init__(intents=intents)
        # Load persistent state once at startup
        self.state: dict[str, Any] = load_state()

        # Command tree holds all slash / application commands
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        """
        Called by discord.py before the bot is fully ready.

        Use this to register / sync app commands.
        """
        # Sync commands to a single guild for fast updates
        self.tree.copy_global_to(guild=GUILD)
        await self.tree.sync(guild=GUILD)
        print(f"Synced commands to guild {GUILD_ID}")

    async def on_ready(self) -> None:
        """
        Event handler called when the client is ready.
        """
        user = self.user
        if user is None:
            print("Logged in, but self.user is None")
            return

        print(f"Logged in as {user} (ID: {user.id})")
        print(f"Number of users: {len(self.state['users'])}")
        print("------")


# Baseline intents: good default for now
intents = discord.Intents.default()
client = WheatleyClient(intents=intents)


class RemoveGameSelect(discord.ui.Select):
    """Select menu that lets a user pick one of their games to remove."""

    def __init__(self, games: list[str]) -> None:
        # Discord limits a select to 25 options; truncate if needed.
        options = [discord.SelectOption(label=game, value=game) for game in games[:25]]

        super().__init__(
            placeholder="Select a game to remove...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the user selecting a game to remove."""
        wheatley = cast(WheatleyClient, interaction.client)
        state = wheatley.state

        user_id = interaction.user.id
        selected_game = self.values[0]

        removed = remove_game_from_state(state, user_id, selected_game)
        if removed:
            save_state(state)
            message = f'Removed "{selected_game}" from your games.'
        else:
            message = f'"{selected_game}" is no longer in your games.'

        # Disable the select so it can’t be reused
        self.disabled = True

        view = self.view  # parent RemoveGameView
        # view should not be None because we added this Select to it
        await interaction.response.edit_message(content=message, view=view)


class RemoveGameView(discord.ui.View):
    """View containing the remove-game select for a single user."""

    def __init__(self, games: list[str]) -> None:
        super().__init__(timeout=60)
        # We only add the select if there are options; the command will guard this.
        self.add_item(RemoveGameSelect(games))


@client.tree.command(
    name="add-game",
    description="Add a game to your list.",
    guild=GUILD,
)
async def add_game(interaction: discord.Interaction, game: str) -> None:
    """Slash command to add a game to the caller's saved list."""
    user_id = interaction.user.id

    wheatley = cast(WheatleyClient, interaction.client)
    state = wheatley.state

    add_game_to_state(state, user_id, game)
    save_state(state)

    await interaction.response.send_message(
        f'Added "{game}" to your games.',
        ephemeral=True,
    )


@client.tree.command(
    name="remove-game",
    description="Remove a game from your list.",
    guild=GUILD,
)
async def remove_game(interaction: discord.Interaction, game: str) -> None:
    """Slash command to remove a game from the caller's saved list."""
    user_id = interaction.user.id

    wheatley = cast(WheatleyClient, interaction.client)
    state = wheatley.state

    removed = remove_game_from_state(state, user_id, game)
    if removed:
        save_state(state)
        message = f'Removed "{game}" from your games.'
    else:
        message = f'"{game}" was not found in your games.'

    await interaction.response.send_message(message, ephemeral=True)


@client.tree.command(
    name="remove-game-menu",
    description="Remove a game from your list using a dropdown menu.",
    guild=GUILD,
)
async def remove_game_menu(interaction: discord.Interaction) -> None:
    """Slash command to remove a game via a select menu."""
    user_id = interaction.user.id

    wheatley = cast(WheatleyClient, interaction.client)
    state = wheatley.state

    games = list_games_from_state(state, user_id)

    if not games:
        await interaction.response.send_message(
            "You don't have any games saved.",
            ephemeral=True,
        )
        return

    view = RemoveGameView(games)

    await interaction.response.send_message(
        "Select a game to remove:",
        view=view,
        ephemeral=True,
    )


@client.tree.command(
    name="list-games",
    description="List the games you have saved.",
    guild=GUILD,
)
async def list_games(interaction: discord.Interaction) -> None:
    """Slash command to list all games from the caller's saved list."""
    user_id = interaction.user.id

    wheatley = cast(WheatleyClient, interaction.client)
    state = wheatley.state

    games = list_games_from_state(state, user_id)
    if games:
        formatted_list = ", ".join(games)
        message = f"Your games: {formatted_list}"
    else:
        message = "You don't have any games saved."

    await interaction.response.send_message(message, ephemeral=True)


@client.tree.command(
    name="common-games",
    description="Show games you have in common with another user.",
    guild=GUILD,
)
async def common_games(
    interaction: discord.Interaction,
    other: discord.User,
) -> None:
    """Slash command to list all common games between two users."""
    wheatley = cast(WheatleyClient, interaction.client)
    state = wheatley.state

    me_id = interaction.user.id
    common = get_common_games(state, me_id, other.id)

    if not common:
        message = f"You and {other.mention} don't have any games in common."
    else:
        common_str = ", ".join(common)
        message = f"You and {other.mention} have these common games: {common_str}."

    await interaction.response.send_message(message, ephemeral=True)


@client.tree.command(
    name="set-timezone",
    description="Set your timezone.",
    guild=GUILD,
)
async def set_timezone(interaction: discord.Interaction, tz: str) -> None:
    """Slash command to set the caller's timezone string."""
    user_id = interaction.user.id

    wheatley = cast(WheatleyClient, interaction.client)
    state = wheatley.state

    set_timezone_in_state(state, user_id, tz)
    save_state(state)

    await interaction.response.send_message(
        f'Set "{tz}" as your timezone.',
        ephemeral=True,
    )


@client.tree.command(
    name="my-timezone",
    description="Show your saved timezone.",
    guild=GUILD,
)
async def my_timezone(interaction: discord.Interaction) -> None:
    """Slash command to show the caller's saved timezone."""
    user_id = interaction.user.id

    wheatley = cast(WheatleyClient, interaction.client)
    state = wheatley.state

    tz = get_timezone_from_state(state, user_id)
    if tz:
        message = f"Your timezone: {tz}"
    else:
        message = "You don't have a timezone saved."

    await interaction.response.send_message(message, ephemeral=True)


@client.tree.command(
    name="set-availability",
    description="Set or clear your availability for a single weekday.",
    guild=GUILD,
)
async def set_availability(
    interaction: discord.Interaction,
    day: str,
    start: str | None = None,
    end: str | None = None,
) -> None:
    """Slash command to set the caller's availability for a day."""
    user_id = interaction.user.id

    wheatley = cast(WheatleyClient, interaction.client)
    state = wheatley.state

    day_key = day.lower()
    if day_key not in DAY_KEYS:
        await interaction.response.send_message(
            "Day must be one of: mon, tue, wed, thu, fri, sat, sun.",
            ephemeral=True,
        )
        return

    set_day_availability_in_state(state, user_id, day_key, start, end)
    save_state(state)

    if not start or not end:
        message = f"Cleared your availability on {day_key}."
    else:
        message = f"Set your availability on {day_key} from {start} to {end}."

    await interaction.response.send_message(message, ephemeral=True)


@client.tree.command(
    name="my-availability",
    description="Show your saved weekly availability.",
    guild=GUILD,
)
async def my_availability(interaction: discord.Interaction) -> None:
    """Slash command to show the caller's weekly availability summary."""
    wheatley = cast(WheatleyClient, interaction.client)
    state = wheatley.state

    user_id = interaction.user.id
    summary = format_user_availability(state, user_id)

    await interaction.response.send_message(summary, ephemeral=True)


if __name__ == "__main__":
    client.run(TOKEN)
