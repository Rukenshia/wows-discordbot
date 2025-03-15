"""
Discord view for Start the 'Keep Alive' feature

- Allows selecting a target channel
- Allows to enter a reward
"""

from typing import Awaitable, Callable, Optional

import discord
from discord.ui import Button, Select, TextInput, View


class StartKeepChannelAliveView(View):
    def __init__(
        self,
        reward: str,
        channels: list[discord.TextChannel],
        callback: Callable[
            [discord.Interaction, discord.TextChannel, str],
            Awaitable[None],
        ],
        placeholder: str = "Select a channel for the message train",
        timeout: float = 180.0,
    ):
        super().__init__(timeout=timeout)

        self.reward = reward

        # Create the dropdown menu
        self.dropdown = Select(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=channel.name,
                    value=str(channel.id),
                    description=f"#{channel.name}",
                )
                for channel in channels[:25]  # Discord limits to 25 options
            ],
        )
        self.dropdown.callback = self.on_select
        self.add_item(self.dropdown)

        self.confirm = Button(
            label="Start",
            style=discord.ButtonStyle.green,
        )
        self.confirm.callback = self.on_confirm
        self.add_item(self.confirm)

        self.selected_channel: Optional[discord.TextChannel] = None
        self.external_callback = callback

    async def on_select(self, interaction: discord.Interaction):
        """Called when a user selects an option."""
        channel_id = int(self.dropdown.values[0])

        assert interaction.guild is not None

        channel = interaction.guild.get_channel(channel_id)
        assert isinstance(channel, discord.TextChannel)

        self.selected_channel = channel

        await interaction.response.defer(ephemeral=True)

    async def on_confirm(self, interaction: discord.Interaction):
        """Called when a user clicks the confirm button."""

        if self.selected_channel is None:
            await interaction.response.send_message(
                "Please select a channel first",
                ephemeral=True,
            )
            return

        assert interaction.message is not None

        # disable the button
        self.confirm.disabled = True

        await interaction.response.edit_message(view=self)

        await self.external_callback(interaction, self.selected_channel, self.reward)

        self.stop()
