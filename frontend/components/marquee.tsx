"use client";

import type { CSSProperties } from "react";

import { fmtSlot, isQueued, type PublishState } from "@/lib/api";

/** Strip stream-title clutter (live dots, emoji) so tiles carry words only. */
export function cleanTitle(title: string | null | undefined): string {
  if (!title) return "";
  return title
    .replace(/[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * The video's title as push-in letter tiles on grooved felt.
 * Tiles drop in once per title (keyed by text), staggered left to right.
 */
export function LetterTitle({ text, max = 12, size = "lg" }: { text: string; max?: number; size?: "lg" | "md" }) {
  const words = cleanTitle(text).split(" ").filter(Boolean);
  const shown = words.slice(0, max);
  const cut = words.length > max;
  const cls = size === "lg" ? "text-[clamp(28px,3.4vw,46px)]" : "text-[clamp(22px,2.4vw,30px)]";
  return (
    <h1 key={text} className={`flex flex-wrap gap-x-[0.28em] gap-y-[0.32em] ${cls}`} aria-label={cleanTitle(text)} title={cleanTitle(text)}>
      {shown.map((w, i) => (
        <span key={`${w}-${i}`} aria-hidden className="tile tile-in" style={{ "--i": i } as CSSProperties}>
          {w}
        </span>
      ))}
      {cut && (
        <span aria-hidden className="tile tile-in opacity-70" style={{ "--i": shown.length } as CSSProperties}>
          …
        </span>
      )}
    </h1>
  );
}

export type BulbState = "queued" | "running" | "done" | "failed";

/**
 * Progress as a row of marquee bulbs. Amber chase while working, letter-white when done,
 * red up to where it stopped on failure. The signature move; nothing else glows.
 */
export function BulbChase({ progress, state, count = 32 }: { progress: number; state: BulbState; count?: number }) {
  const lit = state === "done" ? count : Math.round(Math.min(1, Math.max(0, progress)) * count);
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(progress * 100)}
      className="flex items-center gap-[clamp(3px,0.5vw,7px)]"
    >
      {Array.from({ length: count }, (_, i) => {
        const on = i < lit;
        const tone = !on ? "bulb-off" : state === "failed" ? "bulb-fail" : state === "done" ? "bulb-done" : "bulb-on";
        const chase = on && state === "running";
        return (
          <span
            key={i}
            className={`bulb ${tone} ${chase ? "bulb-chase" : ""} ${i === lit - 1 && state === "running" ? "bulb-head" : ""}`}
            style={{ "--i": i, "--n": lit } as CSSProperties}
          />
        );
      })}
    </div>
  );
}

const PLATFORM_SHORT = { youtube: "YT", instagram: "IG" } as const;

/** One mark per platform in a fixed cell: hollow not posted, ringed dot queued, amber working, filled posted, struck failed. */
export function StateMarks({ publishes }: { publishes?: Partial<Record<"youtube" | "instagram", PublishState>> }) {
  return (
    <div className="flex items-center gap-3">
      {(["youtube", "instagram"] as const).map((p) => {
        const s = publishes?.[p];
        const kind = !s ? "none" : s.status === "done" ? "posted" : s.status === "failed" ? "failed" : isQueued(s) ? "queued" : "working";
        const label =
          kind === "none"
            ? "not posted"
            : kind === "posted"
              ? "posted"
              : kind === "failed"
                ? `failed: ${s?.error ?? ""}`
                : kind === "queued"
                  ? `queued for ${fmtSlot(s!.scheduled_at!)}`
                  : "uploading";
        const mark = <span className={`mark mark-${kind}`} />;
        return (
          <span key={p} className="inline-flex items-center gap-1.5 text-[13px] font-semibold tracking-[0.12em] text-ink-mute" title={`${p}: ${label}`}>
            {kind === "posted" && s?.post_url ? (
              <a href={s.post_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-ink hover:underline">
                {mark}
                {PLATFORM_SHORT[p]}
              </a>
            ) : (
              <>
                {mark}
                {PLATFORM_SHORT[p]}
              </>
            )}
            <span className="sr-only">{label}</span>
          </span>
        );
      })}
    </div>
  );
}

export function ScorePlate({ score }: { score: number }) {
  return (
    <span className="tabular rounded-[2px] bg-felt px-2 py-0.5 text-[26px] font-black leading-none text-ink shadow-[0_2px_8px_rgb(0_0_0/0.45)]" title="Viral score (0-100)">
      {score}
    </span>
  );
}
