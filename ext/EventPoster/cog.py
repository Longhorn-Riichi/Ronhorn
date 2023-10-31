import asyncio
import datetime
import discord
import json
import logging
from discord.ext import commands, tasks
from typing import *

from global_stuff import assert_getenv

GUILD_ID: int = int(assert_getenv("guild_id"))

class EventPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timezone = datetime.timezone(datetime.timedelta(hours=-5)) # CST = UTC-5
        with open("images/sunday_cover_image.png", "rb") as f:
            self.sunday_image = f.read()
        with open("images/friday_cover_image.png", "rb") as f:
            self.friday_image = f.read()

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
            privacy_level = discord.PrivacyLevel.guild_only,
            image = self.sunday_image,
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
            privacy_level = discord.PrivacyLevel.guild_only,
            image = self.friday_image,
            location = "Mahjong Soul")

    @tasks.loop(hours=24, reconnect=True)
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

        print("Looking to post weekly events...")

        if not sunday_event_exists:
            print("Posting sunday event!")
            await self.post_sunday_event()

        if not friday_event_exists:
            print("Posting friday event!")
            await self.post_friday_event()

    async def async_setup(self):
        self.guild = await self.bot.fetch_guild(GUILD_ID)
        await self.try_post_events()
        self.try_post_events.start()

    # ensure bot is ready before try_post_events is called
    @try_post_events.before_loop
    async def try_post_events_ready(self):
        await self.bot.wait_until_ready()

    @try_post_events.error
    async def try_post_events_error(self, error):
        print(f"Error in posting events: {error}")



async def setup(bot: commands.Bot):
    logging.info(f"Loading cog `{EventPoster.__name__}`...")
    cog = EventPoster(bot)
    asyncio.create_task(cog.async_setup())
    await bot.add_cog(cog, guilds=[discord.Object(id=GUILD_ID)])
