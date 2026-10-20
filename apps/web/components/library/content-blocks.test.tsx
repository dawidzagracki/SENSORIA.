import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ContentBlocks } from "@/components/library/content-blocks";

afterEach(cleanup);

describe("ContentBlocks", () => {
  it("renders text blocks as text, never as markup", () => {
    const { container } = render(
      <ContentBlocks
        blocks={[
          { type: "p", text: "<img src=x onerror=alert(1)>" },
          { type: "h2", text: "<b>Nagłówek</b>" },
          { type: "quote", text: "<script>alert(1)</script>" },
          { type: "list", items: ["<i>a</i>", "b"] },
          { type: "exercise", title: "Mapa", items: ["Dotyk"] },
        ]}
      />,
    );
    expect(container.querySelector("img, script, b, i")).toBeNull();
    expect(
      screen.getByText("<img src=x onerror=alert(1)>"),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "<b>Nagłówek</b>",
    );
    expect(screen.getByText("Dotyk")).toBeInTheDocument();
  });
});
