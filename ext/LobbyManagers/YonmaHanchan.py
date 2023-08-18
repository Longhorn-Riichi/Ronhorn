import asyncio
import discord
import gspread
import os
from os import getenv
from discord.ext import commands
from discord import app_commands, Interaction
import logging

from modules.mahjongsoul.contest_manager import ContestManager
from typing import *

EXTENSION_NAME = "UvUManager" # must be the same as class name...

def assert_getenv(name: str) -> Any:
    value = getenv(name)
    assert value is not None, f"missing \"{name}\" in config.env"
    return value

CONTEST_UNIQUE_ID: int     = int(assert_getenv("contest_unique_id"))
CONTEST_TOURNAMENT_ID: str = assert_getenv("contest_tournament_id")
GUILD_ID: int              = int(assert_getenv("guild_id"))
BOT_CHANNEL_ID: int        = int(assert_getenv("bot_channel_id"))
PLAYER_ROLE: str           = assert_getenv("player_role")
ADMIN_ROLE: str            = assert_getenv("admin_role")
TEAM_1: str                = assert_getenv("team_1")
TEAM_2: str                = assert_getenv("team_2")
SPREADSHEET_ID: str        = assert_getenv("spreadsheet_id")

class UvUManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot_channel = None # fetched in `self.async_setup()`
        self.manager = ContestManager(CONTEST_UNIQUE_ID)

        current_path = os.path.dirname(__file__)
        gs_client = gspread.service_account(
            filename=os.path.join(current_path, 'gs_service_account.json'))
        spreadsheet = gs_client.open_by_key(SPREADSHEET_ID)
        self.registry = spreadsheet.worksheet("Registry")
        self.registry_lock = asyncio.Lock()
        self.game_results = spreadsheet.worksheet("Game Results")

    async def async_setup(self):
        """
        to be called in `setup()`:
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
    SLASH COMMANDS
    =====================================================
    """

    @app_commands.command(name="help", description="show helpful hints for using this bot (only visible to you)")
    async def help(self, interaction: Interaction):
        await interaction.response.send_message(
            content=(
                "How to start a tournament game:\n"
                "1. Register your Mahjong Soul account using the `/register` command.\n"
                f"2. On Mahjong Soul: Tournament Match -> Tournament Lobby -> Enter Tournament ID ({CONTEST_TOURNAMENT_ID}) -> Prepare for match.\n"
                "3. Create a table with `/create_table` command. Once everyone chose their seat, the game can be started using the `START` button.\n"
                "Helpful commands for when people need to be AFK (do NOT abuse!):\n"
                "`/terminate_own_game`, `/pause_own_game`, `/unpause_own_game`"),
            ephemeral=True)

    @app_commands.command(name="terminate_any_game", description=f"Terminate the game of the specified player. Only usable by @{ADMIN_ROLE}.")
    @app_commands.describe(nickname="Specify the nickname of a player that's in the game you want to terminate.")
    @app_commands.checks.has_role(ADMIN_ROLE)
    async def terminate_any_game(self, interaction: Interaction, nickname: str):
        await interaction.response.defer()
        message = await self.manager.terminate_game(nickname)
        await interaction.followup.send(content=message)

    @app_commands.command(name="terminate_own_game", description=f"Terminate the game you are currently in. Usable by {PLAYER_ROLE}.")
    @app_commands.checks.has_role(PLAYER_ROLE)
    async def terminate_own_game(self, interaction: Interaction):
        await interaction.response.defer()
        player = self.look_up_player(interaction.user.name)
        if player is None:
            await interaction.followup.send(content="You are not a registered player; there shouldn't be an ongoing game for you.")
            return
        message = await self.manager.terminate_game(player.mjs_nickname)
        await interaction.followup.send(content=message)
    
    @app_commands.command(name="pause_any_game", description=f"Pause the game of the specified player. Only usable by @{ADMIN_ROLE}.")
    @app_commands.describe(nickname="Specify the nickname of a player that's in the game you want to pause.")
    @app_commands.checks.has_role(ADMIN_ROLE)
    async def pause_any_game(self, interaction: Interaction, nickname: str):
        await interaction.response.defer()
        message = await self.manager.pause_game(nickname)
        await interaction.followup.send(content=message)

    @app_commands.command(name="pause_own_game", description=f"Pause the game you are currently in. Usable by {PLAYER_ROLE}.")
    @app_commands.checks.has_role(PLAYER_ROLE)
    async def pause_own_game(self, interaction: Interaction):
        await interaction.response.defer()
        player = self.look_up_player(interaction.user.name)
        if player is None:
            await interaction.followup.send(content="You are not a registered player; there shouldn't be an ongoing game for you.")
            return
        message = await self.manager.pause_game(player.mjs_nickname)
        await interaction.followup.send(content=message)
    
    @app_commands.command(name="unpause_any_game", description=f"Unpause the paused game of the specified player. Only usable by @{ADMIN_ROLE}.")
    @app_commands.describe(nickname="Specify the nickname of a player that's in the paused game you want to unpause.")
    @app_commands.checks.has_role(ADMIN_ROLE)
    async def unpause_any_game(self, interaction: Interaction, nickname: str):
        await interaction.response.defer()
        message = await self.manager.unpause_game(nickname)
        await interaction.followup.send(content=message)

    @app_commands.command(name="unpause_own_game", description=f"Unpause the paused game you were in. Usable by {PLAYER_ROLE}.")
    @app_commands.checks.has_role(PLAYER_ROLE)
    async def unpause_own_game(self, interaction: Interaction):
        await interaction.response.defer()
        player = self.look_up_player(interaction.user.name)
        if player is None:
            await interaction.followup.send(content="You are not a registered player; there shouldn't be an ongoing game for you.")
            return
        message = await self.manager.unpause_game(player.mjs_nickname)
        await interaction.followup.send(content=message)

    async def _register(self, player: discord.Member, friend_id: int, affiliation: str, subbing_for: Optional[str] = None) -> str:
        """Add player to the registry, removing any existing registration first"""
        
        # Fetch Mahjong Soul details
        res = await self.manager.call("searchAccountByEid", eids = [int(friend_id)])
        # if no account found, then `res` won't have a `search_result` field, but it won't
        # have an `error`` field, either (i.e., it's not an error!).
        if not res.search_result:
            raise Exception(f"Couldn't find Mahjong Soul account for this friend ID: {friend_id}")
        mahjongsoul_nickname = res.search_result[0].nickname
        mahjongsoul_account_id = res.search_result[0].account_id

        async with self.registry_lock:
            # Delete any existing registration
            found_cell = self.registry.find(player.name, in_column=1)
            cell_existed = found_cell is not None
            if cell_existed:
                self.registry.delete_row(found_cell.row)

            data = [player.name,
                    mahjongsoul_nickname,
                    friend_id,
                    mahjongsoul_account_id,
                    affiliation,
                    subbing_for]
            self.registry.append_row(data)
            if cell_existed:
                return f"Updated registration for \"{player.name}\" from {affiliation} with Mahjong Soul account \"{mahjongsoul_nickname}\"."
            else:
                return f"Registered \"{player.name}\" from {affiliation} with Mahjong Soul account \"{mahjongsoul_nickname}\"."

    @app_commands.command(name="register", description="Register yourself with your Mahjong Soul friend ID, or update your existing registration.")
    @app_commands.checks.has_role(PLAYER_ROLE)
    @app_commands.choices(affiliation=[
        app_commands.Choice(name=TEAM_1, value=TEAM_1),
        app_commands.Choice(name=TEAM_2, value=TEAM_2)
    ])
    @app_commands.describe(
        friend_id="Find your friend ID in the Friends tab; this is separate from your username.",
        affiliation=f"Which club do you represent: {TEAM_1}? {TEAM_2}?")
    async def register(self, interaction: Interaction, friend_id: int, affiliation: app_commands.Choice[str]):
        """
        here we use Discord ID as the unique identifier
        """
        await interaction.response.defer()
        assert isinstance(interaction.user, discord.Member)
        try:
            response = await self._register(interaction.user, friend_id, affiliation.value)
            await interaction.followup.send(content=response)
        except Exception as e:
            await interaction.followup.send(content=str(e))

    @app_commands.command(name="register_sub", description="Register yourself to sub for a specified player")
    @app_commands.checks.has_role(PLAYER_ROLE)
    @app_commands.describe(
        sub_for="The discord user who you will be subbing for.",
        friend_id="Find your friend ID in the Friends tab; this is separate from your username. Omit if you are already registred.")
    async def register_sub(self, interaction: Interaction, sub_for: discord.Member, friend_id: Optional[int] = None):
        await interaction.response.defer()
        discord_name = interaction.user.name
        if str(sub_for.name) == str(interaction.user.name):
            return await interaction.followup.send(content=f"\"{discord_name}\" cannot sub for themselves.")
        async with self.registry_lock:
            # first, find the discord name and affiliation of the user we're subbing for
            # (ensuring they exist in the registry)
            found_cell: gspread.cell.Cell = self.registry.find(sub_for.name, in_column=1)
            if found_cell is None:
                return await interaction.followup.send(
                    content=f"\"{sub_for}\" must first /register their Mahjong Soul account.")
            else:
                [_, _, _, _, sub_affiliation, *rest] = self.registry.row_values(found_cell.row)

            # If friend_id is not passed in, we must be registered and we use our preexisting friend id
            if friend_id is None:
                found_cell = self.registry.find(discord_name, in_column=1)
                if found_cell is None:
                    return await interaction.followup.send(
                        content=f"\"{discord_name}\" has not registered, so you need to provide the friend_id in /register_sub.")
                else:
                    [_, _, friend_id, _, _, *rest] = self.registry.row_values(found_cell.row)

        # now actually do the registration
        try:
            assert isinstance(interaction.user, discord.Member)
            await self._register(interaction.user, friend_id, sub_affiliation, sub_for.name)
            await interaction.followup.send(
                content=f"\"{discord_name}\" has registered to sub for \"{sub_for.name}\" from {sub_affiliation}.")
        except Exception as e:
            await interaction.followup.send(content=str(e))

    async def _unregister(self, player: discord.Member) -> str:
        async with self.registry_lock:
            found_cell: gspread.cell.Cell = self.registry.find(player.name, in_column=1)
            if found_cell is None:
                return f"\"{player.name}\" has not registered a Mahjong Soul account."
            else:
                [_, mahjongsoul_nickname, _, mahjongsoul_account_id, affiliation, *rest] = self.registry.row_values(found_cell.row)
                self.registry.delete_row(found_cell.row)
                if len(rest) > 0 and len(str(rest[0])) > 0:
                    return f"Removed Mahjong Soul account \"{mahjongsoul_nickname}\" of \"{player.name}\" subbing for {affiliation} from the registry."
                else:
                    return f"Removed Mahjong Soul account \"{mahjongsoul_nickname}\" of \"{player.name}\" from {affiliation} from the registry."

    @app_commands.command(name="unregister", description="Remove your registered Mahjong Soul account from the registry.")
    @app_commands.checks.has_role(PLAYER_ROLE)
    async def unregister(self, interaction: Interaction):
        assert isinstance(interaction.user, discord.Member)
        await interaction.response.defer()
        response = await self._unregister(interaction.user)
        await interaction.followup.send(content=response)

    @app_commands.command(name="unregister_other", description=f"Unregister the given player. Only usable by @{ADMIN_ROLE}.")
    @app_commands.describe(player="The player you want to unregister.")
    @app_commands.checks.has_role(ADMIN_ROLE)
    async def unregister_other(self, interaction: Interaction, player: discord.Member):
        await interaction.response.defer()
        response = await self._unregister(player)
        await interaction.followup.send(content=response)

    @app_commands.command(name="create_table", description="Create a table prompt where players self-assign seats before starting a game.")
    @app_commands.checks.has_role(PLAYER_ROLE)
    async def create_table(self, interaction: Interaction):
        """
        The interactive messages auto-delete self after a certain amount of time.
        
        Originally, there was going to be a way to track the alive interactive
        messages to prevent users from spamming the `create_table` commands and/or
        sitting down at multiple tables. Since the functionality was only useful against
        malicious users, the difficulty in implementing it made it not worthwhile.

        TOTHINK: similarly, it's difficult to connect to listeners to check whether
        someone has hit "prepare for match" (or is `locked` according to MJS terms)
        """
        view = TableView(look_up_player=self.look_up_player,
                         start_game=self.manager.start_game,
                         original_interaction=interaction)
        view.interactive_message = await interaction.response.send_message(
            content="Choose a seat!",
            embed=default_embed,
            view=view)
        

    """
    =====================================================
    MAHJONG SOUL API STUFF
    =====================================================
    """

    async def on_NotifyContestGameStart(self, _, msg):
        nicknames = " | ".join([p.nickname or "AI" for p in msg.game_info.players])
        await self.bot_channel.send(f"UvU game started! Players: {nicknames}.")

    async def on_NotifyContestGameEnd(self, _, msg):
        # It takes some time for the results to register into the log
        await asyncio.sleep(3)

        record = await self.manager.locate_completed_game(msg.game_uuid)

        if record is None:
            await self.bot_channel.send("A game concluded without a record (possibly due to being terminated early).")
            return

        # TODO: just do player look up so affiliation can be included as well
        # TODO: deal with ordering the scores; currently assumes the scores are ordered by
        #       total_point (this algorithm can be shared with manual score entering)
        player_seat_lookup = {a.seat: (a.account_id, a.nickname) for a in record.accounts}

        player_scores_rendered = ["Game concluded! Results:"] # to be newline-separated
        game_results_row = [] # a list of values for a "Game Results" row
        AI_count = 0
        not_registered = [] # list of unregistered players in game, if any

        for p in record.result.players:
            player_account_id, player_nickname = player_seat_lookup.get(p.seat, (0, "AI"))
            player_scores_rendered.append(
                f"{player_nickname} ({p.part_point_1}) [{p.total_point/1000:+}]")

            is_ai = player_account_id == 0
            if is_ai:
                AI_count += 1
                game_results_row.extend(("AI", p.total_point/1000))
            else:
                # replace the id with the id of the person the player is subbing for, if any
                async with self.registry_lock:
                    found_cell: gspread.cell.Cell = self.registry.find(str(player_account_id), in_column=4)
                    if found_cell is not None:
                        [discord_name, _, _, _, _, *rest] = self.registry.row_values(found_cell.row)
                        if len(rest) > 0: # we are subbing for someone
                            discord_name = rest[0]
                        game_results_row.extend((discord_name, p.total_point/1000))
                    else: # The player was not registered?
                        not_registered.append(player_nickname)
                        game_results_row.extend(("Unregistered player", p.total_point/1000))

        if AI_count == 1:
            player_scores_rendered.append("An AI was in this game; remember to edit the score entry on Google Sheets with the respective substituted player's account ID.")
        elif AI_count > 1:
            player_scores_rendered.append(f"{AI_count} AIs were in this game; remember to edit the score entry on Google Sheets with {AI_count} respective substituted players' account ID.")

        for player_nickname in not_registered:
            player_scores_rendered.append(f"Error: Mahjong Soul player {player_nickname} was not registered for this game!")

        asyncio.create_task(self.bot_channel.send(
            content='\n'.join(player_scores_rendered)))

        self.game_results.append_row(game_results_row)

    """
    =====================================================
    GOOGLE SHEETS HELPER FUNCTIONS
    =====================================================
    """

    def look_up_player(self, discord_name: str) -> Player | None:
        found_cell: gspread.cell.Cell = self.registry.find(discord_name, in_column=1)
        if found_cell is not None:
            [_, mjs_nickname, _, mjs_account_id, affiliation, *rest] = self.registry.row_values(found_cell.row)
            subbed_player_discord_name = None
            subbed_player_mjs_name = None
            if len(rest) > 0:
                subbing_for = rest[0]
                # find the name of the player being subbed for
                found_cell = self.registry.find(str(subbing_for), in_column=1)
                if found_cell is None: # possibly the subbed player unregistered; act like there is no sub
                    pass
                else:
                    [subbed_player_discord_name, subbed_player_mjs_name, _, _, _, *rest] = self.registry.row_values(found_cell.row)
            return Player(
                mjs_account_id=int(mjs_account_id),
                mjs_nickname=mjs_nickname,
                discord_name=discord_name,
                affiliation=affiliation,
                subbing_for_discord_name=subbed_player_discord_name,
                subbing_for_mjs_name=subbed_player_mjs_name)
        
        # No player with given Discord name found; returning None
        return None

async def setup(bot: commands.Bot):
    instance = UvUManager(bot)
    asyncio.create_task(instance.async_setup())
    await bot.add_cog(instance, guild=discord.Object(id=GUILD_ID))
    logging.info(f"Extension `{EXTENSION_NAME}` has been loaded")

# `teardown()` currently doesn't get called for some reason...
# async def teardown(bot: commands.Bot):
#     instance: UvUManager = bot.get_cog(EXTENSION_NAME)
#     await instance.manager.close()
#     logging.info(f"Extension `{EXTENSION_NAME}` has been unloaded")