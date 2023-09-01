import re

DISCORD_CHAR_LIMIT = 2000

# this is displayed in place of an unidentified tile like "8z"
DEFAULT_TILE = ":question:"

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


    "1M": "<:1M:1147238374088917185>",
    "2M": "<:2M:1147238407597211768>",
    "3M": "<:3M:1147238414157095033>",
    "4M": "<:4M:1147238465247924225>",
    "5M": "<:5M:1147238469979095131>",
    "6M": "<:6M:1147238492120809472>",
    "7M": "<:7M:1147238496591954077>",
    "8M": "<:8M:1147238508839313540>",
    "9M": "<:9M:1147238545438818405>",
    "0M": "<:0M:1147238370435678228>",

    "1P": "<:1P:1147238375204593675>",
    "2P": "<:2P:1147238408595451906>",
    "3P": "<:3P:1147238415084027995>",
    "4P": "<:4P:1147238466766262332>",
    "5P": "<:5P:1147238472080445571>",
    "6P": "<:6P:1147238493714665472>",
    "7P": "<:7P:1147238498508738723>",
    "8P": "<:8P:1147238510600925337>",
    "9P": "<:9P:1147238544088240189>",
    "0P": "<:0P:1147238371161276477>",

    "1S": "<:1S:1147238377335300106>",
    "2S": "<:2S:1147238410877161483>",
    "3S": "<:3S:1147238416325558292>",
    "4S": "<:4S:1147238467735138394>",
    "5S": "<:5S:1147238473145794711>",
    "6S": "<:6S:1147238494620635136>",
    "7S": "<:7S:1147238499502788829>",
    "8S": "<:8S:1147238511720812614>",
    "9S": "<:9S:1147238562060828743>",
    "0S": "<:0S:1147238373099057172>",

    "1Z": "<:1Z:1147238379499565088>",
    "2Z": "<:2Z:1147238412374511776>",
    "3Z": "<:3Z:1147238418477236346>",
    "4Z": "<:4Z:1147238469140234260>",
    "5Z": "<:5Z:1147238474282455100>",
    "6Z": "<:6Z:1147238495723720776>",
    "7Z": "<:7Z:1147238500727537774>",

    "1X": "<:1X:1147238378685861908>",
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
            output += DISCORD_TILES.get(tile+suit, DEFAULT_TILE)
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
            output += DISCORD_TILES.get(tile+suit, DEFAULT_TILE)
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
