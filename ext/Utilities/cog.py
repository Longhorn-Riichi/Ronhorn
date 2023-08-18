import asyncio
import discord
import gspread
from os import getenv
from discord.ext import commands
from discord import app_commands, Interaction
import logging
from typing import *

def assert_getenv(name: str) -> Any:
    value = getenv(name)
    assert value is not None, f"missing \"{name}\" in config.env"
    return value

GUILD_ID: int              = int(assert_getenv("guild_id"))
OFFICER_ROLE: str          = assert_getenv("officer_role")
SPREADSHEET_ID: str        = assert_getenv("spreadsheet_url")
YH_TOURNAMENT_ID: str      = assert_getenv("yh_tournament_id")
YT_TOURNAMENT_ID: str      = assert_getenv("yt_tournament_id")
SH_TOURNAMENT_ID: str      = assert_getenv("sh_tournament_id")
ST_TOURNAMENT_ID: str      = assert_getenv("st_tournament_id")
REGISTRY_NAME_LENGTH: int  = 15

class Utilities(commands.Cog):
    def __init__(self, bot: commands.Bot):
        assert(isinstance(bot.registry, gspread.Worksheet))
        assert(isinstance(bot.raw_scores, gspread.Worksheet))
        assert(isinstance(bot.registry_lock, asyncio.Lock))
        assert(isinstance(bot.raw_scores_lock, asyncio.Lock))

        self.registry = bot.registry
        self.raw_scores = bot.raw_scores
        self.registry_lock = bot.registry_lock
        self.raw_scores_lock = bot.raw_scores_lock

        # we assume that the manager cogs have already been loaded
        self.yh_manager = bot.get_cog("YonmaHanchanLobbyManager")
        self.yt_manager = bot.get_cog("YonmaTonpuuLobbyManager")
        self.sh_manager = bot.get_cog("SanmaHanchanLobbyManager")
        self.st_manager = bot.get_cog("SanmaTonpuuLobbyManager")


    """
    =====================================================
    SLASH COMMANDS
    =====================================================
    """

    @app_commands.command(name="help", description="show helpful info about the club (only visible to you)")
    async def help(self, interaction: Interaction):
        await interaction.response.send_message(
            content=(
                "How to play online club games:"
                "1. Register your Mahjong Soul account with `/register`.\n"
                "2. Choose the right lobby by Tournament ID:\n"
                f"> 4P South: **{YH_TOURNAMENT_ID}**\n"
                f"> 4P East: **{YT_TOURNAMENT_ID}**\n"
                f"> 3P South: **{SH_TOURNAMENT_ID}**\n"
                f"> 3P East: **{ST_TOURNAMENT_ID}**\n"
                "3. On Mahjong Soul: Tournament Match -> Tournament Lobby -> Enter Tournament ID -> Prepare for match.\n"
                "4. You can **follow** the lobbies for easier access.\n"
                "Helpful commands for when people need to be AFK (do NOT abuse!):\n"
                "`/terminate_own_game`, `/pause_own_game`, `/unpause_own_game`"),
            ephemeral=True)

    """
    @app_commands.command(name="terminate_any_game", description=f"Terminate the game of the specified player. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(nickname="Specify the nickname of a player that's in the game you want to terminate.")
    @app_commands.checks.has_role(OFFICER_ROLE)
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
    
    @app_commands.command(name="pause_any_game", description=f"Pause the game of the specified player. Only usable by @{OFFICER_ROLE}.")
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
    
    @app_commands.command(name="unpause_any_game", description=f"Unpause the paused game of the specified player. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(nickname="Specify the nickname of a player that's in the paused game you want to unpause.")
    @app_commands.checks.has_role(OFFICER_ROLE)
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
    """

    # TODO: command to upgrade someone's membership to paid
    # TODO: command to get someone's registry information (by name or discord name)
        
    async def _register(self, name: str, server_member: discord.Member, friend_id: int) -> str:
        """
        Add player to the registry, removing any existing registration first.
        Assumes input is already sanitized (e.g., `name` isn't 200 chars long)
        Raise exceptions if the friend ID is invalid.
        Returns the response string.
        """

        # Fetch Mahjong Soul details using one of the lobby managers
        res = await self.st_manager.manager.call("searchAccountByEid", eids = [int(friend_id)])
        # if no account found, then `res` won't have a `search_result` field, but it won't
        # have an `error`` field, either (i.e., it's not an error!).
        if not res.search_result:
            raise Exception(f"Couldn't find Mahjong Soul account for this friend ID: {friend_id}")
        mahjongsoul_nickname = res.search_result[0].nickname
        mahjongsoul_account_id = res.search_result[0].account_id
        discord_name = server_member.name

        async with self.registry_lock:
            # Delete any existing registration
            found_cell = self.registry.find(discord_name, in_column=2)
            cell_existed = found_cell is not None
            if cell_existed:
                self.registry.delete_row(found_cell.row)

            data = [name,
                    discord_name,
                    "no",
                    mahjongsoul_nickname,
                    friend_id,
                    mahjongsoul_account_id]
            self.registry.append_row(data)
            if cell_existed:
                return f"\"{discord_name}\" updated registration with name \"{name}\" and Mahjong Soul account \"{mahjongsoul_nickname}\"."
            else:
                return f"\"{discord_name}\" registered with name \"{name}\" and Mahjong Soul account \"{mahjongsoul_nickname}\"."
    
    @app_commands.command(name="register", description="Register with your name and Mahjong Soul friend ID, or update your current registration.")
    @app_commands.describe(
        name=f"Your preferred, real-life name (no more than {REGISTRY_NAME_LENGTH} characters)",
        friend_id="Find your friend ID in the Friends tab; this is separate from your username.")
    async def register(self, interaction: Interaction, name: str, friend_id: int):
        if len(name) > REGISTRY_NAME_LENGTH:
            interaction.response.send_message(f"Please keep your preferred name within {REGISTRY_NAME_LENGTH} characters and `/register` again.", ephemeral=True)
            return

        await interaction.response.defer()
        assert isinstance(interaction.user, discord.Member)
        try:
            response = await self._register(name, interaction.user, friend_id)
            await interaction.followup.send(content=response)
        except Exception as e:
            await interaction.followup.send(content=str(e))

    async def _unregister(self, server_member: discord.Member) -> str:
        discord_name = server_member.name
        async with self.registry_lock:
            found_cell: gspread.cell.Cell = self.registry.find(discord_name, in_column=2)
            if found_cell is None:
                return f"\"{discord_name}\" is not a registered member."
            else:
                self.registry.delete_row(found_cell.row)
                return f"\"{discord_name}\" removed their registration."

    @app_commands.command(name="unregister", description="Remove your registered information.")
    async def unregister(self, interaction: Interaction):
        assert isinstance(interaction.user, discord.Member)
        await interaction.response.defer()
        response = await self._unregister(interaction.user)
        await interaction.followup.send(content=response)

    @app_commands.command(name="unregister_other", description=f"Unregister the given server member. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(server_member="The server member you want to unregister.")
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def unregister_other(self, interaction: Interaction, server_member: discord.Member):
        await interaction.response.defer()
        response = await self._unregister(server_member)
        await interaction.followup.send(content=response)

    @app_commands.command(name="enter_scores", description=f"Enter scores for an IRL game, starting with the East player. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(game_type="Hanchan or tonpuu?",
                           player1="The East player you want to record the score for.",
                           score1="Score for player 1.",
                           player2="The South player you want to record the score for.",
                           score2="Score for player 2.",
                           player3="The West player you want to record the score for.",
                           score3="Score for player 3.",
                           player4="The (optional) North player you want to record the score for.",
                           score4="Score for player 4.",
                           riichi_sticks="(optional) Number of riichi sticks left on the table.")
    @app_commands.choices(game_type=[
        app_commands.Choice(name="Hanchan", value="Hanchan"),
        app_commands.Choice(name="Tonpuu", value="Tonpuu")
    ])
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def enter_scores(self, interaction: Interaction,
                                  game_type: app_commands.Choice[str],
                                  player1: discord.Member, score1: int,
                                  player2: discord.Member, score2: int,
                                  player3: discord.Member, score3: int,
                                  player4: Optional[discord.Member] = None, score4: Optional[int] = None,
                                  riichi_sticks: int = 0):
        await interaction.response.defer()
        try:
            if player4 is None:
                expected_total = 3*35000
                players = [player1, player2, player3]
                scores = [score1, score2, score3]
                game_style = "Sanma"
            else:
                if score4 is None:
                    return await interaction.followup.send(content=f"Error: must enter Player 4's score.")
                expected_total = 4*25000
                players = [player1, player2, player3, player4]
                scores = [score1, score2, score3, score4]
                game_style = "Yonma"

            ordered_players = sorted(zip(players, scores), key=lambda item: -item[1])
            first_player, first_score = ordered_players[0]
            ordered_players[0] = (first_player, first_score + 1000*riichi_sticks)
            total_score = sum(scores) + 1000*riichi_sticks

            if total_score != expected_total:
                riichi_stick_string = '' if riichi_sticks == 0 else f" (+ {riichi_sticks} riichi sticks)"
                return await interaction.followup.send(content=f"Error: Entered scores add up to {'+'.join(map(str,scores))}{riichi_stick_string} = {total_score}, expected {expected_total}.")
            if len(set(players)) < len(players):
                return await interaction.followup.send(content=f"Error: duplicate player entered.")

            # enter the scores into the sheet
            import datetime
            timestamp = str(datetime.datetime.now()).split(".")[0]
            gamemode = f"{game_style} {game_type.value}"
            flatten = lambda xss: (x for xs in xss for x in xs)
            async with self.raw_scores_lock:
                self.raw_scores.append_row([timestamp, gamemode, "yes", *map(str, flatten(ordered_players))])

            player_score_strings = list(flatten(map(lambda p: (p[0].mention, str(p[1])), ordered_players)))
            score_printout = f"Successfully entered scores for a {gamemode} game:\n" \
                              "- **1st**: {}: {}\n" \
                              "- **2nd**: {}: {}\n" \
                              "- **3rd**: {}: {}"
            if player4 is not None:
                score_printout += "\n- **4th**: {}: {}"

            await interaction.followup.send(content=score_printout.format(*player_score_strings))
        except Exception as e:
            await interaction.followup.send(content="Error: " + str(e))



async def setup(bot: commands.Bot):
    logging.info(f"Loading extension `{Utilities.__name__}`...")
    instance = Utilities(bot)
    await bot.add_cog(instance, guild=discord.Object(id=GUILD_ID))
