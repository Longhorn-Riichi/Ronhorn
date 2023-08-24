import re
from typing import *
from global_stuff import account_manager
from modules.pymjsoul.proto import liqi_combined_pb2 as proto

# InjusticeJudge imports
from google.protobuf.json_format import MessageToDict
from modules.InjusticeJudge.injustice_judge.fetch import fetch_tenhou, parse_tenhou, parse_majsoul, save_cache, parse_wrapped_bytes, GameMetadata
from modules.InjusticeJudge.injustice_judge.injustices import evaluate_injustices
from modules.InjusticeJudge.injustice_judge.constants import Kyoku

"""
=====================================================
Modified InjusticeJudge Functions
=====================================================
"""
async def parse_game_link(link: str, specified_player: int = 0) -> Tuple[List[Kyoku], GameMetadata, int]:
    """
    basically the same as the exposed `parse_game_link()` of the InjusticeJudge,
    but with the `fetch_majsoul` part substituted out so we can use our own
    AccountManager (to avoid logging in for each fetch)
    """
    if "tenhou.net/" in link:
        tenhou_log, metadata, player = fetch_tenhou(link)
        kyokus, parsed_metadata = parse_tenhou(tenhou_log, metadata)
    elif "mahjongsoul" in link or "maj-soul" in link:
        # EN: `mahjongsoul.game.yo-star.com`; CN: `maj-soul.com`; JP: `mahjongsoul.com`
        majsoul_log, metadata, player = await fetch_majsoul(link)
        kyokus, parsed_metadata = parse_majsoul(majsoul_log, metadata)
    else:
        raise Exception("expected tenhou link similar to `tenhou.net/0/?log=`"
                        " or mahjong soul link similar to `mahjongsoul.game.yo-star.com/?paipu=`")
    if specified_player is not None:
        player = specified_player
    return kyokus, parsed_metadata, player

async def analyze_game(link: str, specified_player = None) -> List[str]:
    kyokus, game_metadata, player = await parse_game_link(link, specified_player)
    return [injustice for kyoku in kyokus for injustice in evaluate_injustices(kyoku, player)]

async def fetch_majsoul(link: str):
    """
    NOTE:
    basically the same as InjusticeJudge's `fetch_majsoul()`, with 1 difference;
    Instead of logging in for each fetch, just fetch through the already logged-in
    AccountManager.
    """
    identifier_pattern = r'\?paipu=([^_]+)'
    identifier_match = re.search(identifier_pattern, link)
    if identifier_match is None:
        raise Exception(f"Invalid Mahjong Soul link: {link}")
    identifier = identifier_match.group(1)
    
    player_pattern = r'_a(\d+)'
    player_match = re.search(player_pattern, link)
    if player_match is None:
        ms_account_id = None
    else:
        ms_account_id = int((((int(player_match.group(1))-1358437)^86216345)-1117113)/7)
    
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
    if parsed.actions != []:
        actions = [parse_wrapped_bytes(action.result) for action in parsed.actions if len(action.result) > 0]
    else:
        actions = [parse_wrapped_bytes(record) for record in parsed.records]
    return actions, MessageToDict(record.head), next((acc.seat for acc in record.head.accounts if acc.account_id == ms_account_id), 0)
