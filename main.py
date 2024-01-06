import asyncio
from global_stuff import connect_to_google_sheets, load_mjs_account_manager
import logging
from threading import Thread

async def main() -> None:
    # start importing as early as possible
    background_imports_task = asyncio.create_task(_background_imports())

    # setup logging
    # INFO level captures all except DEBUG log messages.
    # the FileHandler by default appends to the given file
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler("log.txt"),
            logging.StreamHandler()
        ]
    )

    # load environmental variables
    import dotenv
    dotenv.load_dotenv("config.env")

    # load the bot
    from bot import setup_bot
    load_bot_task = asyncio.create_task(setup_bot())
    # load global stuff
    gs_task = asyncio.create_task(connect_to_google_sheets())
    mjs_task = asyncio.create_task(load_mjs_account_manager())

    bot = (await asyncio.gather(load_bot_task, gs_task, mjs_task))[0]

    from global_stuff import assert_getenv
    DISCORD_TOKEN = assert_getenv("bot_token")
    await bot.start(DISCORD_TOKEN)

async def _background_imports() -> None:
    """Cache some imports we might need later in an async thread"""
    pkgs = ["discord", "gspread", "json", "numpy", "matplotlib.pyplot", "google.protobuf",
            "requests", "aiohttp", "websockets", "urllib3",
            "functools", "itertools", "hashlib", "hmac", "struct", "uuid", "re",
            "modules.InjusticeJudge.injustice_judge.classes2"]
    import time
    time_elapsed: float = 0
    for pkg in pkgs:
        start_time = time.time()
        try:
            __import__(pkg)
            await asyncio.sleep(0) # yield thread
        except ImportError:
            logging.error(f"_background_imports: failed to import package {pkg}")
            continue
        time_elapsed += time.time() - start_time
        if time_elapsed >= 1:
            time_elapsed = 0
            await asyncio.sleep(0) # yield
    logging.info("Done with async background imports")

asyncio.run(main())
