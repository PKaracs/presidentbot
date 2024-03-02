import os
import certifi
import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
import aiohttp
import asyncio
from dotenv import load_dotenv
import datetime

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)

audio_queues = {}
user_limits = {}


CHAR_LIMIT_PER_DAY = 100


async def check_user_limit(user_id, num_chars):
    current_date = datetime.date.today()
    if user_id in user_limits:
        user_date, char_count = user_limits[user_id]
        if user_date == current_date and char_count + num_chars > CHAR_LIMIT_PER_DAY:
            return False
        elif user_date != current_date:
            user_limits[user_id] = (current_date, num_chars)
        else:
            user_limits[user_id] = (current_date, char_count + num_chars)
    else:
        user_limits[user_id] = (current_date, num_chars)
    return True


async def play_next(ctx):
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        return

    if ctx.guild.id in audio_queues and audio_queues[ctx.guild.id]:
        audio_path = audio_queues[ctx.guild.id].pop(0)
        source = FFmpegPCMAudio(audio_path)
        ctx.voice_client.play(
            source, after=lambda e: client.loop.create_task(play_next(ctx))
        )
    else:
        client.loop.create_task(schedule_leave_with_delay(ctx))


async def schedule_leave_with_delay(ctx):
    await asyncio.sleep(5)
    if not ctx.voice_client.is_playing() and (
        ctx.guild.id not in audio_queues or not audio_queues[ctx.guild.id]
    ):
        await leave(ctx)


@client.event
async def on_ready():
    print("Bot is ready.")
    print("---------------")


async def fetch_tts_audio(text, voice_id):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.3, "similarity_boost": 0.7, "speed": 0.05},
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as response:
            if response.status == 200:

                file_path = "output.mp3"
                with open(file_path, "wb") as f:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                return file_path
            else:
                return None


@client.command()
async def speak(ctx, text, voice_id):
    if not ctx.guild or not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("You need to be in a voice channel to use this command.")
        return

    if not text or len(text) > CHAR_LIMIT_PER_DAY:
        await ctx.send(
            f"Please provide the text you want to say. (Limit: {CHAR_LIMIT_PER_DAY} characters per day)"
        )
        return

    # Check the user's character limit
    if not await check_user_limit(ctx.author.id, len(text)):
        await ctx.send(
            f"You have exceeded your daily limit of {CHAR_LIMIT_PER_DAY} characters."
        )
        return

    audio_path = await fetch_tts_audio(text, voice_id)

    if ctx.guild.id not in audio_queues:
        audio_queues[ctx.guild.id] = []

    audio_queues[ctx.guild.id].append(audio_path)

    channel = ctx.author.voice.channel
    if not ctx.voice_client:
        await channel.connect()

    if not ctx.voice_client.is_playing():
        await play_next(ctx)


@client.command()
async def trump(ctx, *, text: str = None):
    await speak(ctx, text, "9PpxB8vSbbFcfr2LNrEM")


@client.command()
async def obama(ctx, *, text: str = None):
    await speak(ctx, text, "KXTX1lR3CzDpSafnpRGn")


@client.command()
async def biden(ctx, *, text: str = None):
    await speak(ctx, text, "h5TYJW3p1jx9CgJkN885")


@client.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        if ctx.guild.id in audio_queues:
            del audio_queues[ctx.guild.id]


client.run(DISCORD_BOT_TOKEN)
