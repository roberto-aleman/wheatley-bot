import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from state import Database

load_dotenv()

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
]


class WheatleyBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.db = Database()

    async def setup_hook(self) -> None:
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        self.tree.copy_global_to(guild=GUILD)
        await self.tree.sync(guild=GUILD)
        print(f"Synced commands to guild {GUILD_ID}")

    async def on_ready(self) -> None:
        user = self.user
        if user is None:
            print("Logged in, but self.user is None")
            return
        print(f"Logged in as {user} (ID: {user.id})")
        print(f"Number of users: {self.db.user_count()}")
        print("------")

    async def close(self) -> None:
        self.db.close()
        await super().close()


if __name__ == "__main__":
    WheatleyBot().run(TOKEN)
