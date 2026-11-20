"use client";

import { Crosshair, ScanFace, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { type Box, fileUrl, type Job, LAYOUTS, rerenderJob } from "@/lib/api";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

type Rerender = Parameters<typeof rerenderJob>[1];

function useRerender(job: Job, onQueued: () => void) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function go(body: Rerender) {
    setBusy(true);
    setErr(null);
    try {
      await rerenderJob(job.id, body);
      onQueued();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return { busy, err, go };
}

/** Segmented layout control for the clips toolbar. Switching re-renders every clip. */
export function LayoutSwitch({ job, disabled, onQueued }: { job: Job; disabled?: boolean; onQueued: () => void }) {
  const current = job.options?.layout ?? "zoom_fill";
  const { busy, err, go } = useRerender(job, onQueued);
  return (
    <div className="flex flex-col gap-1">
      <div role="radiogroup" aria-label="Layout (re-renders every clip)" className="grid grid-cols-2 rounded-board border border-line-strong p-0.5 sm:flex">
        {LAYOUTS.map((l) => {
          const on = l.id === current;
          return (
            <button
              key={l.id}
              role="radio"
              aria-checked={on}
              title={`${l.hint}. Re-renders every clip.`}
              disabled={disabled || busy || on}
              onClick={() => go({ layout: l.id })}
              className={`h-8 rounded-board px-3 text-[13px] font-bold uppercase tracking-[0.1em] transition-colors disabled:cursor-default ${
                on ? "bg-ink text-felt" : "text-ink-soft hover:text-ink disabled:text-ink-mute"
              }`}
            >
              {l.label}
            </button>
          );
        })}
      </div>
      {err && <p className="text-[14px] text-fail">{err}</p>}
    </div>
  );
}

/** Disclosure panel: drag/resize the face cam box over a frame, then re-render. */
export function FacecamEditor({ job, onClose, onQueued }: { job: Job; onClose: () => void; onQueued: () => void }) {
  const detected = job.options?.facecam ?? null;
  const frame = job.options?.facecam_frame;
  const [box, setBox] = useState<Box | null>(detected);
  const { busy, err, go } = useRerender(job, onQueued);

  useEffect(() => setBox(detected), [detected?.x, detected?.y, detected?.w, detected?.h]); // eslint-disable-line react-hooks/exhaustive-deps

  const changed = !!box && JSON.stringify(box) !== JSON.stringify(detected);

  return (
    <section id="facecam-editor" className="mt-4 rounded-board border border-line bg-felt-raised p-4 sm:p-5" aria-labelledby="facecam-h">
      <div className="flex items-start justify-between gap-4">
        <h3 id="facecam-h" className="text-[18px] font-bold uppercase tracking-[0.08em]">
          Adjust face cam
        </h3>
        <button onClick={onClose} aria-label="Close face cam editor" className="btn btn-line btn-sm px-2">
          <X className="size-4" strokeWidth={2} />
        </button>
      </div>
      <div className="mt-4 grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-start">
        {frame ? (
          <BoxEditor src={fileUrl(frame)} box={box ?? { x: 0.02, y: 0.55, w: 0.22, h: 0.3 }} onChange={setBox} />
        ) : (
          <p className="text-[15px] text-ink-soft">The face cam is found while rendering. Its position shows up here when that finishes.</p>
        )}
        {frame && (
          <div>
            <p className="text-[16px] leading-snug text-ink-soft">
              {detected
                ? "This box becomes the top panel. Drag it onto the webcam, or resize it from the corner. Arrow keys work too."
                : "No webcam was found automatically. Drag the box onto it to use the face cam layout."}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button disabled={busy || !changed} onClick={() => box && go({ layout: "facecam_split", facecam: box })} className="btn btn-primary btn-sm">
                <Crosshair className="size-4" strokeWidth={1.75} /> Use this box
              </button>
              <button disabled={busy} onClick={() => go({ layout: "facecam_split", redetect: true })} className="btn btn-line btn-sm">
                <ScanFace className="size-4" strokeWidth={1.75} /> Detect again
              </button>
            </div>
          </div>
        )}
      </div>
      {err && <p className="mt-3 text-[15px] text-fail">{err}</p>}
    </section>
  );
}

function BoxEditor({ src, box, onChange }: { src: string; box: Box; onChange: (b: Box) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const drag = useRef<{ mode: "move" | "resize"; px: number; py: number; start: Box } | null>(null);

  function down(e: React.PointerEvent, mode: "move" | "resize") {
    e.preventDefault();
    e.stopPropagation();
    (e.target as Element).setPointerCapture(e.pointerId);
    drag.current = { mode, px: e.clientX, py: e.clientY, start: box };
  }

  function move(e: React.PointerEvent) {
    const d = drag.current;
    const rect = wrap.current?.getBoundingClientRect();
    if (!d || !rect) return;
    const dx = (e.clientX - d.px) / rect.width;
    const dy = (e.clientY - d.py) / rect.height;
    const s = d.start;
    onChange(
      d.mode === "move"
        ? { ...s, x: clamp(s.x + dx, 0, 1 - s.w), y: clamp(s.y + dy, 0, 1 - s.h) }
        : { ...s, w: clamp(s.w + dx, 0.05, 1 - s.x), h: clamp(s.h + dy, 0.05, 1 - s.y) },
    );
  }

  // Arrow keys nudge the box (Shift = resize, Alt = fine steps) so it works without a mouse.
  function key(e: React.KeyboardEvent) {
    const step = e.altKey ? 0.002 : 0.01;
    const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (!d) return;
    e.preventDefault();
    onChange(
      e.shiftKey
        ? { ...box, w: clamp(box.w + d[0], 0.05, 1 - box.x), h: clamp(box.h + d[1], 0.05, 1 - box.y) }
        : { ...box, x: clamp(box.x + d[0], 0, 1 - box.w), y: clamp(box.y + d[1], 0, 1 - box.h) },
    );
  }

  return (
    <div ref={wrap} className="relative w-full select-none overflow-hidden rounded-board border border-line" onPointerMove={move} onPointerUp={() => (drag.current = null)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt="A frame from the video" className="block w-full" draggable={false} />
      <div
        role="slider"
        tabIndex={0}
        aria-label="Face cam box. Arrow keys move it, Shift plus arrows resize it."
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(box.x * 100)}
        aria-valuetext={`x ${Math.round(box.x * 100)}%, y ${Math.round(box.y * 100)}%, ${Math.round(box.w * 100)} by ${Math.round(box.h * 100)}%`}
        onPointerDown={(e) => down(e, "move")}
        onKeyDown={key}
        className="absolute cursor-move touch-none rounded-[2px] border-2 border-ink shadow-[0_0_0_9999px_rgb(13_12_11/0.6)]"
        style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.w * 100}%`, height: `${box.h * 100}%` }}
      >
        <span className="tile absolute -top-7 left-0 whitespace-nowrap text-[13px]">Face cam</span>
        <span onPointerDown={(e) => down(e, "resize")} className="absolute -bottom-2 -right-2 size-4 cursor-nwse-resize touch-none rounded-[2px] border-2 border-felt bg-ink" aria-hidden />
      </div>
    </div>
  );
}
