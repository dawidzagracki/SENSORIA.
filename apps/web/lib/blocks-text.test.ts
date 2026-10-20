import { describe, expect, it } from "vitest";
import { blocksToText, textToBlocks } from "@/lib/blocks-text";

describe("blocks text format", () => {
  it("parses headings, quotes, lists and paragraphs", () => {
    const blocks = textToBlocks(
      "## §1\n\nPierwszy akapit\ndruga linia\n\n> Cytat\n\n- a\n- b\n\nKoniec",
    );
    expect(blocks).toEqual([
      { type: "h2", text: "§1" },
      { type: "p", text: "Pierwszy akapit\ndruga linia" },
      { type: "quote", text: "Cytat" },
      { type: "list", items: ["a", "b"] },
      { type: "p", text: "Koniec" },
    ]);
  });

  it("round-trips", () => {
    const text = "## Tytuł\n\nAkapit\n\n- x\n- y\n\n> cytat";
    expect(blocksToText(textToBlocks(text))).toBe(text);
  });

  it("never produces markup blocks from html-looking input", () => {
    const blocks = textToBlocks("<script>alert(1)</script>");
    expect(blocks).toEqual([{ type: "p", text: "<script>alert(1)</script>" }]);
  });
});
