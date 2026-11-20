"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { LoaderCircle, Send, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { CoverEditor } from "@/components/cover-editor";
import { cleanTitle } from "@/components/marquee";
import {
  type Accounts,
  type Clip,
  type ClipMeta,
  fileUrl,
  getAccounts,
  type Platform,
  publishClip,
  saveClipMeta,
  writeClipCaptions,
} from "@/lib/api";

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
  const [tags, setTags] = useState("");
  const [targets, setTargets] = useState<Record<Platform, boolean>>({ youtube: true, instagram: true });
  const [busy, setBusy] = useState<null | "ai" | "post">(null);
  const [err, setErr] = useState<string | null>(null);
  const [side, setSide] = useState<"clip" | "cover">("clip");

  function load(meta: ClipMeta) {
    setTitle(meta.youtube?.title ?? clip.title);
    setDescription(meta.youtube?.description ?? "");
    setPrivacy(meta.youtube?.privacy ?? "public");
    setCaption(meta.instagram?.caption ?? clip.title);
    setTags((meta.hashtags ?? []).join(" "));
  }

  useEffect(() => {
    if (!open) return;
    load(clip.meta ?? {});
    setErr(null);
    getAccounts()
      .then((a) => {
        setAccounts(a);
        setTargets({ youtube: a.youtube.connected, instagram: a.instagram.connected });
      })
      .catch(() => setAccounts(null));
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

  async function post() {
    const platforms = (Object.keys(targets) as Platform[]).filter((p) => targets[p]);
    if (!platforms.length) return setErr("Pick YouTube, Instagram or both.");
    setBusy("post");
    setErr(null);
    try {
      await saveClipMeta(clip.id, {
        youtube: { title, description, privacy },
        instagram: { caption },
        hashtags: tags.split(/[\s,]+/).filter(Boolean),
      });
      await publishClip(clip.id, platforms);
      onPosted();
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const noAccounts = accounts && !accounts.youtube.connected && !accounts.instagram.connected;

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

              {noAccounts && (
                <p className="mt-4 rounded-board border border-line-strong px-3 py-2.5 text-[15px] text-ink-soft">
                  No accounts connected yet.{" "}
                  <Link href="/settings" className="text-ink underline underline-offset-4">
                    Connect YouTube or Instagram
                  </Link>{" "}
                  first.
                </p>
              )}

              <fieldset className="mt-5">
                <legend className="label">Post to</legend>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {(["youtube", "instagram"] as Platform[]).map((p) => {
                    const ok = p === "youtube" ? accounts?.youtube.connected : accounts?.instagram.connected;
                    const who = p === "youtube" ? accounts?.youtube.channel : accounts?.instagram.username && `@${accounts.instagram.username}`;
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
                          <span className="block text-[16px] font-bold uppercase tracking-[0.06em]">{p === "youtube" ? "YouTube Shorts" : "Instagram Reels"}</span>
                          <span className="block truncate text-[14px] text-ink-mute">{ok ? who : "Not connected"}</span>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>

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
                  <Field label="Hashtags" help="Also used as YouTube tags.">
                    <input value={tags} onChange={(e) => setTags(e.target.value)} className="field" placeholder="#gta6 #gtavi" />
                  </Field>
                </div>
              </div>

              {err && <p className="mt-4 text-[15px] text-fail">{err}</p>}

              <button onClick={post} disabled={busy !== null || (!targets.youtube && !targets.instagram)} className="btn btn-primary mt-6 h-12 w-full">
                {busy === "post" ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" strokeWidth={2} />}
                Post now
              </button>
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
