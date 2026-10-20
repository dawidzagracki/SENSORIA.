import type { ContentBlock } from "@/components/library/library-types";

/**
 * Plain-text editing format for information pages:
 *   "## Nagłówek"  → h2      "> Cytat" → quote
 *   "- punkt"      → list (consecutive lines are one list)
 *   blank line     → paragraph break
 */
export function textToBlocks(text: string): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  let paragraph: string[] = [];
  let list: string[] = [];
  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "p", text: paragraph.join("\n") });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list.length) {
      blocks.push({ type: "list", items: list });
      list = [];
    }
  };
  for (const raw of text.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    if (line.trim() === "") {
      flushParagraph();
      flushList();
    } else if (line.startsWith("## ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h2", text: line.slice(3).trim() });
    } else if (line.startsWith("> ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "quote", text: line.slice(2).trim() });
    } else if (line.startsWith("- ")) {
      flushParagraph();
      list.push(line.slice(2).trim());
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();
  return blocks;
}

export function blocksToText(blocks: ContentBlock[]): string {
  return blocks
    .map((block) => {
      if (block.type === "h2") return `## ${block.text ?? ""}`;
      if (block.type === "quote") return `> ${block.text ?? ""}`;
      if (block.type === "list")
        return (block.items ?? []).map((item) => `- ${item}`).join("\n");
      return block.text ?? "";
    })
    .join("\n\n");
}
