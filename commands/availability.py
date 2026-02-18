import discord
from discord import app_commands
from discord.ext import commands

from commands.helpers import EMBED_COLOR
from state import DAY_KEYS, Database, validate_time

US_TIMEZONES = [
    app_commands.Choice(name="Eastern", value="US/Eastern"),
    app_commands.Choice(name="Central", value="US/Central"),
    app_commands.Choice(name="Mountain", value="US/Mountain"),
    app_commands.Choice(name="Pacific", value="US/Pacific"),
    app_commands.Choice(name="Alaska", value="US/Alaska"),
    app_commands.Choice(name="Hawaii", value="US/Hawaii"),
]

DAY_CHOICES = [app_commands.Choice(name=d, value=d) for d in DAY_KEYS]


class AvailabilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> Database:
        return self.bot.db  # type: ignore[attr-defined]

    @app_commands.command(name="set-timezone", description="Set your timezone.")
    @app_commands.choices(tz=US_TIMEZONES)
    async def set_timezone(self, interaction: discord.Interaction, tz: app_commands.Choice[str]) -> None:
        self.db.set_timezone(interaction.user.id, tz.value)
        await interaction.response.send_message(f'Set your timezone to {tz.name} ({tz.value}).', ephemeral=True)

    @app_commands.command(name="my-timezone", description="Show your saved timezone.")
    async def my_timezone(self, interaction: discord.Interaction) -> None:
        tz = self.db.get_timezone(interaction.user.id)
        if tz:
            message = f"Your timezone: {tz}"
        else:
            message = "You don't have a timezone saved."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="set-availability", description="Add a time slot for a weekday.")
    @app_commands.choices(day=DAY_CHOICES)
    async def set_availability(
        self, interaction: discord.Interaction,
        day: app_commands.Choice[str],
        start: str,
        end: str,
    ) -> None:
        if not validate_time(start) or not validate_time(end):
            await interaction.response.send_message(
                "Times must be in HH:MM format (e.g. 18:00).", ephemeral=True,
            )
            return

        self.db.add_day_availability(interaction.user.id, day.value, start, end)
        await interaction.response.send_message(
            f"Added {start}-{end} on {day.value}.", ephemeral=True,
        )

    @app_commands.command(name="clear-availability", description="Clear all time slots for a weekday.")
    @app_commands.choices(day=DAY_CHOICES)
    async def clear_availability(
        self, interaction: discord.Interaction,
        day: app_commands.Choice[str],
    ) -> None:
        self.db.clear_day_availability(interaction.user.id, day.value)
        await interaction.response.send_message(
            f"Cleared all availability on {day.value}.", ephemeral=True,
        )

    @app_commands.command(name="my-availability", description="Show your saved weekly availability.")
    async def my_availability(self, interaction: discord.Interaction) -> None:
        uid = interaction.user.id
        tz = self.db.get_timezone(uid)
        availability = self.db.get_availability(uid)

        embed = discord.Embed(title="Your Availability", color=EMBED_COLOR)
        embed.add_field(name="Timezone", value=tz or "not set", inline=False)

        for day in DAY_KEYS:
            slots = availability[day]
            if slots:
                value = ", ".join(f"{s['start']}-{s['end']}" for s in slots)
            else:
                value = "none"
            embed.add_field(name=day, value=value, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AvailabilityCog(bot))
