import re

DISCORD_CHAR_LIMIT = 2000

DISCORD_TILES = {
    "1m": "<:1m:1142707135021600830>",
    "2m": "<:2m:1142707491713593355>",
    "3m": "<:3m:1142707570251939880>",
    "4m": "<:4m:1142707571120160810>",
    "5m": "<:5m:1142707573192138792>",
    "6m": "<:6m:1142707574119079936>",
    "7m": "<:7m:1142707575108931665>",
    "8m": "<:8m:1142707576740520006>",
    "9m": "<:9m:1142707577357082655>",
    "0m": "<:0m:1142997164679770152>",

    "1p": "<:1p:1142707873802113044>",
    "2p": "<:2p:1142707875261726772>",
    "3p": "<:3p:1142707876159291512>",
    "4p": "<:4p:1142707877002358847>",
    "5p": "<:5p:1142707923605270590>",
    "6p": "<:6p:1142707925475930153>",
    "7p": "<:7p:1142707927292055562>",
    "8p": "<:8p:1142707928239964160>",
    "9p": "<:9p:1142707928885887040>",
    "0p": "<:0p:1142997170870550538>",

    "1s": "<:1s:1142707987526459455>",
    "2s": "<:2s:1142707989405519973>",
    "3s": "<:3s:1142707991351672982>",
    "4s": "<:4s:1142707992580603914>",
    "5s": "<:5s:1142707996460335155>",
    "6s": "<:6s:1142986859488751646>",
    "7s": "<:7s:1142986876144340992>",
    "8s": "<:8s:1142986885195640972>",
    "9s": "<:9s:1142986898017636382>",
    "0s": "<:0s:1142997176641929347>",

    "1z": "<:1z:1142986930422820996>",
    "2z": "<:2z:1142986936223531028>",
    "3z": "<:3z:1142987133599105065>",
    "4z": "<:4z:1142987139311734856>",
    "5z": "<:5z:1142987150984482989>",
    "6z": "<:6z:1142987158920106104>",
    "7z": "<:7z:1142987164406259733>",

    "1x": "<:1x:1142987199369986179>",


    "1M": "<:1M:1143300025863123046>",
    "2M": "<:2M:1143300036097220658>",
    "3M": "<:3M:1143300105886236682>",
    "4M": "<:4M:1143316151015850136>",
    "5M": "<:5M:1143316144183324683>",
    "6M": "<:6M:1143316186218627142>",
    "7M": "<:7M:1143316179818119251>",
    "8M": "<:8M:1143316207915778208>",
    "9M": "<:9M:1143316202161197198>",
    "0M": "<:0M:1143300021635268774>",

    "1P": "<:1P:1143300032213299290>",
    "2P": "<:2P:1143300038144045177>",
    "3P": "<:3P:1143300107702374511>",
    "4P": "<:4P:1143316158150344825>",
    "5P": "<:5P:1143316145257062490>",
    "6P": "<:6P:1143316187783110778>",
    "7P": "<:7P:1143316180778619013>",
    "8P": "<:8P:1143316199095156856>",
    "9P": "<:9P:1143316205021696000>",
    "0P": "<:0P:1143300023703048343>",

    "1S": "<:1S:1143300034486607872>",
    "2S": "<:2S:1143300104808313032>",
    "3S": "<:3S:1143316064613175488>",
    "4S": "<:4S:1143316159052128287>",
    "5S": "<:5S:1143316147488432148>",
    "6S": "<:6S:1143316190240972811>",
    "7S": "<:7S:1143316182351482920>",
    "8S": "<:8S:1143316200403783701>",
    "9S": "<:9S:1143316207001411694>",
    "0S": "<:0S:1143300024625795102>",

    "1Z": "<:1Z:1143315859708850236>",
    "2Z": "<:2Z:1143315875391361215>",
    "3Z": "<:3Z:1143315890771853312>",
    "4Z": "<:4Z:1143316160520134686>",
    "5Z": "<:5Z:1143316148578947102>",
    "6Z": "<:6Z:1143316177708400802>",
    "7Z": "<:7Z:1143316185061015552>",

    "1X": "<:1X:1143315813588291606>",
}

def display_hand(input: str) -> str:
    """
    given a space-separated mahjong notation, return the string containing
    the Discord emoji representation. Note that the length of the returned
    string could be over Discord's message limit!

    basically the same logic as jekyll-mahjong.
    """
    # get the tile groups: "12p78s45p 1Z11z" => ["12p78s45p", "1Z11z"]
    tile_groups = input.split(' ')

    # convert the first group
    output = emoji_for_tile_group(tile_groups[0])

    for tile_group in tile_groups[1:]:
        emoji_tile_group = emoji_for_tile_group(tile_group)

        if emoji_tile_group:
            if output:
                output += "⠀" # add a Braille space between groups
            output += emoji_tile_group

    return output

def emoji_for_tile_group(tile_group: str) -> str:
    """
    given a mahjong notation, return the string containing the
    Discord emoji representation. Note that the length of the returned
    string could be over Discord's message limit!

    can be used as is, or as a helper of `display_hand()`
    """
    output = ''
    # get the Tile Suit Blocks: "12p78s45p" => ["12p", "78s", "45p"]
    tsb_matches = re.finditer(r'\d+[mspzxMSPZX]', tile_group)
    # ["12p", "78s", "45p"] =>
    # "<:1p:1142707873802113044><:2p:1142707875261726772>..."
    for tsb_match in tsb_matches:
        tsb: str = tsb_match.group()
        suit = tsb[-1]
        for tile in tsb[:-1]:
            output += DISCORD_TILES[tile+suit]
    return output

def replace_text(input: str) -> str:
    """
    replaces the mahjong notation in a string with tile emoji
    strings. Does not require special input -- assumes that all
    matches are mahjong notations. This one checks the length of
    the text every time it converts a notation; will simply output
    an error message string instead of failing or dividing up the
    message.
    """
    output = ''
    error_output = "The input is too long! Try dividing up the input message."
    i = 0 # the index of the first character after the last notation
    tsb_matches = re.finditer(r'\d+[mspzxMSPZX]', input)
    for tsb_match in tsb_matches:
        output += input[i:tsb_match.start()]
        # Tile Suit Block
        tsb: str = tsb_match.group()
        suit = tsb[-1]
        for tile in tsb[:-1]:
            output += DISCORD_TILES[tile+suit]
        if len(output) > DISCORD_CHAR_LIMIT:
            return error_output
        i = tsb_match.end()
    
    if i < len(input):
        output += input[i:]
        if len(output) > DISCORD_CHAR_LIMIT:
            return error_output

    return output
                
if __name__ == "__main__":
    # print(display_hand("111m456p8p134s 4p 7z7Z7z"))
    print(replace_text("Do notations like \"3p2m20M1Z 2d2P2223M\" work? What about another tile like 1m? Unquoted and undelimited1s, for example.1p"))
