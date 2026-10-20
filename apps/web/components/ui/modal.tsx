"use client";

import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Button } from "./button";

export type ModalProps = {
  children: ReactNode;
  id?: string;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  title: string;
};

export function Modal({ children, id, onOpenChange, open, title }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const previousOverflowRef = useRef("");
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open && !dialog.open) {
      returnFocusRef.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      previousOverflowRef.current = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      dialog.showModal();
      dialog.querySelector<HTMLButtonElement>("button")?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }

    return () => {
      document.body.style.overflow = previousOverflowRef.current;
    };
  }, [open]);

  function restoreFocus() {
    if (returnFocusRef.current?.isConnected) returnFocusRef.current.focus();
    onOpenChange(false);
  }

  function containTabFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Tab") return;

    const dialog = dialogRef.current;
    if (!dialog) return;

    const focusableElements = Array.from(
      dialog.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter(
      (element) =>
        element.getAttribute("aria-hidden") !== "true" &&
        element.getClientRects().length > 0,
    );

    if (focusableElements.length === 0) {
      event.preventDefault();
      dialog.focus();
      return;
    }

    const first = focusableElements[0];
    const last = focusableElements[focusableElements.length - 1];
    const active = document.activeElement;

    if (event.shiftKey && (active === first || !dialog.contains(active))) {
      event.preventDefault();
      last.focus();
    } else if (
      !event.shiftKey &&
      (active === last || !dialog.contains(active))
    ) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <dialog
      aria-labelledby={titleId}
      aria-modal="true"
      className="m-auto max-h-screen w-dialog max-w-content overflow-y-auto rounded-card border border-border bg-surface p-6 text-ink shadow-overlay backdrop:bg-ink/40"
      id={id}
      onCancel={(event) => {
        event.preventDefault();
        dialogRef.current?.close();
      }}
      onClose={restoreFocus}
      onKeyDown={containTabFocus}
      ref={dialogRef}
      tabIndex={-1}
    >
      <div className="flex items-start justify-between gap-4">
        <h2 className="font-interface text-subtitle font-bold" id={titleId}>
          {title}
        </h2>
        <Button
          aria-label="Zamknij okno"
          onClick={() => dialogRef.current?.close()}
          size="sm"
          variant="text"
        >
          ×
        </Button>
      </div>
      <div className="mt-4">{children}</div>
    </dialog>
  );
}
