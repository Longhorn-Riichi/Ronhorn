import asyncio
import datetime
import gspread
import logging
import discord
from discord.ext import commands
from discord import Interaction
from typing import *

from global_stuff import assert_getenv
# from modules.mahjongsoul.contest_manager import ContestManager
# from global_stuff import assert_getenv, account_manager, registry, raw_scores, registry_lock, raw_scores_lock
# from ..InjusticeJudge.command_view import CommandSuggestionView

BOT_CHANNEL_ID: int        = int(assert_getenv("bot_channel_id"))
GUILD_ID: int              = int(assert_getenv("guild_id"))

YH_NAME = assert_getenv("yh_name")
YT_NAME = assert_getenv("yt_name")
SH_NAME = assert_getenv("sh_name")
ST_NAME = assert_getenv("st_name")

common_rules: Dict[str, Any] = {
    "allow_emote": True,
    "auto_match": True,
    "last_dealer_tenpai_continues": True,
    "last_dealer_win_continues": True,
    "head_bump_enabled": True,
    "hints_enabled": False,
    "immediate_kan_dora": True,
    "renhou_enabled": 1,
    "thinking_type": 4,
    "three_ron_draw_enabled": True
}
all_rules: Dict[str, Dict[str, Any]] = {
    YH_NAME: {**common_rules,
        "contest_name": "LR Yonma Hanchan",
        "round_type": 2,
        "uma": (16,6,-6,-16),
    },
    YT_NAME: {**common_rules,
        "contest_name": "LR Yonma Tonpuu",
        "round_type": 1,
        "uma": (8,-3,-3,-8),
    },
    SH_NAME: {**common_rules,
        "contest_name": "LR Sanma Hanchan",
        "round_type": 12,
        "uma": (16,0,-16),
    },
    ST_NAME: {**common_rules,
        "contest_name": "LR Sanma Tonpuu",
        "round_type": 11,
        "uma": (8,0,-8),
    },
}

