import discord
from discord.ext import commands

from music_cog import music_cog

TOKEN = 'token_here'

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix = 's.', intents=intents)
client.remove_command('help')

# add_cog() is a coroutine in modern discord.py (2.0+), so it must be awaited.
# setup_hook() is the recommended place to do this kind of async setup before login.
@client.event
async def setup_hook():
    await client.add_cog(music_cog(client))

@client.event
async def on_ready():
    print('Sonus Ready')
    await client.change_presence(
        activity=discord.Activity(type=discord.ActivityType.streaming, name='Music', url='https://www.twitch.tv/tehllamah')
    )

@client.command()
async def help(ctx, cata=None):
    user = ctx.message.author

    if cata == None:
        song_embed = discord.Embed(
            title = f"{user.name} | Help (All commands)",
            description = f"`play`,`queue`,`stop`,`pause`,`resume`,`loop`,`skip`,`disconnect`",
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

    elif cata == 'pause':
        song_embed = discord.Embed(
            title = f"{user.name} | Pause",
            description = f"**`Pause`**\n\nSyntax: `s.pause`\n\nPauses the currently playing song, keeping it in place so it can be resumed later",
            color = discord.Color.from_rgb(182,224,222)
        )
        song_embed.set_footer(text='🔧 Help | Aliases : pa')
        await ctx.reply(embed=song_embed, mention_author = False)
        await ctx.message.add_reaction('🔧')

    elif cata == 'resume':
        song_embed = discord.Embed(
            title = f"{user.name} | Resume",
            description = f"**`Resume`**\n\nSyntax: `s.resume`\n\nResumes a paused song from where it left off",
            color = discord.Color.from_rgb(182,224,222)
        )
        song_embed.set_footer(text='🔧 Help | Aliases : r, unpause')
        await ctx.reply(embed=song_embed, mention_author = False)
        await ctx.message.add_reaction('🔧')

    elif cata == 'loop':
        song_embed = discord.Embed(
            title = f"{user.name} | Loop",
            description = f"**`Loop`**\n\nSyntax: `s.loop`\n\nToggles looping the currently playing song on or off. While looping is on, the same song repeats instead of moving on to the next one in the queue ( `s.skip` still moves past it )",
            color = discord.Color.from_rgb(182,224,222)
        )
        song_embed.set_footer(text='🔧 Help | Aliases : lp')
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

    elif cata == 'disconnect':
        song_embed = discord.Embed(
            title = f"{user.name} | Disconnect",
            description = f"**`Disconnect`**\n\nSyntax: `s.disconnect`\n\nStops playback, clears the queue, and leaves the voice channel",
            color = discord.Color.from_rgb(182,224,222)
        )
        song_embed.set_footer(text='🔧 Help | Aliases : dc, leave')
        await ctx.reply(embed=song_embed, mention_author = False)
        await ctx.message.add_reaction('🔧')

client.run(TOKEN)