import discord
from .utilities import analyze_game, draw_graph, long_followup, parse_game, parse_link
from discord import app_commands, ui, ButtonStyle, Colour, Embed, Interaction
from global_stuff import account_manager, logger
from typing import *

async def _parse(interaction: Interaction, link: str, display_hands: Optional[str] = None, display_graph: Optional[bool] = None) -> None:
    logger.info("Running parse...")
    header, ret = await parse_game(link, display_hands)
    logger.info("  game parsed")
    await long_followup(interaction, ret, header)
    logger.info("  response sent")
    if display_graph:
        image = await draw_graph(link)
        logger.info("  graph drawn")
        identifier, _ = parse_link(link)
        file = discord.File(fp=image, filename=f"game-{identifier}.png")
        await interaction.channel.send(file=file)  # type: ignore[union-attr]
        logger.info("  graph sent")

async def _injustice(interaction: Interaction, link: str, player_set: Set[int], nickname: Optional[str] = None) -> None:
    logger.info("Running injustice")
    injustices, specified_players = await analyze_game(link, player_set, nickname=nickname)
    logger.info("  game parsed")
    if len(specified_players) == 0 and len(link) == 20: # riichi city link with no specified players
        # return await interaction.followup.send(content="For riichi city injustices, you must specify the player seat (will fix this later)")
        specified_players = {0} # default to East
    if len(specified_players) == 0:
        player_name = "yourself"
        player_str = "the player specified in the link"
    elif len(specified_players) == 1:
        player_name = ["East", "South", "West", "North"][next(iter(specified_players))]
        player_str = f"the starting {player_name} player"
    else:
        player_name = "all players"
        player_str = "all players"
    if injustices == []:
        injustices = [f"No injustices detected for {player_str}.\n"
                       "Specify another player with the `player` option in `/injustice`.\n"
                       "Did we miss an injustice? Contribute ideas [here](https://github.com/Longhorn-Riichi/InjusticeJudge/issues/1)!"]
    header = f"Input: {link}\nAnalysis result for **{player_name}**:"
    await long_followup(interaction, injustices, header)
    logger.info("  response sent")

async def _skill(interaction: Interaction, link: str, player_set: Set[int]) -> None:
    logger.info("Running skill")
    skills, _ = await analyze_game(link, specified_players=player_set, look_for={"skill"})
    logger.info("  game parsed")
    if skills == []:
        skills = [f"No skills detected for any player.\n"
                   "Did we miss a skill? Contribute ideas [here](https://github.com/Longhorn-Riichi/InjusticeJudge/issues/10)!"]
    header = f"Input: {link}\nSkills everyone pulled off this game:"
    await long_followup(interaction, skills, header)
    logger.info("  response sent")
