import json

import discord
from discord.ext import commands, tasks
import docker

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docker.models.containers import Container

with open("config/config.json", "r") as config_json:
    config = json.load(config_json)

DISC_AUTH = config["disc_auth"]
SERVER_ID = config["server_id"]
OWNER_ID = config["owner_id"]

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

client = docker.from_env()


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
        formatted = f"\u001b[1;{log_level_colors['level']}m{level}\u001b[0;0m"
        message = message.replace(level, formatted)
    return message


@bot.event
async def on_ready():
    send_logs.start()


@tasks.loop(seconds=60)
async def send_logs():
    guild = bot.get_guild(SERVER_ID)
    if guild is None:
        raise Exception("server not found")

    containers = client.containers.list(
        filters={"label": f"com.docker.compose.project=dgg-services"}
    )

    for container in containers:
        if TYPE_CHECKING:
            container = Container()

        container_name = container.name.lower()
        channel = discord.utils.get(guild.text_channels, name=container_name)
        if channel is None:
            raise Exception(f"channel wasn't found for container {container_name}")

        logs = container.logs(since=send_logs._last_iteration).decode("utf-8")
        if logs:
            chunks = logs.split("\n")
            message = ""
            for chunk in chunks:
                if len(message) + len(chunk) > 1950:
                    await channel.send(convert_to_ansi(message))
                    message = ""
                message += chunk.strip()
            await channel.send(convert_to_ansi(message))


if __name__ == "__main__":
    bot.run(DISC_AUTH)
