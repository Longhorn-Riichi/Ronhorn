import asyncio
import aiohttp
import json
import re
import websockets

BASE_URL = 'https://mahjongsoul.game.yo-star.com'
VERSION_URL = 'https://mahjongsoul.game.yo-star.com/version.json'
CONFIG_URL = 'https://mahjongsoul.game.yo-star.com/v{}/config.json' 

CONTEST_MANAGEMENT_BASE_URL = 'https://mahjongsoul.tournament.yo-star.com'
CONTEST_MANAGEMENT_CONFIG_URL = 'https://mahjongsoul.tournament.yo-star.com/dhs/js/config.js' 

async def get_version():
    '''
    Retrieves the most recent version number of Mahjsoul's application

    Returns: string 
    
    Example: "0.8.61.w"
    '''
    async with aiohttp.ClientSession() as session:
        print('Retrieving version number...')

        response = await session.get(VERSION_URL)
        response = await response.json()

        try:
            version = response['version']
        except KeyError:
            return None

        return version

async def get_recommended_servers():
    '''
    Retrieves a list of websocket uri's of recommended game servers

    Returns: list
    
    Example: ["wss://mjusgs.mahjongsoul.com:9663"]
    '''
    async with aiohttp.ClientSession() as session:
        #get the latest version number
        version = await get_version()

        #get the url of the list of recommended servers
        print('Retrieving server list URL...')

        url = CONFIG_URL.format(version)
        response = await session.get(url)
        response = await response.json()    

        serversURL = response['ip'][0]['region_urls'][0]['url'] + '?service=ws-gateway&protocol=ws&ssl=true'

        #get the list of recommended servers
        print(('Retrieving recommended servers...'))
        response = await session.get(serversURL)
        response = await response.json()

        #get the uri of the first recommended server
        try:
            recommendedServers = [f'wss://{server}' for server in response['servers']]
        except KeyError:
            return []

        return recommendedServers

async def check_server_maintenance(self):
    async with aiohttp.ClientSession() as session:
        version = await get_version()

        url = CONFIG_URL.format(version)
        response = await session.get(url)
        response = await response.json()    

        serversURL = response['ip'][0]['region_urls'][0]['url'] + '?service=ws-gateway&protocol=ws&ssl=true'

        response = await session.get(serversURL)
        response = await response.json()

        return 'maintenance' in response

async def get_contest_management_servers():
    async with aiohttp.ClientSession() as session:
        response = await session.get(CONTEST_MANAGEMENT_CONFIG_URL)
        text = await response.text()

        port = re.search('[0-9]{4}', text).group()

        url = f'https://mjusgs.mahjongsoul.com:{port}/api/customized_contest/random'
        response = await session.get(url)
        response = await response.json()

        servers = []

        try:
            servers = response['servers']
        except KeyError:
            return []
        
        return [f'wss://{uri}' for uri in servers]
