import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from state import Database

load_dotenv()

log = logging.getLogger("hourglass")

TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

if TOKEN is None:
    raise RuntimeError("DISCORD_TOKEN is not set in .env")

EXTENSIONS = [
    "commands.games",
    "commands.availability",
    "commands.matchmaking",
    "commands.help",
]


class HourglassBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents.default())
        try:
            self.db = Database()
        except Exception:
            log.exception("Failed to initialize database")
            raise

    async def setup_hook(self) -> None:
        self.tree.on_error = self.on_app_command_error
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        if TEST_GUILD_ID:
            guild = discord.Object(id=int(TEST_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced commands to test guild %s", TEST_GUILD_ID)
        await self.tree.sync()
        log.info("Synced global commands")

    async def on_ready(self) -> None:
        user = self.user
        if user is None:
            log.warning("Logged in, but self.user is None")
            return
        log.info("Logged in as %s (ID: %s)", user, user.id)
        log.info("Number of users: %s", self.db.user_count())

    async def close(self) -> None:
        self.db.close()
        await super().close()

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError,
    ) -> None:
        log.exception("Unhandled command error", exc_info=error)
        msg = "Something went wrong. Please try again."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    HourglassBot().run(TOKEN)
