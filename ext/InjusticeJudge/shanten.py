from typing import *
from modules.InjusticeJudge.injustice_judge.display import ph, pt
from modules.InjusticeJudge.injustice_judge.constants import SUCC, PRED, TANYAOHAI, YAOCHUUHAI
from modules.InjusticeJudge.injustice_judge.shanten import Suits, to_suits, from_suits, eliminate_all_groups, eliminate_some_groups, get_shanten_type, calculate_chiitoitsu_shanten, calculate_kokushi_shanten, eliminate_some_taatsus, get_hand_shanten, get_tenpai_waits, calculate_wait_extensions, calculate_tanki_wait_extensions
from modules.InjusticeJudge.injustice_judge.utils import try_remove_all_tiles, normalize_red_fives, sorted_hand, get_taatsu_wait

SHANTEN_STRINGS = {1: "iishanten", 2: "ryanshanten", 3: "sanshanten"}

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

def _analyze_hand(hand: Tuple[int, ...]) -> Tuple[List[str], Set[int]]:
    if len(hand) not in {4, 7, 10, 13}:
        return ["The given hand must be of length 4, 7, 10, or 13."], set()
    suits = to_suits(hand)
    groupless_hands = eliminate_all_groups(suits)
    groups_needed = (len(next(from_suits(groupless_hands))) - 1) // 3
    removed_taatsus = eliminate_some_taatsus(groupless_hands)
    shanten_int: int = get_hand_shanten(removed_taatsus, groups_needed)
    shanten: float = float(shanten_int)
    waits: Set[int] = set()
    debug_info: Dict[str, Any] = {"hand": hand, "shanten": shanten}
    ctr = Counter(normalize_red_fives(hand))
    ret = [f"Hand: {ph(hand)}", f"Hand with groups removed: {' or '.join(sorted(map(ph, from_suits(groupless_hands))))}", ""]

    # check non-standard shanten
    if len(hand) == 13:
        c_shanten, c_waits = calculate_chiitoitsu_shanten(hand, ctr)
        k_shanten, k_waits = calculate_kokushi_shanten(hand, ctr)
        debug_info["c_shanten"] = c_shanten
        debug_info["k_shanten"] = k_shanten
        if c_shanten <= shanten_int:
            debug_info["chiitoitsu_waits"] = set(c_waits)
        elif k_shanten <= shanten_int:
            debug_info["kokushi_waits"] = set(k_waits)

    if shanten_int == 0:
        waits = get_tenpai_waits(hand)
        debug_info["tenpai_waits"] = waits
        ret.extend(describe_tenpai(debug_info))
    elif shanten_int in {1, 2, 3}:
        shanten, expected_waits, new_debug_info = get_shanten_type(shanten_int, hand, groupless_hands, groups_needed)
        debug_info.update(new_debug_info)
        # shanten returned from this func is always 1.0xx

        # check standard iishanten
        shanten_digits = str(round(shanten*1000))
        if shanten_digits[2] in "23":
            ret.extend(describe_kuttsuki_shanten(shanten_int, debug_info))
            waits |= debug_info["kuttsuki_taatsu_waits"]
            waits |= debug_info["kuttsuki_tanki_waits"]
            waits |= debug_info["kuttsuki_pair_tiles"]
        if shanten_digits[2] in "13":
            ret.extend(describe_headless_shanten(shanten_int, debug_info, waits))
            waits |= debug_info["headless_taatsu_waits"]
            waits |= debug_info["headless_tanki_waits"]
            extended_waits = set(wait for waits, _, _ in debug_info["headless_tanki_extensions"] for wait in waits)
            waits |= extended_waits
        if shanten_digits[3] in "123":
            ret.extend(describe_simple_shanten(shanten_int, debug_info, waits))
            for s_hand in debug_info["simple_hands"]:
                waits |= s_hand["simple_waits"]  # type: ignore[call-overload]
                waits |= s_hand["complex_waits"]  # type: ignore[call-overload]

        # check non-standard iishanten
        if len(hand) == 13:
            if c_shanten == shanten_int and "chiitoitsu_waits" in debug_info:
                ret.extend(describe_chiitoitsu_shanten(shanten_int, debug_info, waits))
                waits |= debug_info["chiitoitsu_waits"]
            elif k_shanten == shanten_int and "kokushi_waits" in debug_info:
                ret.extend(describe_kokushi_shanten(shanten_int, debug_info, waits))
                waits |= debug_info["kokushi_waits"]

    else: # shanten >= 4
        ret.extend(describe_shanten(debug_info))

    # check for tanki iishanten
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

    if len(waits) > 0:
        ret.insert(2, f"Total waits: {ph(sorted_hand(waits))}")
        ret.extend(["", f"This results in an overall wait on {ph(sorted_hand(waits))}."])

    return ret, waits