def construct_game_rule(
        contest_name: str,
        round_type: int, # 1 (4-Player East), 2 (4-Player South), 11 (3-Player East), 12 (3-Player South)
        thinking_type: int = 3, # 1 (3+5s), 2 (5+10s), 3 (5+20s), 4 (60+0s), 5 (20+0s), 6 (10+20s)
        allow_emote: bool = True,
        auto_match: bool = True,
        starting_points: Optional[int] = None,
        min_points_to_win: Optional[int] = None, 
        auto_win_points: Optional[int] = None, 
        goal_points: Optional[int] = None, 
        dora_count: Optional[int] = None,
        noten_payments: Optional[Tuple[int, ...]] = None,
        uma: Optional[Tuple[int, ...]] = None,
        riichi_value: int = 1000,
        honba_value: int = 100,
        busting_enabled: bool = True,
        can_rob_ankan_for_13_orphans: bool = True,
        charleston_enabled: bool = False,
        dealer_tenpai_repeat_enabled: bool = True,
        dealer_win_repeat_enabled: bool = True,
        dora_enabled: bool = True,
        double_wind_is_4_fu: bool = True,
        double_yakuman_enabled: bool = True,
        extend_to_west_round: bool = True,
        four_kan_draw_enabled: bool = True,
        four_riichi_draw_enabled: bool = True,
        four_wind_draw_enabled: bool = True,
        head_bump_enabled: bool = False,
        hints_enabled: bool = True,
        immediate_kan_dora: bool = False,
        ippatsu_enabled: bool = True,
        kan_dora_enabled: bool = True,
        kan_ura_dora_enabled: bool = True,
        kazoe_yakuman_enabled: bool = True,
        kiriage_mangan_enabled: bool = False,
        last_dealer_tenpai_continues: bool = False,
        last_dealer_win_continues: bool = False,
        last_turn_riichi_enabled: bool = False,
        local_yaku_enabled: bool = False,
        multiple_winners_enabled: bool = False,
        multiple_yakuman_enabled: bool = True,
        nagashi_mangan_enabled: bool = True,
        nine_terminal_draw_enabled: bool = True,
        open_tanyao_enabled: bool = True,
        pao_mode: int = 0, # 0 (pao enabled for big three dragons and four big winds), 1 (also include four kans), 2 (disable pao)
        renhou_enabled: int = False, # 0 (disabled), 1 (mangan), 2 (yakuman)
        swap_calling_enabled: bool = False,
        three_ron_draw_enabled: bool = False,
        three_starting_doras: bool = False,
        tsumo_loss_enabled: bool = True,
        ura_dora_enabled: bool = True,
        min_han: int = 1, # allowed values: 1, 2, 4
    ) -> Dict[str, Any]:
    num_players = 3 if round_type > 10 else 4
    if dora_count is None:
        dora_count = 2 if num_players == 3 else 3
    if starting_points is None:
        starting_points = 35000 if num_players == 3 else 25000
    if goal_points is None:
        goal_points = starting_points + 5000
    if min_points_to_win is None:
        min_points_to_win = starting_points
    if auto_win_points is None:
        auto_win_points = 0
    if noten_payments is None:
        noten_payments = (1000, 2000) if num_players == 3 else (1000, 1500, 3000)
    if uma is None:
        uma = (15, 0, -15) if num_players == 3 else (15, 5, -5, -15)
    if not dora_enabled:
        kan_dora_enabled = False
        ura_dora_enabled = False
        kan_ura_dora_enabled = False
    if not dealer_win_repeat_enabled:
        last_dealer_win_continues = False
    if not dealer_tenpai_repeat_enabled:
        last_dealer_tenpai_continues = False
    honba_value *= num_players - 1
    
    noten_payments = (*noten_payments, 0) if len(noten_payments) == 2 else noten_payments
    uma = (*uma, 0) if len(uma) == 3 else uma

    game_rule = {
        "init_point": starting_points,                             # 5; uint32
        "fandian": min_points_to_win,                              # 6; uint32
        "can_jifei": busting_enabled,                              # 7; bool
        "tianbian_value": auto_win_points,                         # 8; uint32
        "liqibang_value": riichi_value,                            # 9; uint32
        "changbang_value": honba_value,                            # 10; uint32
        "noting_fafu_1": noten_payments[0],                        # 11; uint32
        "noting_fafu_2": noten_payments[1],                        # 12; uint32
        "noting_fafu_3": noten_payments[2],                        # 13; uint32
        "have_liujumanguan": nagashi_mangan_enabled,               # 14; bool
        "have_qieshangmanguan": kiriage_mangan_enabled,            # 15; bool
        "have_biao_dora": dora_enabled,                            # 16; bool
        "have_gang_biao_dora": kan_dora_enabled,                   # 17; bool
        "ming_dora_immediately_open": immediate_kan_dora,          # 18; bool
        "have_li_dora": ura_dora_enabled,                          # 19; bool
        "have_gang_li_dora": kan_ura_dora_enabled,                 # 20; bool
        "have_sifenglianda": four_wind_draw_enabled,               # 21; bool
        "have_sigangsanle": four_kan_draw_enabled,                 # 22; bool
        "have_sijializhi": four_riichi_draw_enabled,               # 23; bool
        "have_jiuzhongjiupai": nine_terminal_draw_enabled,         # 24; bool
        "have_sanjiahele": three_ron_draw_enabled,                 # 25; bool
        "have_toutiao": head_bump_enabled,                         # 26; bool
        "have_helelianzhuang": dealer_win_repeat_enabled,          # 27; bool
        "have_helezhongju": not last_dealer_win_continues,         # 28; bool
        "have_tingpailianzhuang": dealer_tenpai_repeat_enabled,    # 29; bool
        "have_tingpaizhongju": not last_dealer_tenpai_continues,   # 30; bool
        "have_yifa": ippatsu_enabled,                              # 31; bool
        "have_nanruxiru": extend_to_west_round,                    # 32; bool
        "jingsuanyuandian": goal_points,                           # 33; uint32
        "shunweima_2": uma[1],                                     # 34; int32
        "shunweima_3": uma[2],                                     # 35; int32
        "shunweima_4": uma[3],                                     # 36; int32
        "bianjietishi": hints_enabled,                             # 37; bool
        # "ai_level": None,                                        # 38; uint32
        "have_zimosun": tsumo_loss_enabled,                        # 39; bool
        # "disable_multi_yukaman": None,                           # 40; bool
        "guyi_mode": local_yaku_enabled,                           # 41; uint32
        "disable_leijiyiman": not kazoe_yakuman_enabled,           # 42; bool
        "dora3_mode": three_starting_doras,                        # 43; uint32
        "xuezhandaodi": multiple_winners_enabled,                  # 44; uint32
        "huansanzhang": charleston_enabled,                        # 45; uint32
        # "chuanma": None,                                         # 46; uint32
        "disable_double_yakuman": not double_yakuman_enabled,      # 62; uint32
        "disable_composite_yakuman": not multiple_yakuman_enabled, # 63; uint32
        "enable_shiti": swap_calling_enabled,                      # 64; uint32
        "enable_nontsumo_liqi": last_turn_riichi_enabled,          # 65; uint32
        "disable_double_wind_four_fu": not double_wind_is_4_fu,    # 66; uint32
        "disable_angang_guoshi": not can_rob_ankan_for_13_orphans, # 67; uint32
        "enable_renhe": renhou_enabled,                            # 68; uint32
        "enable_baopai_extend_settings": pao_mode,                 # 69; uint32
        "fanfu": min_han,                                          # 70; uint32
    }
    game_rule_setting = {
        "round_type": round_type,                   # 1; uint32
        "shiduan": open_tanyao_enabled,             # 2; bool
        # 0 or 2 for sanma; 0 or 3 or 4 for yonma
        "dora_count": dora_count,                   # 3; uint32
        "thinking_type": thinking_type,             # 4; uint32
        "use_detail_rule": True,                    # 5; bool
        "detail_rule_v2": {"game_rule": game_rule}, # 6; ContestDetailRuleV2
    }
    return {
        "contest_name": contest_name,            # 1; string
        # "start_time": None,                    # 2; uint32
        # "finish_time": None,                   # 3; uint32
        # "open": None,                          # 4; bool
        # "rank_rule": None,                     # 5; uint32
        "game_rule_setting": game_rule_setting,  # 6; GameRuleSetting
        "auto_match": auto_match,                # 7; bool
        "auto_disable_end_chat": False,          # 8; bool
        # "contest_type": None,                  # 9; uint32
        # "banned_zones": None,                  # 10; string
        # "hidden_zones": None,                  # 11; string
        "emoji_switch": not allow_emote,         # 12; bool
        # "player_roster_type": None,            # 13; uint32
        # "disable_broadcast": None,             # 14; uint32
    }
