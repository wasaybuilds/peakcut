"use client";

import { motion } from "framer-motion";
import {
  ArrowLeft,
  Check,
  Copy,
  Download,
  LoaderCircle,
  RotateCcw,
  Scissors,
  Send,
  Settings,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { LayoutPanel } from "@/components/layout-panel";
import { PostDialog } from "@/components/post-dialog";
import { type Clip, fileUrl, fmtTime, getJob, type Job, type PublishState, retryJob, writeJobCaptions } from "@/lib/api";

const STEPS = [
  "Fetching video info",
  "Downloading audio",
  "Transcribing",
  "Scanning for action",
  "Finding viral moments",
  "Finding the face cam",
  "Rendering clips",
];

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [pollKey, setPollKey] = useState(0);
  const [captionBusy, setCaptionBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const data = await getJob(id);
        if (!alive) return;
        setJob(data.job);
        setClips(data.clips);
        setErr(null);
        const uploading = data.clips.some((c) =>
          Object.values(c.publishes ?? {}).some((p) => p && (p.status === "pending" || p.status === "uploading")),
        );
        if (data.job.status === "queued" || data.job.status === "running") timer = setTimeout(tick, 1500);
        else if (uploading) timer = setTimeout(tick, 3000);
      } catch (e) {
        if (!alive) return;
        setErr((e as Error).message);
        timer = setTimeout(tick, 3000);
      }
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [id, job?.status === "queued", pollKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const running = job && (job.status === "queued" || job.status === "running");
  const stepIdx = job?.step ? STEPS.indexOf(job.step) : -1;

  return (
    <main className="mx-auto min-h-dvh max-w-6xl px-4 pb-24 sm:px-6">
      <header className="flex items-center justify-between py-5">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground">
          <ArrowLeft className="size-4" /> New video
        </Link>
        <div className="flex items-center gap-4">
          <Link href="/settings" className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-foreground">
            <Settings className="size-4" /> Accounts
          </Link>
          <div className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid size-7 place-items-center rounded-lg bg-gradient-to-br from-accent to-accent-2">
              <Scissors className="size-3.5" />
            </span>
            clip-kr
          </div>
        </div>
      </header>

      {err && !job && <p className="mt-10 text-warn">Can&apos;t reach the API: {err}</p>}

      {job && (
        <section className="mt-6">
          <p className="text-xs uppercase tracking-wider text-muted">{job.channel ?? "YouTube"}</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
            {job.title ?? job.source_url}
          </h1>
          {job.duration ? (
            <p className="mt-1 text-sm text-muted">
              {fmtTime(job.duration)} long
              {job.options?.analyzed && job.options.analyzed[1] - job.options.analyzed[0] < job.duration - 1
                ? ` · analyzed ${fmtTime(job.options.analyzed[0])}–${fmtTime(job.options.analyzed[1])} (most replayed part)`
                : ""}
            </p>
          ) : null}

          {running && (
            <div className="mt-8 rounded-2xl border border-border bg-surface p-5">
              <div className="flex items-center justify-between text-sm">
                <span className="inline-flex items-center gap-2">
                  <LoaderCircle className="size-4 animate-spin text-accent" />
                  {job.status === "queued" ? "Waiting in queue" : job.step}
                </span>
                <span className="font-mono tabular-nums text-muted">{Math.round(job.progress * 100)}%</span>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-2">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-accent to-accent-2"
                  animate={{ width: `${Math.max(2, job.progress * 100)}%` }}
                  transition={{ ease: "easeOut", duration: 0.6 }}
                />
              </div>
              <ol className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-3">
                {STEPS.map((s, i) => (
                  <li key={s} className={`flex items-center gap-1.5 ${i < stepIdx ? "text-ok" : i === stepIdx ? "text-foreground" : "text-muted/60"}`}>
                    {i < stepIdx ? <Check className="size-3" /> : <span className="size-3 text-center">·</span>}
                    {s}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {job.status === "failed" && (
            <div className="mt-8 rounded-2xl border border-warn/30 bg-warn/5 p-5">
              <p className="flex items-center gap-2 font-medium text-warn">
                <TriangleAlert className="size-4" /> Failed at: {job.step}
              </p>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-xs text-muted">{job.error}</pre>
              <button
                onClick={async () => {
                  await retryJob(job.id);
                  setJob({ ...job, status: "queued", error: null });
                }}
                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background active:scale-[0.97]"
              >
                <RotateCcw className="size-4" /> Retry (resumes where it stopped)
              </button>
            </div>
          )}

          {!running && clips.length > 0 && (
            <LayoutPanel job={job} onQueued={() => setJob({ ...job, status: "queued", step: null, progress: 0.65 })} />
          )}

          {!running && clips.length > 0 && (
            <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-medium text-muted">{clips.length} clips</h2>
              <button
                disabled={captionBusy}
                onClick={async () => {
                  setCaptionBusy(true);
                  try {
                    await writeJobCaptions(job.id);
                    setPollKey((k) => k + 1);
                  } catch (e) {
                    setErr((e as Error).message);
                  } finally {
                    setCaptionBusy(false);
                  }
                }}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm active:scale-[0.97] disabled:opacity-50"
              >
                {captionBusy ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4 text-accent" />}
                Write AI captions for all
              </button>
            </div>
          )}

          {clips.length > 0 && (
            <div className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {clips.map((c, i) => (
                <ClipCard key={c.id} clip={c} index={i} onChanged={() => setPollKey((k) => k + 1)} />
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}

function ClipCard({ clip, index, onChanged }: { clip: Clip; index: number; onChanged: () => void }) {
  const [copied, setCopied] = useState(false);
  const [posting, setPosting] = useState(false);
  const caption = clip.meta?.instagram?.caption ?? clip.title;
  const scoreColor = clip.score >= 80 ? "text-ok" : clip.score >= 60 ? "text-warn" : "text-muted";

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: Math.min(index * 0.05, 0.3), ease: [0.22, 1, 0.36, 1] }}
      className="overflow-hidden rounded-2xl border border-border bg-surface"
    >
      <div className="relative aspect-[9/16] bg-surface-2">
        {clip.file_path ? (
          <video
            src={fileUrl(clip.file_path)}
            poster={clip.thumb_path ? fileUrl(clip.thumb_path) : undefined}
            controls
            playsInline
            preload="none"
            className="size-full object-cover"
          />
        ) : (
          <div className="grid size-full place-items-center text-sm text-muted">
            <span className="inline-flex items-center gap-2">
              <LoaderCircle className="size-4 animate-spin" /> Rendering…
            </span>
          </div>
        )}
        <span className={`absolute left-3 top-3 rounded-full bg-black/70 px-2.5 py-1 font-mono text-xs backdrop-blur ${scoreColor}`}>
          {clip.score}
        </span>
      </div>
      <div className="space-y-2 p-4">
        <h3 className="font-medium leading-snug text-pretty">{clip.title}</h3>
        <p className="text-xs text-muted">
          {fmtTime(clip.start)} – {fmtTime(clip.end)} · {Math.round(clip.end - clip.start)}s
        </p>
        <p className="text-sm text-muted text-pretty">{clip.reason}</p>
        <PublishBadges clip={clip} />
        <div className="flex gap-2 pt-1">
          <button
            disabled={!clip.file_path}
            onClick={() => setPosting(true)}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-background active:scale-[0.97] disabled:opacity-40"
          >
            <Send className="size-4" /> Post
          </button>
          {clip.file_path && (
            <a
              href={fileUrl(clip.file_path)}
              download
              aria-label="Download"
              title="Download"
              className="inline-flex items-center justify-center rounded-lg border border-border px-3 py-2 text-sm active:scale-[0.97]"
            >
              <Download className="size-4" />
            </a>
          )}
          <button
            title="Copy Instagram caption"
            onClick={async () => {
              await navigator.clipboard.writeText(caption);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm active:scale-[0.97]"
          >
            {copied ? <Check className="size-4 text-ok" /> : <Copy className="size-4" />}
          </button>
        </div>
      </div>
      <PostDialog clip={clip} open={posting} onClose={() => setPosting(false)} onPosted={onChanged} />
    </motion.article>
  );
}

function PublishBadges({ clip }: { clip: Clip }) {
  const entries = Object.values(clip.publishes ?? {}).filter(Boolean) as PublishState[];
  if (!entries.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map((p) => {
        const name = p.platform === "youtube" ? "YouTube" : "Instagram";
        if (p.status === "done" && p.post_url)
          return (
            <a key={p.platform} href={p.post_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-full bg-ok/15 px-2.5 py-1 text-xs text-ok hover:underline">
              <Check className="size-3" /> {name}
            </a>
          );
        if (p.status === "failed")
          return (
            <span key={p.platform} title={p.error ?? ""} className="inline-flex cursor-help items-center gap-1 rounded-full bg-warn/15 px-2.5 py-1 text-xs text-warn">
              <TriangleAlert className="size-3" /> {name} failed
            </span>
          );
        return (
          <span key={p.platform} className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2.5 py-1 text-xs text-muted">
            <LoaderCircle className="size-3 animate-spin" /> {name} {p.status === "pending" ? "queued" : "uploading"}
          </span>
        );
      })}
    </div>
  );
}
