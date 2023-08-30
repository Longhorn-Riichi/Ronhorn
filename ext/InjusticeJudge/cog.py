import logging
import json
import discord
from discord.ext import commands
from discord import app_commands, Colour, Embed, Interaction
from typing import *

# InjusticeJudge imports
from modules.InjusticeJudge.injustice_judge.utils import ph, short_round_name, sorted_hand, try_remove_all_tiles
from modules.InjusticeJudge.injustice_judge.constants import TRANSLATE, YAOCHUUHAI
from .utilities import analyze_game, parse_game_link
from global_stuff import slash_commands_guilds

class Injustice(commands.Cog):
    """
    invokes a modified version of InjusticeJudge that uses our
    account manager to avoid repeated logging in-and-out. This is
    its own class so we can limit the `injustice` command to a
    given list of servers.
    """

    @app_commands.command(name="injustice", description="Display the injustices in a given game.")  # type: ignore[arg-type]
    @app_commands.describe(link="Link to the game to analyze (Mahjong Soul or tenhou.net)",
                           player="(optional) The seat to analyze the game from. Determined using the link, but defaults to East.")
    @app_commands.choices(player=[
        app_commands.Choice(name="East", value="East"),
        app_commands.Choice(name="South", value="South"),
        app_commands.Choice(name="West", value="West"),
        app_commands.Choice(name="North", value="North")])
    async def injustice(self, interaction: Interaction, link: str, player: Optional[app_commands.Choice[str]]):
        await interaction.response.defer()
        if player is None:
            injustices = await analyze_game(link)
            player_str = "player specified in the link"
        else:
            dir_map = ["East", "South", "West", "North"]
            injustices = await analyze_game(link, dir_map.index(player.value))
            player_str = f"starting {player.value} player"
        if injustices == []:
            injustices = [f"No injustices detected for the {player_str}.\n"
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
            await interaction.channel.send(embed=embed)  # type: ignore[union-attr]

class ParseLog(commands.Cog):
    @app_commands.command(name="parse", description=f"Print out the results of a game.")  # type: ignore[arg-type]
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
        player_names = [f"**{name}**" for name in game_metadata.name]
        game_scores = game_metadata.game_score
        final_scores = game_metadata.final_score
        num_players = len(player_names)
        header = f"Result of game {link}:\n"
        header += ", ".join("{}: {} ({:+.1f})".format(p,g,f/1000.0) for p,g,f in sorted(zip(player_names, game_scores, final_scores), key=lambda z: -z[2]))
        ret = [""]
        for i, rnd, honba, game_results in [(i, kyoku.round, kyoku.honba, kyoku.result) for i, kyoku in enumerate(kyokus)]:
            result_type, *results = game_results
            if result_type in {"ron", "tsumo"}: # ron or tsumo
                result_string = ""
                for j, result in enumerate(results):
                    if j != 0:
                        result_string += "\n` and` "
                    dama = "dama " if result.dama else ""
                    if result_type == "tsumo":
                        result_string += f"{player_names[result.winner]} {dama}tsumos"
                        ko = result.score_ko
                        oya = result.score_oya
                        if ko == oya:
                            result_string += f" for `{result.score}({ko}∀)`"
                        else:
                            result_string += f" for `{result.score}({ko}/{oya})`"
                    else:
                        result_string += f"{player_names[result.winner]} {dama}rons {player_names[result.won_from]} "
                        result_string += f" for `{result.score}`"
                    below_mangan = result.limit_name == ""
                    if below_mangan:
                        result_string += f" ({result.han}/{result.fu})"
                    else:
                        result_string += f" ({result.limit_name})"
                    def translate_yaku(y):
                        [name, value] = y.split('(')
                        value = 13 if "役満" in value else int(value.split("飜")[0])
                        winds = {0:"ton",1:"nan",2:"shaa",3:"pei"}
                        if value > 1 and TRANSLATE[name] in {"dora","aka","ura","kita"}:
                            return f"{TRANSLATE[name]} {value}"
                        elif TRANSLATE[name] == "round wind":
                            return winds[rnd//4]
                        elif TRANSLATE[name] == "seat wind":
                            return winds[result.winner]
                        else:
                            return TRANSLATE[name]
                    result_string += f" *{', '.join(map(translate_yaku, result.yaku.yaku_strs))}*"
                    if display_hands is not None:
                        if "All" in display_hands.value or ("Mangan" in display_hands.value and not below_mangan):
                            w = result.winner
                            final_tile = kyokus[i].final_discard if kyokus[i].result[0] == "ron" else kyokus[i].final_draw
                            if "starting" in display_hands.value:
                                result_string += "\n`    `"

                                result_string += kyokus[i].haipai[w].final_hand(
                                                    ukeire=kyokus[i].haipai_ukeire[w],
                                                    final_tile=final_tile,
                                                    furiten=kyokus[i].furiten[w])
                                result_string += "\n`    ` ⠀ ⠀ ⠀ ⠀ ⠀ ⠀ ⠀ ⠀ ⠀"
                                result_string += f"↓ ({len(kyokus[i].pond[w])} discards)"
                            result_string += "\n`    `"
                            result_string += kyokus[i].hands[w].final_hand(
                                                 ukeire=kyokus[i].final_ukeire[w],
                                                 final_tile=final_tile,
                                                 furiten=kyokus[i].furiten[w])
            elif result_type == "draw":
                score_delta = results[0].score_delta
                draw_name = results[0].name
                # check that there are any winners/losers at all
                if not all(delta == 0 for delta in score_delta):
                    # show that the winners pay out to the losers
                    # also mark the dealer
                    ith_player_string = lambda i: ("oya " if i == rnd % 4 else "") + player_names[i]
                    winners = [ith_player_string(i) for i, delta in enumerate(score_delta) if delta > 0]
                    losers = [ith_player_string(i) for i, delta in enumerate(score_delta) if delta < 0]
                    result_string = f"{draw_name} ({', '.join(losers)}⠀→⠀{', '.join(winners)})"
                else:
                    result_string = f"{draw_name}"
                # show the nagashi discards
                count_terminals = lambda hand: len([t for t in hand if t in YAOCHUUHAI])
                if draw_name == "nagashi mangan" and display_hands is not None:
                    winner = next(seat for seat in range(num_players) if score_delta[seat] > 0)
                    if "starting" in display_hands.value:
                        num_terminals = count_terminals(kyokus[i].haipai[winner])
                        result_string += "\n`    `"
                        result_string += f"{ph(kyokus[i].haipai[winner])} ({num_terminals} terminals)"
                        result_string += "\n`    ` ⠀ ⠀ ⠀ ⠀ ⠀ ⠀ ⠀ ⠀ ⠀"
                        result_string += f"↓ ({len(kyokus[i].pond[winner])} discards)"
                    result_string += "\n`    `"
                    result_string += ph(kyokus[i].pond[winner])
                if draw_name == "9 terminals draw" and display_hands is not None and "All" in display_hands.value:
                    declarer = next(seat for seat in range(num_players) if count_terminals(kyokus[i].haipai[seat]) >= 9)
                    declarer_hand = list(kyokus[i].haipai[declarer].tiles) + [kyokus[i].final_draw]
                    result_string += "\n`    `"
                    result_string += f"{ph(declarer_hand)} ({count_terminals(declarer_hand)} terminals)"

            # add to the end of ret[-1] unless that makes it too long,
            # in which case we append a new string to ret
            to_add = f"\n`{short_round_name(rnd, honba)}` {result_string}"
            if len(to_add) + len(ret[-1]) > 3900:
                ret.append(to_add)
            else:
                ret[-1] += to_add
        green = Colour.from_str("#1EA51E")
        await interaction.followup.send(content=header, embed=Embed(description=ret[0], colour=green))
        for embed in [Embed(description=text, colour=green) for text in ret[1:]]:
            await interaction.channel.send(embed=embed)  # type: ignore[union-attr]

async def setup(bot: commands.Bot):
    logging.info(f"Loading cog `{ParseLog.__name__}`...")
    await bot.add_cog(ParseLog(), guilds=slash_commands_guilds)

    logging.info(f"Loading cog `{Injustice.__name__}`...")
    with open('injustice_servers.json', 'r') as file:
        injustice_servers = json.load(file)
    injustice_guilds = [discord.Object(id=id) for id in injustice_servers.values()]
    await bot.add_cog(Injustice(), guilds=injustice_guilds)
