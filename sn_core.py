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

@client.command()
async def help(ctx, cata=None):
    user = ctx.message.author
    if cata == None:
        song_embed = discord.Embed(
                  title = f"{user.name} | Help (All commands)",
                  description = f"`play`,`queue`,`stop`,`skip`",
                  color = discord.Color.from_rgb(182,224,222)
              )
        song_embed.set_footer(text='🔧 Help | To see how a command works, type: help <name of command>')
        await ctx.reply(embed=song_embed, mention_author = False)
        await ctx.message.add_reaction('🔧')
    
    elif cata == 'play':
        song_embed = discord.Embed(
                  title = f"{user.name} | Play",
                  description = f"**`Play`**\n\nSyntax: `s.play <query (Youtube URL or word search)>`\n\nPlays music, you can either insert a **Youtube** URL, or just type out your query, like this:\n\n`s.play Classical Music` | Plays the closest search for Classical Music",
                  color = discord.Color.from_rgb(182,224,222)
              )
        song_embed.set_footer(text='🔧 Help | Aliases : p')
        await ctx.reply(embed=song_embed, mention_author = False)
        await ctx.message.add_reaction('🔧')

    elif cata == 'queue':
        song_embed = discord.Embed(
                  title = f"{user.name} | Queue",
                  description = f"**`Play`**\n\nSyntax: `s.queue`\n\nShows music queue, if there is any in the first place",
                  color = discord.Color.from_rgb(182,224,222)
              )
        song_embed.set_footer(text='🔧 Help | Aliases : q')
        await ctx.reply(embed=song_embed, mention_author = False)
        await ctx.message.add_reaction('🔧')

    elif cata == 'stop':
        song_embed = discord.Embed(
                  title = f"{user.name} | Stop",
                  description = f"**`Play`**\n\nSyntax: `s.stop`\n\nStops all music reproduction",
                  color = discord.Color.from_rgb(182,224,222)
              )
        song_embed.set_footer(text='🔧 Help | Aliases : st')
        await ctx.reply(embed=song_embed, mention_author = False)
        await ctx.message.add_reaction('🔧')

    elif cata == 'skip':
        song_embed = discord.Embed(
                  title = f"{user.name} | Skip",
                  description = f"**`Play`**\n\nSyntax: `s.skip`\n\nSkips current song, it will then play the next song in the queue, if there is no other song, it will play nothing",
                  color = discord.Color.from_rgb(182,224,222)
              )
        song_embed.set_footer(text='🔧 Help | Aliases : s')
        await ctx.reply(embed=song_embed, mention_author = False)
        await ctx.message.add_reaction('🔧')

client.run(TOKEN)