from typing import cast, Protocol

import discord
from discord import app_commands

from state import Database


class BotClient(Protocol):
    db: Database
    tree: app_commands.CommandTree


def get_bot(interaction: discord.Interaction) -> BotClient:
    return cast(BotClient, interaction.client)
