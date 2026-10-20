import type { ContentBlock } from "./library-types";

/** Renders structured blocks as text only; there is no HTML injection path. */
export function ContentBlocks({ blocks }: { blocks: ContentBlock[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === "h2")
          return (
            <h2
              key={key}
              className="mt-10 font-display text-title font-bold text-ink"
            >
              {block.text}
            </h2>
          );
        if (block.type === "quote")
          return (
            <blockquote
              key={key}
              className="my-8 border-l-4 border-accent pl-5 font-body text-body italic text-ink"
            >
              {block.text}
            </blockquote>
          );
        if (block.type === "list")
          return (
            <ul
              key={key}
              className="my-6 list-disc space-y-2 pl-6 font-body text-body text-ink"
            >
              {(block.items ?? []).map((item, i) => (
                <li key={`${key}-${i}`}>{item}</li>
              ))}
            </ul>
          );
        if (block.type === "exercise")
          return (
            <section
              key={key}
              aria-label={block.title ?? "Ćwiczenie"}
              className="my-8 rounded-card border border-border bg-surface p-6"
            >
              <p className="text-caption font-bold tracking-wide text-accent-action">
                ĆWICZENIE DO ROZDZIAŁU
              </p>
              {block.title ? (
                <h3 className="mt-2 font-display text-emphasis text-ink">
                  {block.title}
                </h3>
              ) : null}
              {block.text ? (
                <p className="mt-3 font-body text-body text-ink">
                  {block.text}
                </p>
              ) : null}
              <ul className="mt-4 space-y-2 font-body text-body text-ink">
                {(block.items ?? []).map((item, i) => (
                  <li key={`${key}-${i}`} className="flex gap-3">
                    <span aria-hidden="true" className="text-accent-action">
                      ✓
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          );
        return (
          <p
            key={key}
            className="my-5 whitespace-pre-line font-body text-body leading-8 text-ink"
          >
            {block.text}
          </p>
        );
      })}
    </>
  );
}
