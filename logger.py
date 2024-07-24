import json
import logging

import discord
from discord.ext import commands, tasks
import docker
from docker.errors import APIError

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docker.models.containers import Container

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with open("config/config.json", "r") as config_json:
    config = json.load(config_json)

DISC_AUTH = config["disc_auth"]
SERVER_ID = config["server_id"]
OWNER_ID = config["owner_id"]

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

client = docker.from_env()
logger.info("Successfully connected to Docker.")


def convert_to_ansi(message: str):
    """takes in a whole Discord message, converts it to ansi, and color codes it"""
    # credit to: https://gist.github.com/kkrypt0nn/a02506f3712ff2d1c8ca7c9e0aed7c06
    log_level_colors = {
        "CRITICAL": 31,
        "ERROR": 31,
        "WARNING": 33,
        "INFO": 34,
        "DEBUG": 37,
    }
    message = f"```ansi\n{message}\n```"
    for level in log_level_colors:
        formatted = f"\u001b[1;{log_level_colors[level]}m{level}\u001b[0;0m"
        message = message.replace(level, formatted)
    return message


@bot.event
async def on_ready():
    logger.info(f"Bot is ready. Logged in as {bot.user.name}")
    send_logs.start()


@tasks.loop(seconds=60)
async def send_logs():
    logger.info("Starting log collection task")
    server = bot.get_guild(SERVER_ID)

    try:
        containers = client.containers.list(
            filters={"label": f"com.docker.compose.project=dgg-services"}
        )
        logger.info(f"Found {len(containers)} containers to monitor")
    except APIError as e:
        logger.error(f"Error listing containers: {e}")
        return

    for container in containers:
        if TYPE_CHECKING:
            container = Container()

        container_name = container.name.lower()
        logger.info(f"Processing logs for container: {container_name}")

        channel = discord.utils.get(server.text_channels, name=container_name)
        if channel is None:
            logger.warning(f"Channel not found for container {container_name}")
            continue

        try:
            logs = container.logs(since=send_logs._last_iteration).decode("utf-8")
        except APIError as e:
            logger.error(f"Error fetching logs for {container_name}: {e}")
            continue

        if logs:
            logger.info(f"Sending logs for {container_name}")
            chunks = logs.split("\n")
            message = ""
            for chunk in chunks:
                if len(message) + len(chunk) > 1950:
                    await channel.send(convert_to_ansi(message))
                    message = ""
                message += chunk.strip()
            if message:
                await channel.send(convert_to_ansi(message))
        else:
            logger.info(f"No new logs for {container_name}")
    logger.info("Log collection task completed")


if __name__ == "__main__":
    logger.info("Starting bot")
    bot.run(DISC_AUTH)