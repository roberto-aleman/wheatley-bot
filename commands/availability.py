from typing import cast

import discord
from discord import app_commands

from commands.helpers import BotClient, get_bot
from state import DAY_KEYS, validate_time

US_TIMEZONES = [
    app_commands.Choice(name="Eastern", value="US/Eastern"),
    app_commands.Choice(name="Central", value="US/Central"),
    app_commands.Choice(name="Mountain", value="US/Mountain"),
    app_commands.Choice(name="Pacific", value="US/Pacific"),
    app_commands.Choice(name="Alaska", value="US/Alaska"),
    app_commands.Choice(name="Hawaii", value="US/Hawaii"),
]

client: discord.Client
GUILD: discord.Object


def setup(c: discord.Client, guild: discord.Object) -> None:
    global client, GUILD
    client = c
    GUILD = guild
    _register_commands()


def _register_commands() -> None:
    tree = cast(BotClient, client).tree

    @tree.command(name="set-timezone", description="Set your timezone.", guild=GUILD)
    @app_commands.choices(tz=US_TIMEZONES)
    async def set_timezone(interaction: discord.Interaction, tz: app_commands.Choice[str]) -> None:
        bot = get_bot(interaction)
        bot.db.set_timezone(interaction.user.id, tz.value)
        await interaction.response.send_message(f'Set your timezone to {tz.name} ({tz.value}).', ephemeral=True)

    @tree.command(name="my-timezone", description="Show your saved timezone.", guild=GUILD)
    async def my_timezone(interaction: discord.Interaction) -> None:
        bot = get_bot(interaction)
        tz = bot.db.get_timezone(interaction.user.id)
        if tz:
            message = f"Your timezone: {tz}"
        else:
            message = "You don't have a timezone saved."
        await interaction.response.send_message(message, ephemeral=True)

    @tree.command(name="set-availability", description="Add a time slot for a weekday.", guild=GUILD)
    @app_commands.choices(day=[app_commands.Choice(name=d, value=d) for d in DAY_KEYS])
    async def set_availability(
        interaction: discord.Interaction,
        day: app_commands.Choice[str],
        start: str,
        end: str,
    ) -> None:
        bot = get_bot(interaction)

        if not validate_time(start) or not validate_time(end):
            await interaction.response.send_message(
                "Times must be in HH:MM format (e.g. 18:00).", ephemeral=True,
            )
            return

        bot.db.add_day_availability(interaction.user.id, day.value, start, end)
        await interaction.response.send_message(
            f"Added {start}-{end} on {day.value}.", ephemeral=True,
        )

    @tree.command(name="clear-availability", description="Clear all time slots for a weekday.", guild=GUILD)
    @app_commands.choices(day=[app_commands.Choice(name=d, value=d) for d in DAY_KEYS])
    async def clear_availability(
        interaction: discord.Interaction,
        day: app_commands.Choice[str],
    ) -> None:
        bot = get_bot(interaction)
        bot.db.clear_day_availability(interaction.user.id, day.value)
        await interaction.response.send_message(
            f"Cleared all availability on {day.value}.", ephemeral=True,
        )

    @tree.command(name="my-availability", description="Show your saved weekly availability.", guild=GUILD)
    async def my_availability(interaction: discord.Interaction) -> None:
        bot = get_bot(interaction)
        summary = bot.db.format_availability(interaction.user.id)
        await interaction.response.send_message(summary, ephemeral=True)
