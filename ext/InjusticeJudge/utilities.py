import re
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import logging
from io import BytesIO
from global_stuff import account_manager
from modules.pymjsoul.proto import liqi_combined_pb2 as proto
from discord import Colour, Embed, Interaction
from typing import *

# InjusticeJudge imports
from google.protobuf.json_format import MessageToDict  # type: ignore[import]
from modules.InjusticeJudge.injustice_judge.fetch import parse_majsoul, parse_majsoul_link, fetch_riichicity, parse_riichicity, fetch_tenhou, parse_tenhou, parse_tenhou_link, save_cache, parse_wrapped_bytes, GameMetadata
from modules.InjusticeJudge.injustice_judge.injustices import evaluate_game
from modules.InjusticeJudge.injustice_judge.classes2 import Kyoku
from modules.InjusticeJudge.injustice_judge.constants import KO_TSUMO_SCORE, OYA_TSUMO_SCORE, TRANSLATE, YAOCHUUHAI
from modules.InjusticeJudge.injustice_judge.display import ph, pt, round_name, short_round_name
from modules.InjusticeJudge.injustice_judge.utils import to_dora_indicator

async def long_followup(interaction: Interaction, chunks: List[str], header: str):
    """Followup with a long message by breaking it into multiple messages"""
    logging.info("Running long_followup")
    ret = [""]
    for to_add in chunks:
        to_add += "\n"
        # assert len(to_add) >= 3900, "single message is too long!"
        if len(to_add) + len(ret[-1]) > 3900:
            ret.append(to_add)
        else:
            ret[-1] += to_add
    green = Colour.from_str("#1EA51E")
    if len(ret) > 1 and interaction.channel is None:
        header += "\n**NOTE:** message is cut off! Ronhorn has no access to the channel to post follow-up messages"
    if interaction.followup is not None:
        await interaction.followup.send(content=header, embed=Embed(description=ret[0], colour=green))
    else:
        logging.info("Error in long_followup: interaction.followup was None")
    if interaction.channel is not None:
        for embed in [Embed(description=text, colour=green) for text in ret[1:]]:
            await interaction.channel.send(embed=embed)  # type: ignore[union-attr]
    else:
        logging.info("Error in long_followup: interaction.channel was None")

"""
=====================================================
Modified InjusticeJudge Functions
=====================================================
"""

async def parse_game_link(link: str, specified_players: Set[int] = set(), nickname: Optional[str]=None) -> Tuple[List[Kyoku], GameMetadata, Set[int]]:
    """
    basically the same as the exposed `parse_game_link()` of the InjusticeJudge,
    but with the `fetch_majsoul` part substituted out so we can use our own
    AccountManager (to avoid logging in for each fetch)
    """
    if "tenhou.net/" in link:
        logging.info("  fetching tenhou log")
        tenhou_log, metadata, player = fetch_tenhou(link)
        logging.info("  tenhou log fetched")
        if metadata["name"][3] == "":
            assert player != 3 or all(p != 3 for p in specified_players), "Can't specify North player in a sanma game"
        kyokus, parsed_metadata, parsed_player_seat = parse_tenhou(tenhou_log, metadata, nickname)
        logging.info("  tenhou log parsed")
    elif "mahjongsoul" in link or "maj-soul" in link or "majsoul" in link:
        # EN: `mahjongsoul.game.yo-star.com`; CN: `maj-soul.com`; JP: `mahjongsoul.com`
        # Old CN (?): http://majsoul.union-game.com/0/?paipu=190303-335e8b25-7f5c-4bd1-9ac0-249a68529e8d_a93025901
        logging.info("  fetching majsoul log")
        majsoul_log, metadata, player = await fetch_majsoul(link)
        logging.info("  majsoul log fetched")
        if len(metadata["accounts"]) == 3:
            assert player != 3 or all(p != 3 for p in specified_players), "Can't specify North player in a sanma game"
        kyokus, parsed_metadata, parsed_player_seat = parse_majsoul(majsoul_log, metadata, nickname)
        logging.info("  majsoul log parsed")
    elif len(link) == 20: # riichi city log id
        logging.info("  fetching riichicity log")
        riichicity_log, metadata = fetch_riichicity(link)
        logging.info("  riichicity log fetched")
        kyokus, parsed_metadata, parsed_player_seat = parse_riichicity(riichicity_log, metadata, nickname)
        logging.info("  riichicity log parsed")
        player = None
    else:
        raise Exception("expected tenhou link similar to `tenhou.net/0/?log=`"
                        " or mahjong soul link similar to `mahjongsoul.game.yo-star.com/?paipu=`"
                        " or 20-character riichi city log id like `cjc3unuai08d9qvmstjg`")
    kyokus[-1].is_final_round = True
    if len(specified_players) == 0:
        if parsed_player_seat is not None:
            specified_players = {parsed_player_seat}
        elif player is not None:
            specified_players = {player}
    return kyokus, parsed_metadata, specified_players

