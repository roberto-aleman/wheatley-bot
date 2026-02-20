from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from commands.helpers import autocomplete_user_games, SUCCESS_COLOR
from state import Database


class MatchmakingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> Database:
        return self.bot.db  # type: ignore[attr-defined]

    @app_commands.command(name="ready-to-play", description="Find available players who share your games.")
    @app_commands.describe(game="Filter results to a specific game")
    @app_commands.autocomplete(game=autocomplete_user_games)
    async def ready_to_play(self, interaction: discord.Interaction, game: str | None = None) -> None:
        now_utc = datetime.now(timezone.utc)

        matches = self.db.find_ready_players(interaction.user.id, now_utc, game_filter=game)

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
            color=SUCCESS_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="next-available", description="Show when a user is next available.")
    @app_commands.describe(user="The user to check (defaults to yourself)")
    async def next_available(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        target = user or interaction.user
        now_utc = datetime.now(timezone.utc)
        result = self.db.next_available(target.id, now_utc)

        if not result:
            await interaction.response.send_message(
                f"{target.mention} has no upcoming availability set.", ephemeral=True,
            )
            return

        day, start, end = result
        await interaction.response.send_message(
            f"{target.mention} is next available **{day} {start}–{end}** (their local time).",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MatchmakingCog(bot))
