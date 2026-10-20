import { ApiError } from "../lib/api";

export type HomepageBenefit = {
  icon: "payment" | "email" | "parcel" | "voucher";
  text: string;
};

export type HomepageContent = {
  eyebrow: string;
  headline: {
    before_emphasis: string;
    emphasis: string;
    after_emphasis: string;
  };
  paragraph: string;
  catalog_button_label: string;
  voucher_button_label: string;
  catalog_button_target: "/sklep";
  benefits: HomepageBenefit[];
  product_selection: {
    voucher_id: string | null;
    audiobook_id: string | null;
    course_id: string | null;
  };
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
): boolean {
  return Object.keys(value).every((key) => allowed.includes(key));
}

const benefitIcons = ["payment", "email", "parcel", "voucher"];

export function parseHomepageContent(value: unknown): HomepageContent {
  if (
    !isRecord(value) ||
    !hasOnlyKeys(value, [
      "eyebrow",
      "headline",
      "paragraph",
      "catalog_button_label",
      "voucher_button_label",
      "catalog_button_target",
      "benefits",
      "product_selection",
    ]) ||
    typeof value.eyebrow !== "string" ||
    !isRecord(value.headline) ||
    !hasOnlyKeys(value.headline, [
      "before_emphasis",
      "emphasis",
      "after_emphasis",
    ]) ||
    typeof value.headline.before_emphasis !== "string" ||
    typeof value.headline.emphasis !== "string" ||
    typeof value.headline.after_emphasis !== "string" ||
    typeof value.paragraph !== "string" ||
    typeof value.catalog_button_label !== "string" ||
    typeof value.voucher_button_label !== "string" ||
    value.catalog_button_target !== "/sklep" ||
    !Array.isArray(value.benefits) ||
    value.benefits.length !== 4 ||
    !isRecord(value.product_selection) ||
    !hasOnlyKeys(value.product_selection, [
      "voucher_id",
      "audiobook_id",
      "course_id",
    ])
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowe ustawienia strony głównej.",
    );
  }
  const benefits = value.benefits.map((benefit) => {
    if (
      !isRecord(benefit) ||
      !hasOnlyKeys(benefit, ["icon", "text"]) ||
      typeof benefit.icon !== "string" ||
      !benefitIcons.includes(benefit.icon) ||
      typeof benefit.text !== "string"
    ) {
      throw new ApiError(
        "INVALID_RESPONSE",
        "Serwer zwrócił nieprawidłowe obietnice strony głównej.",
      );
    }
    return {
      icon: benefit.icon as HomepageBenefit["icon"],
      text: benefit.text,
    };
  });
  const selection = value.product_selection;
  for (const key of ["voucher_id", "audiobook_id", "course_id"] as const) {
    if (!(selection[key] === null || typeof selection[key] === "string")) {
      throw new ApiError(
        "INVALID_RESPONSE",
        "Serwer zwrócił nieprawidłowy wybór produktów.",
      );
    }
  }
  return {
    eyebrow: value.eyebrow,
    headline: {
      before_emphasis: value.headline.before_emphasis,
      emphasis: value.headline.emphasis,
      after_emphasis: value.headline.after_emphasis,
    },
    paragraph: value.paragraph,
    catalog_button_label: value.catalog_button_label,
    voucher_button_label: value.voucher_button_label,
    catalog_button_target: "/sklep",
    benefits,
    product_selection: {
      voucher_id: selection.voucher_id as string | null,
      audiobook_id: selection.audiobook_id as string | null,
      course_id: selection.course_id as string | null,
    },
  };
}
