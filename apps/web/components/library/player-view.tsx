"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import {
  tokenQuery,
  type EntitlementDetail,
} from "@/components/library/library-types";
import { API, apiJson, ClientApiError, formatDuration } from "@/lib/client-api";

const SPEEDS = [0.75, 1, 1.5] as const;
const SAVE_EVERY_MS = 10_000;

export function PlayerView({
  entitlementId,
  orderToken,
}: {
  entitlementId: string;
  orderToken: string | null;
}) {
  const q = tokenQuery(orderToken);
  const [detail, setDetail] = useState<EntitlementDetail | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [completed, setCompleted] = useState<number[]>([]);
  const audio = useRef<HTMLAudioElement>(null);
  const resumeAt = useRef(0);
  const lastSave = useRef(0);

  const save = useCallback(
    async (position: number, offset: number, done?: number) => {
      try {
        await apiJson(`/library/entitlements/${entitlementId}/progress${q}`, {
          method: "PUT",
          json: {
            position,
            offset_seconds: Math.max(0, Math.floor(offset)),
            ...(done === undefined ? {} : { completed_position: done }),
          },
        });
      } catch {
        /* losing a progress write must never interrupt listening */
      }
    },
    [entitlementId, q],
  );

  useEffect(() => {
    (async () => {
      try {
        const info = await apiJson<EntitlementDetail>(
          `/library/entitlements/${entitlementId}${q}`,
        );
        setDetail(info);
        const start = Math.min(
          info.progress.position,
          Math.max(0, info.audio_chapters.length - 1),
        );
        setIndex(start);
        resumeAt.current = info.progress.offset_seconds;
        setCompleted(info.progress.completed);
      } catch (caught) {
        if (
          caught instanceof ClientApiError &&
          caught.status === 401 &&
          !orderToken
        ) {
          window.location.assign(
            `/konto?next=${encodeURIComponent(`/konto/odtwarzacz/${entitlementId}`)}`,
          );
          return;
        }
        setError(
          caught instanceof Error
            ? caught.message
            : "Nie udało się otworzyć audiobooka.",
        );
      }
    })();
  }, [entitlementId, q, orderToken]);

  const chapter = detail?.audio_chapters[index];
  const src = chapter?.file_id
    ? `${API}/library/entitlements/${entitlementId}/audio/${chapter.file_id}${q}`
    : null;

  useEffect(() => {
    const element = audio.current;
    if (element) element.playbackRate = speed;
  }, [speed, src]);

  function select(next: number) {
    if (!detail) return;
    const bounded = Math.max(
      0,
      Math.min(next, detail.audio_chapters.length - 1),
    );
    resumeAt.current = 0;
    setCurrent(0);
    setIndex(bounded);
    void save(bounded, 0);
  }

  function skip(delta: number) {
    const element = audio.current;
    if (!element) return;
    element.currentTime = Math.max(
      0,
      Math.min(element.duration || 0, element.currentTime + delta),
    );
  }

  async function toggle() {
    const element = audio.current;
    if (!element) return;
    if (element.paused) {
      try {
        await element.play();
      } catch {
        setError("Przeglądarka zablokowała odtwarzanie. Spróbuj ponownie.");
      }
    } else {
      element.pause();
    }
  }

  if (error)
    return (
      <Shell>
        <Alert variant="error">{error}</Alert>
        <Link className="mt-4 inline-block underline" href="/konto/biblioteka">
          Wróć do biblioteki
        </Link>
      </Shell>
    );
  if (!detail)
    return (
      <Shell>
        <p role="status" aria-busy="true">
          Otwieramy audiobook…
        </p>
      </Shell>
    );
  if (detail.audio_chapters.length === 0 || !chapter)
    return (
      <Shell>
        <h1 className="font-display text-title">{detail.title}</h1>
        <p className="mt-3">
          Nagrania nie zostały jeszcze dodane do tego audiobooka.
        </p>
      </Shell>
    );

  const totalSeconds = detail.audio_chapters.reduce(
    (s, c) => s + c.length_seconds,
    0,
  );
  const remaining = Math.max(0, (duration || chapter.length_seconds) - current);

  return (
    <div className="min-h-screen bg-gradient-to-b from-ink to-accent-action/70 text-surface">
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto max-w-page-shell px-5 py-8 focus:outline-none"
      >
        <div className="flex items-center justify-between">
          <Link
            href="/konto/biblioteka"
            aria-label="Wróć do biblioteki"
            className="inline-flex min-h-touch min-w-touch items-center justify-center rounded-pill border border-surface/30"
          >
            ‹
          </Link>
          <Link
            href="/konto/biblioteka"
            className="min-h-touch py-3 text-body-small text-surface/80 underline"
          >
            Twoja biblioteka
          </Link>
        </div>
        <div className="mt-8 grid gap-8 md:grid-cols-[minmax(0,20rem)_1fr]">
          <div
            aria-hidden="true"
            className="aspect-product-image rounded-card bg-gradient-to-br from-accent to-accent-action"
          />
          <div className="min-w-0">
            <p className="text-caption font-bold tracking-wide">AUDIOBOOK</p>
            <h1 className="mt-2 font-display text-title">{detail.title}</h1>
            {detail.author ? (
              <p className="mt-2 font-body text-body text-surface/80">
                Czyta {detail.author}
              </p>
            ) : null}
            <p className="mt-4 inline-block rounded-pill bg-surface/10 px-4 py-2 text-body-small font-bold">
              Rozdział {index + 1} · {chapter.title}
            </p>
            {src ? (
              <audio
                key={src}
                ref={audio}
                src={src}
                preload="metadata"
                onLoadedMetadata={(event) => {
                  const element = event.currentTarget;
                  setDuration(element.duration);
                  if (
                    resumeAt.current > 0 &&
                    resumeAt.current < element.duration
                  ) {
                    element.currentTime = resumeAt.current;
                    setCurrent(resumeAt.current);
                  }
                  resumeAt.current = 0;
                  element.playbackRate = speed;
                }}
                onPlay={() => setPlaying(true)}
                onPause={() => {
                  setPlaying(false);
                  void save(index, audio.current?.currentTime ?? 0);
                }}
                onTimeUpdate={(event) => {
                  const element = event.currentTarget;
                  setCurrent(element.currentTime);
                  const now = Date.now();
                  if (now - lastSave.current > SAVE_EVERY_MS) {
                    lastSave.current = now;
                    void save(index, element.currentTime);
                  }
                }}
                onEnded={() => {
                  setCompleted((value) =>
                    value.includes(index)
                      ? value
                      : [...value, index].sort((a, b) => a - b),
                  );
                  void save(index, 0, index);
                  if (index < detail.audio_chapters.length - 1) {
                    select(index + 1);
                    window.setTimeout(
                      () => void audio.current?.play().catch(() => undefined),
                      200,
                    );
                  } else setPlaying(false);
                }}
              />
            ) : (
              <p className="mt-4">Nagranie tego rozdziału jest niedostępne.</p>
            )}
            <div className="mt-6">
              <label className="sr-only" htmlFor="seek">
                Pozycja w rozdziale
              </label>
              <input
                id="seek"
                type="range"
                min={0}
                max={Math.max(
                  1,
                  Math.floor(duration || chapter.length_seconds),
                )}
                value={Math.floor(current)}
                onChange={(event) => {
                  const element = audio.current;
                  if (element) element.currentTime = Number(event.target.value);
                  setCurrent(Number(event.target.value));
                }}
                aria-valuetext={`${formatDuration(current)} z ${formatDuration(duration || chapter.length_seconds)}`}
                className="h-2 w-full cursor-pointer accent-accent"
              />
              <div className="mt-1 flex justify-between text-caption text-surface/80">
                <span>{formatDuration(current)}</span>
                <span>−{formatDuration(remaining)}</span>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Control
                label="Poprzedni rozdział"
                onClick={() => select(index - 1)}
                disabled={index === 0}
              >
                ⏮
              </Control>
              <Control label="Cofnij o 15 sekund" onClick={() => skip(-15)}>
                ↺15
              </Control>
              <button
                type="button"
                onClick={toggle}
                aria-label={playing ? "Wstrzymaj" : "Odtwarzaj"}
                className="inline-flex h-16 min-h-touch w-16 items-center justify-center rounded-pill bg-accent-action text-title text-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-surface"
              >
                {playing ? "❚❚" : "▶"}
              </button>
              <Control label="Do przodu o 30 sekund" onClick={() => skip(30)}>
                30↻
              </Control>
              <Control
                label="Następny rozdział"
                onClick={() => select(index + 1)}
                disabled={index >= detail.audio_chapters.length - 1}
              >
                ⏭
              </Control>
              <div
                role="group"
                aria-label="Prędkość odtwarzania"
                className="ml-auto flex gap-2"
              >
                {SPEEDS.map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={speed === value}
                    onClick={() => setSpeed(value)}
                    className={`min-h-touch min-w-touch rounded-pill px-3 text-caption font-bold ${
                      speed === value
                        ? "bg-surface text-ink"
                        : "border border-surface/30"
                    }`}
                  >
                    {String(value).replace(".", ",")}×
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
        <section
          aria-labelledby="chapters"
          className="mt-10 border-t border-surface/20 pt-6"
        >
          <h2
            id="chapters"
            className="text-caption font-bold tracking-wide text-surface/80"
          >
            ROZDZIAŁY · {Math.floor(totalSeconds / 3600)} GODZ.{" "}
            {Math.floor((totalSeconds % 3600) / 60)} MIN
          </h2>
          <ol className="mt-3">
            {detail.audio_chapters.map((item) => (
              <li key={item.position}>
                <button
                  type="button"
                  onClick={() => select(item.position)}
                  aria-current={item.position === index ? "true" : undefined}
                  className={`flex min-h-touch w-full items-center gap-4 rounded-control px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-surface ${
                    item.position === index
                      ? "bg-surface/15"
                      : "hover:bg-surface/10"
                  }`}
                >
                  <span className="w-6 text-caption font-bold text-surface/70">
                    {String(item.position + 1).padStart(2, "0")}
                  </span>
                  <span className="flex-1 font-bold">{item.title}</span>
                  <span className="text-caption">
                    {completed.includes(item.position) ? (
                      <>
                        <span aria-hidden="true">✓</span>
                        <span className="sr-only">odsłuchany</span>
                      </>
                    ) : (
                      formatDuration(item.length_seconds)
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>
        <p className="mt-8 text-center text-caption text-surface/70">
          Egzemplarz dla: {detail.buyer_email} · zamówienie{" "}
          {detail.order_number}
        </p>
      </main>
    </div>
  );
}

function Control({
  children,
  label,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex min-h-touch min-w-touch items-center justify-center rounded-pill border border-surface/30 px-3 text-body-small font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-surface disabled:opacity-40"
    >
      {children}
    </button>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto max-w-content px-4 py-14 focus:outline-none"
    >
      {children}
    </main>
  );
}
