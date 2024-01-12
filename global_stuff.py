import asyncio
import logging
import dotenv

dotenv.load_dotenv("config.env")

def assert_getenv(name: str) -> str:
    from os import getenv
    value = getenv(name)
    assert value is not None, f"missing \"{name}\" in config.env"
    return value

# Google Sheets stuff
gs_client = None
leaderboard_ss = None
registry = None
raw_scores = None
registry_lock = asyncio.Lock()
raw_scores_lock = asyncio.Lock()
async def connect_to_google_sheets():
    logging.info("Opening connection to gsheets...")
    global gs_client
    global leaderboard_ss
    global registry
    global raw_scores
    import gspread
    await asyncio.sleep(0) # yield thread
    gs_client = gspread.service_account(filename='gs_service_account.json')
    await asyncio.sleep(0) # yield thread
    leaderboard_ss = gs_client.open_by_url(assert_getenv("spreadsheet_url"))
    registry = leaderboard_ss.worksheet("Registry")
    raw_scores = leaderboard_ss.worksheet("Raw Scores")
    logging.info("Opened connection to gsheets!")

account_manager = None
async def load_mjs_account_manager():
    # initialize an account manager to be shared with all extensions.
    # login must happen in `setup_hook()`, before loading extensions
    logging.info("Opening connection to mjs...")
    global account_manager
    from modules.mahjongsoul.account_manager import AccountManager
    account_manager = AccountManager(
        mjs_uid=assert_getenv("mjs_sh_uid"),
        mjs_token=assert_getenv("mjs_sh_token"))

    await asyncio.sleep(0) # yield thread
    account_manager_login = asyncio.create_task(account_manager.connect_and_login())
    await asyncio.sleep(0) # yield thread
    await account_manager_login

    logging.info("Opened connection to mjs!")
