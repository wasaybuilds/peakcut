"use client";

import { Check, ExternalLink, LoaderCircle, Unplug } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { LetterTitle } from "@/components/marquee";
import {
  type Accounts,
  connectInstagram,
  connectTikTok,
  connectYouTube,
  disconnectInstagram,
  disconnectTikTok,
  disconnectYouTube,
  getAccounts,
} from "@/lib/api";

export default function SettingsPage() {
  const [acc, setAcc] = useState<Accounts | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [igToken, setIgToken] = useState("");
  const [igId, setIgId] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(() => getAccounts().then(setAcc).catch((e) => setErr(e.message)), []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  // poll while a Google or TikTok sign-in tab is open
  const signingIn = !!acc?.youtube.connecting || !!acc?.tiktok?.connecting;
  useEffect(() => {
    if (!signingIn) return;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [signingIn, refresh]);

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
  const tt = acc?.tiktok;

  return (
    <div className="mx-auto max-w-[980px] px-4 pb-24 pt-6 sm:px-8 lg:pt-10">
      <section className="felt-grooves rounded-board border border-line px-5 pb-6 pt-7 sm:px-8">
        <LetterTitle text="Accounts" />
        <p className="mt-5 max-w-[62ch] text-[18px] text-ink-soft">
          Connect where your clips get posted. All three use the official free APIs, and your tokens stay on this computer.
        </p>
      </section>
      {err && <p className="mt-4 text-[15px] text-fail">{err}</p>}

      <Account
        name="YouTube Shorts"
        status={yt?.connected ? yt.channel : yt?.client_secret ? "Ready to connect" : "Needs a Google Cloud client first"}
        connected={!!yt?.connected}
        error={yt?.error}
        action={
          yt?.connected ? (
            <button onClick={() => act("yt-off", disconnectYouTube)} className="btn btn-line btn-sm">
              <Unplug className="size-4" strokeWidth={1.75} /> Disconnect
            </button>
          ) : (
            <button disabled={!yt?.client_secret || yt?.connecting || busy !== null} onClick={() => act("yt", connectYouTube)} className="btn btn-primary">
              {yt?.connecting && <LoaderCircle className="size-4 animate-spin" />}
              {yt?.connecting ? "Finish in your browser" : "Connect YouTube"}
            </button>
          )
        }
      >
        {!yt?.connected && (
          <Steps>
            <li>
              Create a project in <A href="https://console.cloud.google.com/projectcreate">Google Cloud Console</A>. Any name works.
            </li>
            <li>
              Turn on the <A href="https://console.cloud.google.com/apis/library/youtube.googleapis.com">YouTube Data API v3</A>.
            </li>
            <li>
              Open <A href="https://console.cloud.google.com/auth/branding">Google Auth Platform</A>, click Get started, pick audience <b>External</b>, then
              click <b>Publish app</b> so the sign-in doesn&apos;t expire every 7 days.
            </li>
            <li>
              Under <A href="https://console.cloud.google.com/auth/clients">Clients</A>, create a <b>Desktop app</b> client and download its JSON.
            </li>
            <li>
              Save it as <code className="rounded-[2px] bg-felt-high px-1.5 py-0.5 text-[15px] text-ink">backend\tokens\client_secret.json</code>, reload this
              page and click Connect YouTube. Google warns the app isn&apos;t verified because it&apos;s your own: choose Advanced, then Go to app.
            </li>
          </Steps>
        )}
        <p className="mt-4 text-[15px] leading-snug text-ink-mute">
          Until Google approves its free API audit, uploads from a new project stay private. Post publicly from YouTube Studio in the meantime.
        </p>
      </Account>

      <Account
        name="Instagram Reels"
        status={ig?.connected ? `@${ig.username}` : "Paste an access token"}
        connected={!!ig?.connected}
        error={ig?.error}
        action={
          ig?.connected ? (
            <button onClick={() => act("ig-off", disconnectInstagram)} className="btn btn-line btn-sm">
              <Unplug className="size-4" strokeWidth={1.75} /> Disconnect
            </button>
          ) : null
        }
      >
        {!ig?.connected && (
          <>
            <Steps>
              <li>
                In the Instagram app, open Settings, then Account type and tools, and <b>switch to a professional (Creator) account</b>. It&apos;s free.
              </li>
              <li>
                Log in to <A href="https://developers.facebook.com/apps">Meta for Developers</A> with any Facebook account and create an app with the use case{" "}
                <b>Manage messaging and content on Instagram</b>. No Facebook Page is needed.
              </li>
              <li>
                Newer apps use <b>API setup with Unified login</b>: create a business portfolio, give your Instagram account the Instagram Tester role
                under App roles, create a configuration in step 1, then add your account and generate a token in step 2.
              </li>
              <li>
                Paste the token below. Tokens starting with EAA never expire; older IGAA tokens last 60 days and PeakCut refreshes them for you. If
                PeakCut asks for it, also paste the account ID shown under your username.
              </li>
            </Steps>
            <form
              className="mt-5 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"
              onSubmit={(e) => {
                e.preventDefault();
                act("ig", () =>
                  connectInstagram(igToken, igId).then(() => {
                    setIgToken("");
                    setIgId("");
                  }),
                );
              }}
            >
              <label htmlFor="ig-token" className="sr-only">
                Instagram access token
              </label>
              <input
                id="ig-token"
                value={igToken}
                onChange={(e) => setIgToken(e.target.value)}
                placeholder="EAA... or IGAA..."
                type="password"
                autoComplete="off"
                className="field h-11 w-full sm:col-span-2"
              />
              <label htmlFor="ig-id" className="sr-only">
                Instagram account ID, optional
              </label>
              <input
                id="ig-id"
                value={igId}
                onChange={(e) => setIgId(e.target.value.replace(/\D/g, ""))}
                placeholder="Account ID (optional)"
                inputMode="numeric"
                autoComplete="off"
                className="field h-11 w-full"
              />
              <button type="submit" disabled={igToken.trim().length < 20 || busy !== null} className="btn btn-primary h-11">
                {busy === "ig" && <LoaderCircle className="size-4 animate-spin" />} Connect Instagram
              </button>
            </form>
          </>
        )}
      </Account>

      <Account
        name="TikTok"
        status={tt?.connected ? (tt.name ?? "Connected") : tt?.configured ? "Ready to connect" : "Needs a TikTok developer app first"}
        connected={!!tt?.connected}
        error={tt?.error}
        action={
          tt?.connected ? (
            <button onClick={() => act("tt-off", disconnectTikTok)} className="btn btn-line btn-sm">
              <Unplug className="size-4" strokeWidth={1.75} /> Disconnect
            </button>
          ) : (
            <button disabled={!tt?.configured || tt?.connecting || busy !== null} onClick={() => act("tt", connectTikTok)} className="btn btn-primary">
              {tt?.connecting && <LoaderCircle className="size-4 animate-spin" />}
              {tt?.connecting ? "Finish in your browser" : "Connect TikTok"}
            </button>
          )
        }
      >
        {!tt?.connected && (
          <Steps>
            <li>
              Log in to <A href="https://developers.tiktok.com/apps">TikTok for Developers</A> with your TikTok account and create an app. Use the PeakCut{" "}
              <A href="https://wasaybuilds.github.io/peakcut/terms.html">terms</A> and <A href="https://wasaybuilds.github.io/peakcut/privacy.html">privacy</A>{" "}
              pages, and tick the <b>Desktop</b> platform.
            </li>
            <li>
              Add the products <b>Login Kit</b> and <b>Content Posting API</b>, with the scopes <b>user.info.basic</b> and <b>video.upload</b>. Leave Direct Post
              off.
            </li>
            <li>
              In Login Kit, add the redirect URI <code className="rounded-[2px] bg-felt-high px-1.5 py-0.5 text-[15px] text-ink">{tt?.redirect_uri ?? "http://localhost:8788/callback/"}</code>.
            </li>
            <li>
              To test before TikTok reviews the app, open <b>Sandbox</b> and add your TikTok account as a target user. Otherwise submit the app for review.
            </li>
            <li>
              Put the client key and secret in <code className="rounded-[2px] bg-felt-high px-1.5 py-0.5 text-[15px] text-ink">.env</code> as <code className="rounded-[2px] bg-felt-high px-1.5 py-0.5 text-[15px] text-ink">TIKTOK_CLIENT_KEY</code> and <code className="rounded-[2px] bg-felt-high px-1.5 py-0.5 text-[15px] text-ink">TIKTOK_CLIENT_SECRET</code>, restart PeakCut, then click Connect TikTok.
            </li>
          </Steps>
        )}
        <p className="mt-4 text-[15px] leading-snug text-ink-mute">
          PeakCut sends clips to your TikTok inbox. Open the notification in the TikTok app, paste the caption and post it there. TikTok allows 5 waiting
          uploads a day.
        </p>
      </Account>
    </div>
  );
}

function Account({
  name,
  status,
  connected,
  error,
  action,
  children,
}: {
  name: string;
  status: string | null | undefined;
  connected: boolean;
  error?: string | null;
  action: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <section className="mt-6 rounded-board border border-line bg-felt-raised px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-[24px] font-bold uppercase leading-none tracking-[0.04em]">{name}</h2>
          <p className={`mt-1.5 inline-flex items-center gap-1.5 text-[16px] ${connected ? "text-ink" : "text-ink-mute"}`}>
            {connected && <Check className="size-4" strokeWidth={2.25} />}
            {status}
          </p>
        </div>
        {action}
      </div>
      {error && <p className="mt-3 text-[15px] text-fail">{error}</p>}
      {children}
    </section>
  );
}

function Steps({ children }: { children: React.ReactNode }) {
  return (
    <ol className="mt-5 list-decimal space-y-2 border-t border-line pl-5 pt-5 text-[16px] leading-relaxed text-ink-soft marker:font-bold marker:text-ink-mute [&_b]:font-bold [&_b]:text-ink">
      {children}
    </ol>
  );
}

function A({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
      {children}
      <ExternalLink className="size-3.5" strokeWidth={1.75} />
    </a>
  );
}
