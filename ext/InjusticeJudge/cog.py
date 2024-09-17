import logging
import json
import discord
from discord.ext import commands
from discord import app_commands, ui, ButtonStyle, Colour, Embed, Interaction
from typing import *

# InjusticeJudge imports
from .commands import _parse, _injustice, _skill, _shanten
from .utilities import analyze_game, draw_graph, long_followup, parse_game, parse_link
from .command_view import CommandSuggestionView


class Injustice(commands.Cog):
    """
    invokes a modified version of InjusticeJudge that uses our
    account manager to avoid repeated logging in-and-out. This is
    its own class so we can limit the `injustice` command to a
    given list of servers.
    """

    @app_commands.command(name="injustice", description="Display the injustices in a given game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to analyze (Mahjong Soul or tenhou.net)",
                           player="(optional) The seat to analyze the game from. Determined using the link, but defaults to East.",
                           nickname="(optional) Alternatively, you may specify your in-game nickname to determine the seat to analyze.")
    @app_commands.choices(player=[
        app_commands.Choice(name="East", value="East"),
        app_commands.Choice(name="South", value="South"),
        app_commands.Choice(name="West", value="West"),
        app_commands.Choice(name="North", value="North"),
        app_commands.Choice(name="All", value="All")])
    async def injustice(self, interaction: Interaction, link: str, player: Optional[app_commands.Choice[str]], nickname: Optional[str]):
        await interaction.response.defer()
        if player is None:
            player_set = set()
        elif player.value == "All":
            player_set = {0,1,2,3}
        else:
            player_set = {["East", "South", "West", "North"].index(player.value)}
        await _injustice(interaction, link, player_set, nickname)

    @app_commands.command(name="skill", description="Display instances of pure mahjong skill in a given game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to analyze (Mahjong Soul or tenhou.net)")
    async def skill(self, interaction: Interaction, link: str):
        await interaction.response.defer()
        await _skill(interaction, link, {0,1,2,3})

    @app_commands.command(name="shanten", description="Analyze a given hand's waits and upgrades.")  # type: ignore[arg-type]
    @app_commands.describe(hand="A hand in the form 123m456p789s1234z. Must be {4,7,10,13} tiles in length.")
    async def shanten(self, interaction: Interaction, hand: str):
        await interaction.response.defer()
        await _shanten(interaction, hand)

class ParseLog(commands.Cog):
    @app_commands.command(name="parse", description=f"Print out the results of a game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to describe (Mahjong Soul or tenhou.net).",
                           display_hands="Display all hands, or just mangan+ hands?",
                           display_graph="Display a graph summary of the game?")
    @app_commands.choices(display_hands=[
        app_commands.Choice(name="Mangan+ hands and starting hands", value="Mangan+ hands and starting hands"),
        app_commands.Choice(name="Mangan+ hands", value="Mangan+ hands"),
        app_commands.Choice(name="All winning hands and starting hands", value="All winning hands and starting hands"),
        app_commands.Choice(name="All winning hands", value="All winning hands")],
                          display_graph=[
        app_commands.Choice(name="Scores only", value="Scores only"),
        app_commands.Choice(name="Scores with placement bonus", value="Scores with placement bonus")])
    async def parse(self, interaction: Interaction, link: str, display_hands: Optional[app_commands.Choice[str]] = None, display_graph: Optional[app_commands.Choice[str]] = None):
        await interaction.response.defer()
        await _parse(interaction,
                     link,
                     display_hands.value if display_hands is not None else None,
                     display_graph.value if display_graph is not None else None)

class ParseLogWithButtons(commands.Cog):
    @app_commands.command(name="parse", description=f"Print out the results of a game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to describe (Mahjong Soul or tenhou.net).",
                           display_hands="Display all hands, or just mangan+ hands?",
                           display_graph="Display a graph summary of the game?")
    @app_commands.choices(display_hands=[
        app_commands.Choice(name="Mangan+ hands and starting hands", value="Mangan+ hands and starting hands"),
        app_commands.Choice(name="Mangan+ hands", value="Mangan+ hands"),
        app_commands.Choice(name="All winning hands and starting hands", value="All winning hands and starting hands"),
        app_commands.Choice(name="All winning hands", value="All winning hands")],
                          display_graph=[
        app_commands.Choice(name="Scores only", value="Scores only"),
        app_commands.Choice(name="Scores with placement bonus", value="Scores with placement bonus")])
    async def parse(self, interaction: Interaction, link: str, display_hands: Optional[app_commands.Choice[str]] = None, display_graph: Optional[app_commands.Choice[str]] = None):
        await interaction.response.defer()
        score_graph_shown = display_graph is not None and display_graph.value == "Scores only"
        bonus_graph_shown = display_graph is not None and display_graph.value == "Scores with placement bonus"
        view = CommandSuggestionView(link,
                                     score_graph_enabled=not score_graph_shown,
                                     bonus_graph_enabled=not bonus_graph_shown,
                                     parse_enabled=False,
                                     injustice_enabled=True,
                                     skill_enabled=True)
        last_message = await _parse(interaction,
                                    link,
                                    display_hands.value if display_hands is not None else None,
                                    display_graph.value if display_graph is not None else None,
                                    view)
        view.set_message(last_message)

async def setup(bot: commands.Bot):
    logging.info(f"Loading cog `{Injustice.__name__}`...")
    with open('injustice_servers.json', 'r') as file:
        injustice_servers = json.load(file)
    injustice_guilds = [discord.Object(id=id) for id in injustice_servers.values()]
    await bot.add_cog(Injustice(), guilds=injustice_guilds)

    logging.info(f"Loading cog `{ParseLog.__name__}`...")
    with open('slash_commands_servers.json', 'r') as file:
        slash_commands_servers = json.load(file)
    slash_commands_guilds = [discord.Object(id=id) for id in slash_commands_servers.values()]
    await bot.add_cog(ParseLogWithButtons(), guilds=list(set(slash_commands_guilds) & set(injustice_guilds)))
    await bot.add_cog(ParseLog(), guilds=list(set(slash_commands_guilds) - set(injustice_guilds)))
