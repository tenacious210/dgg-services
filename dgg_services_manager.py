import json
import logging
from datetime import datetime
from time import sleep

import discord
from discord import app_commands, Interaction
from discord.ext import commands, tasks
import docker
from docker.errors import APIError
from docker.models.containers import Container


logging.basicConfig(level=logging.INFO)
logging.getLogger("discord").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

with open("config/config.json", "r") as config_json:
    config = json.load(config_json)

DISC_AUTH = config["disc_auth"]
SERVER_ID = config["server_id"]
OWNER_ID = config["owner_id"]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

client = docker.from_env()
logger.info("Successfully connected to Docker.")


def get_containers() -> list[Container]:
    try:
        filters = {"label": f"com.docker.compose.project=dgg-services"}
        containers = client.containers.list(filters=filters)
    except APIError as e:
        logger.error(f"Error listing containers: {e}")
        return
    return containers


def get_status() -> str:
    filters = {"label": f"com.docker.compose.project=dgg-services"}
    message = ""
    for container in client.api.containers(filters=filters):
        message += f"{container['Names'][0][1:]}: {container['Status']}\n"
    return f"Container status report:\n{message}"


def get_container_from_channel(channel_name: str) -> Container:
    containers = get_containers()
    container_names = [container.name.lower() for container in containers]
    if channel_name not in container_names:
        return None
    return client.containers.get(channel_name)


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
    container_colors = {
        "dgg-services-manager": 31,
        "dgg-relay": 33,
        "dggpt": 34,
        "dgg-emotes-bot": 35,
        "dgg-logger": 36,
    }
    message = f"```ansi\n{message}\n```"
    for level in log_level_colors:
        formatted = f"\u001b[1;{log_level_colors[level]}m{level}\u001b[0;0m"
        message = message.replace(level, formatted)
    for container in container_colors:
        formatted = f"\u001b[1;{container_colors[container]}m{container}\u001b[0;0m"
        message = message.replace(container, formatted)
    return message


@bot.event
async def on_ready():
    global last_execution
    logger.info(f"Bot is ready. Logged in as {bot.user.name}")
    last_execution = datetime.now()
    log_status.start()
    sleep(5)
    send_logs.start()
    await bot.tree.sync()


@tasks.loop(seconds=65)
async def send_logs():
    global last_execution
    logger.debug("Starting log collection task")
    server = bot.get_guild(SERVER_ID)

    containers = get_containers()
    logger.debug(f"Found {len(containers)} containers to monitor")

    for container in containers:
        container_name = container.name.lower()
        logger.debug(f"Processing logs for container: {container_name}")

        channel = discord.utils.get(server.text_channels, name=container_name)
        if channel is None:
            logger.warning(f"Channel not found for container {container_name}")
            continue

        try:
            logs = container.logs(since=last_execution).decode("utf-8")
        except APIError as e:
            logger.error(f"Error fetching logs for {container_name}: {e}")
            continue

        if logs:
            if container_name != "dgg-services-manager":
                logger.info(f"Sending logs for {container_name}")
            chunks = logs.split("\n")
            message = ""
            for chunk in chunks:
                if len(message) + len(chunk) > 1950:
                    await channel.send(convert_to_ansi(message))
                    message = ""
                message += chunk.strip() + "\n"
            if message:
                await channel.send(convert_to_ansi(message))
        else:
            logger.debug(f"No new logs for {container_name}")
    last_execution = datetime.now()
    logger.debug("Log collection task completed")


@tasks.loop(hours=6)
async def log_status():
    logger.info(get_status())


@bot.command(name="status")
async def status_command(ctx: Interaction):
    await ctx.response.send_message(convert_to_ansi(get_status()))


@bot.command(name="restart")
async def restart_container(ctx: Interaction):
    """Restarts the container of the channel this command is used in"""
    if container := get_container_from_channel(ctx.channel.name):
        container.restart()
        await ctx.response.send_message(f"Container {ctx.channel.name} restarted")
    else:
        await ctx.response.send_message(f"No containers named {ctx.channel.name}")


@bot.command(name="start")
async def start_container(ctx: Interaction):
    """Starts the container of the channel this command is used in"""
    if container := get_container_from_channel(ctx.channel.name):
        container.start()
        await ctx.response.send_message(f"Container {ctx.channel.name} started")
    else:
        await ctx.response.send_message(f"No containers named {ctx.channel.name}")


@bot.command(name="stop")
async def restart_container(ctx: Interaction):
    """Stops the container of the channel this command is used in"""
    if container := get_container_from_channel(ctx.channel.name):
        container.stop()
        await ctx.response.send_message(f"Container {ctx.channel.name} stopped")
    else:
        await ctx.response.send_message(f"No containers named {ctx.channel.name}")


if __name__ == "__main__":
    logger.info("Starting bot")
    bot.run(DISC_AUTH, log_handler=None)
