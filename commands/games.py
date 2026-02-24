import discord
from discord import app_commands
from discord.ext import commands

from commands.helpers import autocomplete_all_games, autocomplete_user_games, get_bot, EMBED_COLOR
from state import Database


class RemoveGameSelect(discord.ui.Select):
    def __init__(self, games: list[str], owner_id: int) -> None:
        self.owner_id = owner_id
        options = [discord.SelectOption(label=game, value=game) for game in games[:25]]
        super().__init__(
            placeholder="Select a game to remove...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu isn't for you.", ephemeral=True)
            return

        bot = get_bot(interaction)
        selected_game = self.values[0]

        removed = bot.db.remove_game(self.owner_id, selected_game)
        if removed:
            message = f'Removed "{selected_game}" from your games.'
        else:
            message = f'"{selected_game}" is no longer in your games.'

        self.disabled = True
        await interaction.response.edit_message(content=message, view=self.view)


class RemoveGameView(discord.ui.View):
    def __init__(self, games: list[str], owner_id: int) -> None:
        super().__init__(timeout=60)
        self.add_item(RemoveGameSelect(games, owner_id))

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                item.disabled = True
        if self.message:
            await self.message.edit(content="This menu has expired.", view=self)


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> Database:
        return self.bot.db  # type: ignore[attr-defined]

    @app_commands.command(name="add-game", description="Add a game to your list.")
    @app_commands.describe(game="Name of the game to add")
    @app_commands.autocomplete(game=autocomplete_all_games)
    async def add_game(self, interaction: discord.Interaction, game: str) -> None:
        self.db.add_game(interaction.user.id, game)
        await interaction.response.send_message(f'Added "{game}" to your games.', ephemeral=True)

    @app_commands.command(name="remove-game", description="Remove a game from your list.")
    @app_commands.describe(game="Name of the game to remove")
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
        view = RemoveGameView(games, interaction.user.id)
        await interaction.response.send_message("Select a game to remove:", view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @app_commands.command(name="list-games", description="List the games you have saved.")
    async def list_games(self, interaction: discord.Interaction) -> None:
        games = self.db.list_games(interaction.user.id)
        if not games:
            await interaction.response.send_message("You don't have any games saved.", ephemeral=True)
            return
        embed = discord.Embed(title="Your Games", description="\n".join(f"• {g}" for g in games), color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="common-games", description="Show games you have in common with another user.")
    @app_commands.describe(other="The user to compare games with")
    async def common_games(self, interaction: discord.Interaction, other: discord.User) -> None:
        common = self.db.get_common_games(interaction.user.id, other.id)
        if not common:
            await interaction.response.send_message(f"You and {other.mention} don't have any games in common.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"Games in Common with {other.display_name}",
            description="\n".join(f"• {g}" for g in common),
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="who-plays", description="List all users who have a specific game.")
    @app_commands.describe(game="Name of the game")
    @app_commands.autocomplete(game=autocomplete_all_games)
    async def who_plays(self, interaction: discord.Interaction, game: str) -> None:
        user_ids = self.db.get_users_for_game(game)
        if not user_ids:
            await interaction.response.send_message(f'No one has "{game}" in their list.', ephemeral=True)
            return
        embed = discord.Embed(
            title=f"Who Plays {game}",
            description="\n".join(f"• <@{uid}>" for uid in user_ids),
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GamesCog(bot))
