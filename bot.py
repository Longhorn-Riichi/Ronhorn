import asyncio
import discord
import logging
from discord import app_commands, Interaction
from discord.ext import commands
from global_stuff import assert_getenv
from typing import *

def get_extensions() -> List[str]:
    EXTENSIONS_FILE = assert_getenv("extensions_file")
    try:
        with open(EXTENSIONS_FILE, 'r') as f:
            return [l.strip('\n') for l in f.readlines()]
    except FileNotFoundError:
        with open(EXTENSIONS_FILE, 'w') as f:
            return []

async def setup_bot() -> commands.Bot:
    logging.info("Initializing bot...")

    COMMAND_PREFIX = assert_getenv("command_prefix")

    # initialize the bot.
    intents = discord.Intents.default()
    intents.members = True # necessary e.g., to get members of a role
    intents.message_content = True # necessary for regular commands to work
    
    bot = commands.Bot(
        command_prefix=COMMAND_PREFIX,
        intents=intents)

    # bot events
    @bot.event
    async def on_ready():
        logging.info(f"{bot.user} is now online.")

    @bot.event
    async def on_guild_join(guild):
        await bot.tree.sync(guild=guild)

    # bot commands (non-slash; only for the admin/owner)
    @bot.command(name='sync', hidden=True)
    @commands.is_owner()
    async def sync(ctx: commands.Context):
        # note that global commands need to be explicitly copied to the guild
        await bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"Synced slash commands exclusive to this server ({ctx.guild.name}).")

    @bot.command(name='sync_server', hidden=True)
    @commands.is_owner()
    async def sync_server(ctx: commands.Context, guild_id: str):
        guild = bot.get_guild(int(guild_id))
        await bot.tree.sync(guild=guild)
        await ctx.send(f"Synced slash commands for guild {guild_id} ({guild.name}).")

    @bot.command(name='sync_global', hidden=True)
    @commands.is_owner()
    async def sync_global(ctx: commands.Context):
        await bot.tree.sync()
        await ctx.send("Synced global slash commands.")

    @bot.command(name='shutdown', hidden=True)
    @commands.is_owner()
    async def shutdown(ctx: commands.Context):
        await ctx.send("Shutting down...")
        await bot.close()

    @bot.command(name='restart', hidden=True)
    @commands.is_owner()
    async def restart(ctx: commands.Context): 
        await ctx.send("Restarting...")
        from os import execl
        execl("./start.sh", "./start.sh")

    @bot.command(name='load', hidden=True)
    @commands.is_owner()
    async def load_extension(ctx: commands.Context, extension_name: str): 
        await ctx.send(f"Loading extension: {extension_name}.")
        await bot.load_extension(extension_name)
        await ctx.send(f"Loaded extension: {extension_name}.")

    @bot.command(name='unload', hidden=True)
    @commands.is_owner()
    async def unload_extension(ctx: commands.Context, extension_name: str): 
        await ctx.send(f"Unloading extension: {extension_name}.")
        await bot.unload_extension(extension_name)
        await ctx.send(f"Unloaded extension: {extension_name}.")

    @bot.command(name='reload', hidden=True)
    @commands.is_owner()
    async def reload_extension(ctx: commands.Context, extension_name: str=None):
        if (extension_name != None):
            await bot.reload_extension(extension_name)

            await ctx.send(f"Reloaded extension: {extension_name}.")
        else:
            extensions = get_extensions()
            for extension in extensions:
                await bot.reload_extension(extension)
            
            await ctx.send(f"Reloaded all extensions: {extensions}.")

    # official way to handle all regular command errors
    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.errors.NotOwner):
            await ctx.send(f"You need to be this bot's owner to use this command.")
        else:
            raise error

    # somewhat unofficial way to handle all slash command errors
    # https://stackoverflow.com/a/75815621/21452015
    # also see here: https://discordpy.readthedocs.io/en/stable/ext/commands/api.html#discord.ext.commands.Cog.cog_app_command_error
    async def on_app_command_error(interaction: Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingRole):
            await interaction.response.send_message(f"You do not have the required role ({error.missing_role}) to use this command.", ephemeral=True)
        elif isinstance(error, app_commands.errors.CommandInvokeError):
            # here it's especially important so the bot isn't stuck "thinking" (e.g., from `defer()`)
            # meanwhile, the user also gets an idea of what they might have done wrong.
            if interaction.response.is_done():
                # NOTE: `ephemeral` here only works if `defer()` was called with `ephemeral=True`
                await interaction.followup.send(repr(error.original), ephemeral=True)
            else:
                await interaction.response.send_message(repr(error.original), ephemeral=True)
            # do NOT raise the error again here; this somehow results in the error being
            # sent here again (TOTHINK: but only once! Intriguing...)
        else:
            raise error
    bot.tree.on_error = on_app_command_error

    async def setup_hook():
        # note that extensions should be loaded before the slash commands
        # are synched. Here we ensure that by only allowing manual synching
        # once the bot finishes loading (i.e., `setup_hook()` has been called)

        # load extensions in parallel
        logging.info("Loading extensions...")
        try:
            await asyncio.gather(*map(bot.load_extension, get_extensions()))
        except Exception as e:
            import traceback as tb
            logging.info("Exception encountered while loading extensions: " + str(e))
            logging.info("".join(tb.format_exception(None, e, e.__traceback__)))
        logging.info("Extensions loaded!")

    bot.setup_hook = setup_hook
    bot.remove_command('help')

    logging.info("Bot initialized!")
    return bot
