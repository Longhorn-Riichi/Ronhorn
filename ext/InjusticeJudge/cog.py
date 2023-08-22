import discord
import logging
import os
from discord.ext import commands
from discord import app_commands, Colour, Embed, Interaction
from typing import *

from modules.mahjongsoul.account_manager import AccountManager
from modules.pymjsoul.proto import liqi_combined_pb2 as proto

# InjusticeJudge imports
from google.protobuf.json_format import MessageToDict
from modules.InjusticeJudge.injustice_judge.fetch import fetch_tenhou, parse_tenhou, parse_majsoul, save_cache, parse_wrapped_bytes, GameMetadata
from modules.InjusticeJudge.injustice_judge.utils import short_round_name, print_full_hand, sorted_hand, try_remove_all_tiles
from modules.InjusticeJudge.injustice_judge.injustices import evaluate_injustices
from modules.InjusticeJudge.injustice_judge.constants import Kyoku, TRANSLATE

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

    @app_commands.command(name="parse", description=f"Print out the results of a game.")
    @app_commands.describe(link="Link to the game to describe (Mahjong Soul or tenhou.net).",
                           display_hands="Display all hands, or just mangan+ hands?")
    @app_commands.choices(display_hands=[
        app_commands.Choice(name="Mangan+ hands and starting hands", value="Mangan+ hands and starting hands"),
        app_commands.Choice(name="Mangan+ hands", value="Mangan+ hands"),
        app_commands.Choice(name="All winning hands and starting hands", value="All winning hands and starting hands"),
        app_commands.Choice(name="All winning hands", value="All winning hands")])
    async def parse(self, interaction: Interaction, link: str, display_hands: Optional[app_commands.Choice[str]] = None):
        await interaction.response.defer()
        kyokus, game_metadata, player = await self.parse_game_link(link)
        results = [(i, kyoku["round"], kyoku["honba"], kyoku["result"]) for i, kyoku in enumerate(kyokus)]
        player_names = [f"**{name}**" for name in game_metadata["name"]]
        game_scores = game_metadata["game_score"]
        final_scores = game_metadata["final_score"]
        num_players = len(player_names)
        header = f"Result of game ([link]({link})):\n"
        header += ", ".join("{}: {} ({:+.1f})".format(p,g,f/1000.0) for p,g,f in sorted(zip(player_names, game_scores, final_scores), key=lambda z: -z[2]))
        ret = [""]
        for i, rnd, honba, result in results:
            result_name, *win_data = result
            if result_name == "和了": # ron or tsumo
                result_string = ""
                wins = [win_data[i*2:i*2+2] for i in range(len(win_data)//2)]
                for j, [score_delta, [winner, from_seat, _, point_string, *yaku]] in enumerate(wins):
                    tsumo = winner == from_seat
                    if j != 0:
                        result_string += "\n` and` "
                    if tsumo:
                        result_string += f"{player_names[from_seat]} tsumos"
                    else:
                        result_string += f"{player_names[winner]} rons {player_names[from_seat]} "
                    below_mangan = "符" in point_string
                    if below_mangan:
                        [fu, rest] = point_string.split("符")
                        [han, rest] = rest.split("飜")
                        [pts, _] = rest.split("点")
                    else: # e.g. "倍満16000点"
                        pts = "".join(c for c in point_string if c.isdigit() or c == "-")
                        limit_name = point_string.split(pts[0])[0]
                    pts = "/".join(pts.split("-"))
                    if tsumo:
                        num_players == 3
                    if tsumo:
                        if "∀" in point_string:
                            result_string += f" for `{int(pts)*(num_players-1)}({pts}∀)`"
                        else:
                            ko, oya = map(int, pts.split('/'))
                            result_string += f" for `{ko+ko+oya if num_players == 4 else ko+oya}({pts})`"
                    else:
                        result_string += f" for `{pts}`"
                    if below_mangan:
                        result_string += f" ({han}/{fu})"
                    else:
                        result_string += f" ({TRANSLATE[limit_name]})"
                    def translate_yaku(y):
                        [name, value] = y.split('(')
                        value = int(value.split("飜")[0])
                        winds = {0:"ton",1:"nan",2:"shaa",3:"pei"}
                        if value > 1 and TRANSLATE[name] in {"dora","aka","ura","kita"}:
                            return f"{TRANSLATE[name]} {value}"
                        elif TRANSLATE[name] == "round wind":
                            return winds[rnd//4]
                        elif TRANSLATE[name] == "seat wind":
                            return winds[winner]
                        else:
                            return TRANSLATE[name]
                    result_string += f" *{', '.join(map(translate_yaku, yaku))}*"
                    if display_hands is not None:
                        if "All" in display_hands.value or ("Mangan" in display_hands.value and not below_mangan):
                            if "starting" in display_hands.value:
                                starting_hand = sorted_hand(kyokus[i]["starting_hands"][winner])
                                starting_shanten = kyokus[i]["starting_shanten"][winner]
                                result_string += "\n`    `" + print_full_hand(starting_hand, [], starting_shanten, -1) + "\n`    `⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀↓"
                            final_closed_hand = sorted_hand(try_remove_all_tiles(tuple(kyokus[i]["hands"][winner]), tuple(kyokus[i]["calls"][winner])))
                            final_waits = kyokus[i]["final_waits"][winner]
                            final_ukeire = kyokus[i]["final_ukeire"][winner]
                            final_call_info = kyokus[i]["call_info"][winner]
                            furiten = kyokus[i]["furiten"][winner]
                            final_tile = kyokus[i]["final_tile"]
                            result_string += "\n`    `" + print_full_hand(final_closed_hand, final_call_info, (0, final_waits), final_ukeire, final_tile, furiten)
            elif result_name in ["流局", "全員聴牌", "流し満貫"]: # ryuukyoku / nagashi
                winners = [player_names[i] for i, delta in enumerate(win_data[0]) if delta > 0]
                losers = [player_names[i] for i, delta in enumerate(win_data[0]) if delta < 0]
                if len(winners) > 0 and len(losers) > 0:
                    result_string = f"{TRANSLATE[result_name]} ({', '.join(losers)}⠀→⠀{', '.join(winners)})"
                else:
                    result_string = f"{TRANSLATE[result_name]}"
            elif result_name in ["九種九牌", "四家立直", "三家和了", "四槓散了", "四風連打"]: # draws
                result_string = TRANSLATE[result_name]
            to_add = f"\n`{short_round_name(rnd, honba)}` {result_string}"
            if len(to_add + ret[-1]) > 4096:
                ret.append(to_add)
            else:
                ret[-1] += to_add
        green = Colour.from_str("#1EA51E")
        await interaction.followup.send(content=header, embed=Embed(description=ret[0], colour=green))
        for embed in [Embed(description=text, colour=green) for text in ret[1:]]:
            await interaction.channel.send(embed=embed)
    
    """
    =====================================================
    Modified InjusticeJudge Functions
    =====================================================
    """
    async def parse_game_link(self, link: str, specified_player: int = 0) -> Tuple[List[Kyoku], GameMetadata, int]:
        """
        basically the same as the exposed `parse_game_link()` of the InjusticeJudge,
        but with the `fetch_majsoul` part substituted out so we can use our own
        AccountManager (to avoid logging in for each fetch)
        """
        # print(f"Analyzing game {link}:")
        if link.startswith("https://tenhou.net/0/?log="):
            tenhou_log, metadata, player = fetch_tenhou(link)
            kyokus, parsed_metadata = parse_tenhou(tenhou_log, metadata)
        elif link.startswith("https://mahjongsoul.game.yo-star.com/?paipu="):
            majsoul_log, metadata, player = await self.fetch_majsoul(link)
            kyokus, parsed_metadata = parse_majsoul(majsoul_log, metadata)
        else:
            raise Exception("expected tenhou link starting with https://tenhou.net/0/?log="
                            " or mahjong soul link starting with https://mahjongsoul.game.yo-star.com/?paipu=")
        if specified_player is not None:
            player = specified_player
        return kyokus, parsed_metadata, player
    
    async def analyze_game(self, link: str, specified_player = None) -> List[str]:
        kyokus, game_metadata, player = await self.parse_game_link(link, specified_player)
        return [injustice for kyoku in kyokus for injustice in evaluate_injustices(kyoku, player)]
    
    async def fetch_majsoul(self, link: str):
        """
        NOTE:
        basically the same as InjusticeJudge's `fetch_majsoul()`, with 1 difference;
        Instead of logging in for each fetch, just fetch through the already logged-in
        AccountManager.
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
        except Exception:
            record = await self.account_manager.call(
                "fetchGameRecord",
                game_uuid=identifier,
                client_version_string=self.account_manager.client_version_string)

            save_cache(
                filename=f"game-{identifier}.log",
                data=record.SerializeToString())

        parsed = parse_wrapped_bytes(record.data)[1]
        if parsed.actions != []:
            actions = [parse_wrapped_bytes(action.result) for action in parsed.actions if len(action.result) > 0]
        else:
            actions = [parse_wrapped_bytes(record) for record in parsed.records]
        return actions, MessageToDict(record.head), next((acc.seat for acc in record.head.accounts if acc.account_id == ms_account_id), 0)

async def setup(bot: commands.Bot):
    logging.info(f"Loading extension `{InjusticeJudge.__name__}`...")
    instance = InjusticeJudge(bot=bot)
    await bot.add_cog(instance, guild=discord.Object(id=GUILD_ID))

