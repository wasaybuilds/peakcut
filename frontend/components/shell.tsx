"use client";

import { CalendarClock, Plus, Settings2, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { cleanTitle } from "@/components/marquee";
import { type Accounts, getAccounts, getSchedule, type Job, listJobs } from "@/lib/api";

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <Link href="/" aria-label="PeakCut home" className={`inline-flex items-center gap-1 text-[22px] ${className}`}>
      <span className="tile">Peak</span>
      <span className="tile bg-bulb">Cut</span>
    </Link>
  );
}

function JobRow({ job, active }: { job: Job; active: boolean }) {
  const running = job.status === "running";
  const n = job.clip_count;
  const label = running
    ? `${Math.round(job.progress * 100)}%`
    : job.status === "queued"
      ? "QUEUED"
      : job.status === "failed"
        ? "FAILED"
        : n === undefined
          ? "DONE" // older API without clip counts
          : `${n} ${n === 1 ? "CLIP" : "CLIPS"}`;
  return (
    <Link
      href={`/jobs/${job.id}`}
      aria-current={active ? "page" : undefined}
      className={`group flex items-center justify-between gap-3 rounded-board px-3 py-2 transition-colors ${
        active ? "bg-felt-high text-ink" : "text-ink-soft hover:bg-felt-raised hover:text-ink"
      }`}
    >
      <span className="min-w-0 truncate text-[16px] leading-snug">{cleanTitle(job.title) || "Fetching title…"}</span>
      <span
        className={`tabular inline-flex shrink-0 items-center gap-1.5 text-[13px] font-semibold tracking-[0.08em] ${
          running ? "text-bulb" : job.status === "failed" ? "text-fail" : "text-ink-mute"
        }`}
      >
        {running && <span className="bulb bulb-on bulb-head w-2" aria-hidden />}
        {label}
      </span>
    </Link>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [accounts, setAccounts] = useState<Accounts | null>(null);
  const [queued, setQueued] = useState<number | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const js = await listJobs();
        if (!alive) return;
        setJobs(js);
        setOffline(false);
        const busy = js.some((j) => j.status === "running" || j.status === "queued");
        timer = setTimeout(tick, busy ? 2500 : 8000);
      } catch {
        if (!alive) return;
        setOffline(true);
        timer = setTimeout(tick, 5000);
      }
    };
    tick();
    getAccounts().then(setAccounts).catch(() => {});
    getSchedule()
      .then((s) => setQueued(s.queue.length))
      .catch(() => {});
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [path]);

  const activeId = path.startsWith("/jobs/") ? Number(path.split("/")[2]) : null;
  const connected = [
    accounts?.youtube.connected && "YT",
    accounts?.instagram.connected && "IG",
    accounts?.tiktok?.connected && "TT",
  ].filter(Boolean);

  return (
    <div className="min-h-[100dvh] lg:grid lg:grid-cols-[272px_1fr]">
      {/* phone / tablet: top bar */}
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-line bg-felt/95 px-4 backdrop-blur lg:hidden">
        <Wordmark />
        <div className="flex items-center gap-2">
          <Link href="/queue" className="btn btn-line btn-sm" aria-label="Queue">
            <CalendarClock className="size-4" strokeWidth={1.75} />
          </Link>
          <Link href="/settings" className="btn btn-line btn-sm" aria-label="Accounts">
            <Settings2 className="size-4" strokeWidth={1.75} />
          </Link>
          <Link href="/" className="btn btn-primary btn-sm">
            <Plus className="size-4" strokeWidth={2} /> New
          </Link>
        </div>
      </header>

      {/* desktop: rail */}
      <aside className="sticky top-0 hidden h-[100dvh] flex-col border-r border-line bg-felt-rail px-4 py-6 lg:flex">
        <Wordmark className="px-1" />
        <Link href="/" className="btn btn-line mt-7 w-full">
          <Plus className="size-4" strokeWidth={2} /> New video
        </Link>

        <nav aria-label="Jobs" className="mt-8 flex min-h-0 flex-1 flex-col">
          <p className="label px-3 pb-2">Jobs</p>
          <div className="-mx-1 flex-1 space-y-0.5 overflow-y-auto px-1">
            {jobs === null && !offline && Array.from({ length: 4 }, (_, i) => <div key={i} className="mx-3 my-3 h-3 animate-pulse rounded-board bg-felt-high" />)}
            {jobs?.length === 0 && <p className="px-3 text-[15px] text-ink-mute">Your videos show up here.</p>}
            {jobs?.map((j) => <JobRow key={j.id} job={j} active={j.id === activeId} />)}
          </div>
        </nav>

        <div className="mt-4 space-y-2 border-t border-line pt-4">
          {offline && (
            <p className="flex items-start gap-2 px-3 text-[14px] leading-snug text-fail">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" strokeWidth={1.75} />
              API offline. Start it with scripts\dev.ps1.
            </p>
          )}
          <Link
            href="/queue"
            aria-current={path === "/queue" ? "page" : undefined}
            className={`flex items-center justify-between rounded-board px-3 py-2 transition-colors ${
              path === "/queue" ? "bg-felt-high text-ink" : "text-ink-soft hover:bg-felt-raised hover:text-ink"
            }`}
          >
            <span className="inline-flex items-center gap-2">
              <CalendarClock className="size-4" strokeWidth={1.75} /> Queue
            </span>
            <span className="tabular text-[13px] font-semibold tracking-[0.08em] text-ink-mute">{queued ? `${queued} QUEUED` : "EMPTY"}</span>
          </Link>
          <Link
            href="/settings"
            aria-current={path === "/settings" ? "page" : undefined}
            className={`flex items-center justify-between rounded-board px-3 py-2 transition-colors ${
              path === "/settings" ? "bg-felt-high text-ink" : "text-ink-soft hover:bg-felt-raised hover:text-ink"
            }`}
          >
            <span className="inline-flex items-center gap-2">
              <Settings2 className="size-4" strokeWidth={1.75} /> Accounts
            </span>
            <span className="text-[13px] font-semibold tracking-[0.08em] text-ink-mute">
              {connected.length ? connected.join(" + ").toUpperCase() : "NOT SET UP"}
            </span>
          </Link>
        </div>
      </aside>

      <main className="min-w-0">{children}</main>
    </div>
  );
}
