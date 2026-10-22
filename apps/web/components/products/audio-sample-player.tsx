"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { formatDurationPolish } from "@/lib/catalog-product";
import { openProductSample } from "@/lib/product-sample-api";

let activeAudio: HTMLAudioElement | null = null;

export function AudioSamplePlayer({
  slug,
  durationSeconds,
}: {
  slug: string;
  durationSeconds: number;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [source, setSource] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [totalTime, setTotalTime] = useState(durationSeconds);
  const [error, setError] = useState<string | null>(null);

  useEffect(
    () => () => {
      const audio = audioRef.current;
      if (audio) {
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
        if (activeAudio === audio) activeAudio = null;
      }
    },
    [],
  );

  async function togglePlayback() {
    const audio = audioRef.current;
    if (!audio) return;
    setError(null);
    if (source && !audio.paused) {
      audio.pause();
      setPlaying(false);
      return;
    }

    setLoading(true);
    try {
      let url = source;
      if (!url) {
        const sample = await openProductSample(slug);
        if (sample.contentType !== "audio/mpeg") {
          throw new Error("Próbka audio nie jest teraz dostępna.");
        }
        url = sample.url;
        setSource(url);
        audio.src = url;
      }
      if (activeAudio && activeAudio !== audio) activeAudio.pause();
      activeAudio = audio;
      await audio.play();
      setPlaying(true);
    } catch (cause: unknown) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie można teraz odtworzyć fragmentu.",
      );
      setPlaying(false);
    } finally {
      setLoading(false);
    }
  }

  function seek(value: string) {
    const audio = audioRef.current;
    if (!audio) return;
    const nextTime = Number(value);
    if (!Number.isFinite(nextTime)) return;
    audio.currentTime = nextTime;
    setCurrentTime(nextTime);
  }

  return (
    <section
      aria-label="Odtwarzacz darmowej próbki audiobooka"
      className="space-y-3"
    >
      <audio
        onDurationChange={(event) => {
          if (Number.isFinite(event.currentTarget.duration)) {
            setTotalTime(event.currentTarget.duration);
          }
        }}
        onEnded={() => setPlaying(false)}
        onError={() => {
          setPlaying(false);
          setError("Nie można teraz odtworzyć fragmentu.");
        }}
        onTimeUpdate={(event) =>
          setCurrentTime(event.currentTarget.currentTime)
        }
        preload="none"
        ref={audioRef}
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button
          aria-label={
            playing
              ? "Wstrzymaj próbkę"
              : source
                ? "Odtwórz ponownie"
                : "Odtwórz darmową próbkę"
          }
          loading={loading}
          loadingLabel="Ładowanie próbki"
          onClick={togglePlayback}
          variant="secondary"
        >
          {playing
            ? "Pauza"
            : source
              ? "Odtwórz ponownie"
              : "Odsłuchaj darmową próbkę"}
        </Button>
        <span aria-live="off" className="text-caption text-ink-muted">
          {formatDurationPolish(Math.floor(currentTime))} /{" "}
          {formatDurationPolish(Math.floor(totalTime))}
        </span>
      </div>
      <label className="block space-y-1 text-caption text-ink-muted">
        <span className="sr-only">Pozycja próbki audio</span>
        <input
          aria-label="Pozycja próbki audio"
          className="min-h-touch w-full accent-accent-action focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
          disabled={!source || !Number.isFinite(totalTime) || totalTime <= 0}
          max={Math.max(0, Math.floor(totalTime))}
          min={0}
          onChange={(event) => seek(event.currentTarget.value)}
          step={1}
          type="range"
          value={Math.min(
            Math.floor(currentTime),
            Math.max(0, Math.floor(totalTime)),
          )}
        />
      </label>
      <p className="text-caption text-ink-muted">
        Darmowy fragment · pełna wersja dostępna w sensoria.shop
      </p>
      {error ? (
        <p className="text-body-small text-on-danger" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
