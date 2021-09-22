import discord
from discord.ext import commands
# from youtube_dl import YoutubeDL
# import nacl
# from discord import FFmpegPCMAudio
# from discord.utils import get
# from youtube_dl import *
from music_cog import music_cog

TOKEN = 'ODkwMjk3ODkxNDU1OTIyMjU2.YUtwhg.T5EDgiCwRrNeGGqAYS-0b8ICDa8'

client = commands.Bot(command_prefix = 's.')
client.remove_command('help')

client.add_cog(music_cog(client))

@client.event
async def on_ready():
    print('Sonus Ready')
    await client.change_presence(activity=discord.Streaming(name='Music', url='https://www.twitch.tv/tehllamah'))

client.run(TOKEN)