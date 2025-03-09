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


bot = WowsDiscordBot(command_prefix="!", intents=intents)
bot.run(os.environ["DISCORD_BOT_TOKEN"])
