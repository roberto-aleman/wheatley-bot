from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from commands.helpers import autocomplete_user_games, fmt_day, fmt_time, setup_hints, SUCCESS_COLOR
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
            hints = setup_hints(self.db, interaction.user.id)
            if hints:
                message = "You're not fully set up yet:\n" + "\n".join(f"• {h}" for h in hints)
            elif game:
                message = f'No one is available right now for "{game}". Try `/next-available` to see when someone will be.'
            else:
                message = "No one with matching games is available right now. Try `/next-available` to see when someone will be."
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
            if target.id == interaction.user.id:
                hints = setup_hints(self.db, target.id)
                if hints:
                    message = "You're not fully set up yet:\n" + "\n".join(f"• {h}" for h in hints)
                else:
                    message = "You have no upcoming availability set."
            else:
                message = f"{target.mention} has no upcoming availability set."
            await interaction.response.send_message(message, ephemeral=True)
            return

        day, start, end = result
        await interaction.response.send_message(
            f"{target.mention} is next available **{fmt_day(day)} {fmt_time(start)}–{fmt_time(end)}** (their local time).",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MatchmakingCog(bot))
