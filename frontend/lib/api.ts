// Same-origin by default: next.config.ts forwards /api, /files and /health to the backend,
// so the app works from a phone on the same Wi-Fi. Set NEXT_PUBLIC_API_URL to bypass the proxy.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export type ProviderStatus = {
  label: string;
  configured: boolean;
  model: string;
  signup_url: string;
};

export type Health = {
  ok: boolean;
  ffmpeg: { found: boolean; version: string | null; encoder: string | null };
  providers: Record<string, ProviderStatus>;
  llm_order: string;
};

export type Job = {
  id: number;
  source_url: string;
  video_id: string | null;
  title: string | null;
  channel: string | null;
  duration: number | null;
  status: "queued" | "running" | "done" | "failed";
  step: string | null;
  progress: number;
  error: string | null;
  created_at: string;
  clip_count?: number; // only on the jobs list
  options: {
    clip_count?: number;
    layout?: string;
    caption_style?: string;
    analyzed?: [number, number];
    facecam?: Box | null;
    facecam_frame?: string;
  };
};

export type Box = { x: number; y: number; w: number; h: number };

export const LAYOUTS: { id: string; label: string; hint: string }[] = [
  { id: "zoom_fill", label: "Zoom", hint: "Gameplay zoomed in, blurred background" },
  { id: "facecam_split", label: "Face cam", hint: "Streamer's cam on top, gameplay below" },
  { id: "blur_fill", label: "Full frame", hint: "Whole picture, blurred bars" },
  { id: "center_crop", label: "Fill", hint: "Fills the screen, sides cut off" },
];

export type Clip = {
  id: number;
  job_id: number;
  start: number;
  end: number;
  score: number;
  title: string;
  hook_text: string;
  reason: string;
  layout: string;
  caption_style: string;
  file_path: string | null;
  thumb_path: string | null;
  meta: ClipMeta;
  publishes?: Partial<Record<Platform, PublishState>>;
};

export type Platform = "youtube" | "instagram";

export type Cover = { path: string; at: number; text: string };

export type ClipMeta = {
  cover?: Cover | null;
  hashtags?: string[];
  youtube?: { title: string; description: string; tags?: string[]; privacy?: "public" | "unlisted" | "private" };
  instagram?: { caption: string };
};

export type PublishState = {
  id: number;
  platform: Platform;
  status: "pending" | "uploading" | "done" | "failed";
  post_url: string | null;
  error: string | null;
  scheduled_at?: string | null; // set while waiting for a queue slot
};

/** Queued for a later slot, as opposed to uploading right now. */
export const isQueued = (p?: PublishState | null) => !!p && p.status === "pending" && !!p.scheduled_at;

export type QueueItem = {
  clip_id: number;
  job_id: number;
  title: string;
  thumb_path: string | null;
  scheduled_at: string;
  platforms: Platform[];
  uploading: boolean; // its slot came and the upload is running
};

export type Schedule = { times: string[]; queue: QueueItem[]; next_slot: string };

export type Accounts = {
  youtube: { client_secret: boolean; connected: boolean; channel: string | null; connecting: boolean; error: string | null };
  instagram: { connected: boolean; username: string | null; error: string | null };
};

export const getAccounts = () => req<Accounts>("/api/accounts");
export const connectYouTube = () => req<{ ok: boolean; message: string }>("/api/accounts/youtube/connect", { method: "POST" });
export const disconnectYouTube = () => req<{ ok: boolean }>("/api/accounts/youtube", { method: "DELETE" });
export const connectInstagram = (access_token: string, account_id?: string) =>
  req<{ ok: boolean; username: string }>("/api/accounts/instagram", {
    method: "POST",
    body: JSON.stringify({ access_token, account_id: account_id?.trim() || null }),
  });
export const disconnectInstagram = () => req<{ ok: boolean }>("/api/accounts/instagram", { method: "DELETE" });

export const writeJobCaptions = (jobId: number) => req<{ ok: boolean }>(`/api/jobs/${jobId}/captions`, { method: "POST" });
export const writeClipCaptions = (clipId: number) => req<ClipMeta>(`/api/clips/${clipId}/captions`, { method: "POST" });
export const saveClipMeta = (
  clipId: number,
  body: { youtube: { title: string; description: string; privacy: string }; instagram: { caption: string }; hashtags: string[] },
) => req<ClipMeta>(`/api/clips/${clipId}/meta`, { method: "PUT", body: JSON.stringify(body) });
export const makeCover = (clipId: number, body: { at?: number; text?: string } = {}) =>
  req<Cover>(`/api/clips/${clipId}/cover`, { method: "POST", body: JSON.stringify(body) });
export const publishClip = (clipId: number, platforms: Platform[], when: "now" | "queue" = "now") =>
  req<{ ok: boolean; queued: number[]; scheduled_at: string | null }>(`/api/clips/${clipId}/publish`, {
    method: "POST",
    body: JSON.stringify({ platforms, when }),
  });
export const unqueueClip = (clipId: number) => req<{ ok: boolean }>(`/api/clips/${clipId}/queue`, { method: "DELETE" });
export const postQueuedNow = (clipId: number) => req<{ ok: boolean }>(`/api/clips/${clipId}/queue/now`, { method: "POST" });
export const markPosted = (clipId: number, platform: Platform, url?: string) =>
  req<{ ok: boolean }>(`/api/clips/${clipId}/posted`, { method: "POST", body: JSON.stringify({ platform, url: url?.trim() || null }) });
export const unmarkPosted = (clipId: number, platform: Platform) =>
  req<{ ok: boolean }>(`/api/clips/${clipId}/posted/${platform}`, { method: "DELETE" });
export const getSchedule = () => req<Schedule>("/api/schedule");
export const saveScheduleTimes = (times: string[]) => req<Schedule>("/api/schedule", { method: "PUT", body: JSON.stringify({ times }) });

/** "Today", "Tomorrow" or "Mon 24 Nov", in this device's time zone. */
export function fmtDay(iso: string) {
  const d = new Date(iso);
  const day = new Date(d);
  day.setHours(0, 0, 0, 0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((day.getTime() - today.getTime()) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
}

export const fmtClock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** "Today 17:00", "Tomorrow 12:00" or "Mon 24 Nov 21:00". */
export const fmtSlot = (iso: string) => `${fmtDay(iso)} ${fmtClock(iso)}`;

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let msg = `API returned ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export const getHealth = () => req<Health>("/health");
export const listJobs = () => req<Job[]>("/api/jobs");
export const getJob = (id: number | string) => req<{ job: Job; clips: Clip[] }>(`/api/jobs/${id}`);
export const deleteJob = (id: number | string) => req<{ ok: boolean }>(`/api/jobs/${id}`, { method: "DELETE" });
export const retryJob = (id: number | string) => req<{ ok: boolean }>(`/api/jobs/${id}/retry`, { method: "POST" });
export const createJob = (body: { url: string; clip_count?: number; layout?: string; caption_style?: string }) =>
  req<Job>("/api/jobs", { method: "POST", body: JSON.stringify(body) });

export const rerenderJob = (
  id: number | string,
  body: { layout: string; caption_style?: string; facecam?: Box; redetect?: boolean },
) => req<{ ok: boolean }>(`/api/jobs/${id}/rerender`, { method: "POST", body: JSON.stringify(body) });

export const fileUrl = (rel: string) => `${API_URL}/files/${rel}`;

export function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const ss = Math.floor(s % 60).toString().padStart(2, "0");
  return h ? `${h}:${(m % 60).toString().padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}
