from typing import *
from modules.InjusticeJudge.injustice_judge.display import ph, pt
from modules.InjusticeJudge.injustice_judge.constants import SUCC, TANYAOHAI, YAOCHUUHAI
from modules.InjusticeJudge.injustice_judge.shanten import to_suits, from_suits, eliminate_all_groups, get_iishanten_type, calculate_chiitoitsu_shanten, calculate_kokushi_shanten, eliminate_some_taatsus, get_hand_shanten, get_tenpai_waits
from modules.InjusticeJudge.injustice_judge.utils import normalize_red_fives, sorted_hand

def translate_hand(hand: str) -> Tuple[int, ...]:
    suit_to_int = {"m": 10, "p": 20, "s": 30, "z": 40}
    current_suit = 0
    ret = []
    for c in reversed(hand):
        if c in suit_to_int:
            current_suit = suit_to_int[c]
        else:
            ix = int(c) if int(c) != 0 else 5
            ret.append(ix + current_suit)
    return tuple(reversed(ret))

def analyze_hand(hand: Tuple[int, ...]) -> List[str]:
    if len(hand) not in {4, 7, 10, 13}:
        return ["The given hand must be of length 4, 7, 10, or 13."]
    suits = to_suits(hand)
    groupless_hands = eliminate_all_groups(suits)
    groups_needed = (len(next(from_suits(groupless_hands))) - 1) // 3
    removed_taatsus = eliminate_some_taatsus(groupless_hands)
    shanten: float = get_hand_shanten(removed_taatsus, groups_needed)
    waits: Set[int] = set()
    debug_info: Dict[str, Any] = {"shanten": shanten}
    ctr = Counter(normalize_red_fives(hand))
    ret = [f"Hand: {ph(hand)}", f"Hand with groups removed: {' or '.join(map(ph, from_suits(groupless_hands)))}", ""]

    # check non-standard shanten
    if len(hand) == 13:
        c_shanten, c_waits = calculate_chiitoitsu_shanten(hand, ctr)
        k_shanten, k_waits = calculate_kokushi_shanten(hand, ctr)
        debug_info["c_shanten"] = c_shanten
        debug_info["k_shanten"] = k_shanten
        if c_shanten < 2:
            shanten = c_shanten
            debug_info["chiitoitsu_waits"] = c_waits
        elif k_shanten < 2:
            shanten = k_shanten
            debug_info["kokushi_waits"] = k_waits

    if shanten == 1:
        shanten, expected_waits, debug_info = get_iishanten_type(hand, groupless_hands, groups_needed)
        # shanten returned from this func is always 1.0xx

        # check standard iishanten
        shanten_digits = str(round(shanten*1000))[1:]
        if shanten_digits[1] in "23":
            ret.extend(describe_kuttsuki_iishanten(debug_info))
            waits |= debug_info["kuttsuki_waits"]  
        if shanten_digits[1] in "13":
            ret.extend(describe_headless_iishanten(debug_info, waits))
            waits |= debug_info["headless_taatsu_waits"]  
            waits |= debug_info["headless_tanki_waits"]  
        if shanten_digits[2] in "23":
            ret.extend(describe_complete_iishanten(debug_info, waits))
        elif shanten_digits[2] == "1":
            ret.extend(describe_floating_iishanten(debug_info, waits))

        # check non-standard iishanten
        if len(hand) == 13:
            if "chiitoitsu_waits" in debug_info:
                ret.extend(describe_chiitoitsu_iishanten(debug_info, waits))
            elif "kokushi_waits" in debug_info:
                ret.extend(describe_kokushi_iishanten(debug_info, waits))
    elif shanten == 0:
        waits = get_tenpai_waits(hand)
        debug_info["tenpai_waits"] = waits
    else:
        ret.extend(describe_shanten(debug_info))

    if shanten < 2:
        # remove all ankan in hand from the waits
        ctr = Counter(normalize_red_fives(hand))
        ankan_tiles = {k for k, v in ctr.items() if v == 4}
        debug_info["ankan_tiles"] = ankan_tiles
        ankan_description = describe_ankan(debug_info, waits)
        if len(ankan_description) > 0 and len(ret) > 3:
            ret.append("")
        ret.extend(ankan_description)
        waits -= ankan_tiles
        if len(waits) == 0 and len(ankan_tiles) > 0:
            debug_info["tanki_iishanten_waits"] = (TANYAOHAI | YAOCHUUHAI) - {k for k, v in ctr.items() if v >= 3}
            if len(ankan_description) > 0:
                ret.append("")
            ret.extend(describe_tanki_iishanten(debug_info))
        elif shanten == 0:
            if len(ankan_description) > 0:
                ret.append("")
            ret.extend(describe_tenpai(debug_info)) 

    return ret