async def analyze_game(link: str, specified_players: Set[int] = set(), look_for: Set[str] = {"injustice"}, nickname: Optional[str] = None) -> Tuple[List[str], Set[int]]:
    """Same analyze_game as fetch.py, but returns specified_players"""
    try:
        kyokus, game_metadata, specified_players = await parse_game_link(link, specified_players, nickname)
        logging.info(f"  game link parsed (players: {specified_players})")
        return [result for kyoku in kyokus for result in evaluate_game(kyoku, specified_players, game_metadata.name, look_for)], specified_players
    except Exception as e:
        kyokus, game_metadata, specified_players = await parse_game_link(link, specified_players - {3}, nickname)
        logging.info("  game link parsed (sanma)")
        return [result for kyoku in kyokus for result in evaluate_game(kyoku, specified_players, game_metadata.name, look_for)], specified_players

async def fetch_majsoul(link: str):
    """
    NOTE:
    basically the same as InjusticeJudge's `fetch_majsoul()`, with 1 difference;
    Instead of logging in for each fetch, just fetch through the already logged-in
    AccountManager.
    """
    identifier_pattern = r'\?paipu=([0-9a-zA-Z-]+)'
    identifier_match = re.search(identifier_pattern, link)
    if identifier_match is None:
        raise Exception(f"Invalid Mahjong Soul link: {link}")
    identifier = identifier_match.group(1)

    if not all(c in "0123456789abcdef-" for c in identifier):
        # deanonymize the link
        codex = "0123456789abcdefghijklmnopqrstuvwxyz"
        decoded = ""
        for i, c in enumerate(identifier):
            decoded += "-" if c == "-" else codex[(codex.index(c) - i + 55) % 36]
        identifier = decoded
    
    try:
        f = open(f"cached_games/game-{identifier}.log", 'rb')
        record = proto.ResGameRecord()  # type: ignore[attr-defined]
        record.ParseFromString(f.read())
    except Exception:
        record = await account_manager.call(
            "fetchGameRecord",
            game_uuid=identifier,
            client_version_string=account_manager.client_version_string)

        save_cache(
            filename=f"game-{identifier}.log",
            data=record.SerializeToString())

    parsed = parse_wrapped_bytes(record.data)[1]
    if parsed.actions != []:  # type: ignore[attr-defined]
        actions = [parse_wrapped_bytes(action.result) for action in parsed.actions if len(action.result) > 0]  # type: ignore[attr-defined]
    else:
        actions = [parse_wrapped_bytes(record) for record in parsed.records]  # type: ignore[attr-defined]
    
    player = 0
    if link.count("_") == 2:
        player = int(link[-1])
    else:
        player_pattern = r'_a(\d+)'
        player_match = re.search(player_pattern, link)
        if player_match is not None:
            ms_account_id = int((((int(player_match.group(1))-1358437)^86216345)-1117113)/7)
            for acc in record.head.accounts:
                if acc.account_id == ms_account_id:
                    player = acc.seat
                    break
    
    return actions, MessageToDict(record.head), player

"""
=====================================================
HELPER FUNCTIONS for `cog.py`
Factored out so we can unit-test them.
=====================================================
"""
def count_terminals(hand: Tuple[int, ...]):
    counter = 0
    for tile in hand:
        if tile in YAOCHUUHAI:
            counter += 1
    return counter

def count_unique_terminals(hand: Tuple[int, ...]):
    unique_yaochuuhai = set()
    for tile in hand:
        if tile in YAOCHUUHAI:
            unique_yaochuuhai.add(tile)
    return len(unique_yaochuuhai)

# constants for `/parse`
CODE_BLOCK_PREFIX = "\n`    `"
CODE_BLOCK_AND_SPACES_PREFIX = "\n`    `              "

