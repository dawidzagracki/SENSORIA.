import type { CatalogAudiobookChapter } from "@/types/catalog";

export type BookAvailability = {
  available: boolean;
  message: string | null;
  state: "unavailable" | "last-copies" | "available";
};

export function getBookAvailability(stock: number): BookAvailability {
  if (!Number.isSafeInteger(stock) || stock < 0) {
    throw new RangeError("Stan książki musi być nieujemną liczbą całkowitą.");
  }
  if (stock === 0) {
    return {
      available: false,
      message: "Chwilowo niedostępna",
      state: "unavailable",
    };
  }
  if (stock < 5) {
    return {
      available: true,
      message: "Zostały ostatnie egzemplarze",
      state: "last-copies",
    };
  }
  return { available: true, message: null, state: "available" };
}

export function sumChapterSeconds(chapters: CatalogAudiobookChapter[]): number {
  return chapters.reduce((total, chapter) => total + chapter.length_seconds, 0);
}

export function hasConsistentAudiobookDuration(
  durationSeconds: number | null,
  chapters: CatalogAudiobookChapter[],
): boolean {
  return (
    durationSeconds === null || sumChapterSeconds(chapters) === durationSeconds
  );
}

export function formatDurationPolish(totalSeconds: number): string {
  if (!Number.isSafeInteger(totalSeconds) || totalSeconds < 0) {
    throw new RangeError(
      "Czas nagrania musi być nieujemną liczbą całkowitą sekund.",
    );
  }
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours} godz.`);
  if (minutes > 0 || (hours > 0 && seconds > 0)) parts.push(`${minutes} min`);
  if (seconds > 0 || parts.length === 0) parts.push(`${seconds} s`);
  return parts.join(" ");
}
