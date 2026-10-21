"use client";

import {
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

export type AccordionItemData = {
  content: ReactNode;
  id: string;
  title: string;
};

export type AccordionProps = {
  defaultExpandedIds?: string[];
  items: AccordionItemData[];
  mode?: "single" | "multiple";
};

export function Accordion({
  defaultExpandedIds = [],
  items,
  mode = "single",
}: AccordionProps) {
  const idPrefix = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [openIds, setOpenIds] = useState<Set<string>>(
    () => new Set(defaultExpandedIds),
  );

  function toggle(id: string) {
    setOpenIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else {
        if (mode === "single") next.clear();
        next.add(id);
      }
      return next;
    });
  }

  function moveFocus(event: KeyboardEvent<HTMLButtonElement>) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const buttons = Array.from(
      rootRef.current?.querySelectorAll<HTMLButtonElement>(
        "[data-accordion-trigger]",
      ) ?? [],
    );
    const currentIndex = buttons.indexOf(event.currentTarget);
    if (currentIndex < 0 || buttons.length === 0) return;
    event.preventDefault();
    const nextIndex =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? buttons.length - 1
          : (currentIndex +
              (event.key === "ArrowDown" ? 1 : buttons.length - 1)) %
            buttons.length;
    buttons[nextIndex]?.focus();
  }

  return (
    <div
      className="divide-y divide-border rounded-card border border-border"
      ref={rootRef}
    >
      {items.map((item, index) => {
        const expanded = openIds.has(item.id);
        const triggerId = `${idPrefix}-trigger-${index}`;
        const panelId = `${idPrefix}-panel-${index}`;
        return (
          <section className="px-4" key={item.id}>
            <h3>
              <button
                aria-controls={panelId}
                aria-expanded={expanded}
                className="flex min-h-control-md w-full items-center justify-between gap-4 py-3 text-left font-interface text-body-small font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                data-accordion-trigger
                id={triggerId}
                onClick={() => toggle(item.id)}
                onKeyDown={moveFocus}
                type="button"
              >
                <span>{item.title}</span>
                <span aria-hidden="true">{expanded ? "−" : "+"}</span>
              </button>
            </h3>
            <div
              aria-labelledby={triggerId}
              className="pb-4 text-body-small text-ink-muted"
              hidden={!expanded}
              id={panelId}
              role="region"
            >
              {item.content}
            </div>
          </section>
        );
      })}
    </div>
  );
}
