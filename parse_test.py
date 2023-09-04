from unit_test_imports import links
import asyncio
from ext.InjusticeJudge.utilities import parse_game

async def test_injustice():
    # this took me so long to debug... I tried to make my own AccountManager, while
    # `utilities.py` was using the one from `global_stuff`... UGH.
    # uncomment the two lines below if the games are not cached yet
    # from global_stuff import account_manager
    # await account_manager.connect_and_login()
    print("===============================")
    for reason, link in links.items():
        print("reason: ", reason, "\n-----------")
        header, ret = await parse_game(link)
        print(header)
        for text in ret:
            print(text)
        print("===============================")

asyncio.run(test_injustice())
