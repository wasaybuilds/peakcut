"use client";

import { Check, Copy, Download, ImageDown, Play, RotateCcw, ScanFace, Send, Sparkles } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";

import { FacecamEditor, LayoutSwitch } from "@/components/layout-panel";
import { BulbChase, type BulbState, cleanTitle, LetterTitle, ScorePlate, StateMarks } from "@/components/marquee";
import { PostDialog } from "@/components/post-dialog";
import { type Clip, fileUrl, fmtTime, getJob, type Job, LAYOUTS, retryJob, writeJobCaptions } from "@/lib/api";

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [pollKey, setPollKey] = useState(0);
  const [captionBusy, setCaptionBusy] = useState(false);
  const [camOpen, setCamOpen] = useState(false);

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
  }, [id, pollKey]);

  const refresh = () => setPollKey((k) => k + 1);

  if (!job) {
    return (
      <div className="mx-auto max-w-[1400px] px-4 pt-6 sm:px-8 lg:pt-10">
        {err ? (
          <p className="text-fail">Can&apos;t load this job: {err}</p>
        ) : (
          <div className="felt-grooves h-56 animate-pulse rounded-board border border-line" aria-label="Loading job" />
        )}
      </div>
    );
  }

  const running = job.status === "queued" || job.status === "running";
  const bulbState: BulbState = job.status === "queued" ? "queued" : job.status;
  const analyzed = job.options?.analyzed;
  const partial = analyzed && job.duration && analyzed[1] - analyzed[0] < job.duration - 1;
  const layoutLabel = LAYOUTS.find((l) => l.id === (job.options?.layout ?? "zoom_fill"))?.label;
  const expected = job.options?.clip_count ?? 6;
  const isFacecam = job.options?.layout === "facecam_split";
  const firstPending = clips.find((c) => !c.file_path)?.id;
  const queued = () => {
    setJob({ ...job, status: "queued", step: null });
    setCamOpen(false);
    refresh();
  };

  return (
    <div className="mx-auto max-w-[1400px] px-4 pb-24 pt-6 sm:px-8 lg:pt-10">
      <section className="felt-grooves rounded-board border border-line px-5 pb-6 pt-7 sm:px-8 sm:pt-8" aria-live="polite">
        <LetterTitle text={job.title ?? "Fetching video info"} />
        <p className="mt-5 text-[17px] text-ink-soft">
          {[job.channel, job.duration ? `${fmtTime(job.duration)} long` : null, layoutLabel ? `${layoutLabel} layout` : null]
            .filter(Boolean)
            .join(", ")}
        </p>
        {partial && (
          <p className="mt-1 text-[16px] text-ink-mute">
            Analyzing {fmtTime(analyzed[0])} to {fmtTime(analyzed[1])}, the most replayed stretch.
          </p>
        )}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
          <div className="min-w-0 flex-1">
            <BulbChase progress={job.progress} state={bulbState} />
          </div>
          <p
            className={`tabular shrink-0 text-[15px] font-bold uppercase tracking-[0.12em] ${
              job.status === "running" ? "text-bulb" : job.status === "failed" ? "text-fail" : job.status === "queued" ? "text-ink-mute" : "text-ink"
            }`}
          >
            {job.status === "queued" && "Waiting in line"}
            {job.status === "running" && `${job.step ?? "Starting"}  ${Math.round(job.progress * 100)}%`}
            {job.status === "done" && `${clips.length} clips ready`}
            {job.status === "failed" && `Stopped at ${job.step ?? "start"}`}
          </p>
        </div>

        {job.status === "failed" && (
          <div className="mt-5 border-t border-line pt-5">
            <p className="max-w-[80ch] whitespace-pre-wrap text-[16px] leading-relaxed text-ink-soft">{job.error}</p>
            <button
              className="btn btn-primary mt-4"
              onClick={async () => {
                await retryJob(job.id);
                setJob({ ...job, status: "queued", error: null });
                refresh();
              }}
            >
              <RotateCcw className="size-4" strokeWidth={2} /> Retry from {job.step ?? "the start"}
            </button>
          </div>
        )}
      </section>

      {/* Clips toolbar: count, layout, face cam, captions in one row */}
      <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-3">
        <h2 className="mr-auto text-[28px] font-bold uppercase leading-none tracking-[0.04em]">
          {clips.length ? `${clips.length} clips` : "Clips"}
          {clips.length > 0 && <span className="ml-3 align-middle text-[15px] font-semibold tracking-[0.1em] text-ink-mute">BEST FIRST</span>}
        </h2>
        {clips.length > 0 && <LayoutSwitch job={job} disabled={running} onQueued={queued} />}
        {clips.length > 0 && isFacecam && (
          <button
            className="btn btn-line btn-sm"
            disabled={running}
            aria-expanded={camOpen}
            aria-controls="facecam-editor"
            onClick={() => setCamOpen((o) => !o)}
          >
            <ScanFace className="size-4" strokeWidth={1.75} /> Adjust face cam
          </button>
        )}
        {!running && clips.length > 0 && (
          <button
            disabled={captionBusy}
            className="btn btn-line btn-sm"
            onClick={async () => {
              setCaptionBusy(true);
              try {
                await writeJobCaptions(job.id);
                refresh();
              } catch (e) {
                setErr((e as Error).message);
              } finally {
                setCaptionBusy(false);
              }
            }}
          >
            <Sparkles className={`size-4 ${captionBusy ? "animate-pulse" : ""}`} strokeWidth={1.75} />
            {captionBusy ? "Writing captions…" : "Rewrite all captions"}
          </button>
        )}
      </div>
      {camOpen && isFacecam && !running && <FacecamEditor job={job} onClose={() => setCamOpen(false)} onQueued={queued} />}
      {err && <p className="mt-2 text-[15px] text-fail">{err}</p>}

      <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3 xl:grid-cols-5">
        {clips.map((c) => (
          <ClipCard key={c.id} clip={c} onChanged={refresh} rendering={job.status === "running" && c.id === firstPending} />
        ))}
        {running &&
          Array.from({ length: Math.max(0, expected - clips.length) }, (_, i) => (
            <div key={`slot-${i}`} aria-hidden>
              <div className="grid aspect-[9/16] place-items-center rounded-board border border-dashed border-line bg-felt-raised">
                <span className="text-center">
                  <span className="tabular block text-[44px] font-black leading-none text-line-strong">{clips.length + i + 1}</span>
                  <span className="mt-2 block text-[13px] font-semibold uppercase tracking-[0.14em] text-ink-mute">Waiting</span>
                </span>
              </div>
              <div className="mt-3 h-4 w-3/4 rounded-board bg-felt-high" />
              <div className="mt-2 h-3 w-1/2 rounded-board bg-felt-raised" />
            </div>
          ))}
      </div>
      {!running && clips.length === 0 && job.status === "done" && (
        <p className="mt-4 text-ink-soft">
          No clips came out of this video. Try another one, or <Link href="/" className="underline underline-offset-4">start over</Link>.
        </p>
      )}
    </div>
  );
}

