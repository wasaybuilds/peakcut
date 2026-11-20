export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export type ClipMeta = {
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
};

export type Accounts = {
  youtube: { client_secret: boolean; connected: boolean; channel: string | null; connecting: boolean; error: string | null };
  instagram: { connected: boolean; username: string | null; error: string | null };
};

export const getAccounts = () => req<Accounts>("/api/accounts");
export const connectYouTube = () => req<{ ok: boolean; message: string }>("/api/accounts/youtube/connect", { method: "POST" });
export const disconnectYouTube = () => req<{ ok: boolean }>("/api/accounts/youtube", { method: "DELETE" });
export const connectInstagram = (access_token: string) =>
  req<{ ok: boolean; username: string }>("/api/accounts/instagram", { method: "POST", body: JSON.stringify({ access_token }) });
export const disconnectInstagram = () => req<{ ok: boolean }>("/api/accounts/instagram", { method: "DELETE" });

export const writeJobCaptions = (jobId: number) => req<{ ok: boolean }>(`/api/jobs/${jobId}/captions`, { method: "POST" });
export const writeClipCaptions = (clipId: number) => req<ClipMeta>(`/api/clips/${clipId}/captions`, { method: "POST" });
export const saveClipMeta = (
  clipId: number,
  body: { youtube: { title: string; description: string; privacy: string }; instagram: { caption: string }; hashtags: string[] },
) => req<ClipMeta>(`/api/clips/${clipId}/meta`, { method: "PUT", body: JSON.stringify(body) });
export const publishClip = (clipId: number, platforms: Platform[]) =>
  req<{ ok: boolean; queued: number[] }>(`/api/clips/${clipId}/publish`, { method: "POST", body: JSON.stringify({ platforms }) });

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
