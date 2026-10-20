import { describe, expect, it } from "vitest";
import {
  formatDurationPolish,
  getBookAvailability,
  hasConsistentAudiobookDuration,
} from "./catalog-product";

describe("physical and audio product data", () => {
  it.each([
    [0, "unavailable", false, "Chwilowo niedostępna"],
    [1, "last-copies", true, "Zostały ostatnie egzemplarze"],
    [3, "last-copies", true, "Zostały ostatnie egzemplarze"],
    [4, "last-copies", true, "Zostały ostatnie egzemplarze"],
    [5, "available", true, null],
  ] as const)(
    "maps stock %i without exposing a count",
    (stock, state, available, message) => {
      expect(getBookAvailability(stock)).toEqual({ state, available, message });
    },
  );

  it("formats exact seconds as Polish hours, minutes, and seconds", () => {
    expect(formatDurationPolish(15120)).toBe("4 godz. 12 min");
    expect(formatDurationPolish(90)).toBe("1 min 30 s");
    expect(formatDurationPolish(42)).toBe("42 s");
  });

  it("detects chapter sums that do and do not match total duration", () => {
    const chapters = [
      { title: "A", length_seconds: 7200, position: 0 },
      { title: "B", length_seconds: 7920, position: 1 },
    ];
    expect(hasConsistentAudiobookDuration(15120, chapters)).toBe(true);
    expect(hasConsistentAudiobookDuration(15121, chapters)).toBe(false);
  });
});
