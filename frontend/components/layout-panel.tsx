"use client";

import { Crosshair, RefreshCw, ScanFace } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { type Box, fileUrl, type Job, LAYOUTS, rerenderJob } from "@/lib/api";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Switch a finished job's layout, and drag/resize the face cam box, then re-render. */
export function LayoutPanel({ job, onQueued }: { job: Job; onQueued: () => void }) {
  const current = job.options?.layout ?? "zoom_fill";
  const detected = job.options?.facecam ?? null;
  const frame = job.options?.facecam_frame;
  const [box, setBox] = useState<Box | null>(detected);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => setBox(detected), [detected?.x, detected?.y, detected?.w, detected?.h]); // eslint-disable-line react-hooks/exhaustive-deps

  async function go(body: Parameters<typeof rerenderJob>[1]) {
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

  const changed = box && detected && JSON.stringify(box) !== JSON.stringify(detected);

  return (
    <div className="mt-8 rounded-2xl border border-border bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-medium">Layout</h2>
        <div className="flex flex-wrap gap-1.5">
          {LAYOUTS.map((l) => (
            <button
              key={l.id}
              title={l.hint}
              disabled={busy || l.id === current}
              onClick={() => go({ layout: l.id })}
              className={`rounded-lg px-3 py-1.5 text-sm transition-colors active:scale-[0.97] ${
                l.id === current ? "bg-foreground text-background" : "border border-border text-muted hover:text-foreground"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {current === "facecam_split" && (
        <div className="mt-4">
          {frame ? (
            <>
              <p className="mb-2 text-xs text-muted">
                {detected ? "Drag the box onto the face cam, or resize it from the corner." : "No face cam found automatically. Draw it: drag the box onto the cam."}
              </p>
              <BoxEditor src={fileUrl(frame)} box={box ?? { x: 0.02, y: 0.55, w: 0.22, h: 0.3 }} onChange={setBox} />
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  disabled={busy || !(changed || (!detected && box))}
                  onClick={() => box && go({ layout: "facecam_split", facecam: box })}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-background active:scale-[0.97] disabled:opacity-40"
                >
                  <Crosshair className="size-4" /> Use this box &amp; re-render
                </button>
                <button
                  disabled={busy}
                  onClick={() => go({ layout: "facecam_split", redetect: true })}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm active:scale-[0.97]"
                >
                  <ScanFace className="size-4" /> Detect again
                </button>
              </div>
            </>
          ) : (
            <p className="flex items-center gap-2 text-xs text-muted">
              <RefreshCw className="size-3.5" /> The face cam is detected while rendering. Its position shows up here after.
            </p>
          )}
        </div>
      )}
      {err && <p className="mt-3 text-sm text-warn">{err}</p>}
    </div>
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
    if (d.mode === "move") {
      onChange({ ...s, x: clamp(s.x + dx, 0, 1 - s.w), y: clamp(s.y + dy, 0, 1 - s.h) });
    } else {
      onChange({ ...s, w: clamp(s.w + dx, 0.05, 1 - s.x), h: clamp(s.h + dy, 0.05, 1 - s.y) });
    }
  }

  return (
    <div ref={wrap} className="relative w-full select-none overflow-hidden rounded-xl border border-border" onPointerMove={move} onPointerUp={() => (drag.current = null)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt="Frame from the video" className="block w-full" draggable={false} />
      <div
        onPointerDown={(e) => down(e, "move")}
        className="absolute cursor-move touch-none rounded-sm border-2 border-ok bg-ok/10 shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]"
        style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.w * 100}%`, height: `${box.h * 100}%` }}
      >
        <span className="absolute -top-6 left-0 rounded bg-ok px-1.5 py-0.5 text-[10px] font-medium text-background">Face cam</span>
        <span
          onPointerDown={(e) => down(e, "resize")}
          className="absolute -bottom-1.5 -right-1.5 size-4 cursor-nwse-resize touch-none rounded-sm border-2 border-background bg-ok"
        />
      </div>
    </div>
  );
}
