import hmac
import hashlib
import requests
import uuid
import asyncio
from typing import *
from modules.pymjsoul.channel import MajsoulChannel, GeneralMajsoulError
from modules.pymjsoul.proto import liqi_combined_pb2
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, InvalidStatusCode

MS_CHINESE_WSS_ENDPOINT = "wss://gateway-hw.maj-soul.com:443/gateway"

class AccountManager(MajsoulChannel):
    """
    wraps around the `MajsoulChannel` class. The main point is so
    we can directly fetch a single game's result
    """
    def __init__(self, mjs_username: str, mjs_password: str, log_messages=False, logger_name="Account Manager"):
        self.mjs_username = mjs_username
        self.mjs_password = mjs_password
        self.client_version_string: Optional[str] = None # obtained in `login`, useful for certain calls like `fetchGameRecord`
        super().__init__(proto=liqi_combined_pb2, log_messages=log_messages, logger_name=logger_name)
        self.huge_ping_task: Optional[asyncio.Task] = None
    
    async def login(self):
        """
        this is its own method so it can be used again without having to establish
        another WSS connection (e.g., when we were logged out outside of this module)
        NOTE: this method starts the `huge_ping` task. It should be canceled before
        reusing this method.
        NOTE: use `super().call()` to avoid infinite errors
        """
        # following sequence is inspired by `mahjong_soul_api`:
        # https://github.com/MahjongRepository/mahjong_soul_api/blob/master/example.py
        # ms_version example: 0.10.269.w
        ms_version = requests.get(url="https://game.maj-soul.com/1/version.json").json()["version"]
        self.logger.info(f"Fetched Mahjong Soul version: {ms_version}")

        self.client_version_string = f"web-{ms_version[:-2]}"
        client_device_info = {"is_browser": True}
        await super().call(
            "login",
            account=self.mjs_username,
            password=hmac.new(b"lailai", self.mjs_password.encode(), hashlib.sha256).hexdigest(),
            device=client_device_info,
            random_key=str(uuid.uuid1()),
            client_version_string=self.client_version_string)
        
        self.logger.info(f"`login` with {self.mjs_username} successful!")

        self.huge_ping_task = asyncio.create_task(self.huge_ping())
    
    async def huge_ping(self, huge_ping_interval=14400):
        """
        this task tries to call `heatbeat` every 4 hours so we know when
        we need to attempt reconnection (via the wrapped `call()`)
        """
        try:
            while True:
                try:
                    await self.call("heatbeat")
                    self.logger.info(f"huge_ping'd.")
                except GeneralMajsoulError:
                    # ignore mahjong soul errors not caught in wrapped `call()`
                    pass
                await asyncio.sleep(huge_ping_interval)
        except asyncio.CancelledError:
            self.logger.info("`huge_ping` task cancelled")

    async def connect_and_login(self):
        """
        Connect to the Chinese game server and login with username and password.
        """
        try:
            await self.connect(MS_CHINESE_WSS_ENDPOINT)
            await self.login()
        except InvalidStatusCode as e:
            self.logger.error("Failed to login for Lobby. Is Mahjong Soul currently undergoing maintenance?")
            raise e
    
    async def reconnect_and_login(self):
        """
        login to Mahjong Soul again, keeping the existing subscriptions.
        Needs to make a new connection with `self.reconnect()` because trying to
        log in through the same connection results in `2504 : "ERR_CONTEST_MGR_HAS_LOGINED"`
        """
        self.huge_ping_task.cancel()
        await self.reconnect()
        await self.login()

    async def call(self, methodName, **msgFields):
        """
        Wrap around `MajsoulChannel.call()` to handle certain errors. Note that
        `MajsoulChannel` already prints the API Errors to the console.
        """
        try:
            return await super().call(methodName, **msgFields)
        except GeneralMajsoulError as mjsError:
            if mjsError.errorCode == 1004:
                """
                "ERR_ACC_NOT_LOGIN"
                In this case, try logging BACK in and retrying the call.
                Do nothing if the retry still failed. (we do this because
                the account may have been logged out elsewhere unintentionally)
                """
                self.logger.info("Received `ERR_ACC_NOT_LOGIN`; now trying to log in again and resend the previous request.")
                await self.reconnect_and_login()
                return await super().call(methodName, **msgFields)
            else:
                # raise other GeneralMajsoulError
                raise mjsError
        except (ConnectionClosedError,
                ConnectionClosed):
            """
            similar to above; try logging back in once and retrying the call.
            Do nothing if the retry still failed.
            """
            self.logger.info("ConnectionClosed[Error]; now trying to log in again and resend the previous request.")
            await self.reconnect_and_login()
            return await super().call(methodName, **msgFields)

    """
    =====================================================
    HELPER FUNCTIONS
    =====================================================
    """

    async def get_game_results(self, uuid_list: List[str]):
        """
        given a list of game uuids, return a list of `RecordGame`
        objects (see protobuf)
        """
        res = await self.call(
            "fetchGameRecordsDetail",
            uuid_list=uuid_list)
        return res.record_list

    async def get_stats(self, account_id: int):
        record = await self.call("fetchAccountStatisticInfo", account_id=account_id)
        ranked = record.detail_data.rank_statistic
        import numpy
        modes = {1: "Yonma Tonpuu", 2: "Yonma Hanchan", 11: "Sanma Tonpuu", 12: "Sanma Hanchan"}
        ends = {0: "0", 1: "1", 2: "tsumo", 3: "ron", 4: "deal-in", 5: "5"}
        stats: Dict[str, Dict[str, Any]] = {m: {} for m in modes.values()}
        for m in ranked.total_statistic.all_level_statistic.game_mode:
            s = stats[modes[m.mode]]
            s["Total games"] = m.game_count_sum
            placements = [round(100 * p / m.game_count_sum, 2) for p in m.game_final_position]
            round_ends = {ends[e.type]: e.sum for e in m.round_end}
            s["Avg score"] = round(m.dadian_sum / (round_ends["ron"] + round_ends["tsumo"]))
            s["Avg rank"] = round(numpy.average([1,2,3,4], weights=placements), 2)
            s["Win rate"] = str(round(100 * (round_ends["ron"] + round_ends["tsumo"])/m.round_count_sum, 2)) + "%"
            s["Tsumo rate"] = str(round(100 * round_ends["tsumo"]/(round_ends["ron"] + round_ends["tsumo"]), 2)) + "%"
            s["Deal-in rate"] = str(round(100 * (round_ends["deal-in"])/m.round_count_sum, 2)) + "%"
            s["Call rate"] = str(round(100 * m.ming_count_sum/m.round_count_sum, 2)) + "%"
            s["Riichi rate"] = str(round(100 * m.liqi_count_sum/m.round_count_sum, 2)) + "%"
        return stats
