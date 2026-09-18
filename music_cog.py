import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio
import re

QUEUE_PAGE_SIZE = 10
URL_REGEX = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
# Rough average time to resolve one song's playable audio format, used only
# to give a ballpark ETA for playlists - actual time varies with network
# conditions and per-video, so this is intentionally a loose estimate.
SECONDS_PER_SONG_ESTIMATE = 3
# How long to sit connected to a voice channel with nothing playing before
# auto-disconnecting. Adjust to taste.
IDLE_TIMEOUT_SECONDS = 600 # 10 min


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
        self.current_lookup_task = None
        self.idle_timer_task = None
        self.last_text_channel = None
        self.loop_current = False
        self.now_playing = None

        self.vc = None

    def _cancel_idle_timer(self):
        if self.idle_timer_task and not self.idle_timer_task.done():
            self.idle_timer_task.cancel()
        self.idle_timer_task = None

    def _start_idle_timer(self):
        self._cancel_idle_timer()
        self.idle_timer_task = asyncio.ensure_future(self._idle_disconnect_after_delay())

    async def _idle_disconnect_after_delay(self):
        try:
            await asyncio.sleep(IDLE_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            return

        # Re-check state before actually leaving - something may have
        # started playing again in the time it took the timer to fire.
        if self.is_playing or self.vc is None or not self.vc.is_connected():
            return

        await self.vc.disconnect()
        self.vc = None

        if self.last_text_channel is not None:
            song_embed = discord.Embed(
                title="Left voice channel",
                description=f"No music was played for {IDLE_TIMEOUT_SECONDS // 60} minutes, so I disconnected",
                color=discord.Color.from_rgb(222, 46, 44)
            )
            song_embed.set_footer(text='👋 Auto-disconnect')
            try:
                await self.last_text_channel.send(embed=song_embed)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # If everyone else leaves the channel the bot is sitting in, leave
        # too rather than sitting there talking to nobody.
        if member.bot:
            return
        if self.vc is None or not self.vc.is_connected():
            return

        channel = self.vc.channel
        if before.channel == channel and after.channel != channel:
            remaining_humans = [m for m in channel.members if not m.bot]
            if remaining_humans:
                return

            self._cancel_idle_timer()
            self.music_queue = []
            self.is_playing = False
            self.now_playing = None

            if self.vc.is_playing() or self.vc.is_paused():
                self.vc.stop()

            await self.vc.disconnect()
            self.vc = None
            self._cancel_idle_timer()

            if self.last_text_channel is not None:
                song_embed = discord.Embed(
                    title="Left voice channel",
                    description="Everyone left the voice channel, so I disconnected and cleared the queue",
                    color=discord.Color.from_rgb(222, 46, 44)
                )
                song_embed.set_footer(text='👋 Auto-disconnect')
                try:
                    await self.last_text_channel.send(embed=song_embed)
                except discord.HTTPException:
                    pass

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
        urls = re.findall(URL_REGEX, item)

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

    def _format_eta(self, seconds, force_minutes=False):
        # Once the estimate goes past double digits (100+ seconds), showing
        # it in minutes is easier to read than a large raw seconds count.
        if force_minutes or seconds >= 100:
            minutes = seconds / 60
            if minutes == int(minutes):
                return f"{int(minutes)}m"
            return f"{minutes:.1f}m"
        return f"{seconds}s"

    async def count_playlist_songs(self, item):
        """Quickly counts songs in a playlist URL without resolving each
        one's audio format, so we can show an ETA before doing the slow work.
        Returns None if `item` isn't a playlist link (or the count can't be
        determined) - the caller should just skip showing an ETA in that case.
        """
        if not re.findall(URL_REGEX, item):
            return None

        loop = self.bot.loop
        flat_options = {'extract_flat': True, 'quiet': True, 'ignoreerrors': True}

        def extract_flat():
            try:
                with YoutubeDL(flat_options) as ydl:
                    return ydl.extract_info(item, download=False, process=False)
            except Exception:
                return None

        info = await loop.run_in_executor(None, extract_flat)
        if not info or 'entries' not in info:
            return None

        try:
            return len(list(info['entries']))
        except Exception:
            return None

    def play_next(self):
        # If looping is on and we still know what was just playing, replay
        # it instead of advancing the queue. skip()/stop() clear
        # now_playing first specifically so this branch gets bypassed then.
        if self.loop_current and self.now_playing is not None:
            self.is_playing = True
            self._cancel_idle_timer()
            song = self.now_playing
            self.vc.play(discord.FFmpegPCMAudio(song['source'], **self._ffmpeg_options_for(song)), after=lambda e: self.play_next())
            return

        if len(self.music_queue) > 0:
            self.is_playing = True
            self._cancel_idle_timer()

            song = self.music_queue[0][0]
            m_url = song['source']

            self.music_queue.pop(0)
            self.now_playing = song

            self.vc.play(discord.FFmpegPCMAudio(m_url, **self._ffmpeg_options_for(song)), after=lambda e: self.play_next())
        else:
            self.is_playing = False
            self.now_playing = None
            self._start_idle_timer()

    async def play_music(self):
        if len(self.music_queue) > 0:
            self.is_playing = True
            self._cancel_idle_timer()

            song = self.music_queue[0][0]
            m_url = song['source']

            if self.vc is None or not self.vc.is_connected():
                self.vc = await self.music_queue[0][1].connect()

            self.music_queue.pop(0)
            self.now_playing = song
            self.vc.play(discord.FFmpegPCMAudio(m_url, **self._ffmpeg_options_for(song)), after=lambda e: self.play_next())
        else:
            self.is_playing = False
            self._start_idle_timer()

    @commands.command(aliases=['p'])
    async def play(self, ctx, *args):
        query = " ".join(args)
        user = ctx.message.author

        if not query.strip():
            song_embed = discord.Embed(
                title=f"{user.name}, there was a problem",
                description="No song was mentioned\nSyntax: `s.play <song name or YouTube link>`",
                color=discord.Color.from_rgb(232, 14, 51)
            )
            song_embed.set_footer(text='🎵 Play')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('🎵')
            return

        # Remembered so the idle/auto-disconnect timer has somewhere to
        # announce itself later, without needing an active command context.
        self.last_text_channel = ctx.channel

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
            return

        # Looking a song (or worse, a playlist) up can take a while, so show
        # a placeholder right away and edit it in place once we know the
        # outcome, rather than leaving the user staring at nothing.
        wait_embed = discord.Embed(
            title=f"{user.name} | Please wait",
            description="Downloading song.. this might take a moment...",
            color=discord.Color.from_rgb(255, 205, 74)
        )
        wait_embed.set_footer(text='⏳ Play')
        status_message = await ctx.reply(embed=wait_embed, mention_author=False)
        await ctx.message.add_reaction('⏳')

        async def _do_lookup():
            # For playlist links, do a fast flat-mode count first so we can
            # show a real ETA before the slower full resolution of every
            # track starts.
            playlist_count = await self.count_playlist_songs(query)
            if playlist_count and playlist_count > 1:
                low = playlist_count * SECONDS_PER_SONG_ESTIMATE
                high = playlist_count * SECONDS_PER_SONG_ESTIMATE * 2

                # Format both ends with the same unit - once the high estimate
                # crosses into triple digits, minutes reads better than a mix
                # of "45s-140s".
                use_minutes = high >= 100
                low_str = self._format_eta(low, force_minutes=use_minutes)
                high_str = self._format_eta(high, force_minutes=use_minutes)

                wait_embed.description = (
                    f"Downloading {playlist_count} songs from the playlist.. "
                    f"this might take a moment...\nEstimated time: ~{low_str}-{high_str}"
                )
                try:
                    await status_message.edit(embed=wait_embed)
                except discord.HTTPException:
                    pass

            return await self.search_yt(query)

        self.current_lookup_task = asyncio.ensure_future(_do_lookup())
        try:
            songs = await self.current_lookup_task
        except asyncio.CancelledError:
            # s.stop cancelled the lookup while it was still running. The
            # background yt-dlp thread can't be forcibly killed, but we just
            # drop its result when it eventually finishes - nothing gets queued.
            cancelled_embed = discord.Embed(
                title=f"{user.name} | Lookup cancelled",
                description="Song lookup was stopped before it finished",
                color=discord.Color.from_rgb(222, 46, 44)
            )
            cancelled_embed.set_footer(text='🛑 Play')
            try:
                await status_message.edit(embed=cancelled_embed)
            except discord.HTTPException:
                pass
            try:
                await ctx.message.remove_reaction('⏳', self.bot.user)
            except discord.HTTPException:
                pass
            await ctx.message.add_reaction('🛑')
            return
        finally:
            self.current_lookup_task = None

        if songs is False:
            song_embed = discord.Embed(
                title=f"{user.name}, there was a problem",
                description="That song was either not found, or currently not available\nPlease try again",
                color=discord.Color.from_rgb(232, 14, 51)
            )
            song_embed.set_footer(text='🎵 Play')
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
        try:
            await status_message.edit(embed=song_embed)
        except discord.HTTPException:
            # Original message got deleted or is otherwise unreachable -
            # send a fresh one instead so the result isn't lost.
            await ctx.send(embed=song_embed)

        try:
            await ctx.message.remove_reaction('⏳', self.bot.user)
        except discord.HTTPException:
            pass
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
            footer = '📃 Queued'
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

        cancelled_lookup = False
        if self.current_lookup_task and not self.current_lookup_task.done():
            self.current_lookup_task.cancel()
            cancelled_lookup = True

        stopped_playback = bool(self.vc and self.vc.is_playing())
        if stopped_playback:
            self.music_queue = []
            self.now_playing = None
            self.vc.stop()

        if stopped_playback and cancelled_lookup:
            description = "Stopped playback, cleared the queue, and cancelled the song lookup in progress"
        elif stopped_playback:
            description = "Music has been stopped and queue has been cleared"
        elif cancelled_lookup:
            description = "Cancelled the song/playlist lookup in progress"
        else:
            description = None

        if description is not None:
            song_embed = discord.Embed(
                title=f"{user.name} | Stopped",
                description=description,
                color=discord.Color.from_rgb(222, 46, 44)
            )
            song_embed.set_footer(text='🛑 Stop')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('🛑')
        else:
            song_embed = discord.Embed(
                title=f"{user.name}, no music is playing",
                description="There is no music playing",
                color=discord.Color.from_rgb(232, 14, 51)
            )
            song_embed.set_footer(text='🛑 Stoped')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('🛑')

    @commands.command(aliases=['dc', 'leave'])
    async def disconnect(self, ctx):
        user = ctx.message.author
        if self.vc and self.vc.is_connected():
            # Clear the queue and flip is_playing off first, so the
            # after-callback triggered by vc.stop() (play_next) sees an
            # empty queue and doesn't try to start another song.
            self.music_queue = []
            self.is_playing = False
            self.now_playing = None

            if self.vc.is_playing():
                self.vc.stop()

            await self.vc.disconnect()
            self.vc = None
            self._cancel_idle_timer()

            song_embed = discord.Embed(
                title=f"{user.name} | Disconnected",
                description="Left the voice channel and cleared the queue",
                color=discord.Color.from_rgb(222, 46, 44)
            )
            song_embed.set_footer(text='👋 Disconnect')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('👋')
        else:
            song_embed = discord.Embed(
                title=f"{user.name}, not connected",
                description="I'm not currently in a voice channel",
                color=discord.Color.from_rgb(232, 14, 51)
            )
            song_embed.set_footer(text='👋 Disconnected')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('👋')

    @commands.command(aliases=['pa'])
    async def pause(self, ctx):
        user = ctx.message.author
        if self.vc and self.vc.is_playing():
            self.vc.pause()
            song_embed = discord.Embed(
                title=f"{user.name} | Paused",
                description="Playback has been paused",
                color=discord.Color.from_rgb(255, 205, 74)
            )
            song_embed.set_footer(text='⏸️ Pause')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('⏸️')
        else:
            song_embed = discord.Embed(
                title=f"{user.name}, nothing to pause",
                description="There is no music currently playing",
                color=discord.Color.from_rgb(232, 14, 51)
            )
            song_embed.set_footer(text='⏸️ Paused')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('⏸️')

    @commands.command(aliases=['r', 'unpause'])
    async def resume(self, ctx):
        user = ctx.message.author
        if self.vc and self.vc.is_paused():
            self.vc.resume()
            song_embed = discord.Embed(
                title=f"{user.name} | Resumed",
                description="Playback has been resumed",
                color=discord.Color.from_rgb(13, 217, 199)
            )
            song_embed.set_footer(text='▶️ Resume')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('▶️')
        else:
            song_embed = discord.Embed(
                title=f"{user.name}, nothing to resume",
                description="Playback is not currently paused",
                color=discord.Color.from_rgb(232, 14, 51)
            )
            song_embed.set_footer(text='▶️ Resumed')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('▶️')

    @commands.command(aliases=['lp'])
    async def loop(self, ctx):
        user = ctx.message.author
        self.loop_current = not self.loop_current

        if self.loop_current:
            description = "Looping the current song is now **on**"
            if self.now_playing:
                description += f"\nRepeating **`{self.now_playing['title']}`**"
            color = discord.Color.from_rgb(13, 217, 199)
        else:
            description = "Looping the current song is now **off**"
            color = discord.Color.from_rgb(232, 14, 51)

        song_embed = discord.Embed(
            title=f"{user.name} | Loop",
            description=description,
            color=color
        )
        song_embed.set_footer(text='🔁 Looping')
        await ctx.reply(embed=song_embed, mention_author=False)
        await ctx.message.add_reaction('🔁')

    @commands.command(aliases=['s'])
    async def skip(self, ctx):
        user = ctx.message.author
        if self.vc is not None:
            self.now_playing = None
            self.vc.stop()
            await self.play_music()
            song_embed = discord.Embed(
                title=f"{user.name} | Skipped",
                description="Skipped current song (even if there are not any other songs in queue)",
                color=discord.Color.from_rgb(213, 234, 247)
            )
            song_embed.set_footer(text='⏩ Skiped')
            await ctx.reply(embed=song_embed, mention_author=False)
            await ctx.message.add_reaction('⏩')