import asyncio
import datetime
import discord
import gspread
import logging
import requests
from os import getenv
from discord.ext import commands
from discord import app_commands, Interaction
from typing import *
from ext.LobbyManagers.cog import LobbyManager

def assert_getenv(name: str) -> str:
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
YH_NAME: str               = assert_getenv("yh_name")
YT_NAME: str               = assert_getenv("yt_name")
SH_NAME: str               = assert_getenv("sh_name")
ST_NAME: str               = assert_getenv("st_name")
REGISTRY_NAME_LENGTH: int  = 15

class Utilities(commands.Cog):
    def __init__(self, bot: commands.Bot):
        assert(isinstance(bot.registry, gspread.Worksheet))
        assert(isinstance(bot.raw_scores, gspread.Worksheet))
        assert(isinstance(bot.registry_lock, asyncio.Lock))
        assert(isinstance(bot.raw_scores_lock, asyncio.Lock))
        
        self.bot = bot
        self.registry = bot.registry
        self.raw_scores = bot.raw_scores
        self.registry_lock = bot.registry_lock
        self.raw_scores_lock = bot.raw_scores_lock

    """
    =====================================================
    HELPERS
    =====================================================
    """

    def get_cog(self, lobby_name: str) -> LobbyManager:
        return self.bot.get_cog(lobby_name)

    def lobby_choices(choices_list):
        def decorator(func):
            def wrapper(*args, **kwargs):
                lobby_choices = [
                    app_commands.Choice(name=choice, value=choice) for choice in choices_list
                ]
                return func(lobby_choices, *args, **kwargs)
            return wrapper
        return decorator

    """
    =====================================================
    SLASH COMMANDS
    =====================================================
    """

    @app_commands.command(name="help", description="show help about club online games")
    async def help(self, interaction: Interaction):
        await interaction.response.send_message(
            content=(
                "How to play online club games:\n"
                "1. Register your Mahjong Soul account with `/register`.\n"
                "2. Choose the right lobby by Tournament ID:\n"
                f"> {YH_NAME}: **{YH_TOURNAMENT_ID}**\n"
                f"> {YT_NAME}: **{YT_TOURNAMENT_ID}**\n"
                f"> {SH_NAME}: **{SH_TOURNAMENT_ID}**\n"
                f"> {ST_NAME}: **{ST_TOURNAMENT_ID}**\n"
                "3. On Mahjong Soul: Tournament Match -> Tournament Lobby -> Enter Tournament ID -> Prepare for match.\n"
                "4. You can **follow** the lobbies for easier access.\n"
                "Helpful commands for when people need to be AFK (do NOT abuse!):\n"
                "`/terminate_own_game`, `/pause_own_game`, `/unpause_own_game`"),
            ephemeral=True)

    @app_commands.command(name="terminate_any_game", description=f"Terminate the game of the specified player. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(
        lobby="Which lobby is the game in?",
        nickname="Mahjong Soul nickname of a player that's in the game you want to terminate.")
    @app_commands.choices(lobby=[
        app_commands.Choice(name=YH_NAME, value=YH_NAME),
        app_commands.Choice(name=YT_NAME, value=YT_NAME),
        app_commands.Choice(name=SH_NAME, value=SH_NAME),
        app_commands.Choice(name=ST_NAME, value=ST_NAME)])
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def terminate_any_game(self, interaction: Interaction, lobby: app_commands.Choice[str], nickname: str):
        await self.get_cog(lobby.value).terminate_any_game(interaction, nickname)

    @app_commands.command(name="terminate_own_game", description=f"Terminate the game you are currently in.")
    @app_commands.describe(
        lobby="Which lobby is your game in?")
    @app_commands.choices(lobby=[
        app_commands.Choice(name=YH_NAME, value=YH_NAME),
        app_commands.Choice(name=YT_NAME, value=YT_NAME),
        app_commands.Choice(name=SH_NAME, value=SH_NAME),
        app_commands.Choice(name=ST_NAME, value=ST_NAME)])
    async def terminate_own_game(self, interaction: Interaction, lobby: app_commands.Choice[str]):
        await self.get_cog(lobby.value).terminate_own_game(interaction)
    
    @app_commands.command(name="pause_any_game", description=f"Pause the game of the specified player. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(
        lobby="Which lobby is the game in?",
        nickname="Mahjong Soul nickname of a player that's in the game you want to pause.")
    @app_commands.choices(lobby=[
        app_commands.Choice(name=YH_NAME, value=YH_NAME),
        app_commands.Choice(name=YT_NAME, value=YT_NAME),
        app_commands.Choice(name=SH_NAME, value=SH_NAME),
        app_commands.Choice(name=ST_NAME, value=ST_NAME)])
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def pause_any_game(self, interaction: Interaction, lobby: app_commands.Choice[str], nickname: str):
        await self.get_cog(lobby.value).pause_any_game(interaction, nickname)

    @app_commands.command(name="pause_own_game", description=f"Pause the game you are currently in.")
    @app_commands.describe(
        lobby="Which lobby is your game in?")
    @app_commands.choices(lobby=[
        app_commands.Choice(name=YH_NAME, value=YH_NAME),
        app_commands.Choice(name=YT_NAME, value=YT_NAME),
        app_commands.Choice(name=SH_NAME, value=SH_NAME),
        app_commands.Choice(name=ST_NAME, value=ST_NAME)])
    async def pause_own_game(self, interaction: Interaction, lobby: app_commands.Choice[str]):
        await self.get_cog(lobby.value).pause_own_game(interaction)
    
    @app_commands.command(name="unpause_any_game", description=f"Unpause the paused game of the specified player. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(
        lobby="Which lobby is the game in?",
        nickname="Mahjong Soul nickname of a player that's in the game you want to unpause.")
    @app_commands.choices(lobby=[
        app_commands.Choice(name=YH_NAME, value=YH_NAME),
        app_commands.Choice(name=YT_NAME, value=YT_NAME),
        app_commands.Choice(name=SH_NAME, value=SH_NAME),
        app_commands.Choice(name=ST_NAME, value=ST_NAME)])
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def unpause_any_game(self, interaction: Interaction, lobby: app_commands.Choice[str], nickname: str):
        await self.get_cog(lobby.value).unpause_any_game(interaction, nickname)

    @app_commands.command(name="unpause_own_game", description=f"Unpause the paused game you were in.")
    @app_commands.describe(
        lobby="Which lobby is your game in?")
    @app_commands.choices(lobby=[
        app_commands.Choice(name=YH_NAME, value=YH_NAME),
        app_commands.Choice(name=YT_NAME, value=YT_NAME),
        app_commands.Choice(name=SH_NAME, value=SH_NAME),
        app_commands.Choice(name=ST_NAME, value=ST_NAME)])
    async def unpause_own_game(self, interaction: Interaction, lobby: app_commands.Choice[str]):
        await self.get_cog(lobby.value).unpause_own_game(interaction)
        
    async def _register(self, name: str, server_member: discord.Member, friend_id: Optional[int]) -> str:
        """
        Add player to the registry, removing any existing registration first.
        Assumes input is already sanitized (e.g., `name` isn't 200 chars long)
        Raise exceptions if the friend ID is invalid.
        Returns the response string.
        """

        if friend_id is not None:
            # Fetch Mahjong Soul details using one of the lobby managers
            res = await self.get_cog(ST_NAME).manager.call("searchAccountByEid", eids = [int(friend_id)])
            # if no account found, then `res` won't have a `search_result` field, but it won't
            # have an `error`` field, either (i.e., it's not an error!).
            if not res.search_result:
                raise Exception(f"Couldn't find Mahjong Soul account for this friend ID: {friend_id}")
            mahjongsoul_nickname = res.search_result[0].nickname
            mahjongsoul_account_id = res.search_result[0].account_id
        else:
            mahjongsoul_nickname = None
            mahjongsoul_account_id = None
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
            register_string = "updated registration" if cell_existed else "registered"
            mjsoul_string = f" and Mahjong Soul account \"{mahjongsoul_nickname}\"" if friend_id is not None else ""
            return f"\"{discord_name}\" {register_string} with name \"{name}\"{mjsoul_string}."
    
    @app_commands.command(name="register", description="Register with your name and Mahjong Soul friend ID, or update your current registration.")
    @app_commands.describe(
        name=f"Your preferred, real-life name (no more than {REGISTRY_NAME_LENGTH} characters)",
        friend_id="(optional) Mahjong Soul friend ID. Find it in the Friends tab; this is not your username.")
    async def register(self, interaction: Interaction, name: str, friend_id: Optional[int] = None):
        if len(name) > REGISTRY_NAME_LENGTH:
            await interaction.response.send_message(f"Please keep your preferred name within {REGISTRY_NAME_LENGTH} characters and `/register` again.", ephemeral=True)
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
                return f"\"{discord_name}\"'s registration has been removed."

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

            total_score = sum(scores) + 1000*riichi_sticks

            if total_score != expected_total:
                riichi_stick_string = '' if riichi_sticks == 0 else f" (+ {riichi_sticks} riichi sticks)"
                return await interaction.followup.send(content=f"Error: Entered scores add up to {'+'.join(map(str,scores))}{riichi_stick_string} = {total_score}, expected {expected_total}.")
            if len(set(players)) < len(players):
                return await interaction.followup.send(content=f"Error: duplicate player entered.")

            # the input is now sanitized; add riichi sticks to the first place's total
            ordered_players = sorted(zip(players, scores), key=lambda item: -item[1])
            first_player, first_score = ordered_players[0]
            ordered_players[0] = (first_player, first_score + 1000*riichi_sticks)

            # enter the scores into the sheet
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

    @app_commands.command(name="update_membership", description=f"Update a player's membership type (paid or unpaid). Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(server_member="The server member whose membership type you want to update",
                           membership="Make them a paid or unpaid member?")
    @app_commands.choices(membership=[
        app_commands.Choice(name="Paid member", value="yes"),
        app_commands.Choice(name="Unpaid member", value="no")
    ])
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def update_membership(self, interaction: Interaction,
                                      server_member: discord.Member,
                                      membership: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        try:
            discord_name = server_member.name
            async with self.registry_lock:
                found_cell = self.registry.find(discord_name, in_column=2)
                if found_cell is None:
                    return await interaction.followup.send(content=f"Error: {discord_name} is not registered as a club member.")
                self.registry.update_cell(row=found_cell.row, col=3, value=membership.value)
            paid_unpaid = "paid" if membership.value == "yes" else "unpaid"
            await interaction.followup.send(content=f"Successfully made {discord_name} a {paid_unpaid} member.")
        except Exception as e:
            await interaction.followup.send(content="Error: " + str(e))

    @app_commands.command(name="nodocchi", description=f"Get a Nodocchi link for a given tenhou.net username.")
    @app_commands.describe(tenhou_name="The tenhou.net username to lookup.")
    async def nodocchi(self, interaction: Interaction, tenhou_name: str):
        await interaction.response.send_message(content=f"https://nodocchi.moe/tenhoulog/#!&name={tenhou_name}")

    @app_commands.command(name="amae_koromo", description=f"Get an Amae-Koromo link for a given Mahjong Soul username.")
    @app_commands.describe(majsoul_name="The Mahjong Soul name to lookup.")
    async def amae_koromo(self, interaction: Interaction, majsoul_name: str):
        await interaction.response.defer()
        result = requests.get(url=f"https://5-data.amae-koromo.com/api/v2/pl4/search_player/{majsoul_name}").json()
        if len(result) == 0:
            return await interaction.followup.send(content=f"Error: could not find player {majsoul_name}")
        majsoul_id = result[0]["id"]
        await interaction.followup.send(content=f"https://amae-koromo.sapk.ch/player/{majsoul_id}")

    @app_commands.command(name="submit_game", description=f"Submit a Mahjong Soul club game to the leaderboard. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(lobby="Which lobby is the game in?",
                           link="The Mahjong Soul club game link to submit.")
    @app_commands.choices(lobby=[
        app_commands.Choice(name=YH_NAME, value=YH_NAME),
        app_commands.Choice(name=YT_NAME, value=YT_NAME),
        app_commands.Choice(name=SH_NAME, value=SH_NAME),
        app_commands.Choice(name=ST_NAME, value=ST_NAME)])
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def submit_game(self, interaction: Interaction, lobby: app_commands.Choice[str], link: str):
        await interaction.response.defer(ephemeral=True)
        # extract the uuid from the game link
        if not link.startswith("https://mahjongsoul.game.yo-star.com/?paipu="):
            return await interaction.followup.send(content="Error: expected mahjong soul link starting with \"https://mahjongsoul.game.yo-star.com/?paipu=\".")
        uuid, *player_string = link.split("https://mahjongsoul.game.yo-star.com/?paipu=")[1].split("_a")
        try:
            # we assume that the officer chose the correct `lobby`
            resp = await self.get_cog(lobby.value).add_game_to_leaderboard(uuid)
        except Exception as e:
            return await interaction.followup.send(content="Error: " + str(e))
        await interaction.followup.send(content=f"Successfully submitted {link} to the {lobby.value} leaderboard.\n" + resp, suppress_embeds=True)

    # @app_commands.command(name="info", description=f"Look up a player's club info (e.g. Mahjong Soul ID).")
    # @app_commands.describe(server_member="The player to lookup.")
    # async def info(self, interaction: Interaction, server_member: discord.Member):
    #     await interaction.response.defer()
    #     try:
    #         discord_name = server_member.name
    #         discord_name = server_member.mention
    #         found_cell = self.registry.find(discord_name, in_column=2)
    #         if found_cell is None:
    #             await interaction.followup.send(content=f"Error: {discord_name} is not registered as a club member.")
    #         else
    #             [name, _, paid_membership, majsoul_name, majsoul_friend_code, majsoul_id, *rest] = self.registry.row_values(found_cell.row)
    #             paid_unpaid = "a paid" if paid_membership == "yes" else "an unpaid"
    #             await interaction.followup.send(content=f"{server_member.mention} (MJS: {majsoul_name}, id {majsoul_id}) is {paid_unpaid} member of Longhorn Riichi.")

        # except Exception as e:
        #     await interaction.followup.send(content="Error: " + str(e))


    # @app_commands.command(name="stats", description=f"Look up a player's club stats (e.g. leaderboard placement).")
    # @app_commands.describe(server_member="The player to lookup.")
    # async def stats(self, interaction: Interaction, server_member: discord.Member):
    #     await interaction.response.defer()
    #     try:
    #         discord_name = server_member.name
    #         discord_name = server_member.mention
    #         found_cell = self.registry.find(discord_name, in_column=2)
    #         if found_cell is None:
    #             return await interaction.followup.send(content=f"Error: {discord_name} is not registered as a club member.")

    #         majsoul_name, majsoul_id = 1, 1
    #         num_games_played = 10
    #         placement = 4
    #         max_placement = 10
    #         avg_yonma_placement = 2.5
    #         avg_sanma_placement = 2
    #         await interaction.followup.send(content=
    #              f"{server_member.mention} ({majsoul_name}) (id {majsoul_id}) has played {num_games_played} games "
    #             +f" and is currently number {placement} (out of {max_placement}) on the leaderboard.\n"
    #             + " Average yonma placement is {:.2f}. Average scores:\n".format(avg_yonma_placement)
    #             + " - (Yonma) 1st place: 42000 (25%% of games)\n"
    #             + " - (Yonma) 2nd place: 32000 (25%% of games)\n"
    #             + " - (Yonma) 3rd place: 22000 (25%% of games)\n"
    #             + " - (Yonma) 4th place: 12000 (25%% of games)\n"
    #             + " Average sanma placement is {:.2f}. Average scores:\n".format(avg_sanma_placement)
    #             + " - (Sanma) 1st place: 52000 (33%% of games)\n"
    #             + " - (Sanma) 2nd place: 32000 (33%% of games)\n"
    #             + " - (Sanma) 3rd place: 12000 (33%% of games)")

    #     except Exception as e:
    #         await interaction.followup.send(content="Error: " + str(e))



async def setup(bot: commands.Bot):
    logging.info(f"Loading extension `{Utilities.__name__}`...")
    instance = Utilities(bot)
    await bot.add_cog(instance, guild=discord.Object(id=GUILD_ID))

