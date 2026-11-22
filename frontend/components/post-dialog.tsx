"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CalendarClock, Check, ChevronDown, Copy, LoaderCircle, Send, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { CoverEditor } from "@/components/cover-editor";
import { cleanTitle } from "@/components/marquee";
import {
  type Accounts,
  type Clip,
  type ClipMeta,
  fileUrl,
  fmtSlot,
  getAccounts,
  getSchedule,
  isQueued,
  markPosted,
  type Platform,
  PLATFORMS,
  postQueuedNow,
  publishClip,
  saveClipMeta,
  tiktokCaption,
  unmarkPosted,
  unqueueClip,
  writeClipCaptions,
} from "@/lib/api";

const PLATFORM_NAME: Record<Platform, string> = { youtube: "YouTube Shorts", instagram: "Instagram Reels", tiktok: "TikTok" };
const PLATFORM_WORD: Record<Platform, string> = { youtube: "YouTube", instagram: "Instagram", tiktok: "TikTok" };

type Busy = "ai" | "post" | "queue" | "unqueue" | "now" | `mark-${Platform}` | `unmark-${Platform}`;

/** Edit the post text for one clip and send it to YouTube / Instagram. */
export function PostDialog({
  clip,
  open,
  onClose,
  onPosted,
  returnFocus,
}: {
  clip: Clip;
  open: boolean;
  onClose: () => void;
  onPosted: () => void;
  returnFocus?: React.RefObject<HTMLElement | null>;
}) {
  const reduce = useReducedMotion();
  const panel = useRef<HTMLDivElement>(null);
  const [accounts, setAccounts] = useState<Accounts | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [privacy, setPrivacy] = useState("public");
  const [caption, setCaption] = useState("");
  const [ttCaption, setTtCaption] = useState("");
  const [copied, setCopied] = useState(false);
  const [tags, setTags] = useState("");
  const [targets, setTargets] = useState<Record<Platform, boolean>>({ youtube: true, instagram: true, tiktok: false });
  const [busy, setBusy] = useState<Busy | null>(null);
  const [nextSlot, setNextSlot] = useState<string | null>(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [links, setLinks] = useState<Record<Platform, string>>({ youtube: "", instagram: "", tiktok: "" });
  const [err, setErr] = useState<string | null>(null);
  const [side, setSide] = useState<"clip" | "cover">("clip");

  function load(meta: ClipMeta) {
    setTitle(meta.youtube?.title ?? clip.title);
    setDescription(meta.youtube?.description ?? "");
    setPrivacy(meta.youtube?.privacy ?? "public");
    setCaption(meta.instagram?.caption ?? clip.title);
    setTtCaption(tiktokCaption(meta, clip.title));
    setTags((meta.hashtags ?? []).join(" "));
  }

  useEffect(() => {
    if (!open) return;
    load(clip.meta ?? {});
    setErr(null);
    getAccounts()
      .then((a) => {
        setAccounts(a);
        setTargets({ youtube: a.youtube.connected, instagram: a.instagram.connected, tiktok: !!a.tiktok?.connected });
      })
      .catch(() => setAccounts(null));
    getSchedule()
      .then((sch) => setNextSlot(sch.next_slot))
      .catch(() => setNextSlot(null));
    setLinks({ youtube: "", instagram: "", tiktok: "" });
    // focus the dialog so keyboard and screen-reader users land inside it
    requestAnimationFrame(() => panel.current?.focus());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, clip.id]);

  // Escape closes; Tab stays inside the dialog (aria-modal promises that).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") return onClose();
      if (e.key !== "Tab" || !panel.current) return;
      const items = Array.from(
        panel.current.querySelectorAll<HTMLElement>('button:not([disabled]), [href], input:not([disabled]), select, textarea, video[controls], [tabindex]:not([tabindex="-1"])'),
      );
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === panel.current)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Give focus back to whatever opened the dialog.
  const wasOpen = useRef(false);
  useEffect(() => {
    if (wasOpen.current && !open) returnFocus?.current?.focus();
    wasOpen.current = open;
  }, [open, returnFocus]);

  async function rewrite() {
    setBusy("ai");
    setErr(null);
    try {
      load(await writeClipCaptions(clip.id));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function post(when: "now" | "queue") {
    const platforms = (Object.keys(targets) as Platform[]).filter((p) => targets[p]);
    if (!platforms.length) return setErr("Pick at least one place to post.");
    setBusy(when === "now" ? "post" : "queue");
    // TikTok's inbox upload carries no caption: have it ready to paste in the TikTok app
    if (targets.tiktok) navigator.clipboard?.writeText(ttCaption).catch(() => {});
    setErr(null);
    try {
      await saveClipMeta(clip.id, {
        youtube: { title, description, privacy },
        instagram: { caption },
        tiktok: { caption: ttCaption },
        hashtags: tags.split(/[\s,]+/).filter(Boolean),
      });
      await publishClip(clip.id, platforms, when);
      onPosted();
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  /** Small actions that refresh the card behind the dialog; most keep the dialog open. */
  async function act(name: Busy, fn: () => Promise<unknown>, close = false) {
    setBusy(name);
    setErr(null);
    try {
      await fn();
      onPosted();
      if (close) onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const noAccounts = accounts && !accounts.youtube.connected && !accounts.instagram.connected && !accounts.tiktok?.connected;
  const anyTarget = PLATFORMS.some((p) => targets[p]);
  const queuedOn = (Object.keys(clip.publishes ?? {}) as Platform[]).filter((p) => isQueued(clip.publishes?.[p]));
  const queuedAt = queuedOn.length ? (clip.publishes?.[queuedOn[0]]?.scheduled_at ?? null) : null;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center bg-[rgb(9_8_7/0.78)] sm:items-center sm:p-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={onClose}
        >
          <motion.div
            ref={panel}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby={`post-h-${clip.id}`}
            onClick={(e) => e.stopPropagation()}
            initial={reduce ? false : { y: 28, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={reduce ? { opacity: 0 } : { y: 28, opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
            className="grid max-h-[94dvh] w-full max-w-4xl overflow-y-auto rounded-t-board border border-line-strong bg-felt-raised outline-none sm:rounded-board md:grid-cols-[260px_1fr]"
          >
            <div className="border-b border-line bg-felt p-4 md:border-b-0 md:border-r">
              <div role="tablist" aria-label="Preview" className="mb-3 grid grid-cols-2 rounded-board border border-line-strong p-0.5">
                {(["clip", "cover"] as const).map((t) => (
                  <button
                    key={t}
                    role="tab"
                    aria-selected={side === t}
                    onClick={() => setSide(t)}
                    className={`h-8 rounded-board text-[13px] font-bold uppercase tracking-[0.1em] transition-colors ${side === t ? "bg-ink text-felt" : "text-ink-soft hover:text-ink"}`}
                  >
                    {t}
                  </button>
                ))}
              </div>
              {side === "clip" ? (
                <div className="mx-auto max-w-[220px] md:max-w-none">
                  {clip.file_path && (
                    <video src={fileUrl(clip.file_path)} poster={clip.thumb_path ? fileUrl(clip.thumb_path) : undefined} controls playsInline className="aspect-[9/16] w-full rounded-board bg-felt-high object-cover" />
                  )}
                  <p className="mt-3 text-[15px] leading-snug text-ink-soft">{cleanTitle(clip.title)}</p>
                </div>
              ) : (
                <div className="mx-auto max-w-[220px] md:max-w-none">
                  <CoverEditor clip={clip} />
                  <p className="mt-3 text-[13px] leading-snug text-ink-mute">
                    Posting from the Instagram app: Edit cover, then Add from camera roll. Auto-posting uses this frame as the cover.
                  </p>
                </div>
              )}
            </div>

            <div className="p-5 sm:p-6">
              <div className="flex items-start justify-between gap-4">
                <h2 id={`post-h-${clip.id}`} className="text-[26px] font-bold uppercase leading-none tracking-[0.04em]">
                  Post this clip
                </h2>
                <button onClick={onClose} aria-label="Close" className="btn btn-line btn-sm px-2">
                  <X className="size-4" strokeWidth={2} />
                </button>
              </div>

              {queuedAt && (
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-board border border-line-strong px-3 py-2.5">
                  <p className="flex items-center gap-2 text-[15px] text-ink">
                    <CalendarClock className="size-4 shrink-0" strokeWidth={1.75} />
                    Queued for {fmtSlot(queuedAt)} on {queuedOn.map((p) => PLATFORM_WORD[p]).join(" and ")}
                  </p>
                  <div className="flex gap-1.5">
                    <button onClick={() => act("now", () => postQueuedNow(clip.id), true)} disabled={busy !== null} className="btn btn-line btn-sm">
                      {busy === "now" && <LoaderCircle className="size-3.5 animate-spin" />} Post now
                    </button>
                    <button onClick={() => act("unqueue", () => unqueueClip(clip.id))} disabled={busy !== null} className="btn btn-line btn-sm">
                      {busy === "unqueue" && <LoaderCircle className="size-3.5 animate-spin" />} Remove from queue
                    </button>
                  </div>
                </div>
              )}

              {noAccounts && (
                <p className="mt-4 rounded-board border border-line-strong px-3 py-2.5 text-[15px] text-ink-soft">
                  No accounts connected yet.{" "}
                  <Link href="/settings" className="text-ink underline underline-offset-4">
                    Connect an account
                  </Link>{" "}
                  first.
                </p>
              )}

              <fieldset className="mt-5">
                <legend className="label">Post to</legend>
                <div className="mt-2 grid gap-2 sm:grid-cols-3">
                  {PLATFORMS.map((p) => {
                    const ok = p === "youtube" ? accounts?.youtube.connected : p === "instagram" ? accounts?.instagram.connected : accounts?.tiktok?.connected;
                    const who =
                      p === "youtube"
                        ? accounts?.youtube.channel
                        : p === "instagram"
                          ? accounts?.instagram.username && `@${accounts.instagram.username}`
                          : (accounts?.tiktok?.name ?? "Connected");
                    const on = targets[p] && !!ok;
                    return (
                      <label
                        key={p}
                        className={`flex items-center gap-3 rounded-board border px-3 py-2.5 transition-colors ${
                          on ? "border-ink bg-felt-high" : "border-line"
                        } ${ok ? "cursor-pointer" : "cursor-not-allowed opacity-50"}`}
                      >
                        <input type="checkbox" disabled={!ok} checked={on} onChange={(e) => setTargets({ ...targets, [p]: e.target.checked })} className="size-4 accent-[var(--ink)]" />
                        <span className="min-w-0">
                          <span className="block text-[16px] font-bold uppercase tracking-[0.06em]">{PLATFORM_NAME[p]}</span>
                          <span className="block truncate text-[14px] text-ink-mute">{ok ? who : "Not connected"}</span>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
              {targets.tiktok && (
                <p className="mt-2 text-[14px] leading-snug text-ink-mute">
                  TikTok gets the clip in your TikTok inbox. Open the notification in the TikTok app, paste the TikTok caption (PeakCut copies it when you
                  post) and publish it there. TikTok allows 5 waiting uploads a day.
                </p>
              )}

              <div className="mt-6 flex items-center justify-between">
                <span className="label">Post text</span>
                <button onClick={rewrite} disabled={busy !== null} className="btn btn-line btn-sm">
                  {busy === "ai" ? <LoaderCircle className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" strokeWidth={1.75} />}
                  Rewrite with AI
                </button>
              </div>

              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div className="space-y-4">
                  <Field label="YouTube title" count={`${title.length}/100`}>
                    <input value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} className="field" />
                  </Field>
                  <Field label="YouTube description">
                    <textarea value={description} rows={5} onChange={(e) => setDescription(e.target.value)} className="field resize-y" />
                  </Field>
                  <Field label="YouTube visibility" help="New API projects can only upload private videos until Google's free audit is approved.">
                    <select value={privacy} onChange={(e) => setPrivacy(e.target.value)} className="field">
                      <option value="public">Public</option>
                      <option value="unlisted">Unlisted</option>
                      <option value="private">Private</option>
                    </select>
                  </Field>
                </div>
                <div className="space-y-4">
                  <Field label="Instagram caption" count={`${caption.length}/2200`}>
                    <textarea value={caption} rows={8} maxLength={2200} onChange={(e) => setCaption(e.target.value)} className="field resize-y" />
                  </Field>
                  <div>
                    <Field label="TikTok caption" count={`${ttCaption.length}/2200`}>
                      <textarea value={ttCaption} rows={4} maxLength={2200} onChange={(e) => setTtCaption(e.target.value)} className="field resize-y" />
                    </Field>
                    <button
                      type="button"
                      onClick={() =>
                        navigator.clipboard
                          ?.writeText(ttCaption)
                          .then(() => {
                            setCopied(true);
                            setTimeout(() => setCopied(false), 1500);
                          })
                          .catch(() => setErr("Couldn't copy. Select the text and copy it yourself."))
                      }
                      className="btn btn-line btn-sm mt-2"
                    >
                      {copied ? <Check className="size-3.5" strokeWidth={2} /> : <Copy className="size-3.5" strokeWidth={1.75} />}
                      {copied ? "Copied" : "Copy TikTok caption"}
                    </button>
                  </div>
                  <Field label="Hashtags" help="Also used as YouTube tags.">
                    <input value={tags} onChange={(e) => setTags(e.target.value)} className="field" placeholder="#gta6 #gtavi" />
                  </Field>
                </div>
              </div>

              {err && <p className="mt-4 text-[15px] text-fail">{err}</p>}

              <div className="mt-6 grid gap-2 sm:grid-cols-2">
                <button
                  onClick={() => post("queue")}
                  disabled={busy !== null || !!queuedAt || !anyTarget}
                  className="btn btn-line h-12"
                  title={queuedAt ? "Already in the queue" : undefined}
                >
                  {busy === "queue" ? <LoaderCircle className="size-4 animate-spin" /> : <CalendarClock className="size-4" strokeWidth={1.75} />}
                  {nextSlot && !queuedAt ? `Queue for ${fmtSlot(nextSlot)}` : "Add to queue"}
                </button>
                <button onClick={() => post("now")} disabled={busy !== null || !anyTarget} className="btn btn-primary h-12">
                  {busy === "post" ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" strokeWidth={2} />}
                  Post now
                </button>
              </div>

              <div className="mt-6 border-t border-line pt-4">
                <button
                  onClick={() => setManualOpen((o) => !o)}
                  aria-expanded={manualOpen}
                  className="flex w-full items-center justify-between text-left text-[15px] font-semibold uppercase tracking-[0.1em] text-ink-soft hover:text-ink"
                >
                  Posted it yourself?
                  <ChevronDown className={`size-4 transition-transform duration-200 ${manualOpen ? "rotate-180" : ""}`} strokeWidth={1.75} />
                </button>
                {manualOpen && (
                  <div className="mt-3 space-y-2">
                    <p className="text-[14px] leading-snug text-ink-mute">Mark the clip as posted so it shows as done here. PeakCut won&apos;t upload it.</p>
                    {PLATFORMS.map((p) => {
                      const s = clip.publishes?.[p];
                      const done = s?.status === "done";
                      const blocked = !!s && (s.status === "uploading" || s.status === "pending");
                      return (
                        <div key={p} className="grid items-center gap-2 rounded-board border border-line px-3 py-2.5 sm:grid-cols-[9.5rem_minmax(0,1fr)_auto]">
                          <span className="text-[15px] font-bold uppercase tracking-[0.06em]">{PLATFORM_NAME[p]}</span>
                          {done ? (
                            <>
                              <span className="flex min-w-0 items-center gap-2 text-[15px] text-ink-soft">
                                <span className="mark mark-posted" aria-hidden />
                                {s.post_url ? (
                                  <a href={s.post_url} target="_blank" rel="noreferrer" className="truncate text-ink underline underline-offset-4">
                                    Posted
                                  </a>
                                ) : (
                                  "Posted"
                                )}
                              </span>
                              <button onClick={() => act(`unmark-${p}`, () => unmarkPosted(clip.id, p))} disabled={busy !== null} className="btn btn-line btn-sm">
                                {busy === `unmark-${p}` && <LoaderCircle className="size-3.5 animate-spin" />} Unmark
                              </button>
                            </>
                          ) : (
                            <>
                              <label className="min-w-0">
                                <span className="sr-only">Link to the {PLATFORM_NAME[p]} post, optional</span>
                                <input
                                  value={links[p]}
                                  onChange={(e) => setLinks({ ...links, [p]: e.target.value })}
                                  placeholder="Link to the post (optional)"
                                  inputMode="url"
                                  disabled={blocked}
                                  className="field h-10 w-full"
                                />
                              </label>
                              <button
                                onClick={() => act(`mark-${p}`, () => markPosted(clip.id, p, links[p]))}
                                disabled={busy !== null || blocked}
                                title={blocked ? "Queued or uploading there" : undefined}
                                className="btn btn-line btn-sm h-10"
                              >
                                {busy === `mark-${p}` ? <LoaderCircle className="size-3.5 animate-spin" /> : <Check className="size-3.5" strokeWidth={2} />}
                                Mark as posted
                              </button>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Field({ label, count, help, children }: { label: string; count?: string; help?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline justify-between text-[14px] font-semibold uppercase tracking-[0.1em] text-ink-mute">
        {label}
        {count && <span className="tabular tracking-normal">{count}</span>}
      </span>
      {children}
      {help && <span className="mt-1.5 block text-[14px] leading-snug text-ink-mute">{help}</span>}
    </label>
  );
}
