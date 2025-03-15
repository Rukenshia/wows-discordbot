import logging
import os

import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True


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


bot = WowsDiscordBot(command_prefix="!", intents=intents, help_command=None)
bot.run(os.environ["DISCORD_BOT_TOKEN"])
