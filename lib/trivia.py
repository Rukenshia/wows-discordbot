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
from lib.embeds import error, success


@dataclass
class TriviaQuestion:
    Question: str
    Answer: str
    Reward: str

    def get_embed(self):
        return discord.Embed(
            title="🎮 Trivia Challenge",
            description=self.Question,
            color=discord.Color.blue(),
        ).set_footer(text="Be the first to answer correctly!")


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
        self.next_question_message: Optional[discord.Message] = None

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

        # Send question number info along with the embed
        await self.channel.send(
            f"**Question {self.current_question + 1}/{len(self.questions)}**",
            embed=embed,
        )

    async def start(self, channel: discord.TextChannel):
        self.channel = channel
        self.active = True

        next_ts = round(arrow.utcnow().shift(minutes=self.time_between).timestamp())

        # Send a welcome message
        welcome_embed = discord.Embed(
            title="🎯 Trivia Session beginning soon",
            description=f"The first question will be available <t:{next_ts}:R>",
            color=discord.Color.gold(),
        )
        await self.channel.send(embed=welcome_embed)

        self.wait_and_continue()

    async def wait_and_continue_task(self):
        if not self.active:
            return

        assert self.channel is not None

        next_ts = round(arrow.utcnow().shift(minutes=self.time_between).timestamp())

        if self.current_question > 0:
            waiting_embed = discord.Embed(
                title="⏳ Next Question Coming Soon",
                description=f"The next question will be available <t:{next_ts}:R>",
                color=discord.Color.purple(),
            )

            self.next_question_message = await self.channel.send(embed=waiting_embed)

        await self.lock_channel()
        await asyncio.sleep(self.time_between * 60)

        if not self.active:
            return

        if self.next_question_message:
            await self.next_question_message.delete()
            self.next_question_message = None

        await self.post_question()

    def wait_and_continue(self):
        asyncio.create_task(self.wait_and_continue_task())


class Trivia(commands.Cog):
    bot: commands.Bot

    active: bool
    channel_id: Optional[int]

    session: Optional[TriviaSession]
    initial_message: Optional[discord.Message]
    next_question_message: Optional[discord.Message]
    winners_thread: Optional[discord.Thread]

    def __init__(self, bot):
        self.bot = bot

        self.active = False
        self.channel_id = None

        self.session = None
        self.initial_message = None
        self.next_question_message = None
        self.winners_thread = None

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
            await ctx.send(embed=error("Trivia is already active"))
            return

        parts = parse("{:d}m", time_between_questions)

        if parts is None:
            await ctx.send(
                embed=error(
                    "Invalid time format. Please use `Xm` (e.g. `5m` for 5 minutes).",
                    title="Invalid Format",
                )
            )
            return

        time_between = cast(int, parts[0])

        if len(ctx.message.attachments) == 0:
            await ctx.send(embed=error("Please attach a trivia CSV file!"))
            return

        try:
            data = await ctx.message.attachments[0].read()
            self.session = TriviaSession(
                self.bot, self.load_trivia_csv(data), time_between
            )
        except Exception as e:
            await ctx.send(
                embed=error(f"An error occurred while loading the trivia: {e}")
            )
            return

        assert ctx.guild is not None

        channel_select = ChannelDropdown(
            channels=ctx.guild.text_channels,
            callback=self.on_channel_select,
        )

        stats_embed = discord.Embed(
            title="📊 Trivia Stats",
            description=f"• **Questions:** {len(self.session.questions)}\n• **Time Between:** {time_between} minutes",
            color=discord.Color.blue(),
        )

        questions_preview = "\n".join(
            f"{i + 1}. {q.Question}"
            for i, q in enumerate(self.session.questions[:5])  # Show first 5 questions
        )
        if len(self.session.questions) > 5:
            questions_preview += f"\n... and {len(self.session.questions) - 5} more"

        questions_embed = discord.Embed(
            title="📝 Question Preview",
            description=questions_preview,
            color=discord.Color.gold(),
        )

        await ctx.send(
            embeds=[
                stats_embed,
                questions_embed,
                success(
                    "Please select a channel to start the trivia.",
                    title="Trivia CSV loaded",
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

        start_embed = discord.Embed(
            title="🚀 Trivia Starting",
            description=f"Trivia session is starting in {channel.mention}!",
            color=discord.Color.green(),
        )
        message = await interaction.response.send_message(embed=start_embed)

        assert interaction.channel is not None
        assert message.message_id is not None

        # retrieve message to create thread
        message = await interaction.channel.fetch_message(message.message_id)

        self.winners_thread = await message.create_thread(
            name="Trivia Winners",
            auto_archive_duration=1440,  # 24 hours
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

            current_question = self.session.get_current_question()

            winner_embed = discord.Embed(
                title="🎉 Correct Answer!",
                description=f"Congratulations {message.author.mention}!",
                color=discord.Color.green(),
            )
            winner_embed.add_field(
                name="Prize", value=f"**{current_question.Reward}**", inline=False
            )

            await message.reply(embed=winner_embed)

            assert self.winners_thread is not None

            admin_winner_embed = discord.Embed(
                title="🏆 Winner Notification",
                description=f"**Prize:** {current_question.Reward}\n**Winner:** {message.author.mention}",
                color=discord.Color.gold(),
            )
            admin_winner_embed.add_field(
                name="Question", value=current_question.Question, inline=False
            )
            admin_winner_embed.add_field(
                name="Answer", value=current_question.Answer, inline=False
            )
            admin_winner_embed.add_field(
                name="Link",
                value=f"[Jump to message]({message.jump_url})",
                inline=False,
            )

            await self.winners_thread.send(embed=admin_winner_embed)

            if self.session.has_next_question():
                self.session.next_question()
                self.session.wait_and_continue()
                return

            complete_embed = discord.Embed(
                title="🎊 Trivia Session Complete",
                description="All questions have been answered! Thanks for playing!",
                color=discord.Color.green(),
            )

            await message.channel.send(embed=complete_embed)

            # Send completion message to the thread
            assert self.winners_thread is not None
            await self.winners_thread.send(embed=complete_embed)

            # Also notify in the original channel
            assert self.initial_message is not None
            await self.initial_message.reply(embed=complete_embed)

            self.active = False
            self.session = None
            self.channel_id = None

            self.initial_message = None
            self.winners_thread = None


async def setup(bot):
    await bot.add_cog(Trivia(bot))
