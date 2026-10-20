"use client";

import { Button } from "../ui/button";
import { OPEN_EVENT } from "../cookies/cookie-consent";

/** Footer entry point that reopens the cookie settings dialog. */
export function CookiePreferencesAction({
  onOpenPreferences,
}: {
  /** Kept for tests and non-browser hosts; defaults to the shared window event. */
  onOpenPreferences?: () => void;
  demoEnabled?: boolean;
}) {
  return (
    <Button
      className="!min-h-touch !justify-start !px-0"
      onClick={() => {
        if (onOpenPreferences) onOpenPreferences();
        else window.dispatchEvent(new Event(OPEN_EVENT));
      }}
      size="sm"
      variant="text"
    >
      Ustawienia cookies
    </Button>
  );
}
