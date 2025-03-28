import os
from dotenv import load_dotenv

# Try to load from .env file if it exists (local development)
load_dotenv()


# Function to get required environment variables
def get_token():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required")
    return token