def describe_floating_iishanten(debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    pair = debug_info["floating_hands"][0]["pair"]
    ret = []
    for floating_hand in sorted(debug_info["floating_hands"], key=lambda h: -len(h["simple_taatsu_waits"] | h["simple_shanpon_waits"])):
        simple_shapes = floating_hand["simple_shapes"]
        simple_taatsu_waits = floating_hand["simple_taatsu_waits"]
        simple_shanpon_waits = floating_hand["simple_shanpon_waits"]
        simple_waits = simple_taatsu_waits | simple_shanpon_waits
        if len(simple_shapes) == 0:
            continue
        if len(waits) == 0:
            ret.append(
                f"Due to having {'2' if len(simple_shapes) == 2 else '2+'} simple shapes {' '.join(map(ph, simple_shapes))} and a pair {ph(pair)},"
                f" this hand is best described as **floating tile iishanten**.")
            ret.append(
                f"\nThe waits for floating tile iishanten are completely determined by"
                f" its simple shapes: {ph(sorted_hand(simple_waits))}.")
        elif not simple_waits.issubset(waits):
            ret.extend(["",
                f"This hand can also be interpreted as having {'2' if len(simple_shapes) == 2 else '2+'} simple shapes {' '.join(map(ph, simple_shapes))} and a pair {ph(pair)},"
                f" which means this hand is also **floating tile iishanten**."])
            ret.append(
                f"\nThe waits for floating tile iishanten are completely determined by"
                f" its simple shapes {ph(sorted_hand(simple_waits))}, adding {ph(sorted_hand(simple_waits - waits))} to the wait.")
        else:
            continue
        waits |= simple_waits
    return ret


def describe_complete_iishanten(debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    ret = []
    is_ryanmen = lambda h: len(h) == 2 and SUCC[h[0]] == h[1] and h[0] not in {11,18,21,28,31,38}
    perfect_str = "\nThis ryanmen-ryanmen form of complete iishanten is also known as **perfect iishanten**."
    for complex_hand in sorted(debug_info["complex_hands"], key=lambda h: -len(h["simple_wait"] | h["complex_waits"])):
        pair = complex_hand["pair"]
        simple_shape = complex_hand["simple_shape"]
        complex_shape = complex_hand["complex_shape"]
        simple_wait = complex_hand["simple_wait"]
        complex_waits = complex_hand["complex_waits"]
        is_complex_pair = len(set(complex_shape)) == 2
        t1, t2 = complex_shape[0:2], complex_shape[1:3]
        is_perfect = is_ryanmen(simple_shape) and (is_ryanmen(t1) or is_ryanmen(t2))
        if len(waits) == 0:
            if is_complex_pair:
                ret.extend([
                    f"Due to having a simple shape {ph(simple_shape)}"
                    f" and a complex shanpon {ph(complex_shape)} {ph(pair)},"
                    f" this hand is best described as **complete iishanten**.",
                    perfect_str if is_perfect else "",
                    f"The waits for complete iishanten with a complex shanpon"
                    f" are comprised of the wait of its simple shape {ph(sorted_hand(simple_wait))}"
                    f" plus the wait of its complex shanpon {ph(sorted_hand(complex_waits))}."
                ])
            else:
                ret.extend([
                    f"Due to having a simple shape {ph(simple_shape)}"
                    f" and a ryankan {ph(complex_shape)} plus a pair {ph(pair)},"
                    f" this hand is best described as **complete iishanten**.",
                    f"\nThe waits for complete iishanten with a ryankan"
                    f" are comprised of the wait of its simple shape {ph(sorted_hand(simple_wait))}"
                    f" plus the wait of its ryankan {ph(sorted_hand(complex_waits))}."
                ])
        elif not (simple_wait | complex_waits).issubset(waits):
            if is_complex_pair:
                ret.extend(["",
                    f"This hand can also be interpreted as having a simple shape {ph(simple_shape)}"
                    f" and a complex shanpon {ph(complex_shape)} {ph(pair)},"
                    f" which means this hand is also **complete iishanten**.",
                    perfect_str if is_perfect else "",
                    f"The waits for complete iishanten with a complex shanpon"
                    f" are comprised of the wait of its simple shape {ph(sorted_hand(simple_wait))}"
                    f" plus the wait of its complex shanpon {ph(sorted_hand(complex_waits))},"
                    f" adding {ph(sorted_hand((simple_wait | complex_waits) - waits))} to the wait."
                ])
            else:
                ret.extend(["",
                    f"This hand can also be interpreted as having a simple shape {ph(simple_shape)}"
                    f" and a ryankan {ph(complex_shape)} plus a pair {ph(pair)},"
                    f" which means this hand is also **complete iishanten**.",
                    f"\nThe waits for complete iishanten with a ryankan"
                    f" are comprised of the wait of its simple shape {ph(sorted_hand(simple_wait))}"
                    f" plus the wait of its ryankan {ph(sorted_hand(complex_waits))},"
                    f" adding {ph(sorted_hand((simple_wait | complex_waits) - waits))} to the wait."
                ])
        else:
            continue
        waits |= simple_wait | complex_waits
    return ret

def describe_headless_iishanten(debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    simple_shapes = debug_info["headless_taatsus"]
    floating_tiles = debug_info["headless_floating_tiles"]
    headless_tanki_waits = debug_info["headless_tanki_waits"]
    headless_taatsu_waits = debug_info["headless_taatsu_waits"]
    if len(waits) == 0:
        if len(simple_shapes) == 1:
            return [
                f"Due to having a simple shape {ph(next(iter(simple_shapes)))}"
                f" and {'2' if len(floating_tiles) == 2 else '2+'} floating tiles {ph(sorted_hand(floating_tiles))},"
                f" this hand is best described as **broken headless iishanten**.\n\n"
                f"The waits for broken headless iishanten are tanki waits on the floating tiles: {ph(sorted_hand(headless_tanki_waits))}"
                f" as well as the waits of its simple shape: {ph(sorted_hand(headless_taatsu_waits))}."
            ]
        else:
            return [
                f"Due to having {'2' if len(simple_shapes) == 2 else '2+'} simple shapes {' '.join(map(ph, simple_shapes))} which are not pairs,"
                f" this hand is best described as **headless iishanten**.\n\n"
                f"The waits for headless iishanten are tanki waits on each tile: {ph(sorted_hand(headless_tanki_waits))}"
                f" as well as the waits of the simple shapes themselves: {ph(sorted_hand(headless_taatsu_waits))}."
            ]
    elif not (headless_tanki_waits | headless_taatsu_waits).issubset(waits):
        if len(simple_shapes) == 1:
            return ["",
                f"This hand can also be interpreted as having one simple shape {ph(next(iter(simple_shapes)))}"
                f" and {'2' if len(floating_tiles) == 2 else '2+'} floating tiles {ph(sorted_hand(floating_tiles))},"
                f" which means this hand is also **broken headless iishanten**.\n\n"
                f"The waits for broken headless iishanten are tanki waits on the floating tiles: {ph(sorted_hand(headless_tanki_waits))}"
                f" as well as the waits of its simple shape: {ph(sorted_hand(headless_taatsu_waits))},"
                f" adding {ph(sorted_hand((headless_tanki_waits | headless_taatsu_waits) - waits))} to the wait."
            ]
        else:
            return ["",
                f"This hand can also be interpreted as having {'2' if len(simple_shapes) == 2 else '2+'} simple shapes {' '.join(map(ph, simple_shapes))} which are not pairs,"
                f" which means this hand is also **headless iishanten**.\n\n"
                f"The waits for headless iishanten are tanki waits on each tile: {ph(sorted_hand(headless_tanki_waits))}"
                f" as well as the waits of the simple shapes themselves: {ph(sorted_hand(headless_taatsu_waits))},"
                f" adding {ph(sorted_hand((headless_tanki_waits | headless_taatsu_waits) - waits))} to the wait."
            ]
    else:
        return []

def describe_kuttsuki_iishanten(debug_info: Dict[str, Any]) -> List[str]:
    floating_tiles = debug_info["kuttsuki_tiles"]
    kuttsuki_waits = debug_info["kuttsuki_waits"]
    return [
        f"Due to having a pair and {'2' if len(floating_tiles) == 2 else '2+'} floating tiles {ph(sorted_hand(floating_tiles))},"
        f" this hand is best described as **sticky iishanten**.\n\n"
        f"The waits for sticky iishanten are the tiles 0-2 away from each floating tile,"
        f" which altogether are {ph(sorted_hand(kuttsuki_waits))}."
    ]

def describe_chiitoitsu_iishanten(debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    chiitoitsu_waits = set(debug_info["chiitoitsu_waits"])
    if len(waits) == 0:
        return [
            f"Due to having five pairs,"
            f" this hand is best described as **chiitoitsu iishanten**.\n\n"
            f"The waits for chiitoitsu iishanten are tanki waits"
            f" on the unpaired tiles {ph(sorted_hand(chiitoitsu_waits))}."
        ]
    elif not chiitoitsu_waits.issubset(waits):
        return ["",
            f"Having five pairs, this hand is also **chiitoitsu iishanten**.\n\n"
            f"The waits for chiitoitsu iishanten are tanki waits"
            f" on the unpaired tiles {ph(sorted_hand(chiitoitsu_waits))},"
            f" adding {ph(sorted_hand(chiitoitsu_waits - waits))} to the wait."
        ]
    else:
        return []


def describe_kokushi_iishanten(debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    kokushi_waits = set(debug_info["kokushi_waits"])
    if len(kokushi_waits) == 2:
        return [
            f"Due to having 11 terminal/honor tiles with a terminal/honor pair,"
            f" this hand is best described as **kokushi iishanten**.\n\n"
            f"The waits for kokushi iishanten are the remaining terminal/honors {ph(sorted_hand(kokushi_waits))}."
        ]
    else:
        return ["",
            f"Due to having 12 terminal/honor tiles with no pair,"
            f" this hand is best described as **13-sided kokushi iishanten**.\n\n"
            f"The waits for kokushi iishanten are any terminal/honor tile {ph(sorted_hand(kokushi_waits))}."
        ]

def describe_tanki_iishanten(debug_info: Dict[str, Any]) -> List[str]:
    tanki_iishanten_waits = debug_info["tanki_iishanten_waits"]
    return [
        f"Since this hand is basically tenpai with a tanki wait, but all four tiles of that tanki wait are in your hand,"
        f" this hand is best described as **tanki iishanten**.\n\n"
        f"The waits for tanki iishanten include everything but that tanki tile: {ph(sorted_hand(tanki_iishanten_waits))}."
    ]

def describe_ankan(debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    ankan_tiles = debug_info["ankan_tiles"]
    if len(ankan_tiles & waits) > 0:
        return [
            f"Since all four tiles are in hand,"
            f" we cannot consider {ph(sorted_hand(ankan_tiles))} as part of the wait."
        ]
    else:
        return []

def describe_tenpai(debug_info: Dict[str, Any]) -> List[str]:
    tenpai_waits = debug_info["tenpai_waits"]
    return [
        f"This hand is tenpai, waiting on {ph(sorted_hand(tenpai_waits))}."
    ]

def describe_shanten(debug_info: Dict[str, Any]) -> List[str]:
    shanten = debug_info["shanten"]
    c_shanten = debug_info["c_shanten"]
    k_shanten = debug_info["k_shanten"]
    if c_shanten < shanten:
        return [f"This hand is standard {shanten}-shanten, but {c_shanten}-shanten for chiitoitsu."]
    elif k_shanten < shanten:
        return [f"This hand is standard {shanten}-shanten, but {k_shanten}-shanten for kokushi musou."]
    else:
        return [f"This hand is {shanten}-shanten."]

# debug
if __name__ == "__main__":
    print("\n".join(analyze_hand(translate_hand("1122345588899m"))))
