import asyncio
import discord
import gspread
import logging
from os import getenv
from discord.ext import commands
from discord import app_commands, Interaction
from typing import *
from modules.InjusticeJudge.injustice_judge import analyze_game

def assert_getenv(name: str) -> Any:
    value = getenv(name)
    assert value is not None, f"missing \"{name}\" in config.env"
    return value

BOT_CHANNEL_ID: int        = int(assert_getenv("bot_channel_id"))
GUILD_ID: int              = int(assert_getenv("guild_id"))

class InjusticeJudge(commands.Cog):

    """
    =====================================================
    SLASH COMMANDS
    =====================================================
    """

    @app_commands.command(name="injustice", description="Display the injustices in a given game.")
    @app_commands.describe(game_link="The game link to analyze (either Mahjong Soul or tenhou.net)",
                           player="(optional) The seat to analyze the game from. Automatically determined using the link, and defaults to East.")
    @app_commands.choices(player=[
        app_commands.Choice(name="East", value=0),
        app_commands.Choice(name="South", value=1),
        app_commands.Choice(name="West", value=2),
        app_commands.Choice(name="North", value=3)])
    async def injustice(self, interaction: Interaction, game_link: str, player: Optional[app_commands.Choice[int]]):
        await interaction.response.defer()
        injustices = analyze_game(game_link, player)
        if injustices == []:
            injustices = ["No injustices detected."]
        await interaction.followup.send(content=f"Analyzing {game_link}:\n" + "\n".join(injustices))


async def setup(bot: commands.Bot):
    logging.info(f"Loading extension `{InjusticeJudge.__name__}`...")
    instance = InjusticeJudge()
    await bot.add_cog(instance, guild=discord.Object(id=GUILD_ID))

