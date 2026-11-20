"use client";

import { ArrowLeft, CircleCheck, ExternalLink, LoaderCircle, Unplug } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { type Accounts, connectInstagram, connectYouTube, disconnectInstagram, disconnectYouTube, getAccounts } from "@/lib/api";

export default function SettingsPage() {
  const [acc, setAcc] = useState<Accounts | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [igToken, setIgToken] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(() => getAccounts().then(setAcc).catch((e) => setErr(e.message)), []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  // poll while the Google sign-in window is open
  useEffect(() => {
    if (!acc?.youtube.connecting) return;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [acc?.youtube.connecting, refresh]);

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

  const yt = acc?.youtube;
  const ig = acc?.instagram;

  return (
    <main className="mx-auto min-h-dvh max-w-3xl px-4 pb-24 sm:px-6">
      <header className="py-5">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground">
          <ArrowLeft className="size-4" /> Home
        </Link>
      </header>
      <h1 className="text-2xl font-semibold tracking-tight">Accounts</h1>
      <p className="mt-1 text-sm text-muted">Connect where clips get posted. Both use the official free APIs.</p>
      {err && <p className="mt-4 rounded-lg border border-warn/30 bg-warn/5 px-3 py-2 text-sm text-warn">{err}</p>}

      {/* YouTube */}
      <section className="mt-8 rounded-2xl border border-border bg-surface p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="font-medium">YouTube Shorts</h2>
            <p className="text-sm text-muted">
              {yt?.connected ? (
                <span className="inline-flex items-center gap-1.5 text-ok">
                  <CircleCheck className="size-4" /> {yt.channel}
                </span>
              ) : yt?.client_secret ? (
                "Ready to connect"
              ) : (
                "Setup needed (steps below)"
              )}
            </p>
          </div>
          {yt?.connected ? (
            <button onClick={() => act("yt-off", disconnectYouTube)} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm">
              <Unplug className="size-4" /> Disconnect
            </button>
          ) : (
            <button
              disabled={!yt?.client_secret || yt?.connecting || busy !== null}
              onClick={() => act("yt", connectYouTube)}
              className="inline-flex items-center gap-2 rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background active:scale-[0.97] disabled:opacity-40"
            >
              {yt?.connecting ? <LoaderCircle className="size-4 animate-spin" /> : null}
              {yt?.connecting ? "Finish in the browser tab…" : "Connect YouTube"}
            </button>
          )}
        </div>
        {yt?.error && <p className="mt-3 text-xs text-warn">{yt.error}</p>}
        {!yt?.connected && (
          <ol className="mt-4 list-decimal space-y-1.5 pl-5 text-sm text-muted">
            <li>
              Open{" "}
              <A href="https://console.cloud.google.com/projectcreate">Google Cloud Console</A> and create a project (any name).
            </li>
            <li>
              Enable <A href="https://console.cloud.google.com/apis/library/youtube.googleapis.com">YouTube Data API v3</A>.
            </li>
            <li>
              <A href="https://console.cloud.google.com/auth/branding">Google Auth Platform</A> → Get started: app name, your email, Audience
              <b className="text-foreground"> External</b>. Then under Audience click <b className="text-foreground">Publish app</b> (so the login
              doesn&apos;t expire every 7 days).
            </li>
            <li>
              <A href="https://console.cloud.google.com/auth/clients">Clients</A> → Create client → type <b className="text-foreground">Desktop app</b> →
              Download JSON.
            </li>
            <li>
              Save it as <code className="rounded bg-surface-2 px-1 font-mono text-xs text-foreground">backend\tokens\client_secret.json</code>, refresh
              this page and click Connect YouTube. Google will warn &quot;app isn&apos;t verified&quot; (it&apos;s your own app): click Advanced → Go to
              app.
            </li>
          </ol>
        )}
      </section>

      {/* Instagram */}
      <section className="mt-5 rounded-2xl border border-border bg-surface p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="font-medium">Instagram Reels</h2>
            <p className="text-sm text-muted">
              {ig?.connected ? (
                <span className="inline-flex items-center gap-1.5 text-ok">
                  <CircleCheck className="size-4" /> @{ig.username}
                </span>
              ) : (
                "Paste an access token (steps below)"
              )}
            </p>
          </div>
          {ig?.connected && (
            <button onClick={() => act("ig-off", disconnectInstagram)} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm">
              <Unplug className="size-4" /> Disconnect
            </button>
          )}
        </div>
        {ig?.error && <p className="mt-3 text-xs text-warn">{ig.error}</p>}
        {!ig?.connected && (
          <>
            <ol className="mt-4 list-decimal space-y-1.5 pl-5 text-sm text-muted">
              <li>
                In the Instagram app: Settings → Account type and tools → <b className="text-foreground">Switch to professional account</b> (Creator).
                Free.
              </li>
              <li>
                Go to <A href="https://developers.facebook.com/apps">Meta for Developers</A>, log in with Facebook and create an app with the use case{" "}
                <b className="text-foreground">Manage messaging &amp; content on Instagram</b>.
              </li>
              <li>
                In the app: Instagram → <b className="text-foreground">API setup with Instagram login</b> → Generate access tokens → Add account → log in
                with your Instagram.
              </li>
              <li>Click Generate token next to your account, copy it and paste it here.</li>
            </ol>
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <input
                value={igToken}
                onChange={(e) => setIgToken(e.target.value)}
                placeholder="IGAA…"
                type="password"
                autoComplete="off"
                className="h-10 flex-1 rounded-lg border border-border bg-surface-2 px-3 text-sm outline-none focus:border-muted"
              />
              <button
                disabled={igToken.trim().length < 20 || busy !== null}
                onClick={() => act("ig", () => connectInstagram(igToken).then(() => setIgToken("")))}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-foreground px-4 text-sm font-medium text-background active:scale-[0.97] disabled:opacity-40"
              >
                {busy === "ig" ? <LoaderCircle className="size-4 animate-spin" /> : null} Connect
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

function A({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-foreground underline decoration-border underline-offset-2 hover:decoration-foreground">
      {children}
      <ExternalLink className="size-3" />
    </a>
  );
}
