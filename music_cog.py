import discord
from discord.ext import commands
from youtube_dl import YoutubeDL
import nacl
from discord.utils import get
from youtube_dl import *
from discord import channel
from discord import voice_client
from discord.voice_client import VoiceClient
import ffmpeg

class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.is_playing = False

        self.music_queue = []
        self.YDL_OPTIONS = {'format' : 'bestaudio', 'noplaylist' : 'True'}
        self.FFMPEG_OPTIONS = {'before_options' : '-reconnect 1 -reconnect_streamed 1', 'options' : '-vn'}

        self.vc = ""

    def search_yt(self, item):
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info("ytsearch:%s" % item, download=False)['entries'][0]
            except Exception:
                return False
        return {'source' : info['formats'][0]['url'], 'title': info['title']}

    def play_next(self):
        if len(self.music_queue) > 0:
            self.is_playing = True

            m_url = self.music_queue[0][0]['source']

            self.music_queue.pop[0]

            self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next())
        else:
            self.is_playing = False

    async def play_music(self):
        if len(self.music_queue) > 0:
            self.is_playing = True

            m_url = self.music_queue[0][0]['source']

            if self.vc == "" or not self.vc.is_connected():
                self.vc = await self.music_queue[0][1].connect()
            else:
                pass

            print(self.music_queue)
            self.music_queue.pop(0)

            self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after = lambda e: self.play_next())
        else:
            self.is_playing = False

    @commands.command(aliases=['p'])
    async def play(self, ctx, *args):
        query = " ".join(args)

        voice_channel = ctx.message.author.voice.channel
        if voice_channel is None:
            await ctx.send('You need to connect to a voice channel to play music')
        else:
            song = self.search_yt(query)
            if type(song) == type(True):
                await ctx.send('Could not download song. Incorrect format, try another keyword')
            else:
                await ctx.send('Song added to the queue')
                self.music_queue.append([song, voice_channel])

                if self.is_playing == False:
                    await self.play_music()

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        retval = ""

        for i in range(0, len(self.music_queue)):
            retval += self.music_queue[i][0]['title'] + "\n"

        print(retval)
        if retval != "":
            await ctx.send(retval)
        else:
            await ctx.send('No music in queue')

    @commands.command(aliases=['s'])
    async def skip(self, ctx):
        if self.vc != "":
            self.vc.stop()
            await self.play_music()
            await ctx.send('Skipped!')
