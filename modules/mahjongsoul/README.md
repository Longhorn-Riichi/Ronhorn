# tips for reverse-engineering Mahjong Soul admin API:
- refer to `liqi_combined.proto` for all API
- learn the message fields' possible values by examining WS messages sent by browser (Chrome: Inspect -> Network -> WS).
- decode the Protobuf with this [tool](https://www.protobufpal.com/) (you might want to use a plugin like [this](https://chrome.google.com/webstore/detail/filter-drop-down-menu/pdfkhgdhohjkogfppjjfbbkdenabhglp) to search through the dropdown menu). This [tool](https://protobuf-decoder.netlify.app/) also works if you don't care about decoding with the `.proto` file. Remember to remove the first 3 bytes of the captured WS messages (those are message type and index; only 4th byte onward is protobuf).

boilerplate references:
- [Chinese game server](https://github.com/MahjongRepository/mahjong_soul_api/blob/master/example.py)
- [English tournament management server](https://github.com/MahjongRepository/mahjong_soul_api/blob/master/example_admin.py)

