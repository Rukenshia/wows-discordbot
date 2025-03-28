# Use Python 3.13 slim as the base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY . .

# Install dependencies using uv with --system flag
RUN uv pip install --system --no-cache-dir python-dotenv
RUN uv pip install --system --no-cache-dir -e .

ARG SENTRY_RELEASE
ENV SENTRY_RELEASE=$SENTRY_RELEASE

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "main.py"]
