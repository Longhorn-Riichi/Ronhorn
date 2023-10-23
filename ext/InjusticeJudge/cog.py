import logging
import json
import discord
from io import BytesIO
from discord.ext import commands
from discord import app_commands, ui, ButtonStyle, Colour, Embed, Interaction
from typing import *

# InjusticeJudge imports
from .commands import _parse, _injustice, _skill
from .utilities import analyze_game, draw_graph, long_followup, parse_game, parse_link
from global_stuff import slash_commands_guilds

class Injustice(commands.Cog):
    """
    invokes a modified version of InjusticeJudge that uses our
    account manager to avoid repeated logging in-and-out. This is
    its own class so we can limit the `injustice` command to a
    given list of servers.
    """

    @app_commands.command(name="injustice", description="Display the injustices in a given game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to analyze (Mahjong Soul or tenhou.net)",
                           player="(optional) The seat to analyze the game from. Determined using the link, but defaults to East.")
    @app_commands.choices(player=[
        app_commands.Choice(name="East", value="East"),
        app_commands.Choice(name="South", value="South"),
        app_commands.Choice(name="West", value="West"),
        app_commands.Choice(name="North", value="North"),
        app_commands.Choice(name="All", value="All")])
    async def injustice(self, interaction: Interaction, link: str, player: Optional[app_commands.Choice[str]]):
        await interaction.response.defer()
        if player is None:
            player_set = set()
        elif player.value == "All":
            player_set = {0,1,2,3}
        else:
            player_set = {["East", "South", "West", "North"].index(player.value)}
        await _injustice(interaction, link, player_set)

    @app_commands.command(name="skill", description="Display instances of pure mahjong skill in a given game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to analyze (Mahjong Soul or tenhou.net)")
    async def skill(self, interaction: Interaction, link: str):
        await interaction.response.defer()
        await _skill(interaction, link, {0,1,2,3})

class ParseLog(commands.Cog):
    @app_commands.command(name="parse", description=f"Print out the results of a game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to describe (Mahjong Soul or tenhou.net).",
                           display_hands="Display all hands, or just mangan+ hands?",
                           display_graph="Display a graph summary of the game?")
    @app_commands.choices(display_hands=[
        app_commands.Choice(name="Mangan+ hands and starting hands", value="Mangan+ hands and starting hands"),
        app_commands.Choice(name="Mangan+ hands", value="Mangan+ hands"),
        app_commands.Choice(name="All winning hands and starting hands", value="All winning hands and starting hands"),
        app_commands.Choice(name="All winning hands", value="All winning hands")])
    async def parse(self, interaction: Interaction, link: str, display_hands: Optional[app_commands.Choice[str]] = None, display_graph: Optional[bool] = None):
        await interaction.response.defer()
        await _parse(interaction, link, display_hands.value if display_hands is not None else None, display_graph)

async def setup(bot: commands.Bot):
    logging.info(f"Loading cog `{ParseLog.__name__}`...")
    await bot.add_cog(ParseLog(), guilds=slash_commands_guilds)

    logging.info(f"Loading cog `{Injustice.__name__}`...")
    with open('injustice_servers.json', 'r') as file:
        injustice_servers = json.load(file)
    injustice_guilds = [discord.Object(id=id) for id in injustice_servers.values()]
    await bot.add_cog(Injustice(), guilds=injustice_guilds)
