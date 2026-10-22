"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Modal } from "@/components/ui";
import { openProductSample } from "@/lib/product-sample-api";

function pageCountLabel(pages: number): string {
  const remainder = pages % 10;
  const teen = pages % 100;
  const noun =
    pages === 1
      ? "strona"
      : remainder >= 2 && remainder <= 4 && !(teen >= 12 && teen <= 14)
        ? "strony"
        : "stron";
  return `${pages} ${noun}`;
}

export function PdfSamplePreview({
  slug,
  pages,
}: {
  slug: string;
  pages: number;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sampleUrl, setSampleUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  async function showPreview() {
    setError(null);
    setLoading(true);
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      const sample = await openProductSample(slug, controller.signal);
      if (sample.contentType !== "application/pdf") {
        setError("Próbka PDF nie jest teraz dostępna.");
        return;
      }
      setSampleUrl(sample.url);
      setOpen(true);
    } catch (cause: unknown) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie można teraz otworzyć fragmentu.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Button
        aria-describedby={error ? "pdf-sample-error" : undefined}
        loading={loading}
        loadingLabel="Otwieranie fragmentu"
        onClick={showPreview}
        variant="secondary"
      >
        Przeczytaj darmowy fragment · {pageCountLabel(pages)}
      </Button>
      {error ? (
        <p
          className="text-body-small text-on-danger"
          id="pdf-sample-error"
          role="alert"
        >
          {error}
        </p>
      ) : null}
      <Modal onOpenChange={setOpen} open={open} title="Darmowy fragment PDF">
        {sampleUrl ? (
          <iframe
            className="h-sample-preview w-full rounded-card border border-border"
            src={sampleUrl}
            title={`Darmowy fragment produktu, ${pages} stron`}
          />
        ) : null}
      </Modal>
    </>
  );
}
