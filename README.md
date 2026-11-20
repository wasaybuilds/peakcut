# PeakCut

Paste a YouTube link → AI finds the best moments → get 9:16 clips with animated captions → post them to YouTube Shorts and Instagram Reels.

It runs on a normal laptop with no NVIDIA GPU, and every AI service it uses has a free tier.

## How it works

| Step | Tool | Cost |
|---|---|---|
| Download | yt-dlp (video, "most replayed" heatmap, stream chat replay) | free |
| Speech-to-text | Groq Whisper → SiliconFlow SenseVoice → local faster-whisper | free |
| Moment signals | ffmpeg loudness + scene cuts, chat spikes, replay heatmap | free |
| Pick highlights, write titles | Z.ai GLM-Flash → SiliconFlow Qwen → Groq → OpenRouter → Gemini | free |
| Render | ffmpeg with Intel QuickSync, ASS karaoke captions | free |
| Publish | YouTube Data API v3, Instagram Graph API | free |

Each AI step tries the next provider when one fails or hits a rate limit, so a single dead key doesn't stop a job.

## Setup (Windows)

1. Run the setup script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
   ```
   It installs ffmpeg, uv and the Python and Node dependencies, and creates `.env`.
2. Add your keys to `.env`. You need at least one speech-to-text key and one LLM key:
   - **Groq:** https://console.groq.com/keys (transcription, and an LLM fallback)
   - **Z.ai:** https://z.ai/manage-apikey/apikey-list (GLM-4.5-Flash, free)
   - **Gemini:** https://aistudio.google.com/apikey (watch mode, and an LLM fallback)
3. Start the app:
   ```powershell
   powershell -File scripts\dev.ps1
   ```
   - The API runs at http://localhost:8000/health
   - The web app runs at http://localhost:3000

### Use it from your phone

Run `powershell -File scripts\dev.ps1 -Phone`. It prints an address like `http://192.168.x.x:3000`; open that on a phone connected to the same Wi-Fi. The phone uses the laptop's data, clips and accounts, because the web app forwards every API and video request to the backend on the laptop. The backend itself stays private to the laptop.

Anyone on the same Wi-Fi can open that address, so only use `-Phone` on a network you trust. Don't expose port 3000 to the internet. For access away from home, use a private network like Tailscale.

### Smart App Control (Windows 11)

Smart App Control is turned on for this PC. It blocks two kinds of files:
- unsigned `python.exe` launchers, which is what uv-managed Pythons use
- native DLLs from brand-new library releases, until those releases build up reputation

So the project works around it:
- The venv is built on the signed python.org Python 3.13.
- Tools run as modules, never through the `.exe` launchers uv creates (those are blocked). For example: `uv run python -m pytest` and `uv run python -m uvicorn app.main:app`.
- `backend/pyproject.toml` pins `pydantic-core` (and anything else that gets blocked) to versions Smart App Control accepts.
- OpenCV is not used at all. ffmpeg handles scene detection instead.

If an import fails with `An Application Control policy has blocked this file`, pin that package to an older release.

## Roadmap

- [x] **M0**: project setup, `/health`, free LLM fallback chain
- [x] **M1**: pipeline (URL → captioned 9:16 MP4s). Run it from the web app or with `uv run python -m app.cli <url>`
- [ ] **M2**: web app editor (trim, caption text and style, layout, re-render). Paste link, progress and clip grid are done.
- [~] **M3**: smarter highlights. Done: heatmap, loudness peaks, face cam split with auto-detect and a drag-to-fix box. Still to do: chat spikes, Gemini watch mode.
- [x] **M4**: publishing to YouTube and Instagram with AI captions and hashtags. Connect accounts at `/settings`.
- [ ] **M5**: batch jobs, campaign presets, AI voiceover intro, "safe start" violence check

## Content and monetization

Clips of other creators' videos usually get Content ID claims. They also don't qualify for the YouTube Partner Program under its reused-content rules. There are two ways to stay on the right side of this:
- **Join creator clipping campaigns.** Streamers on Whop and similar platforms pay per 1,000 views and give clippers permission.
- **Make the clips transformative.** Add commentary or a voiceover.

The tool always adds a source credit, and the `hook_text` and voiceover options are there to make clips transformative.

## Credits

Some code is adapted from [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) and [openshorts](https://github.com/mutonby/openshorts), both MIT-licensed. See [NOTICE](NOTICE).
