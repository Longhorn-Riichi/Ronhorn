import logging
import json
import discord
from discord.ext import commands
from discord import app_commands, Colour, Embed, Interaction
from typing import *

# InjusticeJudge imports
from .utilities import analyze_game, long_followup, parse_game
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
            injustices = await analyze_game(link)
            player_str = "player specified in the link"
        elif player.value == "All":
            try:
                injustices = await analyze_game(link, {0,1,2,3})
            except:
                injustices = await analyze_game(link, {0,1,2})
            player_str = f"all players"
        else:
            dir_map = ["East", "South", "West", "North"]
            try:
                injustices = await analyze_game(link, {dir_map.index(player.value)})
            except Exception as e:
                if player.value == "North":
                    await interaction.followup.send(content="Error: can't specify North player for a 3-player game.")
                else:
                    raise e
            player_str = f"starting {player.value} player"
        if injustices == []:
            injustices = [f"No injustices detected for the {player_str}.\n"
                           "Specify another player with the `player` option in `/injustice`.\n"
                           "Did we miss an injustice? Contribute ideas [here](https://github.com/Longhorn-Riichi/InjusticeJudge/issues/1)!"]
        as_player_string = "yourself" if player is None else "all players" if player.value == "All" else player.name
        header = f"Input: {link}\nAnalysis result for **{as_player_string}**:"
        await long_followup(interaction, injustices, header)

    @app_commands.command(name="skill", description="Display instances of pure mahjong skill in a given game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to analyze (Mahjong Soul or tenhou.net)")
    async def skill(self, interaction: Interaction, link: str):
        await interaction.response.defer()
        try:
            skills = await analyze_game(link, specified_players={0,1,2,3}, look_for={"skill"})
        except:
            skills = await analyze_game(link, specified_players={0,1,2}, look_for={"skill"})
        if skills == []:
            skills = [f"No skills detected for any player.\n"
                       "Did we miss a skill? Contribute ideas [here](https://github.com/Longhorn-Riichi/InjusticeJudge/issues/10)!"]
        header = f"Input: {link}\nSkills everyone pulled off this game:"
        await long_followup(interaction, skills, header)

class ParseLog(commands.Cog):
    @app_commands.command(name="parse", description=f"Print out the results of a game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to describe (Mahjong Soul or tenhou.net).",
                           display_hands="Display all hands, or just mangan+ hands?")
    @app_commands.choices(display_hands=[
        app_commands.Choice(name="Mangan+ hands and starting hands", value="Mangan+ hands and starting hands"),
        app_commands.Choice(name="Mangan+ hands", value="Mangan+ hands"),
        app_commands.Choice(name="All winning hands and starting hands", value="All winning hands and starting hands"),
        app_commands.Choice(name="All winning hands", value="All winning hands")])
    async def parse(self, interaction: Interaction, link: str, display_hands: Optional[app_commands.Choice[str]] = None):
        await interaction.response.defer()
        header, ret = await parse_game(link, display_hands.value if display_hands is not None else None)
        await long_followup(interaction, ret, header)

async def setup(bot: commands.Bot):
    logging.info(f"Loading cog `{ParseLog.__name__}`...")
    await bot.add_cog(ParseLog(), guilds=slash_commands_guilds)

    logging.info(f"Loading cog `{Injustice.__name__}`...")
    with open('injustice_servers.json', 'r') as file:
        injustice_servers = json.load(file)
    injustice_guilds = [discord.Object(id=id) for id in injustice_servers.values()]
    await bot.add_cog(Injustice(), guilds=injustice_guilds)
