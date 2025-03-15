import asyncio
import csv
import io
import math
from dataclasses import dataclass
from typing import Optional, cast

import arrow
import discord
from discord.ext import commands, tasks
from parse import parse

from lib.auth import can_run_bot_commands
from lib.components.channel_dropdown import ChannelDropdown


@dataclass
class TriviaQuestion:
    Question: str
    Answer: str
    Reward: str

    def get_embed(self):
        return discord.Embed(
            title="Trivia Question",
            description=self.Question,
            color=discord.Color.green(),
        )


class TriviaSession:
    def __init__(
        self, bot: commands.Bot, questions: list[TriviaQuestion], time_between: int
    ):
        """
        A trivia session that contains a list of questions and the time between questions.

        :param bot: The bot instance.
        :param questions: A list of trivia questions.
        :param time_between: The time between questions in minutes.
        """

        self.active = False
        self.channel: Optional[discord.TextChannel] = None
        self.bot = bot
        self.questions = questions
        self.current_question = 0
        self.time_between = time_between

    def get_current_question(self):
        return self.questions[self.current_question]

    def has_next_question(self):
        return self.current_question + 1 < len(self.questions)

    def next_question(self):
        self.current_question += 1

    def is_answer_correct(self, answer: str):
        return answer.lower() == self.get_current_question().Answer.lower()

    async def lock_channel(self):
        assert self.channel is not None

        await self.channel.set_permissions(
            self.channel.guild.default_role, send_messages=False
        )

    async def unlock_channel(self):
        assert self.channel is not None

        await self.channel.set_permissions(
            self.channel.guild.default_role, send_messages=True
        )

    async def post_question(self):
        if not self.channel:
            return

        question = self.get_current_question()

        embed = question.get_embed()

        await self.unlock_channel()
        await self.channel.send(embed=embed)

    async def start(self, channel: discord.TextChannel):
        self.channel = channel
        self.active = True

        await self.post_question()

    async def wait_and_continue_task(self):
        if not self.active:
            return

        await self.lock_channel()
        await asyncio.sleep(self.time_between * 60)

        if not self.active:
            return

        self.next_question()

        await self.post_question()

    def wait_and_continue(self):
        asyncio.create_task(self.wait_and_continue_task())


class Trivia(commands.Cog):
    bot: commands.Bot

    active: bool
    channel_id: Optional[int]

    session: Optional[TriviaSession]
    initial_message: Optional[discord.Message]

    def __init__(self, bot):
        self.bot = bot

        self.active = False
        self.channel_id = None

        self.session = None
        self.initial_message = None

    def load_trivia_csv(self, data: bytes):
        trivia = []

        reader = csv.DictReader(io.StringIO(data.decode("utf-8")))

        for row in reader:
            trivia.append(
                TriviaQuestion(
                    Question=row["Question"],
                    Answer=row["Answer"],
                    Reward=row["Reward"],
                )
            )

        return trivia

    @commands.command()
    @commands.check(can_run_bot_commands)
    async def trivia(self, ctx: commands.Context, *, time_between_questions: str):
        if self.active:
            await ctx.send("Trivia is already active!")
            return

        parts = parse("{:d}m", time_between_questions)

        if parts is None:
            await ctx.send("Invalid time format. Please use `Xm`.")
            return

        time_between = cast(int, parts[0])

        if len(ctx.message.attachments) == 0:
            await ctx.send("Please attach a trivia file!")
            return

        try:
            data = await ctx.message.attachments[0].read()
            self.session = TriviaSession(
                self.bot, self.load_trivia_csv(data), time_between
            )
        except Exception as e:
            await ctx.send(f"Error loading trivia: {e}")
            return

        assert ctx.guild is not None

        channel_select = ChannelDropdown(
            channels=ctx.guild.text_channels,
            callback=self.on_channel_select,
        )

        await ctx.send(
            f"""✅ **Trivia file loaded successfully.**
Please select a channel to start the trivia in.
            """,
            embeds=[
                discord.Embed(
                    title="CSV Stats",
                    description=f"{len(self.session.questions)} questions",
                ),
                discord.Embed(
                    title="Trivia Questions",
                    description="\n".join(
                        f"{i + 1}. {q.Question}"
                        for i, q in enumerate(self.session.questions)
                    ),
                ),
                discord.Embed(
                    title="Time Between Questions",
                    description=f"{time_between} minutes",
                ),
            ],
            view=channel_select,
        )

    async def on_channel_select(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        if not self.session:
            return

        self.channel_id = channel.id
        self.active = True
        self.initial_message = interaction.message

        await interaction.response.send_message(
            f"Starting trivia in {channel.mention}!",
        )

        await self.session.start(channel)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.active:
            return

        if not self.session:
            return

        if message.channel.id != self.channel_id:
            return

        if message.author.bot:
            return

        if self.session.is_answer_correct(message.content):
            await message.add_reaction("✅")
            await message.reply(
                f"Correct! You have won `{self.session.get_current_question().Reward}`!"
            )

            next_ts = round(
                arrow.utcnow().shift(minutes=self.session.time_between).timestamp()
            )

            await message.channel.send(
                f"\n⌛ **The next question will be available in <t:{next_ts}:R>**"
            )

            assert self.initial_message is not None

            await self.initial_message.reply(
                f"Winner of {self.session.get_current_question().Reward}: {message.author.mention}\n\n{message.jump_url}"
            )

            if self.session.has_next_question():
                self.session.wait_and_continue()
                return

            self.active = False
            self.session = None
            self.channel_id = None

            await self.initial_message.reply("Trivia session complete!")

            self.initial_message = None


async def setup(bot):
    await bot.add_cog(Trivia(bot))
