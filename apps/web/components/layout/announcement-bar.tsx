import { announcementText } from "./site-config";

export function AnnouncementBar() {
  return (
    <aside className="bg-ink px-4 py-2 text-center font-interface text-caption text-surface">
      {announcementText}
    </aside>
  );
}
