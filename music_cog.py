import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
import re

QUEUE_PAGE_SIZE = 10


class QueueView(discord.ui.View):
    """Adds Previous/Next buttons to a paginated queue embed.

    Only the person who ran the queue command can flip pages, and the
    buttons disable themselves after a couple minutes of inactivity so
    they don't sit there indefinitely as a dead interaction.
    """

    def __init__(self, author_id, pages):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.pages = pages
        self.current = 0
        self.message = None
        self._update_buttons()

    def _update_buttons(self):
        self.previous_button.disabled = self.current == 0
        self.next_button.disabled = self.current == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the person who ran the queue command can flip pages.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label='◀', style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label='▶', style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.is_playing = False

        self.music_queue = []
        self.YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': True, 'ignoreerrors': True}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1', 'options': '-vn'}

        self.vc = None

    def _ffmpeg_options_for(self, song):
        # googlevideo.com URLs often reject requests that don't carry the
        # same headers yt-dlp used when resolving the format, so we forward
        # them to ffmpeg via -headers rather than relying on FFMPEG_OPTIONS alone.
        options = dict(self.FFMPEG_OPTIONS)
        headers = song.get('headers') or {}
        if headers:
            header_str = ''.join(f'{k}: {v}\r\n' for k, v in headers.items())
            options['before_options'] = options['before_options'] + f' -headers "{header_str}"'
        return options

    def _song_from_info(self, info):
        if not info or 'url' not in info:
            return None
        headers = info.get('http_headers', {})
        return {'source': info['url'], 'title': info['title'], 'headers': headers}

    async def search_yt(self, item):
        """Returns a list of song dicts (one per playable track), or False on failure.

        A plain search or single video URL yields a list with one entry.
        A playlist URL yields one entry per track in the playlist.
        """
        loop = self.bot.loop
        urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', item)

        def extract():
            with YoutubeDL(self.YDL_OPTIONS) as ydl:
                if urls:
                    return ydl.extract_info(item, download=False)
                else:
                    result = ydl.extract_info("ytsearch:%s" % item, download=False)
                    entries = result.get('entries') if result else None
                    if not entries:
                        return None
                    return entries[0]

        try:
            # extract_info does blocking network I/O - run it off the event loop
            # so the whole bot doesn't freeze while a search/lookup is happening.
            info = await loop.run_in_executor(None, extract)
        except Exception:
            return False

        if not info:
            return False

        # Playlist URLs (as opposed to a single video, or a video URL that
        # merely carries a &list= param) come back as {'entries': [...]}
        # rather than a single video's info. Build a song dict for every
        # playable entry so the whole playlist can be queued.
        if 'entries' in info:
            songs = [self._song_from_info(e) for e in info['entries'] if e]
            songs = [s for s in songs if s]
            return songs if songs else False

        song = self._song_from_info(info)
        return [song] if song else False

    def play_next(self):
        if len(self.music_queue) > 0:
            self.is_playing = True

            song = self.music_queue[0][0]
            m_url = song['source']

            self.music_queue.pop(0)

            self.vc.play(discord.FFmpegPCMAudio(m_url, **self._ffmpeg_options_for(song)), after=lambda e: self.play_next())
        else:
            self.is_playing = False

    async def play_music(self):
        if len(self.music_queue) > 0:
            self.is_playing = True

            song = self.music_queue[0][0]
            m_url = song['source']

            if self.vc is None or not self.vc.is_connected():
                self.vc = await self.music_queue[0][1].connect()

            self.music_queue.pop(0)
            self.vc.play(discord.FFmpegPCMAudio(m_url, **self._ffmpeg_options_for(song)), after=lambda e: self.play_next())
        else:
            self.is_playing = False

    @commands.command(aliases=['p'])
    async def play(self, ctx, *args):
        query = " ".join(args)
        user = ctx.message.author

        vc_ch_mem = ctx.message.author.voice
        if vc_ch_mem is None:
            song_embed = discord.Embed(
                title=f"{user.name}, there was a problem",
                description="To play music, you need to first connect to a voice channel",
                color=discord.Color.from_rgb(232, 14, 51)
            )
            song_embed.set_footer(text='🎵 Play')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('🎵')
        else:
            songs = await self.search_yt(query)
            if songs is False:
                song_embed = discord.Embed(
                    title=f"{user.name}, there was a problem",
                    description="That song was either not found, or currently not available\nPlease try again",
                    color=discord.Color.from_rgb(232, 14, 51)
                )
                song_embed.set_footer(text='🎵 Play')
                await ctx.reply(embed=song_embed, mention_author=False)
                await ctx.message.add_reaction('🎵')
            else:
                voice_channel = ctx.message.author.voice.channel
                was_empty_and_idle = (len(self.music_queue) == 0 and not self.is_playing)

                for song in songs:
                    self.music_queue.append([song, voice_channel])

                if self.is_playing == False:
                    await self.play_music()

                if len(songs) == 1:
                    title = songs[0]['title']
                    if was_empty_and_idle:
                        song_embed = discord.Embed(
                            title=f"{user.name} | Playing song",
                            description=f"Playing **`{title}`**",
                            color=discord.Color.from_rgb(13, 217, 199)
                        )
                    else:
                        song_embed = discord.Embed(
                            title=f"{user.name} | Added to queue",
                            description=f"Added **`{title}`** to queue",
                            color=discord.Color.from_rgb(109, 167, 250)
                        )
                    song_embed.set_footer(text='🎵 Play')
                    await ctx.reply(embed=song_embed, mention_author=False)
                    await ctx.message.add_reaction('🎵')
                else:
                    if was_empty_and_idle:
                        description = f"Added **`{len(songs)}`** songs from the playlist to queue\nNow playing **`{songs[0]['title']}`**"
                    else:
                        description = f"Added **`{len(songs)}`** songs from the playlist to queue"
                    song_embed = discord.Embed(
                        title=f"{user.name} | Playlist added",
                        description=description,
                        color=discord.Color.from_rgb(109, 167, 250)
                    )
                    song_embed.set_footer(text='🎵 Play')
                    await ctx.reply(embed=song_embed, mention_author=False)
                    await ctx.message.add_reaction('🎵')

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        user = ctx.message.author

        if not self.music_queue:
            song_embed = discord.Embed(
                title=f"{user.name}, queue is empty",
                description="There is no music queued up",
                color=discord.Color.from_rgb(232, 14, 51)
            )
            song_embed.set_footer(text='📃 Queue')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('📃')
            return

        total = len(self.music_queue)
        total_pages = (total - 1) // QUEUE_PAGE_SIZE + 1
        pages = []

        for page_num in range(total_pages):
            start = page_num * QUEUE_PAGE_SIZE
            chunk = self.music_queue[start:start + QUEUE_PAGE_SIZE]

            retval = ""
            for i, entry in enumerate(chunk, start=start + 1):
                retval += f"**`{i}.`** {entry[0]['title']}\n—\n"

            song_embed = discord.Embed(
                title=f"{user.name} | Queue",
                description=f"*`{total}` songs in queue*\n\n—\n{retval}",
                color=discord.Color.from_rgb(109, 167, 250)
            )
            footer = '📃 Queue'
            if total_pages > 1:
                footer += f" | Page {page_num + 1}/{total_pages}"
            song_embed.set_footer(text=footer)
            pages.append(song_embed)

        if total_pages == 1:
            await ctx.reply(embed=pages[0], mention_author=False)
        else:
            view = QueueView(user.id, pages)
            message = await ctx.reply(embed=pages[0], view=view, mention_author=False)
            view.message = message

        await ctx.message.add_reaction('📃')

    @commands.command(aliases=['st'])
    async def stop(self, ctx):
        user = ctx.message.author
        if self.vc and self.vc.is_playing():
            song_embed = discord.Embed(
                title=f"{user.name} | Music stopped",
                description="Music has been stopped and queue has been cleared",
                color=discord.Color.from_rgb(222, 46, 44)
            )
            song_embed.set_footer(text='🛑 Stop')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('🛑')
            self.music_queue = []
            self.vc.stop()
        else:
            song_embed = discord.Embed(
                title=f"{user.name}, no music is playing",
                description="There is no music playing",
                color=discord.Color.from_rgb(232, 14, 51)
            )
            song_embed.set_footer(text='🛑 Stop')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('🛑')

    @commands.command(aliases=['s'])
    async def skip(self, ctx):
        user = ctx.message.author
        if self.vc is not None:
            self.vc.stop()
            await self.play_music()
            song_embed = discord.Embed(
                title=f"{user.name} | Skipped",
                description="Skipped current song (even if there are not any other songs in queue)",
                color=discord.Color.from_rgb(213, 234, 247)
            )
            song_embed.set_footer(text='⏩ Skip')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('⏩')