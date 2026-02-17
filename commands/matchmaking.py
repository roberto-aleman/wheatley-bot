from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from commands.helpers import get_bot, autocomplete_user_games


class MatchmakingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ready-to-play", description="Find available players who share your games.")
    @app_commands.autocomplete(game=autocomplete_user_games)
    async def ready_to_play(self, interaction: discord.Interaction, game: str | None = None) -> None:
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MatchmakingCog(bot))
