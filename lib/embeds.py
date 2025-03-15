"""
Collection of reusable embeds for the bot.
"""

import discord


def error(description: str, title: str = "Error") -> discord.Embed:
    """Create an error embed."""
    return discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=discord.Color.red(),
    )


def success(description: str, title: str = "Success") -> discord.Embed:
    """Create a success embed."""
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=discord.Color.green(),
    )


def info(description: str, title: str = "Info") -> discord.Embed:
    """Create an info embed."""
    return discord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=discord.Color.blue(),
    )
