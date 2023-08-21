# bot.py
import dotenv
from os import getenv, execl
import discord
from discord import app_commands, Interaction
from discord.ext import commands
import logging
import gspread
import asyncio

# INFO level captures all except DEBUG log messages.
# the FileHandler by default appends to the given file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    datefmt='%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("log.txt"),
        logging.StreamHandler()
    ]
)

def assert_getenv(name: str) -> str:
    value = getenv(name)
    assert value is not None, f"missing \"{name}\" in config.env"
    return value

# load environmental variables
dotenv.load_dotenv("config.env")

DISCORD_TOKEN = assert_getenv("bot_token")
EXTENSIONS_FILE = assert_getenv("extensions_file")

try:
    with open(EXTENSIONS_FILE, 'r') as f:
        EXTENSIONS = [l.strip('\n') for l in f.readlines()]
except FileNotFoundError:
    with open(EXTENSIONS_FILE, 'w') as f:
        EXTENSIONS = []

# initialize the bot
intents = discord.Intents.default()
intents.message_content = True # necessary for commands to work
bot = commands.Bot(
    command_prefix='$',
    intents=intents)

# initialize the spreadsheet interface and save references in `bot`
# so they can be accessed by all extensions.
gs_client = gspread.service_account(filename='gs_service_account.json')
bot.spreadsheet = gs_client.open_by_url(assert_getenv("spreadsheet_url"))
bot.registry = bot.spreadsheet.worksheet("Registry")
bot.raw_scores = bot.spreadsheet.worksheet("Raw Scores")
bot.registry_lock = asyncio.Lock()
bot.raw_scores_lock = asyncio.Lock()

# initialize an account manager to be shared with all extensions.
# login must happen in `setup_hook()`, before loading extension
from modules.mahjongsoul.account_manager import AccountManager
bot.account_manager = AccountManager(
    mjs_username=assert_getenv("mjs_sh_username"),
    mjs_password=assert_getenv("mjs_sh_password"))

# bot events
@bot.event
async def on_ready():
    logging.info(f"{bot.user} is now online.")

# bot commands (non-slash; only for the admin/owner)
@bot.command(name='sync', hidden=True)
@commands.is_owner()
async def sync(ctx: commands.Context):
    # note that global commands need to be explicitly copied to the guild
    bot.tree.copy_global_to(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send(f"Synced command tree for this server ({ctx.guild.name}).")

# @bot.command(name='sync_global', hidden=True)
# @commands.is_owner()
# async def sync_global(ctx: commands.Context):
#     await bot.tree.sync()
#     await ctx.send("Synced command tree for ALL servers.")

@bot.command(name='shutdown', hidden=True)
@commands.is_owner()
async def shutdown(ctx: commands.Context):
    await ctx.send("Shutting down...")
    await bot.close()

@bot.command(name='restart', hidden=True)
@commands.is_owner()
async def restart(ctx: commands.Context): 
    await ctx.send("Restarting...")
    execl("./start.sh", "./start.sh")

@bot.command(name='load', hidden=True)
@commands.is_owner()
async def load_extension(ctx: commands.Context, extension_name: str): 
    await bot.load_extension(extension_name)

    await ctx.send(f"Loaded extension: {extension_name}.")

@bot.command(name='unload', hidden=True)
@commands.is_owner()
async def unload_extension(ctx: commands.Context, extension_name: str): 
    await bot.unload_extension(extension_name)

    await ctx.send(f"Unloaded extension: {extension_name}.")

@bot.command(name='reload', hidden=True)
@commands.is_owner()
async def reload_extension(ctx: commands.Context, extension_name: str=None):
    if (extension_name != None):
        await bot.reload_extension(extension_name)

        await ctx.send(f"Reloaded extension: {extension_name}.")
    else:
        for extension in EXTENSIONS:
            await bot.reload_extension(extension)
        
        await ctx.send(f"Reloaded all extensions: {EXTENSIONS}.")

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
            await interaction.followup.send(f"The command failed: {error.original}", ephemeral=True)
        else:
            await interaction.response.send_message(f"The command failed: {error}", ephemeral=True)
        # do NOT raise the error again here; this somehow results in the error being
        # sent here again (TOTHINK: but only once! Intriguing...)
    else:
        raise error
bot.tree.on_error = on_app_command_error

async def setup_hook():
    # note that extensions should be loaded before the slash commands
    # are synched. Here we ensure that by only allowing manual synching
    # once the bot finishes loading (i.e., `setup_hook()` has been called)
    bot.account_manager.connect_and_login()
    for extension in EXTENSIONS:
        await bot.load_extension(extension)
bot.setup_hook = setup_hook
bot.remove_command('help')

bot.run(DISCORD_TOKEN, log_handler=None)
