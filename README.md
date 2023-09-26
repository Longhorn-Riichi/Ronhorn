# Ronhorn

Ronhorn is Longhorn Riichi's Discord Bot, which supports two categories of slash commands:
1. commands specific to Longhorn Riichi's club operations (`/register`, `/enter_score`, etc.)
2. commands that provide utilities for online mahjong games like Mahjong Soul and Tenhou (`/skill`, `/parse`, etc.)

The documentation for the Discord slash commands can be found [here](https://longhornriichi.com/ronhorn/)

It also has a passive component that automatically tracks and records online games played in the club's Mahjong Soul lobbies, which is a more advanced version of that of the [UvUManager](https://github.com/Longhorn-Riichi/UvUManager).

# Repository Structure:
- `bot.py`: entry point of the Discord bot. Does the following:
    1. imports `global_stuff.py`, which does the following:
        1. load all the environment variables from `config.env`
        1. initialize the Google Sheets interface
        1. initialize Mahjong Soul `AccountManager`
    1. set up the non-slash Discord commands
    1. set up command error handlers (both slash and non-slash)
- `/ext/`: Discord bot extensions (each extension is a suite of slash commands and their helper functions)
    - `LobbyManagers`: has commands to pause, unpause, and terminate contest games from all 4 tournaments. Listens for finished games and records results. Automatically extends contest finish_time and reconnects when necessary.
    - `Utilities`: various utilities, including recording in-person games, managing club membership, fetching links to player stats on external websites, etc.
    - `InjusticeJudge`: has commands that rely on the [InjusticJudge](https://github.com/Longhorn-Riichi/InjusticeJudge) submodule, and the helpers that make efficient API calls. Caches the game logs in `/cached_games`, up to 1 GB.
- `/modules/`: modules to be imported into the above extensions
    - `InjusticeJudge`: houses the [InjusticJudge](https://github.com/Longhorn-Riichi/InjusticeJudge) submodule
    - `pymjsoul`: a modified version of [mjsoul.py](https://github.com/RiichiNomi/mjsoul.py) that provides `MajsoulChannel`, a class for interfacing with Mahjong Soul's API
    - `mahjongsoul`: contains two wrappers of `MajsoulChannel`:
        1. `ContestManager`: logs into the Chinese Mahjong Soul contest management server to monitor club tournaments
        1. `AccountManager`: logs into the Chinese Mahjong Soul game server to directly fetch game results/records

# Setting up the bot
First, `cp config.template.env config.env`.
## Discord Stuff
1. set up a bot account on Discord's [developer portal](https://discord.com/developers/applications) (`New Application`).
    - (SETTINGS -> Bot) Privileged Gateway Intents: `SERVER MEMBERS INTENT` AND `MESSAGE CONTENT INTENT`
1. invite the bot to the respective servers. You can use the developer portal's OAuth2 URL Generator (SETTINGS -> OAuth2 -> URL Generator):
    - Scopes: bot
    - Bot Permissions: Send Messages, Manage Messages, Use External Emojis (and more as we add more functionalities)
1. fill in the `Discord Stuff` section of [config.env](config.env). The bot token can be obtained through (SETTINGS -> Bot \[-> Reset Token\])
## Google Sheets Stuff
1. set up a Google Cloud project. Enable Google Sheets API access, and make a service account. Generate a JSON key for that service account and save it as `gs_service_account.json` in the [root directory]
1. make a suitable Google Spreadsheet ([example](https://docs.google.com/spreadsheets/d/1pXlGjyz165S62-3-4ZXxit4Ci0yW8piVfbVObtjg7Is/edit?usp=sharing)) and share the Spreadsheet with that service account.
1. fill in the `Google Sheets Stuff` section of [config.env](config.env)
## Mahjong Soul Stuff
1. fill in the `Mahjong Soul Stuff` section of [config.env](config.env)
## Server Lists
Make an `injustice_servers.json` in the [root directory], with `<server_name>: <server_ID>` pairs. The `<server_name>` is for record-keeping only. Only servers whose `<server_ID>` is specified here will have the `/injustice` command available. Example:
```json
{
  "Longhorn Riichi": "111111111111111111",
  "The Riichi Mahjong Association (UT Dallas)": "111111111111111111",
  "Riichi Nomi": "111111111111111111"
}
```

Similarly, make a `slash_commands_servers.json` in the [root directory], for the servers that want the slash commands that are not exclusive to Longhorn Riichi (excluding `/injustice`).
```json
{
  "Longhorn Riichi": "111111111111111111",
  "The Riichi Mahjong Association (UT Dallas)": "111111111111111111",
  "Main Mahjong Server": "111111111111111111",
  "Riichi Nomi": "111111111111111111"
}
```

# Running the bot
1. in a Unix shell:

        pipenv install
        pipenv shell
        ./start.sh
1. in the relevant Discord server: run `rh/sync` to sync the slash commands for that server (`rh/` is the regular command prefix).

# Relevant Links (References)
- [amae-koromo](https://github.com/SAPikachu/amae-koromo) and [amae-koromo-scripts](https://github.com/SAPikachu/amae-koromo-scripts)
- [Ronnie](https://github.com/RiichiNomi/ronnie)
- [mjsoul.py](https://github.com/RiichiNomi/mjsoul.py) (eventually we'll add our `mahjongsoul` module into the `mjsoul.py` package)
- [mahjong_soul_api](https://github.com/MahjongRepository/mahjong_soul_api/)

[root directory]: /
