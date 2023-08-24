import logging
from discord.ext import commands
from discord import app_commands, Colour, Embed, Interaction
from typing import *

# InjusticeJudge imports
from modules.InjusticeJudge.injustice_judge.utils import short_round_name, print_full_hand, sorted_hand, try_remove_all_tiles
from modules.InjusticeJudge.injustice_judge.constants import TRANSLATE
from utilities import *


class InjusticeJudge(commands.Cog):
    """
    Commands that invoke the InjusticJudge utilities, and the helpers
    that make efficient API calls. Caches the game logs in `/cached_games`,
    up to 1 GB
    """

    """
    =====================================================
    SLASH COMMANDS
    =====================================================
    """

    @app_commands.command(name="injustice", description="Display the injustices in a given game.")
    @app_commands.describe(link="Link to the game to analyze (Mahjong Soul or tenhou.net)",
                           player="(optional) The seat to analyze the game from. Determined using the link, but defaults to East.")
    @app_commands.choices(player=[
        app_commands.Choice(name="East", value=0),
        app_commands.Choice(name="South", value=1),
        app_commands.Choice(name="West", value=2),
        app_commands.Choice(name="North", value=3)])
    async def injustice(self, interaction: Interaction, link: str, player: Optional[app_commands.Choice[int]]):
        await interaction.response.defer()
        if player is None:
            injustices = await analyze_game(link)
        else:
            injustices = await analyze_game(link, player.value)
        if injustices == []:
            starting_dir = player.value if player is not None else None
            player_direction = {None: "player specified in the link",
                                0: "starting East player",
                                1: "starting South player",
                                2: "starting West player",
                                3: "starting North player"}
            injustices = [f"No injustices detected for the {player_direction[starting_dir]}.\n"
                           "Specify another player with the `player` option in `/injustice`.\n"
                           "Did we miss an injustice? Contribute ideas [here](https://github.com/Longhorn-Riichi/InjusticeJudge/issues/1)!"]
        ret = [""]
        for to_add in injustices:
            to_add += "\n"
            if len(to_add) + len(ret[-1]) > 3900:
                ret.append(to_add)
            else:
                ret[-1] += to_add
        title = f"Injustices"
        green = Colour.from_str("#1EA51E")
        as_player_string = "yourself" if player is None else player.name
        await interaction.followup.send(content=f"Input: {link}\nAnalysis result for **{as_player_string}**:", embed=Embed(description=ret[0], colour=green))
        for embed in [Embed(description=text, colour=green) for text in ret[1:]]:
            await interaction.channel.send(embed=embed)

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
        kyokus, game_metadata, player = await parse_game_link(link)
        results = [(i, kyoku["round"], kyoku["honba"], kyoku["result"]) for i, kyoku in enumerate(kyokus)]
        player_names = [f"**{name}**" for name in game_metadata["name"]]
        game_scores = game_metadata["game_score"]
        final_scores = game_metadata["final_score"]
        num_players = len(player_names)
        header = f"Result of game {link}:\n"
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
                                result_string += "\n`    `" + print_full_hand(starting_hand, [], starting_shanten, -1) + f"\n`    ` ⠀ ⠀ ⠀ ⠀ ⠀ ⠀ ⠀ ⠀ ⠀↓ ({len(kyokus[i]['pond'][winner])} discards)"
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
            if len(to_add) + len(ret[-1]) > 3900:
                ret.append(to_add)
            else:
                ret[-1] += to_add
        green = Colour.from_str("#1EA51E")
        await interaction.followup.send(content=header, embed=Embed(description=ret[0], colour=green))
        for embed in [Embed(description=text, colour=green) for text in ret[1:]]:
            await interaction.channel.send(embed=embed)

async def setup(bot: commands.Bot):
    logging.info(f"Loading cog `{InjusticeJudge.__name__}`...")
    instance = InjusticeJudge()
    await bot.add_cog(instance)

