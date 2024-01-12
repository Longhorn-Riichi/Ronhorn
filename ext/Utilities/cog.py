import asyncio
import datetime
import discord
import gspread
import logging
import requests
import urllib3
import os
import json
import matplotlib.pyplot as plt
from matplotlib.cbook import get_sample_data
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from io import BytesIO
from discord.ext import commands
from discord import app_commands, Colour, Embed, Interaction, VoiceChannel
from typing import *
from ext.LobbyManagers.cog import LobbyManager
from .display_hand import replace_text
from global_stuff import account_manager, assert_getenv, registry, raw_scores, registry_lock, raw_scores_lock
from modules.InjusticeJudge.injustice_judge.fetch import parse_majsoul_link

GUILD_ID: int                 = int(assert_getenv("guild_id"))
OFFICER_ROLE: str             = assert_getenv("officer_role")
PAID_MEMBER_ROLE_ID: int      = int(assert_getenv("paid_member_role_id"))
PAST_PAID_MEMBER_ROLE_ID: int = int(assert_getenv("past_paid_member_role_id"))
SPREADSHEET_ID: str           = assert_getenv("spreadsheet_url")
YH_TOURNAMENT_ID: str         = assert_getenv("yh_tournament_id")
YT_TOURNAMENT_ID: str         = assert_getenv("yt_tournament_id")
SH_TOURNAMENT_ID: str         = assert_getenv("sh_tournament_id")
ST_TOURNAMENT_ID: str         = assert_getenv("st_tournament_id")
YH_UNIQUE_ID: int             = int(assert_getenv("yh_contest_unique_id"))
YT_UNIQUE_ID: int             = int(assert_getenv("yt_contest_unique_id"))
SH_UNIQUE_ID: int             = int(assert_getenv("sh_contest_unique_id"))
ST_UNIQUE_ID: int             = int(assert_getenv("st_contest_unique_id"))
YH_NAME: str                  = assert_getenv("yh_name")
YT_NAME: str                  = assert_getenv("yt_name")
SH_NAME: str                  = assert_getenv("sh_name")
ST_NAME: str                  = assert_getenv("st_name")
REGISTRY_NAME_LENGTH: int     = int(assert_getenv("max_name_len"))
VOICE_CHANNEL_ID: int         = int(assert_getenv("voice_channel_id"))

