import hmac
import hashlib
import asyncio
import requests
import datetime
import logging
import time
from typing import *
from modules.pymjsoul.channel import MajsoulChannel, GeneralMajsoulError
from modules.pymjsoul.proto import liqi_combined_pb2
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, InvalidStatusCode

# MS_MANAGER_WSS_ENDPOINT: `__MJ_DHS_WS__` from https://www.maj-soul.com/dhs/js/config.js
# MS_MANAGER_WSS_ENDPOINT = "wss://common-v2.maj-soul.com/contest_ws_gateway"
EAST = 0
SOUTH = 1
WEST = 2
NORTH = 3

class TournamentAPI:
    def __init__(self, log_messages=False, logger_name="Contest Manager"):
        self.logger = logging.getLogger(logger_name)
        self.log_messages = log_messages
        self.endpoint = "https://contesten.mahjongsoul.com:8200/api/"
        self.headers = {
            "Referer": "https://mahjongsoul.tournament.yo-star.com/",
            "Accept": "application/json, */*",
            "Content-Type": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/123.0",
        }

    def get(self, method: str, endpoint: str = "", second_try: bool = False, **params):
        try:
            return requests.get((endpoint or self.endpoint) + method, params=params, headers=self.headers).json()
        except Exception as e:
            if not second_try:
                self.logger.info("Attempting to log in again in order to resend the request...")
                self.login()
                return self.get(method=method, endpoint=endpoint, second_try=True, **params)
            else:
                self.logger.info("Relog failed, not trying again")
    def post(self, method: str, params: Dict = {}, endpoint: str = "", second_try: bool = False, **data):
        try:
            return requests.post((endpoint or self.endpoint) + method, params=params, headers=self.headers, json=data).json()
        except Exception as e:
            if not second_try:
                self.logger.info("Attempting to log in again in order to resend the request...")
                self.login()
                return self.post(method=method, params=params, endpoint=endpoint, second_try=True, **data)
            else:
                self.logger.info("Relog failed, not trying again")
    def login(self):
        pass

class TournamentLogin(TournamentAPI):
    def __init__(self, mjs_uid: int, mjs_token: str, log_messages=False, logger_name="Contest Manager"):
        super().__init__(log_messages, logger_name)
        self.mjs_uid = mjs_uid
        self.mjs_token = mjs_token
        self.login()
    def login(self):
        self.login_token = self.get_new_login_token()
        self.headers["Authorization"] = "Majsoul " + self.login_token
    def get_login_token(self):
        return self.login_token
    def get_new_login_token(self):
        login = self.post("login", endpoint="https://passport.mahjongsoul.com/user/", deviceId="web|"+str(self.mjs_uid), uid=str(self.mjs_uid), token=self.mjs_token)
        if "result" in login and login["result"] == 1:
            raise Exception("Already logged in elsewhere")
        try:
            token = login["accessToken"]
            login2 = self.post("login", params={"method": "oauth2"}, type=7, uid=self.mjs_uid, code=token)
            login_token = login2["data"]["token"]
        except Exception as e:
            print("Error: " + str(e))
            print("login result: " + str(login))
            print("login2 result: " + str(login2))
        if self.log_messages:
            self.logger.info("Login token: " + login_token)
        return login_token

