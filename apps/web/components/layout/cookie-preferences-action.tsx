"use client";

import { useState } from "react";
import { Button } from "../ui/button";
import { Modal } from "../ui/modal";

export function CookiePreferencesAction({
  demoEnabled,
  onOpenPreferences,
}: {
  demoEnabled: boolean;
  onOpenPreferences?: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        disabled={!demoEnabled && !onOpenPreferences}
        className="!min-h-touch !justify-start !px-0"
        onClick={() => {
          if (onOpenPreferences) onOpenPreferences();
          else setOpen(true);
        }}
        size="sm"
        variant="text"
      >
        Ustawienia cookies
      </Button>
      {demoEnabled ? (
        <Modal
          onOpenChange={setOpen}
          open={open}
          title="Ustawienia cookies — demonstracja"
        >
          <p className="text-body-small">
            To wyłącznie demonstracja punktu integracji. Nie zapisuje zgód ani
            nie zmienia ustawień cookies. Pełny panel zgód powstanie w etapie
            [79].
          </p>
        </Modal>
      ) : null}
    </>
  );
}
