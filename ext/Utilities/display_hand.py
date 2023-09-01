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


    "1md": "<:1md:1147275913319428216>",
    "2md": "<:2md:1147276023642210304>",
    "3md": "<:3md:1147276030151766037>",
    "4md": "<:4md:1147276133956591666>",
    "5md": "<:5md:1147276140088672417>",
    "6md": "<:6md:1147276278437773372>",
    "7md": "<:7md:1147276284318191687>",
    "8md": "<:8md:1147276427784355880>",
    "9md": "<:9md:1147276431957696632>",
    "0md": "<:0md:1147275908399509657>",

    "1pd": "<:1pd:1147275914896494642>",
    "2pd": "<:2pd:1147276025835835594>",
    "3pd": "<:3pd:1147276031456202783>",
    "4pd": "<:4pd:1147276135151980634>",
    "5pd": "<:5pd:1147276141191778334>",
    "6pd": "<:6pd:1147276280400711740>",
    "7pd": "<:7pd:1147276285303853147>",
    "8pd": "<:8pd:1147276428841341018>",
    "9pd": "<:9pd:1147276433098559668>",
    "0pd": "<:0pd:1147275909691346984>",

    "1sd": "<:1sd:1147275915932467323>",
    "2sd": "<:2sd:1147276027123482684>",
    "3sd": "<:3sd:1147276032441860186>",
    "4sd": "<:4sd:1147276136900993114>",
    "5sd": "<:5sd:1147276142399717427>",
    "6sd": "<:6sd:1147276281818398943>",
    "7sd": "<:7sd:1147276286172090571>",
    "8sd": "<:8sd:1147276430946865337>",
    "9sd": "<:9sd:1147276434730139779>",
    "0sd": "<:0sd:1147275911922729091>",

    "1zd": "<:1zd:1147275919380185150>",
    "2zd": "<:2zd:1147276027949764669>",
    "3zd": "<:3zd:1147276033549152286>",
    "4zd": "<:4zd:1147276138155089990>",
    "5zd": "<:5zd:1147276143125352449>",
    "6zd": "<:6zd:1147276282866966538>",
    "7zd": "<:7zd:1147276287581372556>",

    "1xd": "<:1xd:1147275917404680375>",


    "1Md": "<:1Md:1147277392931459156>",
    "2Md": "<:2Md:1147277545868382328>",
    "3Md": "<:3Md:1147277551765573735>",
    "4Md": "<:4Md:1147277711652425788>",
    "5Md": "<:5Md:1147277717113413632>",
    "6Md": "<:6Md:1147277954922061945>",
    "7Md": "<:7Md:1147277963688165406>",
    "8Md": "<:8Md:1147278119145853038>",
    "9Md": "<:9Md:1147278123046555781>",
    "0Md": "<:0Md:1147277387747315782>",

    "1Pd": "<:1Pd:1147277394789539952>",
    "2Pd": "<:2Pd:1147277546929524797>",
    "3Pd": "<:3Pd:1147277552805748977>",
    "4Pd": "<:4Pd:1147277713141407825>",
    "5Pd": "<:5Pd:1147277719080542341>",
    "6Pd": "<:6Pd:1147277958592073801>",
    "7Pd": "<:7Pd:1147277965432987770>",
    "8Pd": "<:8Pd:1147278120248954890>",
    "9Pd": "<:9Pd:1147278124262887534>",
    "0Pd": "<:0Pd:1147277389622149355>",

    "1Sd": "<:1Sd:1147277396328845372>",
    "2Sd": "<:2Sd:1147277548733071440>",
    "3Sd": "<:3Sd:1147277554156306503>",
    "4Sd": "<:4Sd:1147277714735247543>",
    "5Sd": "<:5Sd:1147277720095572099>",
    "6Sd": "<:6Sd:1147277959716159649>",
    "7Sd": "<:7Sd:1147277967286861916>",
    "8Sd": "<:8Sd:1147278121926668348>",
    "9Sd": "<:9Sd:1147278126502653952>",
    "0Sd": "<:0Sd:1147277391660580954>",

    "1Zd": "<:1Zd:1147277398727991387>",
    "2Zd": "<:2Zd:1147277550029123654>",
    "3Zd": "<:3Zd:1147277555351687268>",
    "4Zd": "<:4Zd:1147277715968372747>",
    "5Zd": "<:5Zd:1147277721701986335>",
    "6Zd": "<:6Zd:1147277961196748853>",
    "7Zd": "<:7Zd:1147277968419344504>",

    "1Xd": "<:1Xd:1147277396878299148>",
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
                output += " "
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
    # get the Tile Suit Blocks: "12p78s45pd" => ["12p", "78s", "45pd"]
    tsb_matches = re.finditer(r'(\d+[mspzxMSPZX])(d)?', tile_group)
    # ["12p", "78s", "45pd"] =>
    # "<:1p:1142707873802113044><:2p:1142707875261726772>..."
    for tsb_match in tsb_matches:
        tsb: str = tsb_match.group(1)
        if tsb_match.group(2):
            suit = tsb[-1] + "d"
        else:
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
    tsb_matches = re.finditer(r'(\d+[mspzxMSPZX])(d)?', input)
    for tsb_match in tsb_matches:
        j = tsb_match.start()

        if j-i == 1 and input[i] == ' ':
            # if it's a space between two groups of tiles, turn it
            # into a figurespace
            output += " "
        else:
            output += input[i:j]
        
        # Tile Suit Block
        tsb: str = tsb_match.group(1)
        if tsb_match.group(2):
            suit = tsb[-1] + "d"
        else:
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
    # print(display_hand("111md456p8pd134s 4p 7z7Zd7z"))
    print(replace_text("Do notations like \"3p2m20M1Zd 2d2Pd2223Md\" work? What about another tile like 1m? Unquoted and undelimited1s, for example.1p"))
