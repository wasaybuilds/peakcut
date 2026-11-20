"use client";

import { motion } from "framer-motion";
import { ArrowRight, CircleAlert, CircleCheck, Cpu, ExternalLink, Link2, LoaderCircle, Scissors } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { createJob, fmtTime, getHealth, type Health, type Job, LAYOUTS, listJobs } from "@/lib/api";

export default function Home() {
  const [url, setUrl] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [apiDown, setApiDown] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [count, setCount] = useState(6);
  const [layout, setLayout] = useState("zoom_fill");
  const [jobs, setJobs] = useState<Job[]>([]);
  const router = useRouter();

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setApiDown(true));
    listJobs()
      .then(setJobs)
      .catch(() => {});
  }, []);

  const configured = health ? Object.values(health.providers).filter((p) => p.configured).length : 0;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^https?:\/\/(www\.|m\.)?(youtube\.com|youtu\.be)\//.test(url.trim())) {
      setNote("Paste a YouTube link (youtube.com or youtu.be).");
      return;
    }
    setBusy(true);
    try {
      const job = await createJob({ url: url.trim(), clip_count: count, layout });
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setNote((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="relative min-h-dvh overflow-hidden">
      {/* glow */}
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[520px] w-[900px] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(255,61,110,0.22),rgba(124,92,255,0.12),transparent)] blur-2xl" />

      <header className="relative mx-auto flex max-w-5xl items-center justify-between px-4 py-5 sm:px-6">
        <div className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-accent-2">
            <Scissors className="size-4" />
          </span>
          PeakCut
        </div>
        <div className="flex items-center gap-4">
          <Link href="/settings" className="text-sm text-muted transition-colors hover:text-foreground">
            Accounts
          </Link>
          <StatusPill health={health} apiDown={apiDown} configured={configured} />
        </div>
      </header>

      <section className="relative mx-auto max-w-3xl px-4 pt-16 text-center sm:px-6 sm:pt-24">
        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="text-4xl font-semibold tracking-tight text-balance sm:text-6xl"
        >
          Long video in.{" "}
          <span className="bg-gradient-to-r from-accent to-accent-2 bg-clip-text text-transparent">
            Viral clips out.
          </span>
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto mt-4 max-w-xl text-pretty text-muted sm:text-lg"
        >
          Paste a GTA 6 stream or video. AI finds the best moments from chat spikes, loudness and the
          transcript, then cuts 9:16 clips with animated captions.
        </motion.p>

        <motion.form
          onSubmit={submit}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.16, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto mt-10 flex max-w-2xl flex-col gap-2 rounded-2xl border border-border bg-surface/80 p-2 backdrop-blur sm:flex-row"
        >
          <label className="flex flex-1 items-center gap-2 px-3">
            <Link2 className="size-4 shrink-0 text-muted" />
            <input
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setNote(null);
              }}
              placeholder="https://www.youtube.com/watch?v=..."
              className="h-11 w-full bg-transparent text-base outline-none placeholder:text-muted/70"
            />
          </label>
          <select
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            aria-label="Number of clips"
            className="h-11 rounded-xl border border-border bg-surface-2 px-3 text-sm text-foreground outline-none"
          >
            {[3, 6, 8, 12].map((n) => (
              <option key={n} value={n}>
                {n} clips
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={busy}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-foreground px-5 font-medium text-background transition-transform active:scale-[0.97] disabled:opacity-60"
          >
            {busy ? <LoaderCircle className="size-4 animate-spin" /> : null}
            Find clips {!busy && <ArrowRight className="size-4" />}
          </button>
        </motion.form>
        <div className="mt-3 flex flex-wrap items-center justify-center gap-1.5" role="radiogroup" aria-label="Layout">
          {LAYOUTS.map((l) => (
            <button
              key={l.id}
              type="button"
              role="radio"
              aria-checked={layout === l.id}
              title={l.hint}
              onClick={() => setLayout(l.id)}
              className={`rounded-full px-3 py-1 text-xs transition-colors ${
                layout === l.id ? "bg-surface-2 text-foreground ring-1 ring-border" : "text-muted hover:text-foreground"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
        {note && <p className="mt-3 text-sm text-warn">{note}</p>}
      </section>

      {jobs.length > 0 && (
        <section className="relative mx-auto mt-16 max-w-3xl px-4 sm:px-6">
          <h2 className="mb-3 text-sm font-medium text-muted">Recent</h2>
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
            {jobs.slice(0, 8).map((j) => (
              <li key={j.id}>
                <Link href={`/jobs/${j.id}`} className="flex items-center justify-between gap-4 px-4 py-3 transition-colors hover:bg-surface-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{j.title ?? j.source_url}</div>
                    <div className="truncate text-xs text-muted">
                      {j.channel ?? "…"}
                      {j.duration ? ` · ${fmtTime(j.duration)}` : ""}
                    </div>
                  </div>
                  <span
                    className={`shrink-0 text-xs ${j.status === "done" ? "text-ok" : j.status === "failed" ? "text-warn" : "text-muted"}`}
                  >
                    {j.status === "running" ? `${Math.round(j.progress * 100)}%` : j.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {health && (
        <section className="relative mx-auto mt-20 max-w-3xl px-4 pb-20 sm:px-6">
          <h2 className="mb-3 text-sm font-medium text-muted">Free AI providers</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {Object.entries(health.providers).map(([name, p]) => (
              <div key={name} className="flex items-center justify-between rounded-xl border border-border bg-surface px-4 py-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{p.label}</div>
                  <div className="truncate font-mono text-xs text-muted">{p.model}</div>
                </div>
                {p.configured ? (
                  <CircleCheck className="size-4 shrink-0 text-ok" />
                ) : (
                  <a
                    href={p.signup_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex shrink-0 items-center gap-1 text-xs text-accent hover:underline"
                  >
                    Get key <ExternalLink className="size-3" />
                  </a>
                )}
              </div>
            ))}
          </div>
          <p className="mt-3 flex items-center gap-2 text-xs text-muted">
            <Cpu className="size-3.5" /> Encoder: <span className="font-mono">{health.ffmpeg.encoder ?? "n/a"}</span>
          </p>
        </section>
      )}
    </main>
  );
}

function StatusPill({ health, apiDown, configured }: { health: Health | null; apiDown: boolean; configured: number }) {
  if (apiDown)
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs text-warn">
        <CircleAlert className="size-3.5" /> API offline
      </span>
    );
  if (!health) return <span className="h-6 w-24 animate-pulse rounded-full bg-surface-2" />;
  const ready = health.ok && configured > 0;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs ${ready ? "text-ok" : "text-warn"}`}>
      <span className={`size-1.5 rounded-full ${ready ? "bg-ok" : "bg-warn"}`} />
      {ready ? `Ready · ${configured} AI key${configured > 1 ? "s" : ""}` : "Add an API key to .env"}
    </span>
  );
}
