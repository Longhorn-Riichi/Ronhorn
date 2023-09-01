# not testing the command, but rather running the judge over multiple
# game logs (likely already cached) to make sure that it doesn't crash
# and output things like "KeyError(15)" to the Discord users.
import asyncio
from ext.InjusticeJudge.utilities import analyze_game
# this took me so long to debug... I tried to make my own AccountManager, while
# `utilities.py` was using the one from `global_stuff`... UGH.
from global_stuff import account_manager

links = [
    # triple ron
    "https://mahjongsoul.game.yo-star.com/?paipu=220930-8a7c1e7f-2114-46f9-80d4-208067ef0385_a939260192",
    # double houtei ron (long game)
    "https://tenhou.net/4/?log=2023052010gm-000b-18940-a4d57844",
    # dora 4 bomb
    "https://mahjongsoul.game.yo-star.com/?paipu=230823-b98add6f-a6e5-45a2-8e43-432b35b362e9_a878761203",
    # nagashi + 9 terminal draw
    "https://tenhou.net/0/?log=2020030806gm-0089-0000-e963afa0&tw=2",
    # ankan + two kakans
    "https://tenhou.net/0/?log=2023081915gm-0089-0000-0f655b26&tw=3",
    # chankan, early ron
    "http://tenhou.net/0/?log=2018062009gm-0009-7863-8295fab0&tw=2",
    # haitei/rinshan
    "http://tenhou.net/0/?log=2016050112gm-0089-0000-3b554915&tw=2",
    # consecutive kan/rinshan
    "http://tenhou.net/0/?log=2017123008gm-0009-7447-a6773dec&tw=3",
    # houtei
    "http://tenhou.net/0/?log=2016111413gm-0089-0000-a664b045&tw=0",
    # double riichi
    "http://tenhou.net/0/?log=2018111209gm-0029-0000-c34de3ad&tw=0",
    # chiihou
    "http://tenhou.net/0/?log=2017122406gm-0009-0000-7790b074&tw=2",
    # daisangen
    "https://mahjongsoul.game.yo-star.com/?paipu=230819-fb4249b5-ef05-4f89-b831-4f7e5305f05e_a878761203",
    # hidden double dora, kiriage mangan
    "https://tenhou.net/4/?log=2022091409gm-000b-17856-ec9313b9",
    # rinshan
    "https://mahjongsoul.game.yo-star.com/?paipu=230728-5ec4d440-0499-4aee-91e6-dce1c0b5708d",
    # dama kokushi, dama oyappane (no injustice for player)
    "https://mahjongsoul.game.yo-star.com/?paipu=220502-4a0534c9-8b34-4fb2-a1bd-30787d378df1_a933848157"
]

async def test_links():
    await account_manager.connect_and_login()
    print("===============================")
    for link in links:
        print(await analyze_game(link))
        print("===============================")

asyncio.run(test_links())
