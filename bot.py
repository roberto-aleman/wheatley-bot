import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from state import Database

load_dotenv()

log = logging.getLogger("wheatley")

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if TOKEN is None:
    raise RuntimeError("DISCORD_TOKEN is not set in .env")

if GUILD_ID is None:
    raise RuntimeError("GUILD_ID is not set in .env")

GUILD = discord.Object(id=int(GUILD_ID))

EXTENSIONS = [
    "commands.games",
    "commands.availability",
    "commands.matchmaking",
    "commands.help",
]


class WheatleyBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        try:
            self.db = Database()
        except Exception:
            log.exception("Failed to initialize database")
            raise

    async def setup_hook(self) -> None:
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        self.tree.copy_global_to(guild=GUILD)
        await self.tree.sync(guild=GUILD)
        log.info("Synced commands to guild %s", GUILD_ID)

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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    WheatleyBot().run(TOKEN)
