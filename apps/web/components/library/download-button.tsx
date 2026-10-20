"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { apiJson, API } from "@/lib/client-api";

type LinkResponse = { url: string; expires_at: string; uses_left: number };

/** Mints a fresh limited download link on click, then starts the download. */
export function DownloadButton({
  entitlementId,
  fileId,
  orderToken,
  label,
}: {
  entitlementId: string;
  fileId: string;
  orderToken?: string | null;
  label: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start() {
    setBusy(true);
    setError("");
    try {
      const query = orderToken
        ? `?order_token=${encodeURIComponent(orderToken)}`
        : "";
      const link = await apiJson<LinkResponse>(
        `/library/entitlements/${entitlementId}/download-links${query}`,
        { method: "POST", json: { file_id: fileId } },
      );
      // The link is single-purpose and expires; the server stamps the PDF per buyer.
      window.location.assign(
        link.url.startsWith("/api")
          ? link.url.replace(/^\/api/, API)
          : link.url,
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się przygotować pliku.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Button loading={busy} onClick={start} size="sm" variant="secondary">
        {label}
      </Button>
      {error ? (
        <div className="mt-2">
          <Alert variant="error">{error}</Alert>
        </div>
      ) : null}
    </div>
  );
}
