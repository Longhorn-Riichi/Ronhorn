import asyncio
import datetime
import discord
import json
import logging
from discord.ext import commands, tasks
from typing import *

class EventPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timezone = datetime.timezone(datetime.timedelta(hours=-5)) # CST = UTC-5

    async def post_sunday_event(self):
        today = datetime.date.today()
        next_sunday = today + datetime.timedelta(days=((6 - today.weekday() - 1) % 7) + 1)
        two_pm = datetime.time(hour=14)
        six_pm = datetime.time(hour=18)
        await self.guild.create_scheduled_event(
            name = "Riichi Sunday",
            description = "This is our weekly meetup, where we'll be **teaching and playing** Riichi! The meeting location is WCP Student Activity Center, room 2.120, 2-4 PM. We can play more after 4 PM in the same building.",
            start_time = datetime.datetime.combine(date=next_sunday, time=two_pm, tzinfo=self.timezone),
            end_time = datetime.datetime.combine(date=next_sunday, time=six_pm, tzinfo=self.timezone),
            entity_type = discord.EntityType.external,
            location = "WCP Student Activity Center, Room 2.120")

    async def post_friday_event(self):
        today = datetime.date.today()
        next_friday = today + datetime.timedelta(days=((4 - today.weekday() - 1) % 7) + 1)
        eight_pm = datetime.time(hour=20)
        ten_pm = datetime.time(hour=22)
        await self.guild.create_scheduled_event(
            name = "Friday Online Mahjong",
            description = "We'll be playing on Mahjong Soul in our club lobbies. Make sure you have </register:1143698078159868022>ed your Mahjong Soul account with our club bot <@1141507580938686586>! Use </help:1143698078159868015> for help!",
            start_time = datetime.datetime.combine(date=next_friday, time=eight_pm, tzinfo=self.timezone),
            end_time = datetime.datetime.combine(date=next_friday, time=ten_pm, tzinfo=self.timezone),
            entity_type = discord.EntityType.external,
            location = "Mahjong Soul")

    @tasks.loop(hours=24)
    async def try_post_events(self):
        events = await self.guild.fetch_scheduled_events()
        sunday_event_exists = False
        friday_event_exists = False
        for event in events:
            weekday = (event.start_time + self.timezone.utcoffset(None)).weekday()
            if weekday == 6:
                sunday_event_exists = True
            elif weekday == 4:
                friday_event_exists = True

        if not sunday_event_exists:
            print("Posting sunday event!")
            await self.post_sunday_event()

        if not friday_event_exists:
            print("Posting friday event!")
            await self.post_friday_event()

    async def async_setup(self, guild_id: int):
        self.guild = await self.bot.fetch_guild(guild_id)
        print("Hello World!")
        await self.try_post_events()



async def setup(bot: commands.Bot):
    logging.info(f"Loading cog `{EventPoster.__name__}`...")
    with open('event_poster_servers.json', 'r') as file:
        event_poster_servers = json.load(file)
    for guild_id in event_poster_servers.values():
        cog = EventPoster(bot)
        asyncio.create_task(cog.async_setup(guild_id))
        await bot.add_cog(cog, guilds=[discord.Object(id=guild_id)])
