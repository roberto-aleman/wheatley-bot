import discord
from discord import app_commands
from discord.ext import commands

from commands.helpers import get_bot, autocomplete_all_games, autocomplete_user_games


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


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @app_commands.command(name="add-game", description="Add a game to your list.")
    @app_commands.autocomplete(game=autocomplete_all_games)
    async def add_game(self, interaction: discord.Interaction, game: str) -> None:
        self.db.add_game(interaction.user.id, game)
        await interaction.response.send_message(f'Added "{game}" to your games.', ephemeral=True)

    @app_commands.command(name="remove-game", description="Remove a game from your list.")
    @app_commands.autocomplete(game=autocomplete_user_games)
    async def remove_game(self, interaction: discord.Interaction, game: str) -> None:
        removed = self.db.remove_game(interaction.user.id, game)
        if removed:
            message = f'Removed "{game}" from your games.'
        else:
            message = f'"{game}" was not found in your games.'
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="remove-game-menu", description="Remove a game from your list using a dropdown menu.")
    async def remove_game_menu(self, interaction: discord.Interaction) -> None:
        games = self.db.list_games(interaction.user.id)
        if not games:
            await interaction.response.send_message("You don't have any games saved.", ephemeral=True)
            return
        await interaction.response.send_message("Select a game to remove:", view=RemoveGameView(games), ephemeral=True)

    @app_commands.command(name="list-games", description="List the games you have saved.")
    async def list_games(self, interaction: discord.Interaction) -> None:
        games = self.db.list_games(interaction.user.id)
        if not games:
            await interaction.response.send_message("You don't have any games saved.", ephemeral=True)
            return
        embed = discord.Embed(title="Your Games", description="\n".join(f"• {g}" for g in games), color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="common-games", description="Show games you have in common with another user.")
    async def common_games(self, interaction: discord.Interaction, other: discord.User) -> None:
        common = self.db.get_common_games(interaction.user.id, other.id)
        if not common:
            await interaction.response.send_message(f"You and {other.mention} don't have any games in common.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"Games in Common with {other.display_name}",
            description="\n".join(f"• {g}" for g in common),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GamesCog(bot))
