# Sonus
## _A Pretty Average Discord Music Bot_

Sonus, a simple but effective music bot, complete with a skip, stop and a modern queue system — now with playlist support.

## Installation
Sonus requires a [Python](https://www.python.org/downloads/) version 3.10+

Make a Discord bot in the [Discord Developer Portal](https://discord.com/developers/docs/intro) and get its token, and in `sn_core.py`, change the `TOKEN` constant to your bot's corresponding token.

You'll also need `ffmpeg` installed and available on your system PATH (not just the `ffmpeg-python`/`ffmpeg` pip packages, which are just wrappers around the real binary):
```
# Debian/Ubuntu
sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Windows (with winget)
winget install Gyan.FFmpeg

# Windows (with Chocolatey)
choco install ffmpeg
```
On Windows, if you install manually instead (downloading a build from [ffmpeg.org](https://ffmpeg.org/download.html)), make sure you add the `bin` folder from the extracted archive to your system `PATH`, then open a new terminal and confirm it worked with `ffmpeg -version`.

Then install the Python dependencies:
```
pip install -r requirements.txt
```

> Note: This bot was originally written in 2021 and went unmaintained for a while, as YouTube, discord.py, and Discord's own voice protocol all moved on without it. It's no longer outdated - it's been fully patched up and confirmed working on modern discord.py (2.x+) and yt-dlp, with playlist support added on top. See **Changes** below for what was fixed. UR WELCOME ~ TR-ASH 2026

## Modules
Sonus currently uses these modules. (Installed via Pip)
- [discord.py](https://discordpy.readthedocs.io/) — Discord API wrapper (2.x+)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — actively maintained fork of the now-unmaintained `youtube-dl`, used for song search/extraction
- [PyNaCl](https://pynacl.readthedocs.io/) — required by discord.py for voice channel encryption
- [davey](https://pypi.org/project/davey/) — required by discord.py for Discord's DAVE end-to-end voice encryption protocol
- `ffmpeg` — system binary (not a Python package) used to stream audio into voice channels
- [re](https://docs.python.org/3/library/re.html) — standard library, used for URL detection

## Changes
This fork/version patches several issues that had built up since 2021:
- Fixed a startup crash from a missing `Intents` import
- Fixed the cog not loading silently on modern discord.py (`add_cog` needs to be awaited in 2.x+)
- Replaced the dead `youtube_dl` dependency with `yt-dlp`, since YouTube's extraction had broken
- Moved song lookup off the main event loop so the bot no longer freezes while searching
- Fixed a bug where `stop` would corrupt the queue, crashing the next `play`
- Fixed song lookups grabbing the wrong (often unplayable) stream URL instead of the actual selected audio format
- Added the `PyNaCl` and `davey` dependencies now required for Discord voice connections
- Added support for playlist links: `s.play <playlist URL>` now queues every track in the playlist instead of only the first (or crashing)

## History
Created near November, 2021, when many mainstream Discord music bots were taken offline, Sonus was created as a side project to understand why many music bots were going offline and how powerful this technology of streaming _free_, _24/7_ music on Discord Voice Channels really could be. The main objective though was to experiment with the FFmpeg, YoutubeDL and the Discord Voice Client libraries.

## License
MIT
_Free software, For real_