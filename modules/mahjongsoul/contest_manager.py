import hmac
import hashlib
import asyncio
import datetime
from typing import *
from modules.pymjsoul.channel import MajsoulChannel, GeneralMajsoulError
from modules.pymjsoul.proto import liqi_combined_pb2
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, InvalidStatusCode

# MS_MANAGER_WSS_ENDPOINT: `__MJ_DHS_WS__` from https://www.maj-soul.com/dhs/js/config.js
MS_MANAGER_WSS_ENDPOINT = "wss://common-v2.maj-soul.com/contest_ws_gateway"
EAST = 0
SOUTH = 1
WEST = 2
NORTH = 3

class ContestManager(MajsoulChannel):
    """
    wraps around the `MajsoulChannel` class to provide additional functionalities for managing ONE specific contest on Discord
    """
    def __init__(self, contest_unique_id: int, mjs_username: str, mjs_password: str, log_messages=False, logger_name="Contest Manager"):
        self.contest_unique_id = contest_unique_id
        self.mjs_username = mjs_username
        self.mjs_password = mjs_password
        self.contest = None # contest info; `CustomizedContest` protobuf
        super().__init__(proto=liqi_combined_pb2, log_messages=log_messages, logger_name=logger_name)
        self.huge_ping_task: Optional[asyncio.Task] = None
    
    async def login_and_start_listening(self):
        """
        this is its own method so it can be used again without having to establish
        another WSS connection (e.g., when we were logged out outside of this module)
        NOTE: this method starts the `huge_ping` task. It should be canceled before
        reusing this method.
        NOTE: use `super().call()` to avoid infinite errors
        """
        await super().call(
            methodName = "loginContestManager",
            account = self.mjs_username,
            password = hmac.new(b"lailai", self.mjs_password.encode(), hashlib.sha256).hexdigest(),
            type = 0)
        self.logger.info(f"`loginContestManager` with {self.mjs_username} successful!")

        res = await super().call(
            methodName = 'manageContest',
            unique_id = self.contest_unique_id)
        self.contest = res.contest
        self.logger.info(f"`manageContest` for {self.contest.contest_name} successful!")

        self.huge_ping_task = asyncio.create_task(self.huge_ping())

        # `startManageGame` will make mahjong soul start sending notifications
        # like `NotifyContestGameStart` and `NotifyContestGameEnd`
        await super().call(methodName = 'startManageGame')
        
        self.logger.info(f"`startManageGame` successful!")
    
    async def huge_ping(self, huge_ping_interval=14400):
        """
        this task tries to set the contest finish_time to be 90 days from
        `now` regularly (default: every 4 hours). This serves two purposes:
        1. automatically extend the contest finish_time (90 days is the safe max)
        2. attempts reconnection when necessary (via the wrapped `call()`)
        """
        try:
            while True:
                ninety_days_later = datetime.datetime.now() + datetime.timedelta(days=90)
                try:
                    await self.call(
                        "updateContestGameRule",
                        finish_time = int(ninety_days_later.timestamp()))
                    self.logger.info(f"huge_ping'd.")
                except GeneralMajsoulError:
                    # ignore mahjong soul errors not caught in wrapped `call()`
                    pass
                
                await asyncio.sleep(huge_ping_interval)
        except asyncio.CancelledError:
            self.logger.info("`huge_ping` task cancelled")

    async def connect_and_login(self):
        """
        Connect to the Chinese tournament manager server, login with username and password, start managing the specified contest, and start receiving the notifications for the games in that contest.
        """
        try:
            # Establish WSS connection
            await self.connect(MS_MANAGER_WSS_ENDPOINT)
            # Login, manage specific contest, and start listening to notifications
            await self.login_and_start_listening()
        except InvalidStatusCode as e:
            self.logger.error("Failed to login for CustomizedContestManagerApi. Is Mahjong Soul currently undergoing maintenance?")
            raise e
    
    async def reconnect_and_login(self):
        """
        login to Mahjong Soul again, keeping the existing subscriptions.
        Needs to make a new connection with `self.reconnect()` because trying to
        log in through the same connection results in `2504 : "ERR_CONTEST_MGR_HAS_LOGINED"`
        """
        self.huge_ping_task.cancel()
        await self.reconnect()
        await self.login_and_start_listening()

    async def call(self, methodName, **msgFields):
        """
        Wrap around `MajsoulChannel.call()` to handle certain errors. Note that
        `MajsoulChannel` already prints the API Errors to the console.
        """
        try:
            return await super().call(methodName, **msgFields)
        except GeneralMajsoulError as mjsError:
            if mjsError.errorCode == 2505:
                """
                "ERR_CONTEST_MGR_NOT_LOGIN"
                In this case, try logging BACK in and retrying the call.
                Do nothing if the retry still failed. (we do this because
                the account may have been logged out elsewhere unintentionally,
                e.g., from the web version of the tournament manager)
                """
                self.logger.info("Received `ERR_CONTEST_MGR_NOT_LOGIN`; now trying to log in again and resend the previous request.")
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

    async def get_ongoing_game_uuid(self, nickname):
        """
        return the UUID for an ongoing game the specified player is in
        """
        res = await self.call('startManageGame')
        for game in res.games:
            for player in game.players:
                if player.nickname == nickname:
                    return game.game_uuid
    
    async def terminate_game(self, nickname: str) -> str:
        """
        terminate the game that the specified player is in.
        returns a human-readable message whether successful.
        NOTE: this and similar methods assume that nicknames are unique,
        which is not true when multiple servers are allowed to participate
        in the same contest... this potential but unlikely issue is ignored,
        since it's much more convenient to terminate games by nickname.
        NOTE: also, technically we could make more precise wrappers for when
        people want to terminate their own game (we need to fetch their info anyway)
        """
        game_uuid = await self.get_ongoing_game_uuid(nickname)

        if game_uuid == None:
            return f"No ongoing game to be terminated for {nickname}!"
        
        await self.call(
            'terminateGame',
            serviceName='CustomizedContestManagerApi',
            uuid=game_uuid)

        return f"{nickname}'s game has been terminated."

    async def pause_game(self, nickname: str) -> str:
        """
        `pause` variant of the `terminate_game()`
        """
        game_uuid = await self.get_ongoing_game_uuid(nickname)

        if game_uuid == None:
            return f"No ongoing game to be paused for {nickname}!"
        
        await self.call(
            'pauseGame',
            uuid=game_uuid)

        return f"{nickname}'s game has been paused."
    
    async def unpause_game(self, nickname: str) -> str:
        """
        `unpause` variant of the `terminate_game()`
        """
        game_uuid = await self.get_ongoing_game_uuid(nickname)

        if game_uuid == None:
            return f"No paused game to be unpaused for {nickname}!"
        
        await self.call(
            'resumeGame',
            uuid=game_uuid)

        return f"{nickname}'s paused game has been unpaused."

    async def start_game(self, account_ids: List[int]=[0, 0, 0, 0], tag: str="", random_position=False, open_live=True, ai_level=1, starting_points=None) -> None:
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
        playerList = []
        for i in range(len(account_ids)):
            account_id = account_ids[i]
            playerList.append(self.proto.ReqCreateContestGame.Slot(
                account_id=account_id,
                start_point=starting_points,
                seat=i))
            # if it's a real player, call `lockGamePlayer`
            if account_id > 0:
                await self.call('lockGamePlayer', account_id=account_id)
        await self.call(
            methodName='createContestGame',
            slots=playerList,
            tag=tag,
            random_position=random_position,
            open_live=open_live,
            ai_level=ai_level)
