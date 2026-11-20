"use client";

import { Download, ImagePlus, LoaderCircle, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { type Clip, type Cover, fileUrl, fmtTime, makeCover } from "@/lib/api";

/**
 * Cover image for a clip: pick a frame, set the text, preview the profile-grid crop, download.
 * Instagram's grid keeps only the centre 3:4 of a Reel, so the guide marks that band.
 */
export function CoverEditor({ clip, onChange }: { clip: Clip; onChange?: (c: Cover) => void }) {
  const length = Math.max(0.2, clip.end - clip.start);
  const [cover, setCover] = useState<Cover | null>(clip.meta?.cover ?? null);
  const [at, setAt] = useState<number>(clip.meta?.cover?.at ?? Math.round(length * 0.35 * 10) / 10);
  const [text, setText] = useState<string>(clip.meta?.cover?.text ?? clip.hook_text ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0); // bust the browser cache after a redo

  async function save(body: { at?: number; text?: string }) {
    setBusy(true);
    setErr(null);
    try {
      const c = await makeCover(clip.id, body);
      setCover(c);
      setNonce((n) => n + 1);
      onChange?.(c);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // Older clips rendered before covers existed: make one on first open.
  useEffect(() => {
    if (!clip.meta?.cover && clip.file_path) save({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip.id]);

  const dirty = !!cover && (Math.abs(at - cover.at) > 0.05 || text !== cover.text);
  const src = cover ? `${fileUrl(cover.path)}?v=${nonce}` : null;

  return (
    <div>
      <div className="relative aspect-[9/16] w-full overflow-hidden rounded-board border border-line bg-felt-high">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="Cover preview" className={`size-full object-cover transition-opacity ${busy ? "opacity-50" : ""}`} />
        ) : (
          <div className="grid size-full place-items-center text-[13px] font-semibold uppercase tracking-[0.14em] text-ink-mute">
            {busy ? "Making cover" : "No cover yet"}
          </div>
        )}
        {/* the 3:4 band the profile grid shows */}
        <div className="pointer-events-none absolute inset-x-0 top-[12.5%] h-3/4 border-y border-dashed border-ink/70" aria-hidden />
        {busy && <LoaderCircle className="absolute right-2 top-2 size-4 animate-spin text-ink" />}
      </div>
      <p className="mt-1.5 text-[13px] leading-snug text-ink-mute">Dashed lines: what your profile grid shows.</p>

      <label className="mt-3 block">
        <span className="mb-1 flex items-baseline justify-between text-[13px] font-semibold uppercase tracking-[0.1em] text-ink-mute">
          Frame <span className="tabular tracking-normal">{fmtTime(at)}</span>
        </span>
        <input
          type="range"
          min={0}
          max={Math.max(0, length - 0.2)}
          step={0.1}
          value={at}
          onChange={(e) => setAt(Number(e.target.value))}
          className="w-full accent-[var(--ink)]"
          aria-label="Cover frame time"
        />
      </label>
      <label className="mt-2 block">
        <span className="mb-1 flex items-baseline justify-between text-[13px] font-semibold uppercase tracking-[0.1em] text-ink-mute">
          Cover text <span className="tabular tracking-normal">{text.length}/80</span>
        </span>
        <input value={text} maxLength={80} onChange={(e) => setText(e.target.value)} className="field min-h-0 py-2 text-[15px]" placeholder="Leave empty for no text" />
      </label>

      <div className="mt-3 grid grid-cols-2 gap-1.5">
        <button onClick={() => save({ at, text })} disabled={busy || !dirty} className="btn btn-line btn-sm">
          {cover ? <RefreshCw className="size-3.5" strokeWidth={1.75} /> : <ImagePlus className="size-3.5" strokeWidth={1.75} />}
          {cover ? "Update" : "Make"}
        </button>
        {src ? (
          <a href={fileUrl(cover!.path)} download className="btn btn-primary btn-sm">
            <Download className="size-3.5" strokeWidth={2} /> Cover
          </a>
        ) : (
          <button disabled className="btn btn-primary btn-sm">
            <Download className="size-3.5" strokeWidth={2} /> Cover
          </button>
        )}
      </div>
      {err && <p className="mt-2 text-[14px] text-fail">{err}</p>}
    </div>
  );
}
