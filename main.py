import logging
import os

import discord
import sentry_sdk
from aiohttp import web
from discord.ext import commands

sentry_sdk.init(
    dsn="https://f4940923ec4141ec45110af22b275bf5@o283081.ingest.us.sentry.io/4509056289538048",
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

sentry_sdk.capture_message(message=f"Bot started", level="info")

import config

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True

# Get the token from environment variables
TOKEN = config.get_token()


class WowsDiscordBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self) -> None:
        # pass configuration
        await self.load_extension("lib.keep_channel_alive")
        await self.load_extension("lib.trivia")

    # handle command errors
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        await ctx.reply(f"An error occurred: {error}")


bot = WowsDiscordBot(command_prefix="!", intents=intents)  # help_command=None)
bot.run(TOKEN)
