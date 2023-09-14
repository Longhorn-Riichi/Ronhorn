# not testing the command, but rather running the judge over multiple
# game logs (likely already cached) to make sure that it doesn't crash
# and output things like "KeyError(15)" to the Discord users.
from unit_test_imports import links
import asyncio
from ext.InjusticeJudge.utilities import analyze_game

async def test_injustice():
    # this took me so long to debug... I tried to make my own AccountManager, while
    # `utilities.py` was using the one from `global_stuff`... UGH.
    # uncomment the two lines below if the games are not cached yet
    from global_stuff import account_manager
    await account_manager.connect_and_login()
    print("===============================")
    for reason, link in links.items():
        print("reason: ", reason, "\n-----------")
        for injustice in await analyze_game(link, look_for={"skill"}):
            print(injustice)
        print("===============================")

asyncio.run(test_injustice())
