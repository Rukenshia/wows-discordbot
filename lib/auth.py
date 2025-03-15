"""
Utility functions that makes sure users messaging the discord bot
are authorized to do so.
"""

import logging

logger = logging.getLogger(__name__)


async def can_run_bot_commands(ctx):
    """Check if the user can run bot commands."""

    logger.info(
        f"Checking if {ctx.author} can run bot commands, roles: {ctx.author.roles}"
    )

    if [role for role in ctx.author.roles if role.name == "BotAdmin"]:
        return True

    return False
