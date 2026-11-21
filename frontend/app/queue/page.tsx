"use client";

import { CalendarClock, LoaderCircle, Plus, Send, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { cleanTitle, LetterTitle } from "@/components/marquee";
import { fileUrl, fmtClock, fmtDay, fmtSlot, getSchedule, postQueuedNow, type QueueItem, saveScheduleTimes, type Schedule, unqueueClip } from "@/lib/api";

const PLATFORM_SHORT = { youtube: "YT", instagram: "IG", tiktok: "TT" } as const;

/** Group queue items under a day heading ("Today", "Tomorrow", "Mon 24 Nov"). */
function byDay(items: QueueItem[]) {
  const groups: { day: string; items: QueueItem[] }[] = [];
  for (const it of items) {
    const day = fmtDay(it.scheduled_at);
    const last = groups[groups.length - 1];
    if (last && last.day === day) last.items.push(it);
    else groups.push({ day, items: [it] });
  }
  return groups;
}

export default function QueuePage() {
  const [sch, setSch] = useState<Schedule | null>(null);
  const [times, setTimes] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(
    () =>
      getSchedule()
        .then((s) => {
          setSch(s);
          setErr(null);
          return s;
        })
        .catch((e) => {
          setErr((e as Error).message);
          return null;
        }),
    [],
  );

  useEffect(() => {
    refresh().then((s) => s && setTimes(s.times));
    const t = setInterval(refresh, 30_000);
    return () => clearInterval(t);
  }, [refresh]);

  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name);
    setErr(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const dirty = sch !== null && [...times].sort().join() !== sch.times.join();

  return (
    <div className="mx-auto max-w-[980px] px-4 pb-24 pt-6 sm:px-8 lg:pt-10">
      <section className="felt-grooves rounded-board border border-line px-5 pb-6 pt-7 sm:px-8">
        <LetterTitle text="Queue" />
        <p className="mt-5 max-w-[62ch] text-[18px] text-ink-soft">
          Queued clips go out one at a time at your posting times. Keep the laptop on with PeakCut running; a post whose time is missed moves to the next free time.
        </p>
      </section>
      {err && <p className="mt-4 text-[15px] text-fail">{err}</p>}

      <section className="mt-6 rounded-board border border-line bg-felt-raised px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-[24px] font-bold uppercase leading-none tracking-[0.04em]">Posting times</h2>
            <p className="mt-1.5 text-[16px] text-ink-mute">
              {sch ? `${sch.times.length} a day, on the laptop's clock` : "Loading"}
              {sch?.next_slot && `. Next free: ${fmtSlot(sch.next_slot)}`}
            </p>
          </div>
          {dirty && (
            <div className="flex gap-1.5">
              <button onClick={() => sch && setTimes(sch.times)} disabled={busy !== null} className="btn btn-line btn-sm">
                Undo
              </button>
              <button onClick={() => act("times", () => saveScheduleTimes(times).then((s) => setTimes(s.times)))} disabled={busy !== null} className="btn btn-primary btn-sm">
                {busy === "times" && <LoaderCircle className="size-3.5 animate-spin" />} Save times
              </button>
            </div>
          )}
        </div>
        <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-5">
          {sch === null && Array.from({ length: 3 }, (_, i) => <div key={i} className="h-11 w-36 animate-pulse rounded-board bg-felt-high" />)}
          {sch !== null &&
            times.map((t, i) => (
              <div key={i} className="flex items-center rounded-board border border-line-strong bg-groove">
                <label className="sr-only" htmlFor={`time-${i}`}>
                  Posting time {i + 1}
                </label>
                <input
                  id={`time-${i}`}
                  type="time"
                  value={t}
                  onChange={(e) => setTimes(times.map((x, j) => (j === i ? e.target.value : x)))}
                  className="tabular h-11 bg-transparent pl-3 text-[18px] font-semibold text-ink outline-none [color-scheme:dark]"
                />
                <button
                  onClick={() => setTimes(times.filter((_, j) => j !== i))}
                  disabled={times.length <= 1}
                  aria-label={`Remove ${t}`}
                  className="grid h-11 w-9 place-items-center text-ink-mute hover:text-ink disabled:opacity-30"
                >
                  <X className="size-4" strokeWidth={1.75} />
                </button>
              </div>
            ))}
          {sch !== null && times.length < 8 && (
            <button onClick={() => setTimes([...times, "09:00"])} className="btn btn-line h-11">
              <Plus className="size-4" strokeWidth={2} /> Add time
            </button>
          )}
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-[24px] font-bold uppercase leading-none tracking-[0.04em]">Up next</h2>
        {sch === null && <div className="mt-4 h-24 animate-pulse rounded-board bg-felt-raised" />}
        {sch?.queue.length === 0 && (
          <div className="mt-4 rounded-board border border-dashed border-line-strong px-5 py-8 text-center">
            <CalendarClock className="mx-auto size-6 text-ink-mute" strokeWidth={1.5} />
            <p className="mt-3 text-[17px] text-ink">Nothing queued</p>
            <p className="mx-auto mt-1 max-w-[46ch] text-[15px] text-ink-mute">
              Open a job, click Post on a clip, then Queue. It goes out at the next free time.
            </p>
            <Link href="/" className="btn btn-line btn-sm mt-4">
              Clip a new video
            </Link>
          </div>
        )}
        {sch &&
          byDay(sch.queue).map((g) => (
            <div key={g.day} className="mt-5">
              <p className="label pb-2">{g.day}</p>
              <ul className="divide-y divide-line overflow-hidden rounded-board border border-line bg-felt-raised">
                {g.items.map((it) => (
                  <li key={`${it.clip_id}-${it.scheduled_at}`} className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-4 gap-y-3 px-4 py-3 sm:grid-cols-[7rem_auto_minmax(0,1fr)_auto]">
                    <span className="tabular whitespace-nowrap text-[22px] font-bold leading-none text-ink max-sm:col-span-2">{fmtClock(it.scheduled_at)}</span>
                    {it.thumb_path ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={fileUrl(it.thumb_path)} alt="" className="aspect-[9/16] w-11 rounded-[2px] bg-felt-high object-cover" loading="lazy" />
                    ) : (
                      <span className="aspect-[9/16] w-11 rounded-[2px] bg-felt-high" />
                    )}
                    <div className="min-w-0">
                      <Link href={`/jobs/${it.job_id}`} className="line-clamp-2 text-[17px] font-bold leading-snug text-ink hover:underline">
                        {cleanTitle(it.title)}
                      </Link>
                      <p className="mt-0.5 text-[13px] font-semibold tracking-[0.12em] text-ink-mute">
                        {it.platforms.map((p) => PLATFORM_SHORT[p]).join(" + ")}
                      </p>
                    </div>
                    {it.uploading ? (
                      <span className="inline-flex items-center gap-1.5 text-[13px] font-semibold tracking-[0.12em] text-bulb max-sm:col-span-2">
                        <span className="mark mark-working" aria-hidden /> POSTING
                      </span>
                    ) : (
                      <div className="flex gap-1.5 max-sm:col-span-2">
                        <button onClick={() => act(`now-${it.clip_id}`, () => postQueuedNow(it.clip_id))} disabled={busy !== null} className="btn btn-line btn-sm">
                          {busy === `now-${it.clip_id}` ? <LoaderCircle className="size-3.5 animate-spin" /> : <Send className="size-3.5" strokeWidth={2} />} Post now
                        </button>
                        <button
                          onClick={() => act(`rm-${it.clip_id}`, () => unqueueClip(it.clip_id))}
                          disabled={busy !== null}
                          aria-label={`Remove ${cleanTitle(it.title)} from the queue`}
                          title="Remove from queue"
                          className="btn btn-line btn-sm px-2.5"
                        >
                          {busy === `rm-${it.clip_id}` ? <LoaderCircle className="size-3.5 animate-spin" /> : <Trash2 className="size-4" strokeWidth={1.75} />}
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
      </section>
    </div>
  );
}
