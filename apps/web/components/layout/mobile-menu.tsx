"use client";

import { useEffect, useState } from "react";
import { Button } from "../ui/button";
import { Modal } from "../ui/modal";
import { breakpointTokens } from "../../tailwind.config";
import { MainNavigation } from "./main-navigation";

const desktopBreakpoint = breakpointTokens.find(
  ({ name }) => name === "lg",
)!.value;
const dialogId = "mobile-navigation-dialog";

export function MobileMenu({
  desktopNavigationRef,
}: {
  desktopNavigationRef: React.RefObject<HTMLElement | null>;
}) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const media = window.matchMedia(`(min-width: ${desktopBreakpoint})`);
    function closeAtDesktop(event: MediaQueryListEvent) {
      if (!event.matches) return;
      setOpen(false);
      window.requestAnimationFrame(() => {
        desktopNavigationRef.current?.querySelector<HTMLElement>("a")?.focus();
      });
    }
    media.addEventListener("change", closeAtDesktop);
    return () => media.removeEventListener("change", closeAtDesktop);
  }, [desktopNavigationRef]);

  return (
    <div className="lg:hidden">
      <Button
        aria-controls={dialogId}
        aria-expanded={open}
        onClick={() => setOpen(true)}
        variant="secondary"
      >
        Menu
      </Button>
      <Modal
        id={dialogId}
        onOpenChange={setOpen}
        open={open}
        title="Nawigacja główna"
      >
        {open ? <MainNavigation onNavigate={() => setOpen(false)} /> : null}
      </Modal>
    </div>
  );
}
