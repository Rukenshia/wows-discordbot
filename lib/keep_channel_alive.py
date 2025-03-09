import logging
import math
from datetime import datetime
from typing import List, Optional, cast

import discord
from discord.ext import commands, tasks

from lib.views.start_keep_alive import StartKeepChannelAliveView

logger = logging.getLogger(__name__)

DURATION: int = 60

reminders = [
    (
        DURATION / 2,
        "You are at risk of losing your reward of {reward}. Send a message to keep it alive",
    ),
    (DURATION, "You have lost your reward of {reward}. Please start a new one"),
]


class KeepChannelAlive(commands.Cog):
    bot: commands.Bot

    active: bool
    channel_id: Optional[int]
    reward: str
    last_message: Optional[datetime]
    started_at: Optional[datetime]
    last_reminder: Optional[int]

    status_message: Optional[discord.Message]

    def __init__(self, bot):
        self.bot = bot

        self.reset()

    def reset(self):
        self.active = False
        self.channel_id = None
        self.reward = ""
        self.last_message = None
        self.started_at = None
        self.keep_alive.stop()
        self.last_reminder = None
        self.status_message = None

    def progress(self):
        if not self.active:
            return ""

        if self.last_message is None:
            return ""

        elapsed = (datetime.now() - self.last_message).total_seconds()

        if elapsed > DURATION:
            return "Message train has ended"

        # display a box for every 10 seconds.
        num_squares = math.floor(DURATION / 10)

        squares = []
        for i in range(num_squares):
            # elapsed time
            if (i + 1) * 10 < elapsed:
                color = ":black_large_square:"

            # we still have more than 50% left
            elif DURATION - elapsed > DURATION / 2:
                color = ":green_square:"

            # we still have more than 25% left
            elif DURATION - elapsed > DURATION / 4:
                color = ":yellow_square:"

            # danger zone
            else:
                color = ":red_square:"

            squares.append(color)

        return " ".join(squares)

    async def update_status_message(self):
        if self.status_message is None:
            logger.warning("No status message")
            return

        if self.channel_id is None:
            logger.warning("No channel id")
            return

        if self.last_message is None:
            logger.warning("No started at")
            return

        channel = self.bot.get_channel(self.channel_id)

        if channel is None:
            logger.warning("Channel not found")
            return

        channel = cast(discord.TextChannel, channel)

        message = await channel.fetch_message(self.status_message.id)

        elapsed = (datetime.now() - self.last_message).total_seconds()

        await message.edit(
            content=f"**Active Reward**: {self.reward}\n\n{self.progress()}\n\n⌛ You have **{math.trunc(DURATION - elapsed)} seconds** to send a message to keep the reward alive"
        )

    @commands.command()
    async def cancel(self, ctx: commands.Context):
        if not self.active:
            await ctx.reply("Not active")
            return

        self.reset()

        await ctx.reply("Cancelled")

    async def on_start(
        self,
        interaction: discord.Interaction,
        target_channel: discord.TextChannel,
    ):
        await interaction.response.defer(ephemeral=True)

        if self.active:
            return

        self.active = True
        self.channel_id = target_channel.id
        self.reward = self.reward
        self.last_message = datetime.now()
        self.started_at = datetime.now()
        self.keep_alive.start()

        self.status_message = await target_channel.send(f"New message train trarting")

        await self.update_status_message()

    @commands.command()
    async def start(self, ctx: commands.Context, *reward: str):
        # ensure we're in a text channel
        if ctx.channel.type != discord.ChannelType.text:
            logging.warning(
                "Command start can only be used in a text channel, got %s and not %s",
                ctx.channel.type,
                discord.TextChannel.type,
            )
            return

        if self.active:
            await ctx.reply("Already active")
            return

        if not reward:
            await ctx.reply("Please provide a reward")
            return

        self.reward = " ".join(reward)

        # Show a dropdown to select a channel
        channels: List[discord.TextChannel] = [
            ch
            for ch in ctx.guild.text_channels
            if ch.permissions_for(ctx.guild.me).send_messages
        ]

        if not channels:
            await ctx.reply("No channels available to send messages to.")
            return

        view = StartKeepChannelAliveView(
            channels=channels,
            callback=self.on_start,
            timeout=180.0,
        )

        print(view.to_components())

        await ctx.reply("Select a target channel:", view=view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.active:
            return

        if message.channel.id != self.channel_id:
            return

        if message.author.bot:
            return

        logger.info("staying alive with new message")
        self.last_message = datetime.now()
        self.last_reminder = None
        await self.update_status_message()

    @tasks.loop(seconds=5)
    async def keep_alive(self):
        if not self.active:
            return

        if self.last_message is None:
            return

        if self.channel_id is None:
            return

        await self.update_status_message()

        elapsed = (datetime.now() - self.last_message).total_seconds()

        # send reminders
        relevant_reminder = None
        for reminder in reminders:
            if elapsed >= reminder[0] and (
                self.last_reminder is None or reminder[0] > self.last_reminder
            ):
                relevant_reminder = reminder

        if relevant_reminder is not None:
            logger.info(f"Sending reminder {relevant_reminder[1]} at {elapsed}")

            channel = cast(
                Optional[discord.TextChannel], self.bot.get_channel(self.channel_id)
            )
            assert channel is not None

            await channel.send(relevant_reminder[1].format(reward=self.reward))
            self.last_reminder = relevant_reminder[0]

        if (datetime.now() - self.last_message).total_seconds() > 60:
            self.reset()
            return


async def setup(bot: commands.Bot):
    logger.info("Adding KeepChannelAlive cog")
    await bot.add_cog(KeepChannelAlive(bot))
