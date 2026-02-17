from typing import cast

import discord
from discord import app_commands

from commands.helpers import BotClient, get_bot

client: discord.Client
GUILD: discord.Object


def setup(c: discord.Client, guild: discord.Object) -> None:
    global client, GUILD
    client = c
    GUILD = guild
    _register_commands()


async def _autocomplete_user_games(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Suggest from the invoker's own game list."""
    bot = get_bot(interaction)
    games = bot.db.list_games(interaction.user.id)
    lower = current.lower()
    return [
        app_commands.Choice(name=g, value=g)
        for g in games if lower in g.lower()
    ][:25]


async def _autocomplete_all_games(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Suggest from all known games across all users."""
    bot = get_bot(interaction)
    games = bot.db.all_game_names()
    lower = current.lower()
    return [
        app_commands.Choice(name=g, value=g)
        for g in games if lower in g.lower()
    ][:25]


class RemoveGameSelect(discord.ui.Select):
    def __init__(self, games: list[str]) -> None:
        options = [discord.SelectOption(label=game, value=game) for game in games[:25]]
        super().__init__(
            placeholder="Select a game to remove...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = get_bot(interaction)
        selected_game = self.values[0]

        removed = bot.db.remove_game(interaction.user.id, selected_game)
        if removed:
            message = f'Removed "{selected_game}" from your games.'
        else:
            message = f'"{selected_game}" is no longer in your games.'

        self.disabled = True
        await interaction.response.edit_message(content=message, view=self.view)


class RemoveGameView(discord.ui.View):
    def __init__(self, games: list[str]) -> None:
        super().__init__(timeout=60)
        self.add_item(RemoveGameSelect(games))


def _register_commands() -> None:
    tree = cast(BotClient, client).tree

    @tree.command(name="add-game", description="Add a game to your list.", guild=GUILD)
    @app_commands.autocomplete(game=_autocomplete_all_games)
    async def add_game(interaction: discord.Interaction, game: str) -> None:
        bot = get_bot(interaction)
        bot.db.add_game(interaction.user.id, game)
        await interaction.response.send_message(f'Added "{game}" to your games.', ephemeral=True)

    @tree.command(name="remove-game", description="Remove a game from your list.", guild=GUILD)
    @app_commands.autocomplete(game=_autocomplete_user_games)
    async def remove_game(interaction: discord.Interaction, game: str) -> None:
        bot = get_bot(interaction)
        removed = bot.db.remove_game(interaction.user.id, game)
        if removed:
            message = f'Removed "{game}" from your games.'
        else:
            message = f'"{game}" was not found in your games.'
        await interaction.response.send_message(message, ephemeral=True)

    @tree.command(name="remove-game-menu", description="Remove a game from your list using a dropdown menu.", guild=GUILD)
    async def remove_game_menu(interaction: discord.Interaction) -> None:
        bot = get_bot(interaction)
        games = bot.db.list_games(interaction.user.id)
        if not games:
            await interaction.response.send_message("You don't have any games saved.", ephemeral=True)
            return
        await interaction.response.send_message("Select a game to remove:", view=RemoveGameView(games), ephemeral=True)

    @tree.command(name="list-games", description="List the games you have saved.", guild=GUILD)
    async def list_games(interaction: discord.Interaction) -> None:
        bot = get_bot(interaction)
        games = bot.db.list_games(interaction.user.id)
        if not games:
            await interaction.response.send_message("You don't have any games saved.", ephemeral=True)
            return
        embed = discord.Embed(title="Your Games", description="\n".join(f"• {g}" for g in games), color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="common-games", description="Show games you have in common with another user.", guild=GUILD)
    async def common_games(interaction: discord.Interaction, other: discord.User) -> None:
        bot = get_bot(interaction)
        common = bot.db.get_common_games(interaction.user.id, other.id)
        if not common:
            await interaction.response.send_message(f"You and {other.mention} don't have any games in common.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"Games in Common with {other.display_name}",
            description="\n".join(f"• {g}" for g in common),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