class LonghornRiichiUtilities(commands.Cog):
    """
    Utility commands specific to Longhorn Riichi
    """
    def __init__(self, bot: commands.Bot):
        self.player_registry_lock = asyncio.Lock()
        self.bot = bot

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

    @app_commands.command(name="help", description="Learn how to play online club games.")
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

    @app_commands.command(name="help_commands", description="Learn how to use slash commands.")
    async def help_commands(self, interaction: Interaction):
        command_help = [
            "### Registration:",
            "- `/register`: Register your Discord account with the club. Registration is required to show up on the club leaderboard. You must enter a preferred name, and optionally your Mahjong Soul account. Can be used to update your existing registration.",
            "- `/unregister`: Removes your own registration (from `/register`)",
            "### Information:",
            "- `/info`: Look up a player's club info (e.g. Mahjong Soul ID).",
            "- `/stats`: Look up a player's club stats (e.g. leaderboard placement).",
            "- `/parse`: Display a summary of the provided game log link. Has an option to display winning and starting hands.",
            "- `/nodocchi`: Get a Nodocchi link for a given tenhou.net username.",
            "- `/amae_koromo`: Get an Amae-Koromo link for a given Mahjong Soul username.",
            "### Lobby commands:",
            "- `/check_queues`: Checks to see if everyone is queued up in the Mahjong Soul club lobbies. Has an option to check the voice channel for players instead.",
            "- `/start_queued_games`: Start games for everyone queued up in the Mahjong Soul club lobbies.",
            "### In-game commands (do not abuse):",
            "- `/terminate_own_game`: Terminate the game you are currently in.",
            "- `/pause_own_game`: Pause the game you are currently in.",
            "- `/unpause_own_game`: Unpause the paused game you were in.",
            "### Other:",
            "- `/injustice`: Analyze the provided game log link for instances of *mahjong injustice*.",
            "- `/skill`: Analyze the provided game log link for instances of *mahjong skill*.",
            "- `/display`: Write a message, replacing mahjong notation (like 123p 3z3Z3z) with mahjong tile emotes.",
        ]
        green = Colour.from_str("#1EA51E")
        await interaction.response.send_message(
            content="List of commands:", embed=Embed(description="\n".join(command_help), colour=green),
            ephemeral=True)

    @app_commands.command(name="help_officer_commands", description="Learn how to use slash commands (for officers).")
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def help_officer_commands(self, interaction: Interaction):
        command_help = [
            "### Registration:",
            "- `/register_other`: Register a given Discord user.",
            "- `/unregister_other`: Unregister a given Discord user.",
            "- `/update_membership`: Updates a given Discord user's paid membership status.",
            "- `/replace_role`: Remove or replace a provided role for everyone with that role. Used to give <@&1103562892097376308> to all the <@&922743943337218048>s.",
            "### Lobby commands:",
            "- `/toggle_auto_match`: Enable or disable auto-matching for a given lobby.",
            "### In-game commands:",
            "- `/terminate_any_game`: Terminate the game a given player is in.",
            "- `/pause_any_game`: Pause the game a given player is in.",
            "- `/unpause_any_game`: Unpause the game a given player is in.",
            "### Submitting games:",
            "- `/enter_scores`: Submit an IRL game to the leaderboard, given the scores of each player. If the given scores don't total up to the expected total score, the submission is rejected.",
            "- `/submit_game`: Submit an online game to the leaderboard, given a link to the game's log.",
        ]
        green = Colour.from_str("#1EA51E")
        await interaction.response.send_message(
            content="List of officer commands:", embed=Embed(description="\n".join(command_help), colour=green),
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
        
    @app_commands.command(name="test_command", description=f"Test command")
    async def test_command(self, interaction: Interaction, server_member: discord.Member):
        await interaction.response.send_message(server_member.discriminator == "0")
    
    def get_discord_name(self, member: discord.Member) -> str:
        discord_name = member.name
        # add "#1234" if it exists
        if member.discriminator != "0":
            discord_name += "#" + member.discriminator
        return discord_name

    async def _register(self, name: str, server_member: discord.Member, friend_id: Optional[int]) -> str:
        """
        Add player to the registry, removing any existing registration first.
        Assumes input is already sanitized (e.g., `name` isn't 200 chars long)
        Raise exceptions if the friend ID is invalid.
        Returns the response string.
        """
        paid_membership = "no"
        discord_name = self.get_discord_name(server_member)
        
        existing_friend_id: Optional[int] = None
        mahjongsoul_nickname = None
        mahjongsoul_account_id = None
        async with registry_lock:
            assert registry is not None
            # Delete any existing registration
            found_cell: gspread.cell.Cell = registry.find(discord_name, in_column=2)
            cell_existed = found_cell is not None
            if cell_existed:
                [_, _, paid_membership, *mahjongsoul_fields] = registry.row_values(found_cell.row)
                if mahjongsoul_fields:
                    [mahjongsoul_nickname, existing_friend_id, mahjongsoul_account_id] = mahjongsoul_fields
                    assert existing_friend_id is not None, "There are Mahjong Soul fields in the existing registry entry, but no Friend ID??"
                    existing_friend_id = int(existing_friend_id)
                registry.delete_row(found_cell.row)
        
        if friend_id is None:
            friend_id = existing_friend_id
        elif friend_id != existing_friend_id:
            assert account_manager is not None
            result = await account_manager.get_account(friend_id)
            if result is None:
                raise Exception(f"Couldn't find Mahjong Soul account for this friend ID: {friend_id}")
            mahjongsoul_nickname = result[0]
            mahjongsoul_account_id = result[1]

        data = [name,
                discord_name,
                paid_membership,
                mahjongsoul_nickname,
                friend_id,
                mahjongsoul_account_id]

        async with registry_lock:
            registry.append_row(data)
        
        register_string = "updated registration" if cell_existed else "registered"

        if friend_id is None:
            mjsoul_string = f" without a Mahjong Soul account"
        elif friend_id == existing_friend_id:
            mjsoul_string = f" with the same Friend ID as before"
        else:
            mjsoul_string = f" and Mahjong Soul account \"{mahjongsoul_nickname}\""
        
        return f"\"{discord_name}\" {register_string} with name \"{name}\"{mjsoul_string}."
    
    @app_commands.command(name="register", description="Register with your name and Mahjong Soul friend ID, or update your current registration.")
    @app_commands.describe(
        real_name=f"Your preferred, real-life name (no more than {REGISTRY_NAME_LENGTH} characters)",
        friend_id="(optional) Mahjong Soul friend ID. Find it in the Friends tab; this is not your username.")
    async def register(self, interaction: Interaction, real_name: str, friend_id: Optional[int] = None):
        await interaction.response.defer()
        if len(real_name) > REGISTRY_NAME_LENGTH:
            await interaction.response.send_message(f"Please keep your preferred name within {REGISTRY_NAME_LENGTH} characters and `/register` again.", ephemeral=True)
            return
        assert isinstance(interaction.user, discord.Member)
        try:
            response = await self._register(real_name, interaction.user, friend_id)
            await interaction.followup.send(content=response)
        except Exception as e:
            await interaction.followup.send(content=str(e))

    @app_commands.command(name="register_other", description=f"Register the given server member. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(
        server_member="The server member you want to register.",
        real_name=f"The given member's preferred, real-life name (no more than {REGISTRY_NAME_LENGTH} characters)",
        friend_id="(optional) Mahjong Soul friend ID. Find it in the Friends tab; this is not your username.")
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def register_other(self, interaction: Interaction, server_member: discord.Member, real_name: str, friend_id: Optional[int] = None):
        await interaction.response.defer()
        response = await self._register(real_name, server_member, friend_id)
        await interaction.followup.send(content=response)

    async def _unregister(self, server_member: discord.Member) -> str:
        discord_name = self.get_discord_name(server_member)
        async with registry_lock:
            found_cell: gspread.cell.Cell = registry.find(discord_name, in_column=2)
            if found_cell is None:
                return f"\"{discord_name}\" is not a registered member."
            else:
                registry.delete_row(found_cell.row)
                return f"\"{discord_name}\"'s registration has been removed."

    @app_commands.command(name="unregister", description="Remove your registered information.")
    async def unregister(self, interaction: Interaction):
        await interaction.response.defer()
        assert isinstance(interaction.user, discord.Member)
        response = await self._unregister(interaction.user)
        await interaction.followup.send(content=response)

    @app_commands.command(name="unregister_other", description=f"Unregister the given server member. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(server_member="The server member you want to unregister.")
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def unregister_other(self, interaction: Interaction, server_member: discord.Member):
        await interaction.response.defer()
        response = await self._unregister(server_member)
        await interaction.followup.send(content=response)


    async def _get_queued_players(self, lobby):
        # get all queued players
        players = list((await self.get_cog(lobby).manager.call("fetchContestMatchingPlayer")).players)

        # # debug
        # make_ai = lambda: self.get_cog(lobby).manager.proto.ContestPlayerInfo(account_id=0, nickname="")
        # for _ in range(12 - len(players)):
        #     players.append(make_ai())

        # shuffle players before returning
        import random
        random.shuffle(players)
        return players

    def _split_queued_players(self, players, excluded=[]):
        import random
        random.shuffle(players)
        num = len(players)
        player_names = [player if isinstance(player, str) else (player.nickname or 'AI') for player in players]
        player_names = [name for name in player_names if name not in excluded]
        if len(player_names) == 0:
            return "No players are looking to play!", ""
        overflow = (num%4) or 4
        yonma = ((num-1) // 4) + (overflow - 3)
        sanma = 4 - overflow
        if yonma < 0 or sanma < 0 or (yonma + sanma == 0): # when num = 0, 1, 2, 5
            return f"Unable to split {num } player{'' if num == 1 else 's'} into yonma/sanma tables.", ""

        # ask players to queue up
        header = f"{num} players can be split into"
        header += f" {yonma} yonma table{'' if yonma == 1 else 's'} and"
        header += f" {sanma} sanma table{'' if sanma == 1 else 's'}. Possible assignment:"
        name_list_to_str = lambda name_list: ', '.join(name for name in name_list if name not in excluded)
        msg = f"- **Yonma Hanchan ({YH_TOURNAMENT_ID})**: {name_list_to_str(player_names[:yonma*4])}\n"
        msg += f"- **Sanma Hanchan ({SH_TOURNAMENT_ID})**: {name_list_to_str(player_names[yonma*4:])}\n"
        return header, msg

    @app_commands.command(name="check_queues", description=f"Check to see if everyone is queued up on Mahjong Soul.")
    @app_commands.describe(
        check_voice_channel="Whether to check the voice channel for players instead.",
        exclude1="A player who wishes to not be included in the check.",
        exclude2="A player who wishes to not be included in the check.",
        exclude3="A player who wishes to not be included in the check.",
        exclude4="A player who wishes to not be included in the check.")
    async def check_queues(self, interaction: Interaction, check_voice_channel: Optional[bool],
            exclude1: Optional[discord.User], exclude2: Optional[discord.User],
            exclude3: Optional[discord.User], exclude4: Optional[discord.User]):
        await interaction.response.defer()
        yh_players = await self._get_queued_players(YH_NAME)
        yt_players = await self._get_queued_players(YT_NAME)
        sh_players = await self._get_queued_players(SH_NAME)
        st_players = await self._get_queued_players(ST_NAME)
        excluded = [e.name for e in (exclude1, exclude2, exclude3, exclude4) if e is not None]

        header = ""
        msg = ""
        if check_voice_channel == True:
            voice_channel = await self.bot.fetch_channel(VOICE_CHANNEL_ID)
            assert isinstance(voice_channel, VoiceChannel)
            if len(voice_channel.members) == 0:
                header = "Nobody is currently in the voice channel!"
            else:
                # otherwise, partition everyone up into tables and give a suggestion of who goes where
                header, msg = self._split_queued_players([member.name for member in voice_channel.members], excluded)
        elif len(yh_players) + len(yt_players) + len(sh_players) + len(st_players) == 0:
            header = "Nobody is currently queued in any lobby!"
        elif len(yh_players) % 4 == len(yt_players) % 4 == len(sh_players) % 3 == len(st_players) % 3 == 0:
            # there's enough players queued up in yonma/sanma to just start all the games
            header = f"Each lobby has a correct number of players, start with `/start_queued_games`!"
            for players, lobby, lobby_id in \
                    [(yh_players, YH_NAME, YH_TOURNAMENT_ID), (yt_players, YT_NAME, YT_TOURNAMENT_ID),
                     (sh_players, SH_NAME, SH_TOURNAMENT_ID), (st_players, ST_NAME, ST_TOURNAMENT_ID)]:
                if len(players) > 0:
                    msg += f"- **{lobby} ({lobby_id})**: {', '.join(p.nickname or 'AI' for p in players)}\n"
        else:
            # otherwise, partition everyone up into tables and give a suggestion of who goes where
            header, msg = self._split_queued_players(yh_players + yt_players + sh_players + st_players)

        if len(msg) > 0:
            green = Colour.from_str("#1EA51E")
            await interaction.followup.send(content=header, embed=Embed(description=msg, colour=green))
        else:
            await interaction.followup.send(content=header)

    @app_commands.command(name="start_queued_games", description=f"Start games for everyone queued up in the Mahjong Soul club lobbies.")
    async def start_queued_games(self, interaction: Interaction):
        await interaction.response.defer()
        yh_players = await self._get_queued_players(YH_NAME)
        yt_players = await self._get_queued_players(YT_NAME)
        sh_players = await self._get_queued_players(SH_NAME)
        st_players = await self._get_queued_players(ST_NAME)

        header = ""
        msg = ""
        if len(yh_players) + len(yt_players) + len(sh_players) + len(st_players) == 0:
            header = "Nobody is currently queued in any lobby!"

        # determine if there's enough players queued up in yonma/sanma to just start all the games
        elif len(yh_players) % 4 == len(yt_players) % 4 == len(sh_players) % 3 == len(st_players) % 3 == 0:
            # create games corresponding to those tables
            num_tables = 0
            for num_players, players, lobby, lobby_id in \
                    [(4, yh_players, YH_NAME, YH_TOURNAMENT_ID), (4, yt_players, YT_NAME, YT_TOURNAMENT_ID),
                     (3, sh_players, SH_NAME, SH_TOURNAMENT_ID), (3, st_players, ST_NAME, ST_TOURNAMENT_ID)]:
                if len(players) > 0:
                    for i in range(len(players) // num_players):
                        num_tables += 1
                        table = players[i*num_players:(i+1)*num_players]
                        await self.get_cog(lobby).manager.start_game(account_ids=[p.account_id for p in table])
                        msg += f"- **Table {num_tables}** ({lobby} {lobby_id}): {', '.join(p.nickname or 'AI' for p in table)}\n"
            header = f"Created the following table{'' if num_tables == 1 else 's'}:"
        else:
            # otherwise, partition everyone up into tables and give a suggestion of who goes where
            header, msg = self._split_queued_players(yh_players + yt_players + sh_players + st_players)

        if len(msg) > 0:
            green = Colour.from_str("#1EA51E")
            await interaction.followup.send(content=header, embed=Embed(description=msg, colour=green))
        else:
            await interaction.followup.send(content=header)

    async def _toggle_auto_match(self, lobby_name: str, enabled: bool):
        await self.get_cog(lobby_name).manager.call("updateContestGameRule", auto_match=enabled)

    @app_commands.command(name="toggle_auto_match", description=f"Enable or disable auto-matching for a given lobby. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(
        lobby="Which lobby do you want to configure?",
        enabled="True if you want to enable auto matching")
    @app_commands.choices(lobby=[
        app_commands.Choice(name=YH_NAME, value=YH_NAME),
        app_commands.Choice(name=YT_NAME, value=YT_NAME),
        app_commands.Choice(name=SH_NAME, value=SH_NAME),
        app_commands.Choice(name=ST_NAME, value=ST_NAME)])
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def toggle_auto_match(self, interaction: Interaction, lobby: app_commands.Choice[str], enabled: bool):
        await interaction.response.defer()
        await self._toggle_auto_match(lobby.value, enabled)
        contest = (await self.get_cog(lobby.value).manager.call("fetchContestInfo")).contest
        assert contest is not None
        if contest.auto_match == enabled:
            await interaction.followup.send(content=f"Successfully {'enabled' if enabled else 'disabled'} auto-matching for {lobby.value}.")
        else:
            await interaction.followup.send(content=f"Failed to {'enable' if enabled else 'disable'} auto-matching for {lobby.value}.")

    @app_commands.command(name="enter_scores", description=f"Enter scores for an IRL game. Will check if points add up. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(game_type="Hanchan or tonpuu?",
                           east_player="The East player you want to record the score for.",
                           east_score="The East player's score.",
                           south_player="The South player you want to record the score for.",
                           south_score="The South player's score.",
                           west_player="The West player you want to record the score for.",
                           west_score="The West player's score.",
                           north_player="The (optional) North player you want to record the score for.",
                           north_score="The North player's score.",
                           riichi_sticks="(optional) Number of riichi sticks left on the table.")
    @app_commands.choices(game_type=[
        app_commands.Choice(name="Hanchan", value="Hanchan"),
        app_commands.Choice(name="Tonpuu", value="Tonpuu")
    ])
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def enter_scores(self, interaction: Interaction,
                                 game_type: app_commands.Choice[str],
                                 east_player: discord.Member, east_score: int,
                                 south_player: discord.Member, south_score: int,
                                 west_player: discord.Member, west_score: int,
                                 north_player: Optional[discord.Member] = None, north_score: Optional[int] = None,
                                 riichi_sticks: int = 0):
        await interaction.response.defer()
        try:
            if north_player is None:
                expected_total = 3*35000
                players = [east_player, south_player, west_player]
                scores = [east_score, south_score, west_score]
                game_style = "Sanma"
            else:
                if north_score is None:
                    return await interaction.followup.send(content=f"Error: must enter North player's score for a yonma game.")
                assert north_score is not None
                expected_total = 4*25000
                players = [east_player, south_player, west_player, north_player]
                scores = [east_score, south_score, west_score, north_score]
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
            async with raw_scores_lock:
                raw_scores.append_row([timestamp, gamemode, "yes", *map(str, flatten(ordered_players))])

            player_score_strings = list(flatten(map(lambda p: (p[0].mention, str(p[1])), ordered_players)))
            score_printout = f"Successfully entered scores for a {gamemode} game:\n" \
                              "- **1st**: {}: {}\n" \
                              "- **2nd**: {}: {}\n" \
                              "- **3rd**: {}: {}"
            if north_player is not None:
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
        discord_name = self.get_discord_name(server_member)
        async with registry_lock:
            found_cell = registry.find(discord_name, in_column=2)
            if found_cell is None:
                return await interaction.followup.send(content=f"Error: {discord_name} is not registered as a club member.")
            registry.update_cell(row=found_cell.row, col=3, value=membership.value)
        if membership.value == "yes":
            await server_member.add_roles(discord.Object(PAID_MEMBER_ROLE_ID))
            await interaction.followup.send(content=f"Updated {discord_name} to be a paid member.")
        else:
            await server_member.remove_roles(discord.Object(PAID_MEMBER_ROLE_ID))
            await interaction.followup.send(content=f"Revoked {discord_name}'s paid membership status.")
    
    @app_commands.command(name="replace_role", description=f"Remove/replace a role from everyone. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(old_role="The role to be removed/replaced",
                           new_role="The new role to replace the old one with")
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def replace_role(self, interaction: Interaction, old_role: discord.Role, new_role: Optional[discord.Role]):
        """
        This is good for scenarios like replacing @Paid Member with @Past Paid Member
        """
        await interaction.response.defer(ephemeral=True)
        if new_role is None:
            for member in old_role.members:
                await member.remove_roles(old_role)
            await interaction.followup.send(content=f"Removed the role `@{old_role}` from everyone.")
        else:
            for member in old_role.members:
                await member.remove_roles(old_role)
                await member.add_roles(new_role)
            await interaction.followup.send(content=f"Replaced the role `@{old_role}` with `@{new_role}` for everyone.")

    async def _submit_game(self, interaction: Interaction, link: str) -> str:
        # extract the uuid from the game link
        try:
            uuid = parse_majsoul_link(link)[0]
        except:
            await interaction.followup.send(content="Error: expected mahjong soul link starting with \"https://mahjongsoul.game.yo-star.com/?paipu=\".")
            return ""
        try:
            # get the game record
            record_list = await account_manager.get_game_results([uuid])
            if len(record_list) == 0:
                raise Exception("A game concluded without a record (possibly due to being terminated early).")
            record = record_list[0]
            # figure out which lobby the game was played in
            contest_uid = record.config.meta.contest_uid
            uid_to_name = {YH_UNIQUE_ID: YH_NAME, YT_UNIQUE_ID: YT_NAME, SH_UNIQUE_ID: SH_NAME, ST_UNIQUE_ID: ST_NAME}
            if contest_uid not in uid_to_name.keys():
                raise Exception(f"/submit_game was given a game which wasn't played in our lobby. (uid={contest_uid})\n{link}")
            resp = await self.get_cog(uid_to_name[contest_uid]).add_game_to_leaderboard(uuid, record)
        except Exception as e:
            await interaction.followup.send(content="Error: " + str(e))
            return ""
        return f"Successfully submitted the game to {uid_to_name[contest_uid]} leaderboard.\n" + resp

    @app_commands.command(name="submit_game", description=f"Submit a Mahjong Soul club game to the leaderboard. Only usable by @{OFFICER_ROLE}.")
    @app_commands.describe(link1="A Mahjong Soul club game link to submit.",
                           link2="A Mahjong Soul club game link to submit.",
                           link3="A Mahjong Soul club game link to submit.",
                           link4="A Mahjong Soul club game link to submit.")
    @app_commands.checks.has_role(OFFICER_ROLE)
    async def submit_game(self, interaction: Interaction, link1: str, link2: Optional[str], link3: Optional[str], link4: Optional[str]):
        await interaction.response.defer()
        # extract the uuid from the game link
        for i, link in enumerate((link1, link2, link3, link4)):
            if link is not None:
                resp = await self._submit_game(interaction, link)
                if i == 0:
                    await interaction.followup.send(content=resp, suppress_embeds=True)  # type: ignore[union-attr]
                else:
                    await interaction.channel.send(content=resp, suppress_embeds=True)  # type: ignore[union-attr]

    # @app_commands.command(name="info", description=f"Look up a player's club info (e.g. Mahjong Soul ID).")
    # @app_commands.describe(server_member="The player to lookup.")
    # async def info(self, interaction: Interaction, server_member: discord.Member):
    #     await interaction.response.defer(ephemeral=True)
    #     try:
    #         discord_name = self.get_discord_name(server_member)
    #         discord_name = server_member.mention
    #         found_cell = registry.find(discord_name, in_column=2)
    #         if found_cell is None:
    #             await interaction.followup.send(content=f"Error: {discord_name} is not registered as a club member.")
    #         else
    #             [name, _, paid_membership, *mahjongsoul_fields] = registry.row_values(found_cell.row)
    #                if mahjongsoul_fields is not None:
    #                    [mahjongsoul_nickname, _, _] = mahjongsoul_fields
    #             paid_unpaid = "a paid" if paid_membership == "yes" else "an unpaid"
    #             await interaction.followup.send(content=f"{server_member.mention} (MJS: {mahjongsoul_nickname}, id {majsoul_id}) is {paid_unpaid} member of Longhorn Riichi.")

        # except Exception as e:
        #     await interaction.followup.send(content="Error: " + str(e))


    # @app_commands.command(name="stats", description=f"Look up a player's club stats (e.g. leaderboard placement).")
    # @app_commands.describe(server_member="The player to lookup.")
    # async def stats(self, interaction: Interaction, server_member: discord.Member):
    #     await interaction.response.defer()
    #     try:
    #         discord_name = self.get_discord_name(server_member)
    #         discord_name = server_member.mention
    #         found_cell = registry.find(discord_name, in_column=2)
    #         if found_cell is None:
    #             return await interaction.followup.send(content=f"Error: {discord_name} is not registered as a club member.")

    #         mahjongsoul_nickname, majsoul_id = 1, 1
    #         num_games_played = 10
    #         placement = 4
    #         max_placement = 10
    #         avg_yonma_placement = 2.5
    #         avg_sanma_placement = 2
    #         await interaction.followup.send(content=
    #              f"{server_member.mention} ({mahjongsoul_nickname}) (id {majsoul_id}) has played {num_games_played} games "
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

class GlobalUtilities(commands.Cog):
    """
    Utility commands that are applicable in- and outside Longhorn Riichi
    """
    # def __init__(self, bot: commands.Bot):
    #     self.bot = bot

    """
    =====================================================
    SLASH COMMANDS
    =====================================================
    """

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

    @app_commands.command(name="display", description=f"Write a message, replacing mahjong notation (like 123p 3z3Z3z) with mahjong tile emotes.")
    @app_commands.describe(text="The text containing mahjong tiles to display")
    async def display(self, interaction: Interaction, text: str):
        await interaction.response.send_message(replace_text(text))

    @app_commands.command(name="register_stats", description=f"Register your (Mahjong Soul, tenhou.net, Riichi City) id for /stats.")
    @app_commands.describe(majsoul_friend_code="Mahjong Soul friend code to register.",
                           # tenhou_name="tenhou.net username to register.",
                           riichicity_name="Riichi City username to register. (case-insensitive)",
                           riichicity_friend_code="Alternatively, register with Riichi City friend code.",
                           )
    async def register_stats(self, interaction: Interaction,
                                   majsoul_friend_code: Optional[int],
                                   # tenhou_name: Optional[str],
                                   riichicity_name: Optional[str],
                                   riichicity_friend_code: Optional[int]):
        await interaction.response.defer(ephemeral=True)
        tenhou_name = None # no way to get tenhou stats outside of nodocchi so we will ignore tenhou.net
        async with registry_lock:
            if not os.path.isfile("player_registry.json"):
                registry = {}
            with open("player_registry.json", "rb") as file:
                registry = json.load(file)
            discord_name = interaction.user.name
            if discord_name not in registry:
                registry[discord_name] = {}

            updated = {}
            if majsoul_friend_code is not None:
                assert account_manager is not None
                result = await account_manager.get_account(majsoul_friend_code)
                if result is None:
                    raise Exception(f"Invalid Mahjong soul friend code {majsoul_friend_code}")
                registry[discord_name]["ms_name"] = result[0]
                registry[discord_name]["ms_id"] = result[1]
                registry[discord_name]["ms_friendcode"] = majsoul_friend_code
                updated["Mahjong Soul"] = registry[discord_name]["ms_name"]
            if tenhou_name is not None:
                registry[discord_name]["tenhou_name"] = tenhou_name
                updated["tenhou.net"] = registry[discord_name]["tenhou_name"]
            if riichicity_name is not None or riichicity_friend_code is not None:
                query = str(riichicity_friend_code) if riichicity_friend_code is not None else riichicity_name
                SID = os.getenv("rc_sid")
                assert SID is not None
                results = requests.post(
                    url="http://13.112.183.79/mixed_client/findFriend",
                    headers={
                        "Cookies": "{\"sid\":\"" + SID + "\"}",
                        "User-Agent": urllib3.util.SKIP_HEADER,  # type: ignore[attr-defined]
                        "Accept-Encoding": urllib3.util.SKIP_HEADER,  # type: ignore[attr-defined]
                        "Connection": "close",
                    },
                    data="{\"findType\":2,\"content\":\"" + query + "\"}").json()
                if results["code"] != 0:
                    raise Exception(f"Error {results['code']}: {results['message']}")
                registry[discord_name]["rc_name"] = results["data"]["friendList"][0]["nickname"]
                registry[discord_name]["rc_friendcode"] = results["data"]["friendList"][0]["userID"]
                updated["Riichi City"] = registry[discord_name]["rc_name"]
            with open("player_registry.json", "wb") as file:
                file.write(json.dumps(registry, ensure_ascii=False).encode("utf-8"))

        out_header = f"Updated your registration for {' and '.join(updated.keys())}:"
        green = Colour.from_str("#1EA51E")
        embed = Embed(description="Registered accounts:", colour=green)
        for k, v in {"Mahjong Soul": "ms_name", "tenhou.net": "tenhou_name", "Riichi City": "rc_name"}.items():
            if v in registry[discord_name]:
                embed.add_field(name=f"**{k}**", value=registry[discord_name][v], inline=True)
        await interaction.followup.send(content=out_header, embed=embed)

    def draw_ms_trendline(self, data):
        plt.rcParams["font.size"] = 36
        plt.rcParams["text.color"] = "orange"
        plt.rcParams["xtick.color"] = "gray"
        plt.rcParams["ytick.color"] = "gray"
        data = [(3, False), (1, True), (4, False), (2, False), (2, False), (2, False), (3, False), (2, False), (4, False), (2, False)]
        plt.figure(figsize=(20, 4))
        plt.plot(range(10), [rank for rank, _ in data], marker="o", markersize=28, color="orange", linestyle="-", linewidth=8)

        fn = get_sample_data(os.path.join(os.getcwd(), "images/sunglasses_cat.png"), asfileobj=False)
        ax = plt.gca()
        sunglasses_cat = OffsetImage(plt.imread(fn, format='png'), zoom=0.15)
        for x, (rank, sunglasses) in zip(range(10), data):
            if sunglasses:
                ax.add_artist(AnnotationBbox(sunglasses_cat, (x, rank), frameon=False, box_alignment=(0.5, 0.5)))

        ax.invert_yaxis()
        plt.yticks(range(1, 5), ["1st", "2nd", "3rd", "4th"])
        plt.ylim(4.5, 0.5)
        plt.grid(axis="y")
        plt.tick_params(axis="x", which="both", bottom=False, top=False, labelbottom=False)
        plt.box(False)
        plt.tight_layout()

        # return as a BytesIO object
        buf = BytesIO()
        plt.savefig(buf, format="png", transparent=True, bbox_inches="tight")
        buf.seek(0)
        plt.cla()
        plt.clf()
        return buf

    @app_commands.command(name="ms_stats", description=f"Fetch Mahjong Soul stats for yourself or someone else.")
    @app_commands.describe(game_type="Game type to display stats for.",
                           user="(optional) Discord user to display stats for (if they've registered their Mahjong Soul account)",
                           majsoul_name="(optional) The Mahjong Soul name to lookup. Must have games played in Gold room or higher")
    @app_commands.choices(game_type=[
        app_commands.Choice(name="Yonma Hanchan", value="Yonma Hanchan"),
        app_commands.Choice(name="Yonma Tonpuu", value="Yonma Tonpuu"),
        app_commands.Choice(name="Sanma Hanchan", value="Sanma Hanchan"),
        app_commands.Choice(name="Sanma Tonpuu", value="Sanma Tonpuu")])
    async def ms_stats(self, interaction: Interaction, game_type: app_commands.Choice[str], user: Optional[discord.Member], majsoul_name: Optional[str]):
        await interaction.response.defer()
        majsoul_id = None
        if user is None and majsoul_name is not None:
            result = requests.get(url=f"https://5-data.amae-koromo.com/api/v2/pl4/search_player/{majsoul_name}").json()
            if len(result) == 0:
                return await interaction.followup.send(content=f"Error: could not find player {majsoul_name}")
            majsoul_id = result[0]["id"]
        if user is None:
            assert isinstance(interaction.user, discord.Member)
            user = interaction.user
        if majsoul_id is None:
            async with registry_lock:
                if not os.path.isfile("player_registry.json"):
                    registry = {}
                with open("player_registry.json", "rb") as file:
                    registry = json.load(file)
                majsoul_name = registry[user.name]["ms_name"]
                majsoul_id = registry[user.name]["ms_id"]
        assert majsoul_name is not None
        assert majsoul_id is not None

        assert account_manager is not None
        stats = await account_manager.get_stats(majsoul_id)
        trendline_key = "Yonma recents" if "Yonma" in game_type.value else "Sanma recents"
        trendline = discord.File(fp=self.draw_ms_trendline(stats[trendline_key]), filename=f"trendline.png")

        green = Colour.from_str("#1EA51E")
        embed = Embed(title=f"**{game_type.value}** stats for Mahjong Soul player **{majsoul_name}**", colour=green)
        embed.set_image(url='attachment://trendline.png')

        if game_type.value in stats:
            for k, v in stats[game_type.value].items():
                embed.add_field(name=k, value=v, inline=True)
            await interaction.followup.send(file=trendline, embed=embed)
        else:
            await interaction.followup.send(content=f"{majsoul_name} has no {game_type.value} games on record.")

    def get_riichicity_stats(self, riichicity_id: int, game_type: str) -> Dict[str, Any]:
        SID = os.getenv("rc_sid")
        assert SID is not None
        num_rounds = 1 if "Tonpuu" in game_type else 2
        player_count = 3 if "Sanma" in game_type else 4
        results = requests.post(
            url="http://13.112.183.79/stats/userDetailStatsV2",
            headers={
                "Cookies": "{\"sid\":\"" + SID + "\"}",
                "User-Agent": urllib3.util.SKIP_HEADER,  # type: ignore[attr-defined]
                "Accept-Encoding": urllib3.util.SKIP_HEADER,  # type: ignore[attr-defined]
                "Connection": "close",
            },
            data="{\"gameplay\":1001,\"dataType\":0,\"stageType\":[1,2,3,4],\"playerCount\":" + str(player_count) + ",\"userID\":" + str(riichicity_id) + ",\"round\":[" + str(num_rounds) + "]}").json()
        if results["code"] != 0:
            raise Exception(f"Error {results['code']}: {results['message']}")

        import numpy
        m = results["data"][0]
        stats = {}
        stats["Total games"] = m["totalEndTimes"]
        placements_raw = [m[p + "Times"] for p in ["first", "second", "third", "fourth"]]
        placements = [round(100 * p / m["totalEndTimes"], 2) for p in placements_raw]
        stats["Avg score"] = round(m["huTotalScore"] / m["huTotalCount"])
        stats["Avg rank"] = round(numpy.average([1,2,3,4], weights=placements), 2)
        stats["Win rate"] = str(round(100 * m["huTotalCount"]/m["gameCount"], 2)) + "%"
        stats["Tsumo rate"] = str(round(100 * m["ziMoCount"]/m["huTotalCount"], 2)) + "%"
        stats["Deal-in rate"] = str(round(100 * m["chongTotalCount"]/m["gameCount"], 2)) + "%"
        stats["Call rate"] = str(round(100 * m["existFuLouCount"]/m["gameCount"], 2)) + "%"
        stats["Riichi rate"] = str(round(100 * m["existLiZhiCount"]/m["gameCount"], 2)) + "%"
        return stats

    @app_commands.command(name="rc_stats", description=f"Fetch Riichi City stats for yourself or someone else.")
    @app_commands.describe(game_type="Game type to display stats for.",
                           user="(optional) Discord user to display stats for (if they've registered their Riichi City account)")
    @app_commands.choices(game_type=[
        app_commands.Choice(name="Yonma Hanchan", value="Yonma Hanchan"),
        app_commands.Choice(name="Yonma Tonpuu", value="Yonma Tonpuu"),
        app_commands.Choice(name="Sanma Hanchan", value="Sanma Hanchan"),
        app_commands.Choice(name="Sanma Tonpuu", value="Sanma Tonpuu")])
    async def rc_stats(self, interaction: Interaction, game_type: app_commands.Choice[str], user: Optional[discord.Member], majsoul_name: Optional[str]):
        await interaction.response.defer()
        riichicity_id = None
        if user is None:
            assert isinstance(interaction.user, discord.Member)
            user = interaction.user
        if riichicity_id is None:
            async with registry_lock:
                if not os.path.isfile("player_registry.json"):
                    registry = {}
                with open("player_registry.json", "rb") as file:
                    registry = json.load(file)
                riichicity_name = registry[user.name]["rc_name"]
                riichicity_id = registry[user.name]["rc_friendcode"]
        assert riichicity_name is not None
        assert riichicity_id is not None

        stats = self.get_riichicity_stats(riichicity_id, game_type.value)

        green = Colour.from_str("#1EA51E")
        embed = Embed(title=f"**{game_type.value}** stats for Riichi City player **{riichicity_name}**", colour=green)
        for k, v in stats.items():
            embed.add_field(name=k, value=v, inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="display", description=f"Write a message, replacing mahjong notation (like 123p 3z3Z3z) with mahjong tile emotes.")
    @app_commands.describe(text="The text containing mahjong tiles to display")
    async def display(self, interaction: Interaction, text: str):
        await interaction.response.send_message(replace_text(text))

async def setup(bot: commands.Bot):
    logging.info(f"Loading cog `{LonghornRiichiUtilities.__name__}`...")
    await bot.add_cog(LonghornRiichiUtilities(bot), guild=discord.Object(id=GUILD_ID))

    logging.info(f"Loading cog `{GlobalUtilities.__name__}`...")
    with open('slash_commands_servers.json', 'r') as file:
        slash_commands_servers = json.load(file)
    slash_commands_guilds = [discord.Object(id=id) for id in slash_commands_servers.values()]
    await bot.add_cog(GlobalUtilities(bot), guilds=slash_commands_guilds)

