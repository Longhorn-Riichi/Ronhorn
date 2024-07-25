import asyncio
import datetime
import gspread
import logging
import discord
from discord.ext import commands
from discord import Interaction
from typing import *

from modules.mahjongsoul.contest_manager import TournamentLogin, ContestManager
from global_stuff import assert_getenv, account_manager, registry, raw_scores, registry_lock, raw_scores_lock
from ..InjusticeJudge.command_view import CommandSuggestionView

BOT_CHANNEL_ID: int        = int(assert_getenv("bot_channel_id"))
GUILD_ID: int              = int(assert_getenv("guild_id"))

class LobbyManager(commands.Cog):
    """
    There will be multiple instances of this class, one for each lobby.
    See `setup()` below
    """
    def __init__(self, bot: commands.Bot, contest_unique_id: int, game_type: str, api: TournamentLogin):
        self.bot = bot
        self.bot_channel: Optional[discord.TextChannel] = None # fetched in `self.async_setup()`
        self.game_type = game_type
        self.manager = ContestManager(contest_unique_id, api, game_type)

    async def async_setup(self):
        self.bot_channel = await self.bot.fetch_channel(BOT_CHANNEL_ID)

    """
    =====================================================
    MAHJONG SOUL API STUFF
    =====================================================
    """

    # async def on_NotifyContestMatchingPlayer(self, _, msg):
    #     if msg.type == 1: # join
    #         self.manager.logger.info(f"Player joined matching for {self.game_type}: {msg}")
    #     if msg.type == 2: # exit (unqueued or entered game)
    #         self.manager.logger.info(f"Player exited matching for {self.game_type}: {msg}")

    # async def on_NotifyContestGameStart(self, _, msg):
    #     self.manager.logger.info(f"Match started for {self.game_type}: {msg}")
    #     seat_name = ["East", "South", "West", "North"]
    #     nicknames = " | ".join([f"{p.nickname or 'AI'} ({s})" for s, p in zip(seat_name, msg.game_info.players)])
    #     await self.bot_channel.send(f"{self.game_type} game started! Players:\n{nicknames}.")

    # async def on_NotifyContestGameEnd(self, _, msg):
    #     self.manager.logger.info(f"Match ended for {self.game_type}: {msg}")
    #     try:
    #         resp = await self.add_game_to_leaderboard(msg.game_uuid)
    #     except Exception as e:
    #         return await self.bot_channel.send(content="Error: " + str(e))

    #     link = f"https://mahjongsoul.game.yo-star.com/?paipu={msg.game_uuid}"
    #     view = CommandSuggestionView(link,
    #                                  score_graph_enabled=True,
    #                                  bonus_graph_enabled=True,
    #                                  parse_enabled=True,
    #                                  injustice_enabled=True,
    #                                  skill_enabled=True)
    #     message = await self.bot_channel.send(content=resp, suppress_embeds=True, view=view)
    #     view.set_message(message)


# need to make dummy classes so discord.py can distinguish between
# different instances (as separate cogs)
YH_NAME = assert_getenv("yh_name")
YT_NAME = assert_getenv("yt_name")
SH_NAME = assert_getenv("sh_name")
ST_NAME = assert_getenv("st_name")
class YonmaHanchanLobbyManager(LobbyManager, name=YH_NAME):
    pass
class YonmaTonpuuLobbyManager(LobbyManager, name=YT_NAME):
    pass
class SanmaHanchanLobbyManager(LobbyManager, name=SH_NAME):
    pass
class SanmaTonpuuLobbyManager(LobbyManager, name=ST_NAME):
    pass

async def setup(bot: commands.Bot):
    logging.info(f"Loading `{LobbyManager.__name__}` cogs:")
    # we can use the same login token across all managers, so we will
    api = TournamentLogin(
        mjs_uid=int(assert_getenv("mjs_uid")),
        mjs_token=assert_getenv("mjs_token"))
    cog_instances: List[LobbyManager] = []
    cog_instances.append(YonmaHanchanLobbyManager(
        bot=bot,
        contest_unique_id=int(assert_getenv("yh_contest_unique_id")),
        game_type=YH_NAME,
        api=api))
    cog_instances.append(YonmaTonpuuLobbyManager(
        bot=bot,
        contest_unique_id=int(assert_getenv("yt_contest_unique_id")),
        game_type=YT_NAME,
        api=api))
    cog_instances.append(SanmaHanchanLobbyManager(
        bot=bot,
        contest_unique_id=int(assert_getenv("sh_contest_unique_id")),
        game_type=SH_NAME,
        api=api))
    cog_instances.append(SanmaTonpuuLobbyManager(
        bot=bot,
        contest_unique_id=int(assert_getenv("st_contest_unique_id")),
        game_type=ST_NAME,
        api=api))
    for cog_instance in cog_instances:
        logging.info(f"Loading cog `{cog_instance.game_type}`.")
        asyncio.create_task(cog_instance.async_setup())
        await bot.add_cog(
            cog_instance,
            guild=discord.Object(id=GUILD_ID))
    
    logging.info(f"Finished loading `{LobbyManager.__name__}` cogs.")
