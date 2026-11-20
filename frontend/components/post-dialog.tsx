"use client";

import { AnimatePresence, motion } from "framer-motion";
import { LoaderCircle, Send, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  type Accounts,
  type Clip,
  type ClipMeta,
  getAccounts,
  type Platform,
  publishClip,
  saveClipMeta,
  writeClipCaptions,
} from "@/lib/api";

const field =
  "w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-muted";

/** Edit the post text for one clip and send it to YouTube / Instagram. */
export function PostDialog({ clip, open, onClose, onPosted }: { clip: Clip; open: boolean; onClose: () => void; onPosted: () => void }) {
  const [accounts, setAccounts] = useState<Accounts | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [privacy, setPrivacy] = useState("public");
  const [caption, setCaption] = useState("");
  const [tags, setTags] = useState("");
  const [targets, setTargets] = useState<Record<Platform, boolean>>({ youtube: true, instagram: true });
  const [busy, setBusy] = useState<null | "ai" | "post">(null);
  const [err, setErr] = useState<string | null>(null);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, clip.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

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
    if (!platforms.length) return setErr("Pick at least one platform.");
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
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm sm:items-center sm:p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Post clip"
            onClick={(e) => e.stopPropagation()}
            initial={{ y: 24, opacity: 0, scale: 0.98 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 24, opacity: 0, scale: 0.98 }}
            transition={{ type: "spring", duration: 0.35, bounce: 0.1 }}
            className="max-h-[92dvh] w-full max-w-xl overflow-y-auto rounded-t-2xl border border-border bg-surface p-5 sm:rounded-2xl"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-semibold tracking-tight">Post this clip</h2>
                <p className="mt-0.5 line-clamp-1 text-xs text-muted">{clip.title}</p>
              </div>
              <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-muted hover:text-foreground">
                <X className="size-5" />
              </button>
            </div>

            {noAccounts && (
              <p className="mt-4 rounded-lg border border-warn/30 bg-warn/5 px-3 py-2 text-sm text-warn">
                No accounts connected yet.{" "}
                <Link href="/settings" className="underline">
                  Connect YouTube or Instagram
                </Link>
              </p>
            )}

            <div className="mt-4 flex gap-2">
              {(["youtube", "instagram"] as Platform[]).map((p) => {
                const ok = p === "youtube" ? accounts?.youtube.connected : accounts?.instagram.connected;
                const who = p === "youtube" ? accounts?.youtube.channel : accounts?.instagram.username && `@${accounts.instagram.username}`;
                return (
                  <label
                    key={p}
                    className={`flex flex-1 cursor-pointer items-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition-colors ${
                      targets[p] ? "border-foreground/40 bg-surface-2" : "border-border"
                    } ${ok ? "" : "cursor-not-allowed opacity-50"}`}
                  >
                    <input
                      type="checkbox"
                      disabled={!ok}
                      checked={targets[p] && !!ok}
                      onChange={(e) => setTargets({ ...targets, [p]: e.target.checked })}
                      className="accent-[var(--accent)]"
                    />
                    <span className="min-w-0">
                      <span className="block font-medium">{p === "youtube" ? "YouTube Shorts" : "Instagram Reels"}</span>
                      <span className="block truncate text-xs text-muted">{ok ? who : "not connected"}</span>
                    </span>
                  </label>
                );
              })}
            </div>

            <div className="mt-5 flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wider text-muted">Post text</span>
              <button
                onClick={rewrite}
                disabled={busy !== null}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs active:scale-[0.97] disabled:opacity-50"
              >
                {busy === "ai" ? <LoaderCircle className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5 text-accent" />}
                Rewrite with AI
              </button>
            </div>

            <div className="mt-2 space-y-3">
              <label className="block">
                <span className="mb-1 flex justify-between text-xs text-muted">
                  YouTube title <span className="tabular-nums">{title.length}/100</span>
                </span>
                <input value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} className={field} />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs text-muted">YouTube description</span>
                <textarea value={description} rows={4} onChange={(e) => setDescription(e.target.value)} className={field} />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs text-muted">YouTube visibility</span>
                <select value={privacy} onChange={(e) => setPrivacy(e.target.value)} className={field}>
                  <option value="public">Public</option>
                  <option value="unlisted">Unlisted</option>
                  <option value="private">Private</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1 flex justify-between text-xs text-muted">
                  Instagram caption <span className="tabular-nums">{caption.length}/2200</span>
                </span>
                <textarea value={caption} rows={5} maxLength={2200} onChange={(e) => setCaption(e.target.value)} className={field} />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs text-muted">Hashtags (YouTube tags)</span>
                <input value={tags} onChange={(e) => setTags(e.target.value)} className={field} placeholder="#gta6 #gtavi ..." />
              </label>
            </div>

            {err && <p className="mt-3 text-sm text-warn">{err}</p>}

            <button
              onClick={post}
              disabled={busy !== null || (!targets.youtube && !targets.instagram)}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-foreground py-3 font-medium text-background active:scale-[0.98] disabled:opacity-50"
            >
              {busy === "post" ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}
              Post now
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
