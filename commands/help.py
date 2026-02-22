import discord
from discord import app_commands
from discord.ext import commands

from commands.helpers import EMBED_COLOR


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="hourglass", description="Show all available commands.")
    async def hourglass(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Hourglass Commands",
            description="Coordinate gaming sessions with your friends.",
            color=EMBED_COLOR,
        )
        embed.add_field(
            name="Games",
            value=(
                "`/add-game` — Add a game to your list\n"
                "`/remove-game` — Remove a game by name\n"
                "`/remove-game-menu` — Remove a game with a dropdown\n"
                "`/list-games` — Show your saved games\n"
                "`/common-games` — Games you share with another user\n"
                "`/who-plays` — See who has a specific game"
            ),
            inline=False,
        )
        embed.add_field(
            name="Availability",
            value=(
                "`/set-timezone` — Set your timezone\n"
                "`/my-timezone` — Show your timezone\n"
                "`/set-availability` — Add a time slot for a weekday\n"
                "`/clear-availability` — Clear slots for a weekday\n"
                "`/my-availability` — Show your weekly schedule"
            ),
            inline=False,
        )
        embed.add_field(
            name="Matchmaking",
            value=(
                "`/ready-to-play` — Find who's available now and shares your games\n"
                "`/next-available` — See when a user is next available\n"
                "`/snooze` — Temporarily hide from matchmaking\n"
                "`/unsnooze` — Cancel your snooze early"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
