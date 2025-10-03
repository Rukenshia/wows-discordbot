import logging
import math
import random
from datetime import datetime
from typing import cast

import discord
from discord.ext import commands, tasks

from lib.embeds import error
from lib.views.start_keep_alive import StartKeepChannelAliveView

logger = logging.getLogger(__name__)

DURATION: int = 60

reminders = [
    (
        DURATION / 2,
        "You are at risk of losing your reward of {reward}. Send a message to keep it alive",
    ),
]

MemberId = int
MessageCount = int


class KeepChannelAlive(commands.Cog):
    bot: commands.Bot

    active: bool
    channel_id: int | None
    reward: str
    last_message: datetime | None
    started_at: datetime | None
    last_reminder: int | None
    participants: dict[MemberId, MessageCount]

    status_message: discord.Message | None

    def get_duration_text(self):
        """Return a formatted string of how long the challenge has been running"""
        if not self.started_at:
            return "unknown duration"

        duration = datetime.now() - self.started_at
        minutes, seconds = divmod(duration.total_seconds(), 60)

        if minutes > 0:
            return f"{int(minutes)} minutes and {int(seconds)} seconds"
        else:
            return f"{int(seconds)} seconds"

    def __init__(self, bot: commands.Bot):
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
        self.participants = {}

    def get_color_based_on_time(self, remaining_time: float):
        """Return a color based on the remaining time"""
        if remaining_time > DURATION / 2:
            # More than 50% time remaining - green
            return discord.Color.green()
        elif remaining_time > DURATION / 4:
            # More than 25% time remaining - yellow
            return discord.Color.gold()
        else:
            # Less than 25% time remaining - red
            return discord.Color.red()

    def progress(self):
        if not self.active:
            return ""

        if self.last_message is None:
            return ""

        elapsed = (datetime.now() - self.last_message).total_seconds()

        if elapsed > DURATION:
            return "Message train has ended"

        # Create a visual progress bar with 20 segments
        bar_length = 20
        filled_length = int(bar_length * elapsed / DURATION)

        # Determine the color based on remaining time
        if DURATION - elapsed > DURATION / 2:
            # More than 50% time remaining - green
            bar_color = "🟩"
            empty_color = "⬜"
        elif DURATION - elapsed > DURATION / 4:
            # More than 25% time remaining - yellow
            bar_color = "🟨"
            empty_color = "⬜"
        else:
            # Less than 25% time remaining - red
            bar_color = "🟥"
            empty_color = "⬜"

        progress_bar = bar_color * filled_length + empty_color * (
            bar_length - filled_length
        )

        return progress_bar

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
        remaining_time = max(0, DURATION - elapsed)

        # Create a list of participants with their message counts
        participant_list: list[str] = []
        for user_id, count in self.participants.items():
            participant_list.append(f"<@{user_id}> - {count} messages")

        # Create an embed for the status message
        embed = discord.Embed(
            title="🚂 Message Train Challenge",
            description="Keep the conversation going to win the reward!",
            color=self.get_color_based_on_time(remaining_time),
        )

        _ = embed.add_field(name="🎁 Reward", value=self.reward, inline=False)

        _ = embed.add_field(
            name="⏱️ Time Remaining",
            value=f"{math.trunc(remaining_time)} seconds",
            inline=True,
        )

        _ = embed.add_field(
            name="👥 Participants",
            value=f"{len(self.participants.keys())} active",
            inline=True,
        )

        _ = embed.add_field(name="Progress", value=self.progress(), inline=False)

        # Add a footer with instructions
        _ = embed.set_footer(text="Send a message to keep the train alive!")

        _ = await message.edit(content=None, embed=embed)

    @commands.command()
    async def cancel(self, ctx: commands.Context[commands.Bot]):
        if not self.active:
            _ = await ctx.reply(
                embed=error("No active message train challenge to cancel.")
            )
            return

        self.reset()

        cancel_embed = discord.Embed(
            title="🛑 Challenge Cancelled",
            description="The message train challenge has been cancelled.",
            color=discord.Color.orange(),
        )
        _ = await ctx.reply(embed=cancel_embed)

    async def on_start(
        self,
        _interaction: discord.Interaction,
        target_channel: discord.TextChannel,
        reward: str,
    ):
        if self.active:
            return

        self.active = True
        self.channel_id = target_channel.id
        self.reward = reward
        self.last_message = datetime.now()
        self.started_at = datetime.now()
        _ = self.keep_alive.start()

        # Create an initial embed
        initial_embed = discord.Embed(
            title="🚂 Message Train Challenge Starting",
            description="A new message train challenge has begun!",
            color=discord.Color.blue(),
        )
        _ = initial_embed.add_field(name="🎁 Reward", value=self.reward, inline=False)
        _ = initial_embed.add_field(
            name="⏱️ Duration",
            value=f"{DURATION} seconds between messages",
            inline=False,
        )
        _ = initial_embed.add_field(
            name="📝 Instructions",
            value="Keep sending messages to keep the train alive. If no one sends a message for 60 seconds, the train stops and a random participant wins!",
            inline=False,
        )
        _ = initial_embed.set_footer(text="Good luck!")

        self.status_message = await target_channel.send(embed=initial_embed)

        await self.update_status_message()

    @commands.command()
    async def start_keep_alive(
        self, ctx: commands.Context[commands.Bot], *rewards: str
    ):
        # ensure we're in a text channel
        if ctx.channel.type != discord.ChannelType.text:
            logging.warning(
                "Command start can only be used in a text channel, got %s and not %s",
                ctx.channel.type,
                discord.TextChannel.type,
            )
            return

        if self.active:
            already_active_embed = discord.Embed(
                title="⚠️ Already Active",
                description="A message train challenge is already running.",
                color=discord.Color.orange(),
            )
            _ = await ctx.reply(embed=already_active_embed)
            return

        if not rewards:
            _ = await ctx.reply(
                embed=error(
                    "Please provide a reward for the message train challenge.",
                    title="Missing Reward",
                ).add_field(
                    name="Usage", value="!start [reward description]", inline=False
                )
            )
            return

        reward = " ".join(rewards)

        # Show a dropdown to select a channel
        channels: list[discord.TextChannel] = [
            ch
            for ch in (ctx.guild.text_channels if ctx.guild else [])
            if ctx.guild and ch.permissions_for(ctx.guild.me).send_messages
        ]

        if not channels:
            _ = await ctx.reply(
                embed=error(
                    "No channels available to send messages to.",
                    title="No Channels Available",
                )
            )
            return

        view = StartKeepChannelAliveView(
            reward=reward,
            channels=channels,
            callback=self.on_start,
            timeout=180.0,
        )

        start_embed = discord.Embed(
            title="🚂 New Message Train Challenge",
            description="Start a new message train challenge where participants must keep sending messages to keep the train alive!",
            color=discord.Color.blue(),
        )

        _ = start_embed.add_field(name="🎁 Reward", value=reward, inline=False)

        _ = start_embed.add_field(
            name="⏱️ Duration",
            value=f"{DURATION} seconds between messages",
            inline=False,
        )

        _ = start_embed.add_field(
            name="📝 Instructions",
            value="Select a channel below to start the challenge",
            inline=False,
        )

        _ = await ctx.reply(embed=start_embed, view=view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.active:
            return

        if message.channel.id != self.channel_id:
            return

        if message.author.bot:
            return

        if message.author.id not in self.participants:
            self.participants[message.author.id] = 0
        self.participants[message.author.id] += 1

        logger.info("staying alive with new message")

        # restart so that we stay on the 5-second interval
        self.keep_alive.restart()
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
                discord.TextChannel | None, self.bot.get_channel(self.channel_id)
            )
            assert channel is not None

            reminder_embed = discord.Embed(
                title="⚠️ Message Train Alert",
                description=relevant_reminder[1].format(reward=self.reward),
                color=discord.Color.orange(),
            )

            _ = reminder_embed.add_field(
                name="⏱️ Time Remaining",
                value=f"{math.trunc(DURATION - elapsed)} seconds",
                inline=True,
            )

            _ = reminder_embed.add_field(
                name="Progress", value=self.progress(), inline=False
            )

            _ = await channel.send(embed=reminder_embed)
            self.last_reminder = int(relevant_reminder[0])

        if (datetime.now() - self.last_message).total_seconds() > 60:
            await self.distribute_reward()

            self.reset()
            return

    async def distribute_reward(self):
        if self.channel_id is None:
            return

        channel = cast(
            discord.TextChannel | None, self.bot.get_channel(self.channel_id)
        )
        assert channel is not None

        participants = list(self.participants.keys())

        if not participants:
            no_winner_embed = discord.Embed(
                title="😔 Challenge Ended",
                description="No participants joined the message train challenge.",
                color=discord.Color.light_grey(),
            )
            _ = await channel.send(embed=no_winner_embed)
            return

        winner_id = random.choice(participants)
        try:
            winner = await self.bot.fetch_user(winner_id)
        except discord.NotFound:
            _ = await channel.send(embed=error("No winner could be determined"))
            return

        # Create a list of all participants
        participant_list: list[str] = []
        for user_id, count in self.participants.items():
            if user_id == winner_id:
                participant_list.append(f"👑 <@{user_id}> - {count} messages")
            else:
                participant_list.append(f"<@{user_id}> - {count} messages")

        participants_text = "\n".join(participant_list)

        # Create winner announcement embed
        winner_embed = discord.Embed(
            title="🎉 Message Train Challenge Complete!",
            description=f"The message train has ended after {self.get_duration_text()}",
            color=discord.Color.gold(),
        )

        _ = winner_embed.add_field(
            name="🏆 Winner", value=f"<@{winner.id}>", inline=False
        )

        _ = winner_embed.add_field(name="🎁 Reward", value=self.reward, inline=False)

        _ = winner_embed.add_field(
            name="👥 Participants", value=participants_text, inline=False
        )

        # Add winner's avatar if available
        if winner.avatar:
            _ = winner_embed.set_thumbnail(url=winner.avatar.url)

        _ = await channel.send(embed=winner_embed)


async def setup(bot: commands.Bot):
    logger.info("Adding KeepChannelAlive cog")
    await bot.add_cog(KeepChannelAlive(bot))
