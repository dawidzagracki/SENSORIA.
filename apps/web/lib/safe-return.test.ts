import { describe, expect, it } from "vitest";
import { safeReturnPath } from "./safe-return";

describe("safeReturnPath", () => {
  it("keeps local account destinations and their query", () => {
    expect(safeReturnPath("/konto/biblioteka?typ=ebook")).toBe(
      "/konto/biblioteka?typ=ebook",
    );
  });

  it.each([
    "https://attacker.example",
    "//attacker.example/path",
    "/\\attacker.example",
    "/%252f%252fattacker.example",
    "javascript:alert(1)",
    "/konto\r\nLocation:https://attacker.example",
  ])("rejects unsafe address %s", (value) => {
    expect(safeReturnPath(value)).toBe("/konto");
  });
});
