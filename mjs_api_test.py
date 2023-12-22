import asyncio
from typing import *
import google.protobuf as pb  # type: ignore[import]
import modules.pymjsoul.proto.liqi_combined_pb2 as proto
from modules.pymjsoul.errors import ERRORS
from google.protobuf.message import Message  # type: ignore[import]
import hmac
import hashlib

class MahjongSoulAPI:
    def __init__(self, endpoint):
        self.endpoint = endpoint
    """Helper class to interface with the Mahjong Soul API"""
    async def __aenter__(self):
        import websockets
        self.ws = await websockets.connect(self.endpoint)
        self.ix = 0
        return self
    async def __aexit__(self, err_type, err_value, traceback):
        await self.ws.close()

    async def call(self, name, **fields: Dict[str, Any]) -> Message:
        method = next((svc.FindMethodByName(name) for svc in proto.DESCRIPTOR.services_by_name.values() if name in [method.name for method in svc.methods]), None)
        assert method is not None, f"couldn't find method {name}"

        req: Message = pb.reflection.MakeClass(method.input_type)(**fields)
        res: Message = pb.reflection.MakeClass(method.output_type)()

        tx: bytes = b'\x02' + self.ix.to_bytes(2, "little") + proto.Wrapper(name=f".{method.full_name}", data=req.SerializeToString()).SerializeToString()  # type: ignore[attr-defined]
        await self.ws.send(tx)
        rx: bytes = await self.ws.recv()
        assert rx[0] == 3, f"Expected response message, got message of type {rx[0]}"
        assert self.ix == int.from_bytes(rx[1:3], "little"), f"Expected response index {self.ix}, got index {int.from_bytes(rx[1:3], 'little')}"
        self.ix += 1

        wrapper: Message = proto.Wrapper()  # type: ignore[attr-defined]
        wrapper.ParseFromString(rx[3:])
        res.ParseFromString(wrapper.data)
        assert not res.error.code, f"{method.full_name} request received error {res.error.code} = {ERRORS.get(res.error.code, '')}"
        return res

async def test_lobby_api(method_name, **params):
    import os
    import dotenv
    import requests
    import uuid
    env_path = os.path.join(os.path.dirname(__file__), "config.env")
    dotenv.load_dotenv("config.env")
    UID = os.environ.get("test_mjs_uid")
    TOKEN = os.environ.get("test_mjs_token")
    MS_VERSION = requests.get(url="https://mahjongsoul.game.yo-star.com/version.json").json()["version"][:-2]

    async with MahjongSoulAPI("wss://mjusgs.mahjongsoul.com:9663/") as api:
        print("Calling heatbeat...")
        await api.call("heatbeat")
        print("Requesting initial access token...")
        USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0"
        access_token = requests.post(url="https://passport.mahjongsoul.com/user/login", headers={"User-Agent": USER_AGENT, "Referer": "https://mahjongsoul.game.yo-star.com/"}, data={"uid":UID,"token":TOKEN,"deviceId":f"web|{UID}"}).json()["accessToken"]
        print("Requesting oauth access token...")
        oauth_token = (await api.call("oauth2Auth", type=7, code=access_token, uid=UID, client_version_string=f"web-{MS_VERSION}")).access_token
        print("Calling heatbeat...")
        await api.call("heatbeat")
        print("Calling oauth2Check...")
        assert (await api.call("oauth2Check", type=7, access_token=oauth_token)).has_account, "couldn't find account with oauth2Check"
        print("Calling oauth2Login...")
        client_device_info = {"platform": "pc", "hardware": "pc", "os": "mac", "is_browser": True, "software": "Firefox", "sale_platform": "web"}
        await api.call("oauth2Login", type=7, access_token=oauth_token, reconnect=False, device=client_device_info, random_key=str(uuid.uuid1()), client_version={"resource": f"{MS_VERSION}.w"}, currency_platforms=[], client_version_string=f"web-{MS_VERSION}", tag="en")
        print(f"Calling {method_name}...")
        res3 = await api.call(method_name, **params)
        print(res3)

    import datetime
    date_string = str(datetime.datetime.now()).split(".")[0]
    if not os.path.isdir("cached_results"):
        os.mkdir("cached_results")
    with open(f"cached_results/{method_name}-{date_string}.json", "wb") as f:
        f.write(res3.SerializeToString())
    return res3

