from datetime import datetime, timezone
from typing import cast

import discord
from discord import app_commands

from commands.helpers import BotClient, get_bot

client: discord.Client
GUILD: discord.Object


def setup(c: discord.Client, guild: discord.Object) -> None:
    global client, GUILD
    client = c
    GUILD = guild
    _register_commands()


async def _autocomplete_user_games(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    bot = get_bot(interaction)
    games = bot.db.list_games(interaction.user.id)
    lower = current.lower()
    return [
        app_commands.Choice(name=g, value=g)
        for g in games if lower in g.lower()
    ][:25]


def _register_commands() -> None:
    tree = cast(BotClient, client).tree

    @tree.command(name="ready-to-play", description="Find available players who share your games.", guild=GUILD)
    @app_commands.autocomplete(game=_autocomplete_user_games)
    async def ready_to_play(interaction: discord.Interaction, game: str | None = None) -> None:
        bot = get_bot(interaction)
        now_utc = datetime.now(timezone.utc)

        matches = bot.db.find_ready_players(interaction.user.id, now_utc, game_filter=game)

        if not matches:
            if game:
                message = f'No one is available right now for "{game}".'
            else:
                message = "No one with matching games is available right now."
            await interaction.response.send_message(message, ephemeral=True)
            return

        lines: list[str] = []
        for user_id, common in matches:
            games_str = ", ".join(common)
            lines.append(f"<@{user_id}> — {games_str}")

        embed = discord.Embed(
            title="Players Available Now",
            description="\n".join(lines),
            color=0x57F287,
        )
        await interaction.response.send_message(embed=embed)
