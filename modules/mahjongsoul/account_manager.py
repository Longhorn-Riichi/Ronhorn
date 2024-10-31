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
MS_ENGLISH_WSS_ENDPOINT = "wss://engame.mahjongsoul.com:443/gateway"

class AccountManager(MajsoulChannel):
    """
    wraps around the `MajsoulChannel` class. The main point is so
    we can directly fetch a single game's result
    """
    def __init__(self, mjs_username: Optional[str]=None, mjs_password: Optional[str]=None, mjs_uid: Optional[str]=None, mjs_token: Optional[str]=None, log_messages=False, logger_name="Account Manager"):
        self.mjs_username = mjs_username
        self.mjs_password = mjs_password
        self.mjs_uid = mjs_uid
        self.mjs_token = mjs_token
        self.use_cn = self.mjs_username is not None and self.mjs_password is not None
        self.use_en = self.mjs_uid is not None and self.mjs_token is not None
        if not self.use_cn and not self.use_en:
            raise Exception("Account manager was initialized without login credentials!")

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
        if self.use_cn:
            await self.login_cn()
        elif self.use_en:
            await self.login_en()

        self.huge_ping_task = asyncio.create_task(self.huge_ping())
    
    async def login_en(self):
        UID = self.mjs_uid
        TOKEN = self.mjs_token
        MS_VERSION = requests.get(url="https://mahjongsoul.game.yo-star.com/version.json").json()["version"][:-2]
        self.client_version_string = f"web-{MS_VERSION}"
        self.logger.info("Calling heatbeat...")
        await super().call("heatbeat")
        self.logger.info("Requesting initial access token...")
        USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0"
        access_token = requests.post(url="https://passport.mahjongsoul.com/user/login", headers={"User-Agent": USER_AGENT, "Referer": "https://mahjongsoul.game.yo-star.com/"}, data={"uid":UID,"token":TOKEN,"deviceId":f"web|{UID}"}).json()["accessToken"]
        self.logger.info("Requesting oauth access token...")
        oauth_token = (await super().call("oauth2Auth", type=7, code=access_token, uid=UID, client_version_string=self.client_version_string)).access_token
        self.logger.info("Calling heatbeat...")
        await super().call("heatbeat")
        self.logger.info("Calling oauth2Check...")
        assert (await super().call("oauth2Check", type=7, access_token=oauth_token)).has_account, "couldn't find account with oauth2Check"
        self.logger.info("Calling oauth2Login...")
        client_device_info = {"platform": "pc", "hardware": "pc", "os": "mac", "is_browser": True, "software": "Firefox", "sale_platform": "web"}
        await super().call("oauth2Login", type=7, access_token=oauth_token, reconnect=False, device=client_device_info, random_key=str(uuid.uuid1()), client_version={"resource": f"{MS_VERSION}.w"}, currency_platforms=[], client_version_string=self.client_version_string, tag="en")
        self.logger.info(f"`login` with token successful!")

    async def login_cn(self):
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
            if self.use_cn:
                await self.connect(MS_CHINESE_WSS_ENDPOINT)
            else:
                await self.connect(MS_ENGLISH_WSS_ENDPOINT)
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

    async def get_account(self, friend_id: int) -> Optional[Tuple[str, int]]:
        res = await self.call("searchAccountByPattern", pattern=str(friend_id))
        print(res)
        if not res.decode_id:
            return None
        res2 = await self.call("fetchMultiAccountBrief", account_id_list=[res.decode_id])
        if len(res2.players) == 0:
            return None
        return res2.players[0].nickname, res2.players[0].account_id

    async def get_stats(self, account_id: int):
        import numpy
        res = await self.call("fetchAccountStatisticInfo", account_id=account_id)
        ranked = res.detail_data.rank_statistic
        res2 = await self.call("fetchAccountInfo", account_id=account_id)
        yonma_rank, yonma_rank_pts = res2.account.level.id % 10000, res2.account.level.score
        sanma_rank, sanma_rank_pts = res2.account.level3.id % 10000, res2.account.level3.score
        modes = {1: "Yonma Tonpuu", 2: "Yonma Hanchan", 11: "Sanma Tonpuu", 12: "Sanma Hanchan"}
        ends = {0: "abortive draw", 1: "ryuukyoku", 2: "tsumo", 3: "ron", 4: "deal-in", 5: "hit by tsumo"}
        placement_names = ["1st", "2nd", "3rd", "4th", "Negative"]
        stats: Dict[str, Any] = {m: {} for m in modes.values()}
        for m in ranked.total_statistic.all_level_statistic.game_mode:
            s = stats[modes[m.mode]]
            is_yonma = "Yonma" in modes[m.mode]
            placements = [p / m.game_count_sum for p in m.game_final_position]
            placements.append(m.fly_count / m.game_count_sum)
            round_ends = {ends[e.type]: e.sum for e in m.round_end}
            if "ron" not in round_ends:
                round_ends["ron"] = 0
            if "tsumo" not in round_ends:
                round_ends["tsumo"] = 0
            if "deal-in" not in round_ends:
                round_ends["deal-in"] = 0
            total_wins = round_ends["ron"] + round_ends["tsumo"]
            s["Placement"] = "\n".join(f"{n}: **{100*p:.2f}%**" for n, p in zip(placement_names, placements))

            basic_stats = {}
            basic_stats["Total games"] = m.game_count_sum
            format_percent = lambda v: f"{100*v:.2f}%"
            basic_stats["% Win"] = format_percent(total_wins/m.round_count_sum)
            basic_stats["% Tsumo"] = format_percent(round_ends["tsumo"]/total_wins)
            basic_stats["% Deal-in"] = format_percent(round_ends["deal-in"]/m.round_count_sum)
            basic_stats["% Call"] = format_percent(m.ming_count_sum/m.round_count_sum)
            basic_stats["% Riichi"] = format_percent(m.liqi_count_sum/m.round_count_sum)
            basic_stats["% Draw"] = format_percent(round_ends["ryuukyoku"]/m.round_count_sum)
            basic_stats["% Hit by Tsumo"] = format_percent(round_ends["hit by tsumo"]/m.round_count_sum)
            s["Basic stats"] = "\n".join(f"{n}: **{v}**" for n, v in basic_stats.items())

            misc_stats = {}
            misc_stats["Avg win score"] = round(m.dadian_sum/total_wins)
            misc_stats["Avg placement"] = round(numpy.average([1,2,3,4], weights=placements[:-1]), 2)
            misc_stats["Avg turns to win"] = round(m.xun_count_sum/total_wins, 2)
            misc_stats["Avg rounds/game"] = round(m.round_count_sum/m.game_count_sum, 2)
            misc_stats["Highest honba"] = m.highest_lianzhuang
            s["Misc stats"] = "\n".join(f"{n}: **{v}**" for n, v in misc_stats.items())

            rank_stats: Dict[str, Any] = {}
            RANKS: Dict[int, str] = {1: "Novice", 2: "Adept", 3: "Expert", 4: "Master", 5: "Saint", 7: "Celestial"}
            RANK_PTS_GOAL: Dict[int, List[int]] = {
                1: [0, 20, 80, 200],
                2: [0, 600, 800, 1000],
                3: [0, 1200, 1400, 2000],
                4: [0, 2800, 3200, 3600],
                5: [0, 4000, 6000, 9000],
                }
            rank: int = (yonma_rank if is_yonma else sanma_rank) // 100
            stars: int = (yonma_rank if is_yonma else sanma_rank) % 100
            rank_pts: int = yonma_rank_pts if is_yonma else sanma_rank_pts
            if RANKS[rank] != "Celestial":
                assert stars in {1,2,3}
                rank_stats["Rank"] = RANKS[rank] + " (" + "★"*stars + ")"
                rank_stats["Rank points"] = str(rank_pts) + "/" + str(RANK_PTS_GOAL[rank][stars])
            else:
                rank_stats["Rank"] = RANKS[rank] + " (Lv. " + str(stars) + ")"
                rank_stats["Soul points"] = round(rank_pts/100, 1)
            rank_stats["Avg rank pts/game"] = round(m.score_earn_sum/m.game_count_sum)
            s["Ranking"] = "\n".join(f"{n}: **{v}**" for n, v in rank_stats.items())

            # RANK_BONUS = {
            #     "Yonma Tonpuu": [[10, 5, 0], [20, 10, 0], [40, 20, 0], [55, 30, 0], [60, 30, 0]],
            #     "Yonma Hanchan": [[20, 10, 0], [40, 20, 0], [80, 40, 0], [110, 55, 0], [120, 60, 0]],
            #     "Sanma Tonpuu": [[15, 0], [30, 0], [55, 0], [75, 0], [120, 0]],
            #     "Sanma Hanchan": [[30, 0], [60, 0], [105, 0], [160, 0], [240, 0]]
            # }
            # FOURTH_PENALTY = {
            #     "Yonma Tonpuu": [[0, 0, 0], [10, 20, 30], [40, 50, 60], [80, 90, 100], [110, 120, 130]],
            #     "Yonma Hanchan": [[0, 0, 0], [20, 40, 60], [80, 100, 120], [165, 180, 195], [210, 225, 240]],
            #     "Sanma Tonpuu": [[0, 0, 0], [10, 20, 30], [40, 50, 60], [80, 95, 110], [125, 140, 160]],
            #     "Sanma Hanchan": [[0, 0, 0], [20, 40, 60], [80, 100, 120], [165, 190, 215], [240, 265, 290]]
            # }
            # if is_yonma:
            #     uma = [15, 5, -5, -15]
            #     starting_pts = 25000
            # else:
            #     uma = [15, 0, -15]
            #     starting_pts = 35000
            # rank_bonus = RANK_BONUS[modes[m.mode]][rank-1] + [FOURTH_PENALTY[modes[m.mode]][rank-1][stars-1]]
            # parsed_rank_score = {r.rank: (r.score_sum, r.count) for r in m.rank_score}
            # bonus = [u+b for u, b in zip(uma, rank_bonus)]
            # delta_pts = {placement: score_sum - bonus[placement-1]*count for placement, (score_sum, count) in parsed_rank_score.items()}
            # avg_final_score = round(starting_pts + 1000*sum(delta_pts.values())/m.game_count_sum)
            # s["Misc stats"] += f"\nAvg game score: **{avg_final_score}**"
            # NOTE: this assumes all games were played at the current rank, which is false
            #       meaning that it severely underestimates the average score (e.g. -20k)

        for r in res.statistic_data:
            t = (r.mahjong_category, r.game_category, r.game_type)
            if t == (1, 2, 1):
                s1 = stats["Yonma Tonpuu"]
                s2 = stats["Yonma Hanchan"]
            elif t == (2, 2, 1):
                s1 = stats["Sanma Tonpuu"]
                s2 = stats["Sanma Hanchan"]
            else:
                continue
            
            clamp = lambda n: min(100, max(0, int(n * 100)))
            total_rounds = r.statistic.recent_round.total_count
            avg_pt = r.statistic.recent_20_hu_summary.average_hu_point

            # all stats scale linearly

            radial_stats = {
                # = k == A.liqi4 ? (f - 3000) / 5000 * 100 : (f - 4000) / 8000 * 100
                # in yonma, 3000 avg points is 0 ATK, 8000 avg points is 100 ATK
                # in sanma, 4000 avg points is 0 ATK, 12000 avg points is 100 ATK
                "ATK": clamp((avg_pt-3000)/5000 if r.mahjong_category == 1 else (avg_pt-4000)/8000),
                # = (1.12 - v.recent_round.fangchong_count / v.recent_round.total_count * 3.4) * 100
                # 32.94% deal-in rate is 0 DEF, 3.53% deal-in rate is 100 DEF
                "DEF": clamp(1.12-(r.statistic.recent_round.fangchong_count/total_rounds*3.4)),
                # = ((v.recent_round.rong_count + v.recent_round.zimo_count) / v.recent_round.total_count - 0.1) / 0.3 * 100
                # 10% winrate is 0 SPD, 40% winrate is 100 SPD
                "SPD": clamp((((r.statistic.recent_round.rong_count+r.statistic.recent_round.zimo_count)/total_rounds)-0.1)/0.3),
                # = v.recent_10_hu_summary.total_xuanshang / v.recent_10_hu_summary.total_fanshu * 1.5 * 100
                # 0% lucky han is 0 LUK, 66.67% lucky han is 100 LUK
                "LUK": clamp(r.statistic.recent_10_hu_summary.total_xuanshang / r.statistic.recent_10_hu_summary.total_fanshu * 1.5),
            }

            s1["Radial stats"] = s2["Radial stats"] = "\n".join(f"{n}: **{v}**" for n, v in radial_stats.items())

            if r.mahjong_category == 1:
                stats["Yonma recents"] = [(g.rank, g.final_point >= 50000) for g in r.statistic.recent_10_game_result]
            else:
                stats["Sanma recents"] = [(g.rank, g.final_point >= 70000) for g in r.statistic.recent_10_game_result]
            
        return stats
