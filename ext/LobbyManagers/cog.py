import asyncio
import datetime
import gspread
import logging
import discord
from discord.ext import commands, tasks
from discord import Interaction
from typing import *

from modules.mahjongsoul.contest_manager import TournamentLogin, ContestManager
from global_stuff import assert_getenv, account_manager, registry, raw_scores, registry_lock, raw_scores_lock
from ..InjusticeJudge.command_view import CommandSuggestionView

BOT_CHANNEL_ID: int        = int(assert_getenv("bot_channel_id"))
GUILD_ID: int              = int(assert_getenv("guild_id"))

DISCORD_NAME_COL = 2
MJS_NICKNAME_COL = 4
MJS_ACCOUNT_ID_COL = 6

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

    async def async_setup(self) -> None:
        self.bot_channel = await self.bot.fetch_channel(BOT_CHANNEL_ID)  # type: ignore[assignment]
        self.participants: Set[str] = set()
        self.games: Set[str] = set()
        self.poll_participants.start()
        self.poll_games.start()

    # replaces on_NotifyContestMatchingPlayer
    @tasks.loop(seconds=30, reconnect=True)
    async def poll_participants(self) -> None:
        participants = {player["nickname"] for player in self.manager.poll_participants()}
        for name in participants - self.participants:
            self.manager.logger.info(f"Player {name} joined matching for {self.game_type}.")
        for name in self.participants - participants:
            self.manager.logger.info(f"Player {name} exited matching for {self.game_type}.")
        self.participants = participants
    # ensure bot is ready before poll_participants is called
    @poll_participants.before_loop
    async def poll_participants_ready(self):
        await self.bot.wait_until_ready()
    @poll_participants.error
    async def poll_participants_error(self, error):
        logging.error(f"Error in polling participants: {error}")

    # replaces on_NotifyContestGameStart, on_NotifyContestGameEnd
    @tasks.loop(seconds=30, reconnect=True)
    async def poll_games(self) -> None:
        game_details = {game["game_uuid"]: game for game in self.manager.poll_match_list()}
        games = set(game_details.keys())
        for uuid in games - self.games:
            self.manager.logger.info(f"Match started for {self.game_type}: {uuid}")
            players = game_details[uuid]["players"]
            seat_name = ["East", "South", "West", "North"]
            nicknames = " | ".join([f"{p['nickname'] if 'nickname' in p else 'AI'} ({s})" for s, p in zip(seat_name, players)])
            await self.bot_channel.send(f"{self.game_type} game started! Players:\n{nicknames}.")  # type: ignore[union-attr]
        for uuid in self.games - games:
            self.manager.logger.info(f"Match ended for {self.game_type}: {uuid}")
            try:
                resp = await self.add_game_to_leaderboard(self.game_type, uuid)
            except Exception as e:
                await self.bot_channel.send(content="Error: " + str(e))  # type: ignore[union-attr]
                self.games = games
                return
            link = f"https://mahjongsoul.game.yo-star.com/?paipu={uuid}"
            view = CommandSuggestionView(link,
                                         score_graph_enabled=True,
                                         bonus_graph_enabled=True,
                                         parse_enabled=True,
                                         injustice_enabled=True,
                                         skill_enabled=True)
            message = await self.bot_channel.send(content=resp, suppress_embeds=True, view=view)  # type: ignore[union-attr]
            view.set_message(message)
        self.games = games
    # ensure bot is ready before poll_games is called
    @poll_games.before_loop
    async def poll_games_ready(self):
        await self.bot.wait_until_ready()
    @poll_games.error
    async def poll_games_error(self, error):
        logging.error(f"Error in polling games: {error}")

    async def add_game_to_leaderboard(self, lobby: str, uuid: str, record=None) -> str:
        if record is None:
            assert account_manager is not None
            record_list = await account_manager.get_game_results([uuid])
            if len(record_list) == 0:
                raise Exception("A game concluded without a record (possibly due to being terminated early).")
            record = record_list[0]
        # TODO: deal with ordering the scores; currently assumes the scores are ordered by
        #       total_point (adopt the algorithm of `enter_scores` command)
        seat_player_dict = {a.seat: (a.account_id, a.nickname) for a in record.accounts}

        player_scores_rendered = ["Game concluded!"] # to be newline-separated
        player_scores_rendered.append(f"https://mahjongsoul.game.yo-star.com/?paipu={uuid}")

        timestamp = str(datetime.datetime.now()).split(".")[0]
        raw_scores_row = [timestamp, lobby, "no"] # a list of values for a "Raw Scores" row
        not_registered = [] # list of unregistered players in game, if any

        seat_name = ["East", "South", "West", "North"]
        for p in record.result.players:
            player_account_id, player_nickname = seat_player_dict.get(p.seat, (0, "AI"))
            
            raw_score = p.part_point_1
            async with registry_lock:
                assert registry is not None
                found_cell: gspread.cell.Cell = registry.find(str(player_account_id), in_column=MJS_ACCOUNT_ID_COL)
                if found_cell is not None:
                    discord_name = registry.cell(found_cell.row, DISCORD_NAME_COL).value
                    raw_scores_row.extend((discord_name, raw_score))
                else: # The player was not registered?
                    not_registered.append(player_nickname)
                    raw_scores_row.extend(("Unregistered player", raw_score))
            
            player_scores_rendered.append(
                f"{player_nickname} ({seat_name[p.seat]}): {p.part_point_1} ({(p.total_point/1000):+})")

        for player_nickname in not_registered:
            player_scores_rendered.append(f"*WARNING*: Mahjong Soul player `{player_nickname}` is not registered!")

        async with raw_scores_lock:
            assert raw_scores is not None
            raw_scores.append_row(raw_scores_row)

        return '\n'.join(player_scores_rendered)
    

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
