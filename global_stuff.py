import gspread
import asyncio
import dotenv
import json
import discord
import logging
from os import getenv
from modules.mahjongsoul.account_manager import AccountManager

# load environmental variables
dotenv.load_dotenv("config.env")

def assert_getenv(name: str) -> str:
    value = getenv(name)
    assert value is not None, f"missing \"{name}\" in config.env"
    return value

# Google Sheets stuff
gs_client = gspread.service_account(filename='gs_service_account.json')
leaderboard_ss = gs_client.open_by_url(assert_getenv("spreadsheet_url"))
registry = leaderboard_ss.worksheet("Registry")
raw_scores = leaderboard_ss.worksheet("Raw Scores")
registry_lock = asyncio.Lock()
raw_scores_lock = asyncio.Lock()

# initialize an account manager to be shared with all extensions.
# login must happen in `setup_hook()`, before loading extensions
account_manager = AccountManager(
    mjs_username=assert_getenv("mjs_sh_username"),
    mjs_password=assert_getenv("mjs_sh_password"))

# load the list of servers that want the
# non-Longhorn Riichi, non-/injustice commands
with open('slash_commands_servers.json', 'r') as file:
    slash_commands_servers = json.load(file)
slash_commands_guilds = [discord.Object(id=id) for id in slash_commands_servers.values()]

# logging
logger = logging.getLogger("Log")
