import asyncio
import datetime
import gspread
import logging
import discord
from discord.ext import commands
from discord import Interaction
from typing import *

from modules.mahjongsoul.contest_manager import ContestManager
from global_stuff import assert_getenv, account_manager, registry, raw_scores, registry_lock, raw_scores_lock

BOT_CHANNEL_ID: int        = int(assert_getenv("bot_channel_id"))
GUILD_ID: int              = int(assert_getenv("guild_id"))

DISCORD_NAME_COL: int      = 2
MJS_NICKNAME_COL: int      = 4
MJS_ACCOUNT_ID_COL: int    = 6

class LobbyManager(commands.Cog):
    """
    There will be multiple instances of this class, one for each lobby.
    See `setup()` below
    """
    def __init__(self, bot: commands.Bot, contest_unique_id: int, mjs_username: str, mjs_password: str, game_type: str):
        self.bot = bot
        self.bot_channel: Optional[int] = None # fetched in `self.async_setup()`
        self.game_type = game_type
        self.manager = ContestManager(
            contest_unique_id,
            mjs_username,
            mjs_password,
            False,
            game_type)

    async def async_setup(self):
        """
        to be called in `setup()`, before any methods can be invoked
        1. fetch the channel specified in JSON
        2. connect and login to Mahjong Soul...
        3. subscribe to relevant events
        """
        
        # note that `bot.get_channel()` doesn't work because at this point
        # the bot has not cached the channel yet...
        self.bot_channel = await self.bot.fetch_channel(BOT_CHANNEL_ID)
        await self.manager.connect_and_login()
        await self.manager.subscribe("NotifyContestGameStart", self.on_NotifyContestGameStart)
        await self.manager.subscribe("NotifyContestGameEnd", self.on_NotifyContestGameEnd)

    """
    =====================================================
    SLASH COMMAND INNER FUNCTIONS
    =====================================================
    """

    async def terminate_any_game(self, interaction: Interaction, nickname: str):
        await interaction.response.defer()
        message = await self.manager.terminate_game(nickname)
        await interaction.followup.send(content=message)

    async def terminate_own_game(self, interaction: Interaction):
        await interaction.response.defer()
        mjs_nickname = self.get_member_mjs_nickname(interaction.user.name)
        if mjs_nickname is None:
            await interaction.followup.send(content="You are not a registered player; there shouldn't be an ongoing game for you.")
            return
        message = await self.manager.terminate_game(mjs_nickname)
        await interaction.followup.send(content=message)
    
    async def pause_any_game(self, interaction: Interaction, nickname: str):
        await interaction.response.defer()
        message = await self.manager.pause_game(nickname)
        await interaction.followup.send(content=message)

    async def pause_own_game(self, interaction: Interaction):
        await interaction.response.defer()
        mjs_nickname = self.get_member_mjs_nickname(interaction.user.name)
        if mjs_nickname is None:
            await interaction.followup.send(content="You are not a registered player; there shouldn't be an ongoing game for you.")
            return
        message = await self.manager.pause_game(mjs_nickname)
        await interaction.followup.send(content=message)
    
    async def unpause_any_game(self, interaction: Interaction, nickname: str):
        await interaction.response.defer()
        message = await self.manager.unpause_game(nickname)
        await interaction.followup.send(content=message)

    async def unpause_own_game(self, interaction: Interaction):
        await interaction.response.defer()
        mjs_nickname = self.get_member_mjs_nickname(interaction.user.name)
        if mjs_nickname is None:
            await interaction.followup.send(content="You are not a registered player; there shouldn't be an ongoing game for you.")
            return
        message = await self.manager.unpause_game(mjs_nickname)
        await interaction.followup.send(content=message)

    async def add_game_to_leaderboard(self, uuid):
        record_list = await account_manager.get_game_results([uuid])
        if len(record_list) == 0:
            raise Exception("A game concluded without a record (possibly due to being terminated early).")

        record = record_list[0]

        # TODO: deal with ordering the scores; currently assumes the scores are ordered by
        #       total_point (adopt the algorithm of `enter_scores` command)
        seat_player_dict = {a.seat: (a.account_id, a.nickname) for a in record.accounts}

        player_scores_rendered = ["Game concluded! Results:"] # to be newline-separated

        timestamp = str(datetime.datetime.now()).split(".")[0]
        raw_scores_row = [timestamp, self.game_type, "no"] # a list of values for a "Raw Scores" row
        not_registered = [] # list of unregistered players in game, if any

        for p in record.result.players:
            player_account_id, player_nickname = seat_player_dict.get(p.seat, (0, "AI"))

            if player_account_id == 0:
                player_scores_rendered.append("ERROR: a game ended with AI players. How???")
            
            raw_score = p.part_point_1
            async with registry_lock:
                found_cell: gspread.cell.Cell = registry.find(str(player_account_id), in_column=MJS_ACCOUNT_ID_COL)
                if found_cell is not None:
                    discord_name = registry.cell(found_cell.row, DISCORD_NAME_COL).value
                    raw_scores_row.extend((discord_name, raw_score))
                else: # The player was not registered?
                    not_registered.append(player_nickname)
                    raw_scores_row.extend(("Unregistered player", raw_score))
            
            player_scores_rendered.append(
                f"{player_nickname}: {p.part_point_1} ({(p.total_point/1000):+})")

        for player_nickname in not_registered:
            player_scores_rendered.append(f"WARNING: Mahjong Soul player {player_nickname} is not registered! Modify spreadsheet after registration!")

        async with raw_scores_lock:
            raw_scores.append_row(raw_scores_row)

        return '\n'.join(player_scores_rendered)
    
    """
    =====================================================
    MAHJONG SOUL API STUFF
    =====================================================
    """

    async def on_NotifyContestGameStart(self, _, msg):
        nicknames = " | ".join([p.nickname or "AI" for p in msg.game_info.players])
        await self.bot_channel.send(f"{self.game_type} game started! Players:\n{nicknames}.")

    async def on_NotifyContestGameEnd(self, _, msg):
        try:
            resp = self.add_game_to_leaderboard(msg.game_uuid)
        except Exception as e:
            return await self.bot_channel.send(content="Error: " + str(e))
        await self.bot_channel.send(content=resp)

    """
    =====================================================
    GOOGLE SHEETS HELPER FUNCTIONS
    =====================================================
    """

    def get_member_mjs_nickname(self, discord_name: str) -> str | None:
        found_cell: gspread.cell.Cell = registry.find(discord_name, in_column=DISCORD_NAME_COL)
        if found_cell is None:
            # No player with given Discord name found; returning None
            return None
        
        return registry.cell(found_cell.row, MJS_NICKNAME_COL).value

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
    cog_instances: List[LobbyManager] = []
    cog_instances.append(YonmaHanchanLobbyManager(
        bot=bot,
        contest_unique_id=int(assert_getenv("yh_contest_unique_id")),
        mjs_username=assert_getenv("mjs_yh_username"),
        mjs_password=assert_getenv("mjs_yh_password"),
        game_type=YH_NAME))
    cog_instances.append(YonmaTonpuuLobbyManager(
        bot=bot,
        contest_unique_id=int(assert_getenv("yt_contest_unique_id")),
        mjs_username=assert_getenv("mjs_yt_username"),
        mjs_password=assert_getenv("mjs_yt_password"),
        game_type=YT_NAME))
    cog_instances.append(SanmaHanchanLobbyManager(
        bot=bot,
        contest_unique_id=int(assert_getenv("sh_contest_unique_id")),
        mjs_username=assert_getenv("mjs_sh_username"),
        mjs_password=assert_getenv("mjs_sh_password"),
        game_type=SH_NAME))
    cog_instances.append(SanmaTonpuuLobbyManager(
        bot=bot,
        contest_unique_id=int(assert_getenv("st_contest_unique_id")),
        mjs_username=assert_getenv("mjs_st_username"),
        mjs_password=assert_getenv("mjs_st_password"),
        game_type=ST_NAME))
    
    for cog_instance in cog_instances:
        logging.info(f"Loading cog `{cog_instance.game_type}`.")
        asyncio.create_task(cog_instance.async_setup())
        await bot.add_cog(
            cog_instance,
            guild=discord.Object(id=GUILD_ID))