async def test_contest_manager_api(method_name, **params):
    import os
    import dotenv
    dotenv.load_dotenv("config.env")
    mjs_username = os.environ.get("test_mjs_username")
    mjs_password = os.environ.get("test_mjs_password")
    contest_unique_id = int(os.environ.get("test_contest_unique_id"))

    async with MahjongSoulAPI("wss://common-v2.maj-soul.com/contest_ws_gateway") as api:
        print("Calling loginContestManager...")
        res1 = await api.call("loginContestManager", account=mjs_username, password=hmac.new(b"lailai", mjs_password.encode(), hashlib.sha256).hexdigest(), type=0)
        print("Calling manageContest...")
        res2 = await api.call('manageContest', unique_id=contest_unique_id)
        print(f"Calling {method_name}...")
        res3 = await api.call(method_name, **params)
        print(res3)

    import datetime
    date_string = str(datetime.datetime.now()).split(".")[0]
    if not os.path.isdir("cached_results"):
        os.mkdir("cached_results")
    with open(f"cached_results/{method_name}-{date_string}.json", "wb") as f:
        f.write(res3.SerializeToString())
    return res3

async def test_account_manager_api(method_name, **params):
    import os
    import dotenv
    import requests
    import uuid
    dotenv.load_dotenv("config.env")
    mjs_username = os.environ.get("mjs_sh_username")
    mjs_password = os.environ.get("mjs_sh_password")

    # following sequence is inspired by `mahjong_soul_api`:
    # https://github.com/MahjongRepository/mahjong_soul_api/blob/master/example.py
    # ms_version example: 0.10.269.w
    ms_version = requests.get(url="https://game.maj-soul.com/1/version.json").json()["version"]
    config = requests.get(url=f"https://game.maj-soul.com/1/v{ms_version}/config.json").json()

    # recommended_list_url example: https://lb-hw.maj-soul.com/api/v0/recommend_list
    recommended_list_url = config["ip"][0]["region_urls"][1]["url"]

    # servers json example: {"servers":["gateway-hw.maj-soul.com:443"]}
    servers_json = requests.get(url=
        f"{recommended_list_url}?service=ws-gateway&protocol=ws&ssl=true").json()
    server = servers_json["servers"][0]

    # endpoint example: wss://gateway-hw.maj-soul.com:443/gateway
    endpoint = f"wss://{server}/gateway"

    async with MahjongSoulAPI(endpoint) as api:
        client_version_string = f"web-{ms_version[:-2]}"
        client_device_info = {"is_browser": True}
        await api.call(
            "login",
            account=mjs_username,
            password=hmac.new(b"lailai", mjs_password.encode(), hashlib.sha256).hexdigest(),
            device=client_device_info,
            random_key=str(uuid.uuid1()),
            client_version_string=client_version_string)
        print(f"Calling {method_name}...")
        res = await api.call(method_name, **params)
        print(f"{res}")

if __name__ == "__main__":
    import datetime
    yesterday = datetime.datetime.now() + datetime.timedelta(days=-1)
    ninety_days_later = datetime.datetime.now() + datetime.timedelta(days=89)
    asyncio.run(test_contest_manager_api(
        "updateContestGameRule",
        start_time = int(yesterday.timestamp()),
        finish_time = int(ninety_days_later.timestamp())))

    # asyncio.run(test_contest_manager_api("searchAccountByPattern", query_nicknames=["Kalanchloe"]))
    # asyncio.run(test_contest_manager_api("searchAccountByNickname", query_nicknames=["Kalanchloe"]))
    # asyncio.run(test_contest_manager_api("searchAccountByNickname", query_nicknames=["Kalanchloe"]))
    # asyncio.run(test_contest_manager_api("searchAccountByEid", eids=[78562538]))
    # asyncio.run(test_contest_manager_api("fetchContestGameRecords"))
    # asyncio.run(test_contest_manager_api("fetchContestPlayer"))
    # asyncio.run(test_lobby_api("searchAccountById", account_id=118325554))
    # asyncio.run(test_lobby_api("accountList", account_id_list=[118325554]))
    # asyncio.run(test_lobby_api("searchAccountByPattern", search_next=False, pattern="Kalanchloe"))
    # asyncio.run(test_account_manager_api(
    #     "fetchGameRecord",
    #     game_uuid="230814-90607dc4-3bfd-4241-a1dc-2c639b630db3",
    #     client_version_string="web-0.10.269"))
    # asyncio.run(test_account_manager_api(
    #     "fetchGameRecord",
    #     game_uuid="230818-91f270e2-1ece-4a0b-a712-cb160acfe7e5",
    #     client_version_string="web-0.10.269"))
    # asyncio.run(test_account_manager_api(
    #     "fetchGameRecordsDetail",
    #     uuid_list=[
    #         "230814-90607dc4-3bfd-4241-a1dc-2c639b630db3",
    #         "230818-91f270e2-1ece-4a0b-a712-cb160acfe7e5"]))
    # asyncio.run(test_account_manager_api(
    #     "fetchGameRecordsDetail",
    #     uuid_list=[
    #         "230814-90607dc4-3bfd-4241-a1dc-2c639b631234"])) # false game record




    # f = open(f"cached_results/fetchContestGameRecords-2023-08-18 20:03:43.json", 'rb')
    # record = proto.ResFetchCustomizedContestGameRecordList()  # type: ignore[attr-defined]
    # record.ParseFromString(f.read())
    # print(record)

    # pass