def analyze_hand(hand: Tuple[int, ...]) -> List[str]:
    ret, waits = _analyze_hand(hand)
    return ret

def get_shape_str(max_shapes: int, simple_shapes: Tuple[Tuple[int, ...], ...], complex_shapes: Tuple[Tuple[int, ...], ...], pair: Optional[Tuple[int, ...]], max_floating: int, floating_tiles: Tuple[int, ...]):
    has_complex_pair = any(len(set(complex_shape)) == 2 for complex_shape in complex_shapes)
    shape_str = ""
    shape_num = len(simple_shapes) + len(complex_shapes)
    simple_shape_has_pair = any((t1 == t2) for t1, t2 in simple_shapes)
    if shape_num > 0 and max_shapes > 0:
        s = "s" if shape_num != 1 else ""
        if len(complex_shapes) == 0:
            if simple_shape_has_pair:
                shape_str = f"pair{s}/simple shape{s} {' '.join(map(ph, simple_shapes + complex_shapes))}"
            else:
                shape_str = f"simple shape{s} {' '.join(map(ph, simple_shapes + complex_shapes))}"
        elif len(simple_shapes) == 0:
            shape_str = f"complex shape{s} {' '.join(map(ph, simple_shapes + complex_shapes))}"
        else:
            shape_str = f"simple and complex shape{s} {' '.join(map(ph, simple_shapes + complex_shapes))}"
        shape_num_str = f"{max_shapes}+" if shape_num > max_shapes else "a" if shape_num == 1 else str(shape_num)
        shape_str = f"{shape_num_str} {shape_str}"

    pair_str = f"a pair {ph(pair)}" if pair is not None else "no pairs" if not simple_shape_has_pair and shape_num > 0 else ""
    floating_num = len(floating_tiles)
    floating_num_str = f"{max_floating}+" if floating_num > max_floating else "a" if floating_num == 1 else str(floating_num)
    floating_str = f"{floating_num_str} floating {ph(floating_tiles)}" if floating_num > 0 else "no floating tiles"
    return f" and ".join(s for s in [shape_str, pair_str, floating_str] if s != "")

