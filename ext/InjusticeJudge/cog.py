import discord
import logging
import os
from discord.ext import commands
from discord import app_commands, Interaction
from typing import *
from modules.mahjongsoul.account_manager import AccountManager
from modules.InjusticeJudge.injustice_judge.fetch import fetch_tenhou, parse_tenhou, parse_majsoul
from modules.InjusticeJudge.injustice_judge.injustices import evaluate_injustices
from modules.pymjsoul.proto import liqi_combined_pb2 as proto

def assert_getenv(name: str) -> str:
    value = os.getenv(name)
    assert value is not None, f"missing \"{name}\" in config.env"
    return value

BOT_CHANNEL_ID: int        = int(assert_getenv("bot_channel_id"))
GUILD_ID: int              = int(assert_getenv("guild_id"))

class InjusticeJudge(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        assert(isinstance(bot.account_manager, AccountManager))
        self.account_manager = bot.account_manager

    """
    =====================================================
    SLASH COMMANDS
    =====================================================
    """

    @app_commands.command(name="injustice", description="Display the injustices in a given game.")
    @app_commands.describe(game_link="The game link to analyze (either Mahjong Soul or tenhou.net)",
                           player="(optional) The seat to analyze the game from. Determined using the link, but defaults to East.")
    @app_commands.choices(player=[
        app_commands.Choice(name="East", value=0),
        app_commands.Choice(name="South", value=1),
        app_commands.Choice(name="West", value=2),
        app_commands.Choice(name="North", value=3)])
    async def injustice(self, interaction: Interaction, game_link: str, player: Optional[app_commands.Choice[int]]):
        await interaction.response.defer()
        if player is not None:
            injustices = await self.analyze_game(game_link, player.value)
        else:
            injustices = await self.analyze_game(game_link)
        if injustices == []:
            injustices = ["No injustices detected."]
        as_player_string = "yourself" if player is None else player.name
        await interaction.followup.send(content=f"Analyzing {game_link} for {as_player_string}:\n" + "\n".join(injustices), suppress_embeds=True)

    """
    =====================================================
    Modified InjusticeJudge Functions
    =====================================================
    """
    
    async def analyze_game(self, link: str, specified_player = None) -> List[str]:
        """
        basically the same as the exposed `analyze_game()` of the InjusticeJudge,
        but with the `fetch_majsoul` part substituted out so we can use our own
        AccountManager (to avoid logging in for each fetch)
        """
        # print(f"Analyzing game {link}:")
        kyokus = []
        if link.startswith("https://tenhou.net/0/?log="):
            tenhou_log, player = fetch_tenhou(link)
            for raw_kyoku in tenhou_log:
                kyoku = parse_tenhou(raw_kyoku)
                kyokus.append(kyoku)
        elif link.startswith("https://mahjongsoul.game.yo-star.com/?paipu="):
            majsoul_log, player = await self.fetch_majsoul(link)
            kyokus = parse_majsoul(majsoul_log)
        else:
            raise Exception("expected tenhou link starting with https://tenhou.net/0/?log="
                            " or mahjong soul link starting with https://mahjongsoul.game.yo-star.com/?paipu=")
        if specified_player is not None:
            player = specified_player
        return [injustice for kyoku in kyokus for injustice in evaluate_injustices(kyoku, player)]
    
    async def fetch_majsoul(self, link: str):
        """
        NOTE:
        basically the same as InjusticeJudge's `fetch_majsoul()`, with 2 differences;
        1. Instead of logging in for each fetch, just fetch through the already logged-in
        AccountManager.
        2. save and read the Mahjong Soul game log cache from this extension's directory,
        instead of the submodule's directory. This also means 2 GB total cache instead of
        1 GB.
        """
        assert link.startswith("https://mahjongsoul.game.yo-star.com/?paipu="), "expected mahjong soul link starting with https://mahjongsoul.game.yo-star.com/?paipu="
        if not "_a" in link:
            print("Assuming you're the first east player, since mahjong soul link did not end with _a<number>")

        identifier, *player_string = link.split("https://mahjongsoul.game.yo-star.com/?paipu=")[1].split("_a")
        ms_account_id = None if len(player_string) == 0 else int((((int(player_string[0])-1358437)^86216345)-1117113)/7)
        try:
            f = open(f"cached_games/game-{identifier}.log", 'rb')
            record = proto.ResGameRecord()  # type: ignore[attr-defined]
            record.ParseFromString(f.read())
            return (record.head, record.data), next((acc.seat for acc in record.head.accounts if acc.account_id == ms_account_id), 0)
        except Exception:
            res = await self.account_manager.call(
                "fetchGameRecord",
                game_uuid=identifier,
                client_version_string=self.account_manager.client_version_string)

            """
            NOTE: Here's this extension's own version of `save_cache()`
            """
            filename=f"game-{identifier}.log"
            data=res.SerializeToString()
            # make sure the cache directory exists
            if not os.path.isdir("cached_games"):
                os.mkdir("cached_games")
            # make sure we have enough space
            dir_size = sum(os.path.getsize(os.path.join(dirpath, f)) for dirpath, _, filenames in os.walk("cached_games") for f in filenames)
            if dir_size < (1024 ** 3): # 1GB
                with open(f"cached_games/{filename}", "wb") as file:
                    file.write(data)

            return (res.head, res.data), next((acc.seat for acc in res.head.accounts if acc.account_id == ms_account_id), 0)

async def setup(bot: commands.Bot):
    logging.info(f"Loading extension `{InjusticeJudge.__name__}`...")
    instance = InjusticeJudge(bot=bot)
    await bot.add_cog(instance, guild=discord.Object(id=GUILD_ID))

