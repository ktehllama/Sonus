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
import re

class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.is_playing = False

        self.music_queue = []
        self.YDL_OPTIONS = {'format' : 'bestaudio', 'noplaylist' : 'True'}
        self.FFMPEG_OPTIONS = {'before_options' : '-reconnect 1 -reconnect_streamed 1', 'options' : '-vn'}

        self.vc = ""

    def search_yt(self, item):
        global info
        urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', item)
        if urls:
            with YoutubeDL(self.YDL_OPTIONS) as ydl:
                info = ydl.extract_info(item, download=False)
                url2 = info['formats'][0]['url']
                discord.FFmpegOpusAudio.from_probe(url2, **self.FFMPEG_OPTIONS)
            return {'source' : info['formats'][0]['url'], 'title': info['title']}
        else:
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

            self.music_queue.pop(0)

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

            self.music_queue.pop(0)
            self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after = lambda e: self.play_next())
        else:
            self.is_playing = False

    @commands.command(aliases=['p'])
    async def play(self, ctx, *args):
        query = " ".join(args)
        user = ctx.message.author

        vc_ch_mem = ctx.message.author.voice
        if vc_ch_mem is None:
            song_embed = discord.Embed(
                  title = f"{user.name}, there was a problem",
                  description = f"To play music, you need to first connect to a voice channel",
                  color = discord.Color.from_rgb(232,14,51)
              )
            song_embed.set_footer(text='🎵 Play')
            await ctx.reply(embed=song_embed, mention_author = False)
            await ctx.message.add_reaction('🎵')
        else:
            song = self.search_yt(query)
            if type(song) == type(True):
                song_embed = discord.Embed(
                  title = f"{user.name}, there was a problem",
                  description = f"That song was either not found, or currently not available\nPlease try again",
                  color = discord.Color.from_rgb(232,14,51)
                )
                song_embed.set_footer(text='🎵 Play')
                await ctx.reply(embed=song_embed, mention_author = False)
                await ctx.message.add_reaction('🎵')
            else:
                voice_channel = ctx.message.author.voice.channel
                self.music_queue.append([song, voice_channel])

                if self.is_playing == False:
                    await self.play_music()

                if len(self.music_queue) == 0:
                    song_embed = discord.Embed(
                        title = f"{user.name} | Playing song",
                        description = f"Playing **`{info['title']}`**",
                        color = discord.Color.from_rgb(13,217,199)
                    )
                    song_embed.set_footer(text='🎵 Play')
                    await ctx.reply(embed=song_embed, mention_author = False)
                    await ctx.message.add_reaction('🎵')
                else:
                    song_embed = discord.Embed(
                        title = f"{user.name} | Added to queue",
                        description = f"Added **`{info['title']}`** to queue",
                        color = discord.Color.from_rgb(109,167,250)
                    )
                    song_embed.set_footer(text='🎵 Play')
                    await ctx.reply(embed=song_embed, mention_author = False)
                    await ctx.message.add_reaction('🎵')

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        user = ctx.message.author
        retval = ""

        for i in range(0, len(self.music_queue)):
            if i != len(self.music_queue):
                retval += "**`" + self.music_queue[i][0]['title'] + "`**\n—\n"

        if retval != "":
            song_embed = discord.Embed(
                        title = f"{user.name} | Queue",
                        description = f"*`{i+1}` songs in queue*\n\n—\n{retval}",
                        color = discord.Color.from_rgb(109,167,250)
            )
            song_embed.set_footer(text='📃 Queue')
            await ctx.reply(embed=song_embed, mention_author = False)
            await ctx.message.add_reaction('📃')
        else:
            song_embed = discord.Embed(
                  title = f"{user.name}, queue is empty",
                  description = f"There is no music queued up",
                  color = discord.Color.from_rgb(232,14,51)
            )
            song_embed.set_footer(text='📃 Queue')
            await ctx.reply(embed=song_embed, mention_author = False)
            await ctx.message.add_reaction('📃')

    @commands.command(aliases=['st'])
    async def stop(self, ctx):
        user = ctx.message.author
        if self.vc and self.vc.is_playing():
            song_embed = discord.Embed(
                  title = f"{user.name} | Music stopped",
                  description = f"Music has been stopped",
                  color = discord.Color.from_rgb(222,46,44)
            )
            song_embed.set_footer(text='🛑 Stop')
            await ctx.reply(embed=song_embed, mention_author = False)
            await ctx.message.add_reaction('🛑')
            self.vc.stop()
        else:
            song_embed = discord.Embed(
                  title = f"{user.name}, no music is playing",
                  description = f"There is no music playing",
                  color = discord.Color.from_rgb(232,14,51)
            )
            song_embed.set_footer(text='🛑 Stop')
            await ctx.reply(embed=song_embed, mention_author = False)
            await ctx.message.add_reaction('🛑')

    @commands.command(aliases=['s'])
    async def skip(self, ctx):
        user = ctx.message.author
        if self.vc != "":
            self.vc.stop()
            await self.play_music()
            song_embed = discord.Embed(
                  title = f"{user.name} | Skipped",
                  description = f"Skipped current song (even if there are not any other songs in queue)",
                  color = discord.Color.from_rgb(213,234,247)
            )
            song_embed.set_footer(text='⏩ Skip')
            await ctx.reply(embed=song_embed, mention_author = False)
            await ctx.message.add_reaction('⏩')
