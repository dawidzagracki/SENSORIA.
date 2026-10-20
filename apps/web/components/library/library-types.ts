export type LibraryItem = {
  id: string;
  kind: "digital" | "audiobook";
  title: string;
  order_number: string | null;
  granted_at: string;
  has_reader: boolean;
  chapters_total: number;
  chapters_completed: number;
};

export type EntitlementDetail = {
  id: string;
  kind: "digital" | "audiobook";
  product_id: string;
  title: string;
  author: string | null;
  order_number: string | null;
  buyer_email: string;
  granted_at: string;
  files: Array<{
    id: string;
    kind: "pdf" | "audio";
    label: string;
    chapter_id: string | null;
  }>;
  reader_chapters: Array<{
    position: number;
    title: string;
    page_count: number | null;
  }>;
  audio_chapters: Array<{
    position: number;
    title: string;
    length_seconds: number;
    file_id: string | null;
  }>;
  total_pages: number | null;
  progress: {
    position: number;
    offset_seconds: number;
    completed: number[];
    font_scale: number;
  };
};

export type ChapterContent = {
  position: number;
  title: string;
  blocks: ContentBlock[];
  total_chapters: number;
  footer: string;
};

export type ContentBlock = {
  type: "p" | "h2" | "quote" | "list" | "exercise";
  text?: string;
  title?: string;
  items?: string[];
};

/** Guest access is carried by the order token in the URL; accounts use the session cookie. */
export function tokenQuery(orderToken: string | null): string {
  return orderToken ? `?order_token=${encodeURIComponent(orderToken)}` : "";
}
