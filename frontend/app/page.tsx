"use client";

import { ArrowRight, Check, CircleDashed, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { cleanTitle, LetterTitle } from "@/components/marquee";
import { createJob, fmtTime, getAccounts, getHealth, type Accounts, type Health, type Job, LAYOUTS, listJobs } from "@/lib/api";

const LAYOUT_USE: Record<string, string> = {
  zoom_fill: "Best for no-commentary gameplay.",
  facecam_split: "Best for streams with a webcam.",
  blur_fill: "When on-screen text or the map matters.",
  center_crop: "For centered action like driving.",
};

export default function Home() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [count, setCount] = useState(6);
  const [layout, setLayout] = useState("zoom_fill");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [accounts, setAccounts] = useState<Accounts | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    getAccounts().then(setAccounts).catch(() => {});
    listJobs().then(setJobs).catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^https?:\/\/(www\.|m\.)?(youtube\.com|youtu\.be)\//i.test(url.trim())) {
      setError("That isn't a YouTube link. Paste one from youtube.com or youtu.be.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const job = await createJob({ url: url.trim(), clip_count: count, layout });
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const providers = health ? Object.values(health.providers) : [];
  const setup = [
    { done: !!health?.ffmpeg.found, text: "ffmpeg installed", help: "Run scripts\\setup.ps1" },
    { done: !!health?.providers.groq?.configured, text: "Speech-to-text key (Groq)", help: "Add GROQ_API_KEY to .env", href: health?.providers.groq?.signup_url },
    { done: providers.some((p) => p.configured), text: "At least one AI key", help: "Add ZHIPU_API_KEY or GEMINI_API_KEY to .env", href: health?.providers.zhipu?.signup_url },
    { done: !!(accounts?.youtube.connected || accounts?.instagram.connected), text: "A posting account (optional)", help: "Connect YouTube or Instagram", href: "/settings" },
  ];
  const missing = setup.filter((s) => !s.done);

  return (
    <div className="mx-auto max-w-[1180px] px-4 pb-24 pt-6 sm:px-8 lg:pt-10">
      <section className="felt-grooves rounded-board border border-line px-5 pb-6 pt-7 sm:px-8 sm:pt-9">
        <LetterTitle text="Paste a YouTube link" />
        <p className="mt-5 max-w-[60ch] text-[18px] text-ink-soft">
          PeakCut finds the moments worth posting and cuts them into captioned 9:16 clips. Long streams work too.
        </p>

        <form onSubmit={submit} className="mt-7" noValidate>
          <label htmlFor="url" className="label">
            Video link
          </label>
          <div className="mt-2 grid gap-2 sm:grid-cols-[minmax(0,1fr)_9.5rem_auto]">
            <input
              id="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setError(null);
              }}
              inputMode="url"
              autoComplete="off"
              placeholder="https://www.youtube.com/watch?v=..."
              aria-invalid={!!error}
              aria-describedby={error ? "url-error" : undefined}
              className="field h-13 text-[18px]"
            />
            <label className="sr-only" htmlFor="count">
              Number of clips
            </label>
            <select id="count" value={count} onChange={(e) => setCount(Number(e.target.value))} className="field h-13">
              {[3, 6, 8, 12].map((n) => (
                <option key={n} value={n}>
                  {n} clips
                </option>
              ))}
            </select>
            <button type="submit" disabled={busy} className="btn btn-primary h-13 px-7">
              {busy ? <LoaderCircle className="size-4 animate-spin" /> : null}
              Find clips
              {!busy && <ArrowRight className="size-4" strokeWidth={2} />}
            </button>
          </div>
          {error && (
            <p id="url-error" className="mt-2 text-[15px] text-fail">
              {error}
            </p>
          )}

          <fieldset className="mt-6">
            <legend className="label">Layout</legend>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {LAYOUTS.map((l) => {
                const on = layout === l.id;
                return (
                  <label
                    key={l.id}
                    className={`cursor-pointer rounded-board border px-4 py-3 transition-colors ${
                      on ? "border-ink bg-felt-high" : "border-line bg-felt hover:border-line-strong"
                    }`}
                  >
                    <input type="radio" name="layout" value={l.id} checked={on} onChange={() => setLayout(l.id)} className="sr-only" />
                    <span className="flex items-center justify-between text-[17px] font-bold uppercase tracking-[0.08em]">
                      {l.label}
                      {on && <Check className="size-4" strokeWidth={2.25} />}
                    </span>
                    <span className="mt-1 block text-[15px] leading-snug text-ink-soft">{l.hint}.</span>
                    <span className="mt-1 block text-[14px] leading-snug text-ink-mute">{LAYOUT_USE[l.id]}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        </form>
      </section>

      {health && missing.length > 0 && (
        <section className="mt-10" aria-labelledby="setup-h">
          <h2 id="setup-h" className="text-[24px] font-bold uppercase tracking-[0.04em]">
            Finish setting up
          </h2>
          <ul className="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-2">
            {setup.map((s) => (
              <li key={s.text} className="flex items-start gap-3">
                {s.done ? (
                  <Check className="mt-1 size-4 shrink-0 text-ink" strokeWidth={2.25} />
                ) : (
                  <CircleDashed className="mt-1 size-4 shrink-0 text-ink-mute" strokeWidth={1.75} />
                )}
                <span>
                  <span className={s.done ? "text-ink-mute line-through decoration-line-strong" : "text-ink"}>{s.text}</span>
                  {!s.done &&
                    (s.href ? (
                      <a href={s.href} target={s.href.startsWith("http") ? "_blank" : undefined} rel="noreferrer" className="block text-[15px] text-ink-soft underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                        {s.help}
                      </a>
                    ) : (
                      <span className="block text-[15px] text-ink-soft">{s.help}</span>
                    ))}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {health === null && (
        <p className="mt-8 text-[16px] text-fail">Can&apos;t reach the PeakCut API on port 8000. Start it with scripts\dev.ps1, then reload.</p>
      )}

      {jobs.length > 0 && (
        <section className="mt-12 lg:hidden" aria-labelledby="recent-h">
          <h2 id="recent-h" className="text-[24px] font-bold uppercase tracking-[0.04em]">
            Your videos
          </h2>
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {jobs.slice(0, 8).map((j) => (
              <li key={j.id}>
                <Link href={`/jobs/${j.id}`} className="flex items-center justify-between gap-4 py-3">
                  <span className="min-w-0">
                    <span className="block truncate">{cleanTitle(j.title) || j.source_url}</span>
                    <span className="block text-[14px] text-ink-mute">
                      {j.channel ?? "YouTube"}
                      {j.duration ? `, ${fmtTime(j.duration)}` : ""}
                    </span>
                  </span>
                  <span className={`tabular shrink-0 text-[13px] font-semibold tracking-[0.08em] ${j.status === "failed" ? "text-fail" : j.status === "done" ? "text-ink-mute" : "text-bulb"}`}>
                    {j.status === "running" ? `${Math.round(j.progress * 100)}%` : j.status.toUpperCase()}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
