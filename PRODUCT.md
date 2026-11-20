# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Solo short-form clippers, starting with the author and then other clippers who clone the public repo and run it on their own laptops. They clip other creators' long GTA 6 streams and gameplay videos into vertical Shorts/Reels to grow accounts and earn from clipping campaigns. Typical session: paste a YouTube link (often a multi-hour stream), wait while it processes, review the clips, fix the ones that need it, post the good ones.

## Product Purpose

PeakCut turns a long YouTube video into ready-to-post 9:16 clips with animated captions, then posts them to YouTube Shorts and Instagram Reels. Success: a clipper gets several post-worthy clips from one link with no paid tools, and spends their time choosing and posting rather than editing.

## Positioning

Free and local: runs on an ordinary laptop with no NVIDIA GPU, using free AI tiers (Groq, Z.ai GLM, Gemini, OpenRouter) with automatic fallback. It finds moments from signals transcript-only clippers ignore: loudness spikes, YouTube's most-replayed heatmap, and stream structure. It handles 24-hour stream VODs by analyzing only the most-replayed stretch and downloading just the pieces each clip needs.

## Operating Context

- Runs locally: Python FastAPI backend on :8000, Next.js web app on :3000, ffmpeg with Intel QuickSync.
- Jobs take minutes (download, transcribe, find moments, render), so users watch progress and come back.
- Output per clip: 1080x1920 MP4 with word-by-word captions, a hook line, a "via @creator" credit, a score (0-100), title, reason, and AI-written post text.
- Layouts: Zoom, Face cam split (auto-detected webcam with a drag-to-fix box), Full frame, Fill.
- Posting goes through the official free YouTube Data API and Instagram API; accounts are connected on the Settings page.

## Capabilities and Constraints

- Both quick volume (skim scores, post many) and careful review (watch, adjust face cam, edit captions) are first-class; neither may slow the other.
- First-run must guide strangers: missing API keys, unconnected accounts, YouTube's bot check (cookies file), Smart App Control on Windows.
- YouTube uploads from unaudited API projects are locked private; the UI must not imply otherwise.
- Not built yet: caption/hook text editing and trimming in the clip editor, scheduling, chat-spike signals.

## Brand Commitments

Name: PeakCut. No logo or other brand assets exist yet.

## Evidence on Hand

Real clips rendered from real videos exist locally (not in the repo). No testimonials, user counts or metrics exist; none may be invented.

## Product Principles

1. Time to first good clip beats feature count.
2. Show the machine's reasoning (score, why it picked a moment, analyzed range) so clippers can trust or override it quickly.
3. Every failure explains what to do next in plain words.
4. Free and local is the promise; never nudge toward paid services.
5. Be honest about copyright and platform limits.