/** Poster with a drawn play button; the browser's controls appear only once playback starts. */
function ClipVideo({ clip }: { clip: Clip }) {
  const [playing, setPlaying] = useState(false);
  if (!clip.file_path) return null;
  if (playing) {
    return <video src={fileUrl(clip.file_path)} controls autoPlay playsInline className="size-full object-cover" />;
  }
  return (
    <button onClick={() => setPlaying(true)} aria-label={`Play ${cleanTitle(clip.title)}`} className="group/play relative block size-full">
      {clip.thumb_path ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={fileUrl(clip.thumb_path)} alt="" className="size-full object-cover" loading="lazy" />
      ) : (
        <span className="block size-full bg-felt-high" />
      )}
      {/* bottom-right corner: clear of the burned-in hook and caption bands people review */}
      <span className="absolute bottom-2.5 right-2.5 grid size-11 place-items-center rounded-full bg-felt/85 text-ink shadow-[0_4px_14px_rgb(0_0_0/0.45)] transition-transform duration-200 ease-out group-hover/play:scale-110">
        <Play className="ml-0.5 size-5 fill-ink" strokeWidth={1.5} />
      </span>
    </button>
  );
}

function ClipCard({ clip, onChanged, rendering }: { clip: Clip; onChanged: () => void; rendering: boolean }) {
  const [copied, setCopied] = useState(false);
  const [posting, setPosting] = useState(false);
  const postBtn = useRef<HTMLButtonElement>(null);
  const caption = clip.meta?.instagram?.caption ?? clip.title;
  const length = Math.round(clip.end - clip.start);

  return (
    <article className="group flex min-w-0 flex-col">
      <div className="relative aspect-[9/16] overflow-hidden rounded-board border border-line bg-felt-raised">
        {clip.file_path ? (
          <ClipVideo clip={clip} />
        ) : (
          <div className={`grid size-full place-items-center text-[14px] font-semibold uppercase tracking-[0.14em] ${rendering ? "text-bulb" : "text-ink-mute"}`}>
            {rendering ? "Rendering" : "Waiting"}
          </div>
        )}
        <div className="pointer-events-none absolute left-2.5 top-2.5">
          <ScorePlate score={clip.score} />
        </div>
      </div>

      <h3 className="mt-3 text-[19px] font-bold leading-[1.15] text-pretty">{cleanTitle(clip.title)}</h3>
      <p className="tabular mt-1 text-[14px] text-ink-mute">
        {fmtTime(clip.start)} to {fmtTime(clip.end)}, {length}s
      </p>
      <p className="mt-2 line-clamp-3 text-[15px] leading-snug text-ink-soft">{clip.reason}</p>

      {/* pushed to the bottom so every card's marks and actions line up across the row */}
      <div className="mt-auto flex items-center justify-between gap-2 pt-3">
        <StateMarks publishes={clip.publishes} />
      </div>
      <div className="mt-3 flex gap-1.5">
        <button ref={postBtn} disabled={!clip.file_path} onClick={() => setPosting(true)} className="btn btn-primary btn-sm flex-1">
          <Send className="size-3.5" strokeWidth={2} /> Post
        </button>
        {clip.file_path && (
          <a href={fileUrl(clip.file_path)} download aria-label="Download clip" title="Download" className="btn btn-line btn-sm px-2.5">
            <Download className="size-4" strokeWidth={1.75} />
          </a>
        )}
        {clip.meta?.cover?.path && (
          <a href={fileUrl(clip.meta.cover.path)} download aria-label="Download cover image" title="Download cover" className="btn btn-line btn-sm px-2.5">
            <ImageDown className="size-4" strokeWidth={1.75} />
          </a>
        )}
        <button
          aria-label="Copy Instagram caption"
          title="Copy caption"
          className="btn btn-line btn-sm px-2.5"
          onClick={async () => {
            await navigator.clipboard.writeText(caption);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? <Check className="size-4" strokeWidth={2.25} /> : <Copy className="size-4" strokeWidth={1.75} />}
        </button>
      </div>
      <PostDialog clip={clip} open={posting} onClose={() => setPosting(false)} onPosted={onChanged} returnFocus={postBtn} />
    </article>
  );
}
