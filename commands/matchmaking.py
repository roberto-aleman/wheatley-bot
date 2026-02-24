from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from commands.availability import autocomplete_time
from commands.helpers import autocomplete_user_games, fmt_day, fmt_time, setup_hints, SUCCESS_COLOR
from state import Database, validate_time


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

    @app_commands.command(name="snooze", description="Temporarily hide from matchmaking until a time today.")
    @app_commands.describe(until="Time to snooze until (omit to check status)")
    @app_commands.autocomplete(until=autocomplete_time)
    async def snooze(self, interaction: discord.Interaction, until: str | None = None) -> None:
        if until is None:
            snooze_val = self.db.get_snooze_until(interaction.user.id)
            now_utc = datetime.now(timezone.utc)
            if snooze_val and now_utc.strftime("%Y-%m-%dT%H:%M") < snooze_val:
                # Convert stored UTC back to user's local time for display
                tz_name = self.db.get_timezone(interaction.user.id)
                if tz_name:
                    local = datetime.strptime(snooze_val, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name))
                    msg = f"You're snoozed until {fmt_time(local.strftime('%H:%M'))}."
                else:
                    msg = "You're currently snoozed."
            else:
                msg = "You're not snoozed."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        tz_name = self.db.get_timezone(interaction.user.id)
        if not tz_name:
            await interaction.response.send_message(
                "Set your timezone first with `/set-timezone`.", ephemeral=True,
            )
            return

        if not validate_time(until):
            await interaction.response.send_message(
                "Please pick a time from the suggestions.", ephemeral=True,
            )
            return

        tz = ZoneInfo(tz_name)
        local_now = datetime.now(timezone.utc).astimezone(tz)
        h, m = int(until[:2]), int(until[3:])
        snooze_local = local_now.replace(hour=h, minute=m, second=0, microsecond=0)

        if snooze_local <= local_now:
            await interaction.response.send_message(
                "That time has already passed today.", ephemeral=True,
            )
            return

        snooze_utc = snooze_local.astimezone(timezone.utc)
        self.db.set_snooze(interaction.user.id, snooze_utc)
        await interaction.response.send_message(
            f"Snoozed until {fmt_time(until)}. Use `/unsnooze` to come back early.",
            ephemeral=True,
        )

    @app_commands.command(name="unsnooze", description="Cancel your snooze and show as available again.")
    async def unsnooze(self, interaction: discord.Interaction) -> None:
        self.db.clear_snooze(interaction.user.id)
        await interaction.response.send_message("Snooze cleared! You're available again.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MatchmakingCog(bot))
