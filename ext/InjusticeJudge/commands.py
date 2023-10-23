import discord
from .utilities import analyze_game, draw_graph, long_followup, parse_game, parse_link
from discord import app_commands, ui, ButtonStyle, Colour, Embed, Interaction
from typing import *

async def _parse(interaction: Interaction, link: str, display_hands: Optional[str] = None, display_graph: Optional[bool] = None):
    header, ret = await parse_game(link, display_hands)
    await long_followup(interaction, ret, header)
    if display_graph:
        image = await draw_graph(link)
        identifier, _ = parse_link(link)
        file = discord.File(fp=image, filename=f"game-{identifier}.png")
        await interaction.channel.send(file=file)  # type: ignore[union-attr]

async def _injustice(interaction: Interaction, link: str, player_set: Set[int]):
    if len(player_set) == 0:
        player_name = "yourself"
        player_str = "the player specified in the link"
    elif len(player_set) == 1:
        player_name = ["East", "South", "West", "North"][next(iter(player_set))]
        player_str = f"the starting {player_name} player"
    else:
        player_name = "all players"
        player_str = "all players"
    injustices = await analyze_game(link, player_set)
    if injustices == []:
        injustices = [f"No injustices detected for {player_str}.\n"
                       "Specify another player with the `player` option in `/injustice`.\n"
                       "Did we miss an injustice? Contribute ideas [here](https://github.com/Longhorn-Riichi/InjusticeJudge/issues/1)!"]
    header = f"Input: {link}\nAnalysis result for **{player_name}**:"
    await long_followup(interaction, injustices, header)

async def _skill(interaction: Interaction, link: str, player_set: Set[int]):
    skills = await analyze_game(link, specified_players=player_set, look_for={"skill"})
    if skills == []:
        skills = [f"No skills detected for any player.\n"
                   "Did we miss a skill? Contribute ideas [here](https://github.com/Longhorn-Riichi/InjusticeJudge/issues/10)!"]
    header = f"Input: {link}\nSkills everyone pulled off this game:"
    await long_followup(interaction, skills, header)