def describe_simple_shanten(shanten: int, debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    ret = []
    is_ryanmen = lambda h: len(h) == 2 and SUCC[h[0]] == h[1] and h[0] not in {11,18,21,28,31,38}
    shanten_string = SHANTEN_STRINGS[shanten]
    def add_hand(hand):
        nonlocal waits
        pair = hand["pair"]
        simple_shapes = hand["simple_shapes"]
        complex_shapes = hand["complex_shapes"]
        floating_tiles = hand["floating_tiles"]
        simple_waits = hand["simple_waits"]
        complex_waits = hand["complex_waits"]
        extensions = hand["extensions"]
        has_complex_pair = any(len(set(complex_shape)) == 2 for complex_shape in complex_shapes)
        perfect_str = ""
        is_complete = len(floating_tiles) == 0
        if shanten == 1 and len(complex_shapes) > 0:
            t1, t2 = complex_shapes[0][0:2], complex_shapes[0][1:3]
            is_perfect = is_ryanmen(simple_shapes) and (is_ryanmen(t1) or is_ryanmen(t2))
            if is_perfect:
                perfect_str = "\n\nThis ryanmen-ryanmen form of complete iishanten is also known as **perfect iishanten**.\n"
        if is_complete:
            shape_str = get_shape_str(shanten+1, simple_shapes, complex_shapes, pair, 100, floating_tiles)
            if len(waits) == 0:
                ret.extend([
                    f"Due to having {shape_str},"
                    f" this hand is best described as **complete {shanten_string}**." + perfect_str
                ])
            elif not (simple_waits | complex_waits).issubset(waits):
                ret.extend(["",
                    f"This hand can also be interpreted as having {shape_str},"
                    f" which means this hand is also **complete {shanten_string}**." + perfect_str,
                    
                ])
            else:
                return
        else:
            shape_str = get_shape_str(shanten+1, simple_shapes, complex_shapes, pair, 100, floating_tiles)
            if len(waits) == 0:
                ret.append(
                    f"Due to having {shape_str},"
                    f" this hand is best described as **floating tile {shanten_string}**.")
            elif not (simple_waits | complex_waits).issubset(waits):
                ret.extend(["",
                    f"This hand can also be interpreted as having {shape_str},"
                    f" which means this hand is also **floating tile {shanten_string}**."])
            else:
                return

        wait_strs = []
        if len(simple_shapes) > 0:
            s = "s" if len(simple_shapes) != 1 else ""
            wait_strs.append(f"its simple shape{s} {ph(sorted_hand(simple_waits))}")
        if len(complex_shapes) > 0:
            s = "s" if len(complex_shapes) != 1 else ""
            wait_strs.append(f"its complex shape{s} {ph(sorted_hand(complex_waits))}")
        add_string = "" if len(waits) == 0 else f", adding {ph(sorted_hand((simple_waits | complex_waits) - waits))} to the wait"
        ret.extend(["",
            f"The waits for {'complete' if is_complete else 'floating tile'} {shanten_string} are completely determined by the waits of"
            f" {' and '.join(wait_strs)}{add_string}."
        ])

        waits |= simple_waits | complex_waits
        ret.extend(describe_extensions(waits, extensions, []))
        extended_waits = set(wait for waits, _, _ in extensions for wait in waits)
        waits |= extended_waits

    n_waits = lambda h: len(h["simple_waits"] | h["complex_waits"] | set(wait for waits, _, _ in h["extensions"] for wait in waits) - waits)
    key = lambda h: -(10 * n_waits(h) + len(h["complex_shapes"]))

    all_hands = sorted(debug_info["simple_hands"], key=key)
    while len(all_hands) > 0:
        add_hand(all_hands[0])
        all_hands = [hand for hand in sorted(all_hands[1:], key=key) if n_waits(hand) != 0]
    return ret

def describe_extensions(
        waits: Set[int],
        extensions: List[Tuple[Set[int], int, Tuple[int, int, int]]],
        tanki_extensions: List[Tuple[Set[int], int, Tuple[int, int, int]]]) -> List[str]:
    ret = []
    used_sequence = False
    used_adj_sequence = False
    used_triplet = False
    extend_text = []
    # (wait, is_tanki) => [relative groups like (1,2,3)]
    extensions_for_tile: Dict[Tuple[int, bool], List[Tuple[int, ...]]] = {}

    all_extensions = [(ext, False) for ext in extensions] + [(ext, True) for ext in tanki_extensions]
    for (new_waits, tile, group), is_tanki in all_extensions:
        # build up a catalog of relative extensions for each tile
        if (tile, is_tanki) not in extensions_for_tile:
            extensions_for_tile[(tile, is_tanki)] = []
        extensions_for_tile[(tile, is_tanki)].append(tuple(t - tile for t in group))

        # skip if all the waits of this group are covered
        if len(new_waits - waits) == 0:
            continue

        # set flags based on kinds of groups we've used
        is_triplet = group[0] == group[1]
        if is_triplet:
            used_triplet = True
        elif tile not in group:
            used_adj_sequence = True
        else:
            used_sequence = True

        # actually describe the extension now
        extend_text.append(f"the {'triplet' if is_triplet else 'sequence'} {ph(sorted_hand(group))} extends the {pt(tile)} wait to {ph(sorted_hand(new_waits))}")
        waits |= new_waits

    if len(extend_text) > 1:
        extend_text[-1] = "and " + extend_text[-1]

    # mention named shapes based on extensions
    # the way we do this is by referencing the catalog we built
    named_shape_text = []
    ignore_nobetan = False
    ignore_ryantan_pentan = False
    ignore_sanmenchan = False
    pg = lambda tile, ext_group: ph(tuple(t + tile for t in ext_group)) # print group
    # we do a two-pass system since some shapes subsume other shapes
    # first pass
    for (wait, is_tanki), ext_groups in extensions_for_tile.items():
        left_triplet = (-1,-1,-1) in ext_groups
        right_adj_sequence = (1,2,3) in ext_groups
        is_happoubijin = False
        is_2223456 = False
        is_2345666 = False
        if is_tanki and right_adj_sequence: # nobetan
            suji = (SUCC[SUCC[SUCC[wait]]], True)
            if suji in extensions_for_tile:
                suji_ext_groups = extensions_for_tile[suji]
                if (1,1,1) in suji_ext_groups:
                    if left_triplet:
                        is_happoubijin = True
                    else:
                        is_2345666 = True
            if left_triplet:
                is_2223456 = True

        if is_happoubijin or is_2223456 or is_2345666:
            ignore_nobetan = True
            ignore_ryantan_pentan = True
            ignore_sanmenchan = True

        if is_happoubijin:
            named_shape_text.append(f"The extended shape {pg(wait, (-1,-1,-1,0,1,2,3,4,4,4))} is often called **happoubijin**, waiting on {pg(wait, (-2,-1,0,1,2,3,4,5))}.")
        elif is_2223456:
            named_shape_text.append(f"The extended shape {pg(wait, (-1,-1,-1,0,1,2,3))} is often seen as a combination of the **sanmenchan** {pg(wait, (-1,0,1,2,3))} and **nobetan** {pg(wait, (0,1,2,3))} shapes, waiting on {pg(wait, (-2,0,1,3,4))}.")
        elif is_2345666:
            named_shape_text.append(f"The extended shape {pg(wait, (0,1,2,3,4,4,4))} is often seen as a combination of the **sanmenchan** {pg(wait, (0,1,2,3,4))} and **nobetan** {pg(wait, (0,1,2,3))} shapes, waiting on {pg(wait, (-1,0,2,3,5))}.")

    # second pass
    # to deduplicate, we evaluate the leftmost tile with the most extensions first
    for (wait, is_tanki), ext_groups in sorted(extensions_for_tile.items(), key=lambda x: -10*len(x[1])+(x[0][0]%10)):
        left_triplet = (-1,-1,-1) in ext_groups
        right_triplet = (1,1,1) in ext_groups
        left_left_triplet = (-2,-2,-2) in ext_groups
        right_right_triplet = (2,2,2) in ext_groups
        right_sequence = (0,1,2) in ext_groups
        left_sequence = (-2,-1,0) in ext_groups
        left_adj_sequence = (-3,-2,-1) in ext_groups
        right_adj_sequence = (1,2,3) in ext_groups
        right_adj_sequence2 = (4,5,6) in ext_groups
        if left_triplet and right_triplet:
            named_shape_text.append(f"The extended tanki shape {pg(wait, (-1,-1,-1,0,1,1,1))} is often called **tatsumaki**, waiting on {pg(wait, (-2,-1,0,1,2))}.")
        elif left_left_triplet and right_right_triplet:
            named_shape_text.append(f"The extended tanki shape {pg(wait, (-2,-2,-2,0,2,2,2))} is often called **kankantan**, waiting on {pg(wait, (-1,0,1))}.")
        elif left_triplet and not ignore_ryantan_pentan:
            if SUCC[wait] != 0 and PRED[PRED[wait]] != 0:
                named_shape_text.append(f"The extended tanki shape {pg(wait, (-1,-1,-1,0))} is often called **ryantan**, waiting on {pg(wait, (-2,0,1))}.")
            elif SUCC[wait] == 0:
                named_shape_text.append(f"The extended tanki shape {pg(wait, (-1,-1,-1,0))} is often called **pentan**, waiting on {pg(wait, (-2,0))}.")
            else:
                named_shape_text.append(f"The extended tanki shape {pg(wait, (-1,-1,-1,0))} is often called **pentan**, waiting on {pg(wait, (0,1))}.")
        elif right_triplet and not ignore_ryantan_pentan:
            if PRED[wait] != 0 and SUCC[SUCC[wait]] != 0:
                named_shape_text.append(f"The extended tanki shape {pg(wait, (0,1,1,1))} is often called **ryantan**, waiting on {pg(wait, (-1,0,2))}.")
            elif PRED[wait] == 0:
                named_shape_text.append(f"The extended tanki shape {pg(wait, (0,1,1,1))} is often called **pentan**, waiting on {pg(wait, (0,2))}.")
            else:
                named_shape_text.append(f"The extended tanki shape {pg(wait, (0,1,1,1))} is often called **pentan**, waiting on {pg(wait, (-1,0))}.")
        elif left_left_triplet:
            named_shape_text.append(f"The extended tanki shape {pg(wait, (-2,-2,-2,0))} is often called **kantan**, waiting on {pg(wait, (-1,0))}.")
        elif right_right_triplet:
            named_shape_text.append(f"The extended tanki shape {pg(wait, (0,2,2,2))} is often called **kantan**, waiting on {pg(wait, (0,1))}.")

        if right_adj_sequence and not ignore_nobetan:
            if right_adj_sequence2:
                named_shape_text.append(f"The extended tanki shape {pg(wait, (0,1,2,3,4,5,6))} is often called **sanmentan**, waiting on {pg(wait, (0,3,6))}.")
                ignore_nobetan = True
            else:
                named_shape_text.append(f"The extended tanki shape {pg(wait, (0,1,2,3))} is often called **nobetan**, waiting on {pg(wait, (0,3))}.")
        elif left_sequence and is_tanki:
            named_shape_text.append(f"The extended tanki shape {pg(wait, (-2,-1,0,0))} is often called **aryanmen**, waiting on {pg(wait, (-3,0))}.")
        elif left_sequence and right_sequence and not ignore_sanmenchan:
            named_shape_text.append(f"The extended shape {pg(wait, (-2,-1,0,1,2))} is often called **sanmenchan**, waiting on {pg(wait, (-3,0,3))}.")
        elif right_sequence and is_tanki:
            named_shape_text.append(f"The extended tanki shape {pg(wait, (0,0,1,2))} is often called **aryanmen**, waiting on {pg(wait, (0,3))}.")

    # TODO:
    # - entotsu (shanpon extension)

    if len(named_shape_text) > 0:
        named_shape_text[0] = "Note that t" + named_shape_text[0][1:]
    if len(named_shape_text) > 1:
        named_shape_text[-1] = "And t" + named_shape_text[-1][1:]

    explain_text = []
    if used_sequence:
        explain_text.append(f"sequences in hand can extend the waits if one of their ends overlaps a wait")
    if used_adj_sequence:
        if used_sequence:
            explain_text.append(f" or is adjacent to a tanki wait")
        else:
            explain_text.append(f"sequences in hand can extend a tanki wait if one of their ends is adjacent to the tanki wait")
    if used_triplet:
        explain_text.append(f"any triplet near a tanki wait extends a tanki wait")

    if len(explain_text) > 1:
        explain_text[-1] = "and " + explain_text[-1]

    if len(extend_text) > 0:
        ret.extend(["", ", ".join(explain_text).capitalize() + ".", f" In particular, " + ", ".join(extend_text) + "."])
    if len(named_shape_text) > 0:
        ret.extend(["", " ".join(named_shape_text)])

    return ret

def describe_headless_shanten(shanten: int, debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    simple_shapes = debug_info["headless_taatsus"]
    floating_tiles = debug_info["headless_floating_tiles"]
    headless_tanki_waits = debug_info["headless_tanki_waits"]
    headless_taatsu_waits = debug_info["headless_taatsu_waits"]
    extensions = debug_info["headless_tanki_extensions"]
    shanten_string = SHANTEN_STRINGS[shanten]
    shape_str = get_shape_str(shanten+1, simple_shapes, (), None, shanten+1, floating_tiles)
    is_broken = len(simple_shapes) == shanten
    ret = []
    if len(waits) == 0:
        if is_broken:
            ret.append(f"Due to having {shape_str}, this hand is best described as **broken headless {shanten_string}**.")
        else:
            ret.append(f"Due to having {shape_str}, this hand is best described as **headless {shanten_string}**.")
    elif not (headless_tanki_waits | headless_taatsu_waits).issubset(waits):
        if is_broken:
            ret.extend(["",
                f"This hand can also be interpreted as having {shape_str},"
                f" which means this hand is also **broken headless {shanten_string}**."
            ])
        else:
            ret.extend(["",
                f"This hand can also be interpreted as having {shape_str},"
                f" which means this hand is also **headless {shanten_string}**."
            ])
    else:
        return []

    add_string = "" if len(waits) == 0 else f" adding {ph(sorted_hand((headless_tanki_waits | headless_taatsu_waits) - waits))} to the wait."
    ret.extend(["",
        f"The waits for {'broken headless' if is_broken else 'headless'} {shanten_string}"
        f" are tanki waits on {'the floating tiles' if is_broken else 'each tile'}: {ph(sorted_hand(headless_tanki_waits))}"
        f" as well as the simple shape waits themselves: {ph(sorted_hand(headless_taatsu_waits))}{add_string}."
    ])

    ret.extend(describe_extensions(waits | headless_tanki_waits | headless_taatsu_waits, [], extensions))

    return ret

def describe_kuttsuki_shanten(shanten: int, debug_info: Dict[str, Any]) -> List[str]:
    floating_tiles = debug_info["kuttsuki_tiles"]
    kuttsuki_taatsus = debug_info["kuttsuki_taatsus"]
    kuttsuki_taatsu_waits = debug_info["kuttsuki_taatsu_waits"]
    kuttsuki_tanki_waits = debug_info["kuttsuki_tanki_waits"]
    kuttsuki_pair_tiles = debug_info["kuttsuki_pair_tiles"]
    pairs = tuple((tile, tile) for tile in kuttsuki_pair_tiles)
    pair = pairs[0] if len(pairs) > 0 else None
    shanten_string = SHANTEN_STRINGS[shanten]
    shape_str = get_shape_str(0 if shanten == 1 else 1, kuttsuki_taatsus, (), pair, shanten*2, floating_tiles)
    ret = []
    ret.append(f"Due to having {shape_str}, this hand is best described as **sticky {shanten_string}**.")

    ps = "s" if len(kuttsuki_pair_tiles) != 1 else ""
    ss = "s" if len(kuttsuki_taatsus) != 1 else ""
    pair_string = "" if len(kuttsuki_pair_tiles) == 0 else f"pair{ps} {ph(sorted_hand(kuttsuki_pair_tiles))}"
    taatsu_string = "" if len(kuttsuki_taatsus) == 0 else f"simple shape{ss} {ph(sorted_hand(kuttsuki_taatsu_waits))}"
    extra_wait_str = " and ".join(s for s in [pair_string, taatsu_string] if s != "")
    if extra_wait_str != "":
        extra_wait_str = ", as well as the waits of its " + extra_wait_str
    ret.extend(["",
        f"The waits for sticky {shanten_string} are the tiles 0-2 away from each floating tile,"
        f" which altogether are {ph(sorted_hand(kuttsuki_tanki_waits))}" + extra_wait_str + "."
    ])

    return ret

def describe_chiitoitsu_shanten(shanten: int, debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    chiitoitsu_waits = set(debug_info["chiitoitsu_waits"])
    shanten_string = SHANTEN_STRINGS[shanten]
    num_pairs = {1: "five", 2: "four", 3: "three"}[shanten]
    if len(waits) == 0:
        return [
            f"Due to having {num_pairs} pairs,"
            f" this hand is best described as **chiitoitsu {shanten_string}**.\n\n"
            f"The waits for chiitoitsu {shanten_string} are tanki waits"
            f" on the unpaired tiles {ph(sorted_hand(chiitoitsu_waits))}."
        ]
    elif not chiitoitsu_waits.issubset(waits):
        return ["",
            f"Having {num_pairs} pairs, this hand is also **chiitoitsu {shanten_string}**.\n\n"
            f"The waits for chiitoitsu {shanten_string} are tanki waits"
            f" on the unpaired tiles {ph(sorted_hand(chiitoitsu_waits))},"
            f" adding {ph(sorted_hand(chiitoitsu_waits - waits))} to the wait."
        ]
    else:
        return []

def describe_kokushi_shanten(shanten: int, debug_info: Dict[str, Any], waits: Set[int]) -> List[str]:
    kokushi_waits = set(debug_info["kokushi_waits"])
    shanten_string = SHANTEN_STRINGS[shanten]
    num_pairs = {1: 11, 2: 10, 3: 9}[shanten]
    if len(kokushi_waits) == 2:
        return [
            f"Due to having {num_pairs} terminal/honor tiles with a terminal/honor pair,"
            f" this hand is best described as **kokushi {shanten_string}**.\n\n"
            f"The waits for kokushi {shanten_string} are the remaining terminal/honors {ph(sorted_hand(kokushi_waits))}."
        ]
    else:
        return ["",
            f"Due to having {num_pairs+1} terminal/honor tiles with no pair,"
            f" this hand is best described as **13-sided kokushi {shanten_string}**.\n\n"
            f"The waits for 13-sided kokushi {shanten_string} are any terminal/honor tile {ph(sorted_hand(kokushi_waits))}."
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
    ret = [f"This hand is tenpai, waiting on {ph(sorted_hand(tenpai_waits))}."]
    hand = debug_info["hand"]
    suits = to_suits(hand)
    groupless_removed = list(from_suits(eliminate_some_groups(suits)))
    tanki_hands = [hand for hand in groupless_removed if len(hand) == 1]
    def remove_pair(hand):
        ctr = Counter(hand)
        [pair_tile] = [tile for tile, cnt in ctr.items() if cnt > 1]
        return try_remove_all_tiles(hand, (pair_tile, pair_tile))
    taatsu_hands = [hand for hand in groupless_removed if len(hand) == 4 if set(Counter(hand).values()) in [{1, 2}, {1, 3}] if get_taatsu_wait(remove_pair(hand)) != set()]
    shanpon_hands = [hand for hand in groupless_removed if len(hand) == 4 if set(Counter(hand).values()) == {2}]
    orig_waits: Set[int] = set()
    waits: Set[int] = set()
    extensions: List[Tuple[Set[int], int, Tuple[int, int, int]]] = []
    tanki_extensions: List[Tuple[Set[int], int, Tuple[int, int, int]]] = []

    if len(tanki_hands) > 0:
        tanki_tiles = tuple(tile for hand in tanki_hands for tile in hand)
        s = "s" if len(tanki_hands) != 1 else ""
        ret.extend(["", f"The waits for this hand include the tanki wait{s} {ph(tanki_tiles)}."])
        # look for extensions
        waits |= set(tanki_tiles)
        orig_waits |= set(tanki_tiles)
        for tanki_hand in tanki_hands:
            groups = try_remove_all_tiles(hand, tanki_hand)
            new_extensions = calculate_tanki_wait_extensions(groups, set(tanki_hand))
            tanki_extensions.extend(new_extensions)
            waits |= set().union(wait for waits, _, _ in new_extensions for wait in waits)

    taatsus_used: Set[Tuple[int, ...]] = set()
    if len(taatsu_hands) > 0:
        # look for extensions
        # taatsus_used = [(taatsu, waits)]
        taatsu_extensions: List[Tuple[Tuple[int, ...], Set[int], Set[int], List[Tuple[Set[int], int, Tuple[int, int, int]]]]] = []
        for taatsu_hand in taatsu_hands:
            groups = try_remove_all_tiles(hand, taatsu_hand)
            taatsu = remove_pair(taatsu_hand)
            new_waits = get_taatsu_wait(taatsu)
            new_extensions = calculate_wait_extensions(groups, new_waits)
            extended_waits = new_waits.union(wait for waits, _, _ in new_extensions for wait in waits)
            if not (new_waits | extended_waits).issubset(waits):
                taatsu_extensions.append((taatsu, new_waits, extended_waits, new_extensions))
        taatsu_waits: Set[int] = set()
        def add_taatsu_extension(taatsu, new_waits, extended_waits, new_extensions):
            nonlocal waits
            nonlocal taatsus_used
            nonlocal taatsu_waits
            nonlocal extensions
            taatsus_used.add(taatsu)
            taatsu_waits |= new_waits
            waits |= new_waits
            extensions.extend(new_extensions)

        n_waits = lambda h: len((h[1] | h[2]) - waits)
        key = lambda h: -(10 * n_waits(h) + len(h[1]))
        taatsu_extensions = sorted(taatsu_extensions, key=key)
        while len(taatsu_extensions) > 0:
            add_taatsu_extension(*taatsu_extensions[0])
            taatsu_extensions = [h for h in sorted(taatsu_extensions[1:], key=key) if n_waits(h) != 0]

        if len(taatsus_used) > 0 and not taatsu_waits.issubset(orig_waits):
            s = "s" if len(taatsus_used) != 1 else ""
            also = "also " if len(tanki_hands) > 0 else ""
            ret.extend(["",
                f"This hand {also}has the simple shape{s} {' '.join(ph(sorted_hand(taatsu)) for taatsu in sorted(taatsus_used))},"
                f" adding {ph(sorted_hand(taatsu_waits - orig_waits))} to the wait."])
            orig_waits |= taatsu_waits

    if len(shanpon_hands) > 0:
        shanpon_waits = set(tile for hand in shanpon_hands for tile in hand)
        if not shanpon_waits.issubset(waits):
            also = "also " if len(tanki_hands) > 0 or len(taatsus_used) > 0 else ""
            ret.extend(["",
                f"This hand {also}has the shanpon {' '.join(ph((wait, wait)) for wait in shanpon_waits)},"
                f" adding {ph(sorted_hand(shanpon_waits - waits))} to the wait."])
            orig_waits |= shanpon_waits

    ret.extend(describe_extensions(orig_waits, extensions, tanki_extensions))
    return ret

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

def assert_analyze_hand(hand: str, expected_waits: str, print_anyways: bool = False, mentions: str = ""):
    ret, waits = _analyze_hand(translate_hand(hand))
    expected_wait_set = set(translate_hand(expected_waits))
    if waits != expected_wait_set:
        print("\n".join(ret))
        # print(f"\nExpected to wait on {ph(sorted_hand(expected_wait_set))}.")
        print(f"\nMissing waits: {ph(sorted_hand(expected_wait_set - waits))}.")
        print(f"\nExtra waits: {ph(sorted_hand(waits - expected_wait_set))}.")
    elif mentions != "" and not any(mentions in r for r in ret):
        print("\n".join(ret))
        print(f"\nExpected output to mention '{mentions}'.")
    elif print_anyways:
        print("\n".join(ret))

# debug
if __name__ == "__main__":
    pass
    # # tenpai
    # assert_analyze_hand("2345666m222444p", "12457m", mentions="combination")
    # assert_analyze_hand("2223456m222444p", "13467m", mentions="combination")
    # assert_analyze_hand("2223456777m222p", "12345678m", mentions="happoubijin")
    # assert_analyze_hand("12345688p34567s", "258s", mentions="sanmenchan")
    # assert_analyze_hand("123456p2234567s", "258s", mentions="aryanmen")
    # assert_analyze_hand("123456p2345677s", "147s", mentions="aryanmen")
    # assert_analyze_hand("123456p1234567s", "147s", mentions="sanmentan")
    # assert_analyze_hand("123456789p1234s", "14s", mentions="nobetan")
    # assert_analyze_hand("123456789p1222s", "13s", mentions="pentan")
    # assert_analyze_hand("123456789p1112s", "23s", mentions="pentan")
    # assert_analyze_hand("123456789p8999s", "78s", mentions="pentan")
    # assert_analyze_hand("123456789p8889s", "79s", mentions="pentan")
    # assert_analyze_hand("123456789p2333s", "124s", mentions="ryantan")
    # assert_analyze_hand("123456789p3334s", "245s", mentions="ryantan")
    # assert_analyze_hand("3334444555666p", "23567p", mentions="tatsumaki")
    # assert_analyze_hand("2224444666999p", "35p", mentions="kankantan")
    # assert_analyze_hand("3334444555566p", "367p")
    # assert_analyze_hand("3334444555666p", "23567p")
    # assert_analyze_hand("1223344445566m", "1567m")
    # assert_analyze_hand("2233445555667m", "1467m")
    # assert_analyze_hand("2223344556677s", "2345678s") # chinitsu shanpon
    # assert_analyze_hand("2345667777888s", "14568s") # chinitsu ryanmen
    # assert_analyze_hand("2345567777888s", "2568s") # chinitsu tanki
    # assert_analyze_hand("234567m23456p66s", "147p") # sanmenchan
    # assert_analyze_hand("234567m23488p67s", "58s") # ryanmen

    # # 1-shanten
    # assert_analyze_hand("445789p3455789s", "34567p234567s") # kuttsuki + headless
    # assert_analyze_hand("3334555s4555p23m", "14m346p23456s") # broken headless tatsumaki
    # assert_analyze_hand("234567m2468p678s", "2345678p") # headless
    # assert_analyze_hand("23455667m56p678s", "12345678m4567p") # headless + complete
    # assert_analyze_hand("34445566p22256s", "234567p4567s") # headless + complete
    # assert_analyze_hand("23345566p22256s", "14567p47s") # complete + floating
    # assert_analyze_hand("11123456m227p12s", "147m2p3s") # double floating with extensions
    # assert_analyze_hand("3334555m12678p1z", "23456m3p1z") # broken headless + floating with extensions
    # assert_analyze_hand("123456m55568p12s", "4678p123s") # headless + floating
    # assert_analyze_hand("1122345588899m", "1234569m") # chiitoi complete + floating
    # assert_analyze_hand("7m45678p23456s11z", "369p147s") # two extensions
    # # 2-shanten
    # assert_analyze_hand("123789m23458p1s2z", "123456789p123s2z") # super kuttsuki

    # assert_analyze_hand("123789m2267p1s23z", "258p123s23z") # kuttsuki

    # assert_analyze_hand("123789m2367p12s3z", "12345678p123s3z") # headless
    # assert_analyze_hand("123789m2367p15s3z", "1458p15s3z") # broken headless
    # assert_analyze_hand("12377m2356p1245s", "147p36s") # simple with 4 taatsu
    # assert_analyze_hand("12377m2356p12s45z", "147p3s") # simple with 3 taatsu
    # assert_analyze_hand("12377m2356p122s5z", "7m147p23s") # 1 complex
    # assert_analyze_hand("12377m233p12566s", "7m134p3467s") # 2 complex diff suit
    # assert_analyze_hand("12377m233566p12s", "7m13467p3s") # 2 complex same suit diff from pair
    # assert_analyze_hand("123m23356699p12s", "134679p3s") # 2 complex same suit as pair
    # assert_analyze_hand("123466m12445p57s", "56m346p6s") # many floating
    # assert_analyze_hand("123788m233557p1s", "146p") # floating
    # # 3-shanten
    # assert_analyze_hand("123788m23458p1s2z", "56789m123456789p123s2z") # kuttsuki

    # assert_analyze_hand("123788m233668p1s", "12356789m123456789p123s") # not sure


    # assert_analyze_hand("34445566p22256s", "234567p4567s", True) # headless + complete
    # assert_analyze_hand("12377m2356p122s5z", "7m147p23s", True) # 1 complex