class ContestManager:
    def __init__(self, contest_unique_id: int, api: TournamentLogin, game_type: str):
        self.contest_unique_id = contest_unique_id
        self.api = api
        self.game_type = game_type
        self.logger = logging.getLogger(game_type)
    def pause_match_impl(self, uuid: str, resume: int):
        return self.api.post(method="contest/pause_contest_running_game", unique_id=str(self.contest_unique_id), game_uuid=uuid, resume=resume)
    def pause_match(self, uuid: str):
        return self.pause_match_impl(uuid=uuid, resume=1)
    def resume_match(self, uuid: str):
        return self.pause_match_impl(uuid=uuid, resume=2)
    def terminate_match(self, uuid: str):
        return self.api.post(method="contest/terminate_contest_running_game", unique_id=str(self.contest_unique_id), uuid=uuid)
    def poll_participants(self) -> List[Dict]: # ready players in lobby
        # call returns {"data":[{"account_id":118325554,"nickname":"Kalanchloe"}]}
        return self.api.get(method="contest/ready_player_list", unique_id=self.contest_unique_id, season_id=1)["data"]
    def poll_match_list(self) -> List[Dict]:
        # call returns {"data":[{"game_uuid":"240725-550d2f43-904b-4412-bd31-514668e4d4d5","players":[{"account_id":118325554,"nickname":"Kalanchloe"},{"account_id":0},{"account_id":0},{"account_id":0}],"start_time":1721920249,"tag":""}]}
        return self.api.get(method="contest/contest_running_game_list", unique_id=self.contest_unique_id, season_id=1)["data"]
    def poll_match(self, uuid: str) -> Dict:
        # call returns {"uuid":"240725-550d2f43-904b-4412-bd31-514668e4d4d5","chang":0,"ju":0,"ben":0,"is_end":0,"update_time":1721920266,"scores":[1000,1000,1000,1000]}
        return self.api.get(method=f"game/realtime/{uuid}/progress/latest", endpoint="https://contesten.mahjongsoul.com:7443/api/")
    def fetch_rules(self):
        return self.api.get(method="contest/fetch_contest_detail", endpoint="https://mjusgs.mahjongsoul.com:8200/api/", unique_id=str(self.contest_unique_id))["data"]
    def change_season_rules(self, auto_match: Optional[bool] = True):
        default_rules = self.fetch_rules()["season_list"][0]
        data = {
            "unique_id": self.contest_unique_id,
            "season_id": 1,
            "setting":
            {
                "rank_rule": default_rules["rank_rule"],
                "auto_match": 1 if auto_match else 0,
                "signup_end_time": default_rules["signup_end_time"],
                "signup_start_time": default_rules["signup_start_time"],
                "end_time": default_rules["end_time"],
                "signup_type": default_rules["signup_type"]
            }
        }
        return self.api.post(method=f"contest/update_contest_season", endpoint="https://mjusgs.mahjongsoul.com:8200/api/", **data)
    def change_contest_detail_rules(self, detail_rule):
        # see Utilities/rules.py and Utilities/cog.py for how the argument is constructed
        default_rules = self.fetch_rules()
        game_mode = default_rules["game_mode"]
        game_mode["detail_rule"] = detail_rule
        data = {
            "unique_id": self.contest_unique_id,
            "setting": default_rules["contest_setting"],
            "game_rule_setting": game_mode
        }
        return self.api.post(method=f"contest/update_contest_base", endpoint="https://mjusgs.mahjongsoul.com:8200/api/", **data)
    def change_contest_name(self, name):
        default_rules = self.fetch_rules()
        data = {
            "unique_id": self.contest_unique_id,
            "setting": {
                "name": [{"lang": "default", "content": name}],
                "open_show": default_rules["open"],
                "show_zones": default_rules["show_zones"],
                "available_zones": default_rules["available_zones"]
            }
        }
        return self.api.post(method=f"contest/update_contest_base", endpoint="https://mjusgs.mahjongsoul.com:8200/api/", **data)
    def change_contest_desc(self, desc):
        data = {
            "unique_id": self.contest_unique_id,
            "notice": [
                {"lang": "default", "content": desc},
                {"lang": "chs", "content": ""},
                {"lang": "chs_t", "content": ""},
                {"lang": "jp", "content": ""},
                {"lang": "en", "content": ""},
                {"lang": "kr", "content": ""}
            ]
        }
        return self.api.post(method=f"contest/update_contest_external_notice", endpoint="https://mjusgs.mahjongsoul.com:8200/api/", **data)

    def get_ongoing_game_uuid(self, nickname):
        """
        return the self.mjs_uid for an ongoing game the specified player is in
        """
        res = self.api.get(method="contest/contest_running_game_list", unique_id=self.contest_unique_id, season_id=1)
        for game in res["data"]:
            for player in game["players"]:
                if player["nickname"] == nickname:
                    return game["game_uuid"]
    
    def terminate_game(self, nickname: str) -> Tuple[bool, str]:
        game_uuid = self.get_ongoing_game_uuid(nickname)
        if game_uuid == None:
            return False, f"No ongoing game to be terminated for {nickname}!"
        self.terminate_match(game_uuid)
        return True, f"{nickname}'s game has been terminated."

    def pause_game(self, nickname: str) -> Tuple[bool, str]:
        game_uuid = self.get_ongoing_game_uuid(nickname)
        if game_uuid == None:
            return False, f"No ongoing game to be paused for {nickname}!"
        self.pause_match(game_uuid)
        return True, f"{nickname}'s game has been paused."
    
    def unpause_game(self, nickname: str) -> Tuple[bool, str]:
        game_uuid = self.get_ongoing_game_uuid(nickname)
        if game_uuid == None:
            return False, f"No paused game to be unpaused for {nickname}!"
        self.resume_match(game_uuid)
        return True, f"{nickname}'s paused game has been unpaused."

    def start_game(self, account_ids: List[int]=[0, 0, 0, 0], tag: str="", random_position=False, open_live=True, ai_level=1, starting_points=None) -> None:
        """
        start a tournament game. `account_ids` is a list of mahjong soul player
        ids, where 0 means adding a computer at the given seat.
        
        parameters
        ------------
        account_ids: a list of Mahjong Soul account ids [East, South, West, North]
        random_position: whether to randomize the seats (ignore the ordering in accounts_ids)
        open_live: whether the game can be spectated. DOESN'T WORK AS OF 7/19/2023.
        ai_level: 0 for Auto-Discard, 1 for Easy, 2 for Normal
        """

        data = {
            "unique_id": self.contest_unique_id,
            "season_id": 1,
            "account_list": account_ids,
            "init_points": [starting_points or 25000] * len(account_ids),
            "game_start_time": int(time.time()),
            "shuffle_seats": random_position,
            "ai_level": ai_level
        }
        return self.api.post(method="contest/create_game_plan", **data)
