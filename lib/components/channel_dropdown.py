from typing import Awaitable, Callable, List, Optional

import discord
from discord.ui import Select, View


class ChannelDropdown(View):
    """A dropdown view that allows users to select a channel."""

    def __init__(
        self,
        channels: List[discord.TextChannel],
        placeholder: str = "Select a channel",
        callback: Optional[
            Callable[[discord.Interaction, discord.TextChannel], Awaitable[None]]
        ] = None,
        timeout: float = 180.0,
    ):
        super().__init__(timeout=timeout)

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

        self.selected_channel: Optional[discord.TextChannel] = None
        self.external_callback = callback

        # Set the callback for the dropdown
        self.dropdown.callback = self.on_select

        # Add the dropdown to the view
        self.add_item(self.dropdown)

    async def on_select(self, interaction: discord.Interaction):
        """Called when a user selects an option."""
        channel_id = int(self.dropdown.values[0])
        self.selected_channel = interaction.guild.get_channel(channel_id)

        await interaction.response.defer(ephemeral=True)

        if self.external_callback:
            await self.external_callback(interaction, self.selected_channel)
        else:
            await interaction.followup.send(
                f"Selected channel: {self.selected_channel.mention}", ephemeral=True
            )

        # Stop listening for interactions
        self.stop()