async def parse_game(link: str, display_hands: Optional[str]="All winning hands and starting hands") -> Tuple[str, List[str]]:
    kyokus, game_metadata, player = await parse_game_link(link)
    player_names = [f"**{name}**" for name in game_metadata.name]
    game_scores = game_metadata.game_score
    final_scores = game_metadata.final_score
    num_players = game_metadata.num_players
    header = f"Result of game {link}:\n"
    seat_names = [pt(t) for t in range(41,45)]
    header += ", ".join("{} {}: {} ({:+.1f})".format(d,p,g,f) for p,d,g,f in sorted(list(zip(player_names, seat_names, game_scores, final_scores))[:num_players], key=lambda z: -z[3]))
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
                    ko = KO_TSUMO_SCORE[result.score.han][result.score.fu]  # type: ignore[index]
                    oya = OYA_TSUMO_SCORE[result.score.han][result.score.fu]  # type: ignore[index]
                    if ko == oya:
                        result_string += f" for `{result.score.to_points()}({ko}∀)`"
                    else:
                        result_string += f" for `{result.score.to_points()}({ko}/{oya})`"
                else:
                    result_string += f"{player_names[result.winner]} {dama}rons {player_names[result.won_from]} "
                    result_string += f" for `{result.score.to_points()}`"
                below_mangan = result.score.get_limit_hand_name() == ""
                if below_mangan:
                    result_string += f" ({result.score.han}/{result.score.fu})"
                else:
                    result_string += f" ({result.score.get_limit_hand_name()})"
                def get_yaku_name(t: Tuple[str, int]):
                    name = t[0]
                    winds = {0:"ton",1:"nan",2:"shaa",3:"pei"}
                    if name == "round wind":
                        return winds[rnd//4]
                    elif name == "seat wind":
                        return winds[result.winner]
                    else:
                        return name
                result_string += f" *{', '.join(map(get_yaku_name, result.score.yaku))}*"
                if display_hands is not None:
                    if "All" in display_hands or ("Mangan" in display_hands and not below_mangan):
                        w: int = result.winner
                        final_tile = kyokus[i].final_discard if kyokus[i].result[0] == "ron" else kyokus[i].final_draw
                        if "starting" in display_hands:
                            result_string += CODE_BLOCK_PREFIX
                            starting_dora_indicators = [to_dora_indicator(dora, game_metadata.num_players) for dora in kyokus[i].get_starting_doras() if dora not in {51,52,53}]
                            result_string += kyokus[i].haipai[w].print_hand_details(
                                                ukeire=kyokus[i].hands[w].ukeire(starting_dora_indicators),
                                                final_tile=final_tile,
                                                furiten=kyokus[i].furiten[w],
                                                doras=kyokus[i].doras,
                                                uras=kyokus[i].doras)
                            result_string += CODE_BLOCK_AND_SPACES_PREFIX
                            result_string += f"↓ ({len(kyokus[i].pond[w])} discards)"
                        result_string += CODE_BLOCK_PREFIX
                        result_string += kyokus[i].hands[w].print_hand_details(
                                                ukeire=kyokus[i].get_ukeire(w),
                                                final_tile=final_tile,
                                                furiten=kyokus[i].furiten[w],
                                                doras=kyokus[i].doras,
                                                uras=kyokus[i].doras)
        elif result_type in {"draw", "ryuukyoku"}:
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
            
            if display_hands is not None:
                if draw_name == "nagashi mangan":
                    winner = next(seat for seat in range(num_players) if score_delta[seat] > 0)
                    if "starting" in display_hands:
                        num_terminals = count_terminals(kyokus[i].haipai[winner].tiles)
                        result_string += CODE_BLOCK_PREFIX
                        result_string += f"{ph(kyokus[i].haipai[winner].tiles)} ({num_terminals} terminals)"
                        result_string += CODE_BLOCK_AND_SPACES_PREFIX
                        result_string += f"↓ ({len(kyokus[i].pond[winner])} discards)"
                    result_string += CODE_BLOCK_PREFIX
                    result_string += ph(kyokus[i].pond[winner])
                elif draw_name == "9 terminals draw" and "All" in display_hands:
                    kyoku = kyokus[i]
                    
                    # determine the declarer of the draw by identifying the
                    # first player without a discard, starting from the dealer
                    curr_seat = rnd % 4 # initialized as the current dealer's seat
                    while True:
                        if len(kyoku.pond[curr_seat]) == 0:
                            declarer = curr_seat
                            break
                        curr_seat = (curr_seat + 1) % kyoku.num_players

                    declarer_hand = (*kyoku.haipai[declarer].tiles, kyoku.final_draw)

                    result_string += CODE_BLOCK_PREFIX
                    result_string += f"{ph(declarer_hand)} ({count_unique_terminals(declarer_hand)} unique terminals)"
        else:
            assert False, f"unknown result type {result_type} for round {round_name(rnd, honba)}"

        # add to the end of ret[-1] unless that makes it too long,
        # in which case we append a new string to ret
        to_add = f"\n`{short_round_name(rnd, honba)}` {result_string}"
        if len(to_add) + len(ret[-1]) > 3900:
            ret.append(to_add)
        else:
            ret[-1] += to_add

    return header, ret

async def draw_graph(link: str, display_graph: Optional[str] = None) -> BytesIO:
    kyokus, game_metadata, player = await parse_game_link(link)
    # setup matplotlib
    font_path = "fonts/Arial Unicode MS.ttf"
    fm.fontManager.addfont(font_path)
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams["font.family"] = font_prop.get_name()
    plt.rcParams["font.size"] = 24
    plt.rcParams["text.color"] = "gray"
    plt.rcParams["xtick.color"] = "gray"
    plt.rcParams["ytick.color"] = "gray"
    plt.rcParams["figure.figsize"] = [12.8, 8.4]
    plt.xticks(rotation=45, ha="right")
    plt.margins(0.02)
    plt.box(False)

    # collect data
    rounds = [""] + [round_name(kyoku.round, kyoku.honba) for kyoku in kyokus]
    scores = [[kyoku.start_scores[i] for kyoku in kyokus] + [game_metadata.game_score[i]] for i in range(game_metadata.num_players)]
    scaling_unit: float = 100
    if display_graph == "Scores with placement bonus":
        scores = list(zip(*(list(game_metadata.rules.apply_placement_bonus(round, score)) for round, score in zip([0] + [kyoku.round for kyoku in kyokus], zip(*scores)))))
        scaling_unit = 0.2
    colors = ["orangered", "gold", "forestgreen", "darkviolet"]

    # calculate offsets for annotations (so numbers don't overlap)
    min_score = min(score for scores_per_round in scores for score in scores_per_round)
    max_score = max(score for scores_per_round in scores for score in scores_per_round)
    min_separation = (max_score - min_score) / 12
    check_closeness = True
    gas = 1000
    yoffsets: List[float] = [0] * game_metadata.num_players
    while check_closeness and gas >= 0:
        check_closeness = False
        gas -= 1
        final_scores = sorted((scores_per_round[-1], i) for i, scores_per_round in enumerate(scores))
        for (s1, i1), (s2, i2) in zip(final_scores[:-1], final_scores[1:]):
            if (s2 + yoffsets[i2]) - (s1 + yoffsets[i1]) < min_separation:
                check_closeness = True
                yoffsets[i1] -= scaling_unit
                yoffsets[i2] += scaling_unit
    # draw the graph
    plt.grid(linestyle="--", linewidth=1.0)
    plt.axhline(0, color="gray", linewidth=4.0)
    for name, score, color, yoffset in zip(game_metadata.name, scores, colors, yoffsets):
        yoffset *= 100/scaling_unit
        plt.plot(rounds, score, label=name, color=color, alpha=0.8, linewidth=8, solid_capstyle="round")
        # display end score
        plt.annotate(str(score[-1]), (rounds[-1], score[-1]), textcoords="offset points", xytext=(10,yoffset/plt.rcParams["figure.dpi"]), va="center", color=color)
        if display_graph == "Scores with placement bonus":
            # display starting placement bonus, too
            plt.annotate(str(int(score[0])), (rounds[0], score[0]), textcoords="offset points", xytext=(0,10), va="center", ha="center")
    plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), framealpha=0, ncol=range(game_metadata.num_players), handlelength=0.04)
    plt.tight_layout()

    # return as a BytesIO object
    buf = BytesIO()
    plt.savefig(buf, format="png", transparent=True)
    buf.seek(0)
    plt.cla()
    plt.clf()
    return buf

def parse_link(link: str) -> Tuple[str, Optional[int]]:
    try:
        return parse_tenhou_link(link)
    except:
        pass

    try:
        identifier, _, player_seat = parse_majsoul_link(link)
        return identifier, player_seat
    except:
        pass

    return link, 0
