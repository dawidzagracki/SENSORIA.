import { expect, type BrowserContext, type Page } from "@playwright/test";

export const CUSTOMER = {
  email: "anna.kowalska@sensoria.demo",
  password: "Demo-Sensoria-2026",
};
export const ADMIN = {
  email: "wlascicielka@sensoria.demo",
  password: "Demo-Sensoria-2026",
};

/** Pre-answers the cookie banner so it never covers the controls under test. */
export async function acceptEssentialCookies(
  context: BrowserContext,
  baseURL: string,
) {
  await context.addCookies([
    {
      name: "sensoria_cookie_consent",
      value: encodeURIComponent(
        JSON.stringify({
          v: "v1",
          subject: null,
          analytics: false,
          marketing: false,
        }),
      ),
      url: baseURL,
    },
  ]);
}

/**
 * The fake payment gateway advertises http://localhost:9911, which a browser inside the test
 * container cannot reach; forward those requests to its Compose hostname.
 */
export async function bridgeGateway(
  context: BrowserContext,
  target = "http://fake-stripe:9911",
) {
  await context.route("http://localhost:9911/**", async (route) => {
    const request = route.request();
    const url = request.url().replace("http://localhost:9911", target);
    const response = await route.fetch({ url, maxRedirects: 0 });
    await route.fulfill({ response });
  });
}

export async function cartCount(page: Page): Promise<number> {
  const link = page.getByRole("link", { name: /^Koszyk/ });
  const label = (await link.getAttribute("aria-label")) ?? "";
  if (label.includes("pusty")) return 0;
  const match = label.match(/(\d+)/);
  return match ? Number(match[1]) : -1;
}

export async function expectNoServerError(page: Page) {
  await expect(page.getByText("Coś poszło nie tak")).toHaveCount(0);
  await expect(page.getByText("Application error")).toHaveCount(0);
}

/** GET through the page (same cookies, same host mapping as the browser). */
export async function pageFetch(page: Page, url: string) {
  return page.evaluate(async (target) => {
    const response = await fetch(target, { credentials: "include" });
    const bytes = new Uint8Array(await response.arrayBuffer());
    return {
      status: response.status,
      type: response.headers.get("content-type") ?? "",
      head: String.fromCharCode(...bytes.slice(0, 5)),
    };
  }, url);
}

/** Polls Mailpit (the demo SMTP sink) for the newest mail to `to` and returns the first link matching `pattern`. */
export async function mailLink(
  context: BrowserContext,
  to: string,
  pattern: RegExp,
): Promise<string> {
  const page = await context.newPage();
  try {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      await page.goto(
        `http://localhost:8025/api/v1/search?query=${encodeURIComponent(`to:${to}`)}`,
      );
      const found = JSON.parse(await page.locator("body").innerText()) as {
        messages?: Array<{ ID: string }>;
      };
      for (const summary of found.messages ?? []) {
        await page.goto(`http://localhost:8025/api/v1/message/${summary.ID}`);
        const message = JSON.parse(await page.locator("body").innerText()) as {
          Text?: string;
          HTML?: string;
        };
        const match = `${message.Text ?? ""}\n${message.HTML ?? ""}`.match(
          pattern,
        );
        if (match) return match[0].replace(/&amp;/g, "&");
      }
      await page.waitForTimeout(1500);
    }
  } finally {
    await page.close();
  }
  throw new Error(`Brak wiadomości z linkiem ${pattern} dla ${to}`);
}

/** Visible boxed controls whose corners are square (the app must have none). */
export async function findSquareControls(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    [
      ...document.querySelectorAll(
        "input:not([type=hidden]):not([type=radio]):not([type=range]), select, textarea, button, .rounded-card",
      ),
    ]
      .filter((el) => {
        const box = el.getBoundingClientRect();
        return (
          box.width > 8 &&
          box.height > 8 &&
          getComputedStyle(el).visibility !== "hidden"
        );
      })
      .filter((el) => {
        const style = getComputedStyle(el);
        const radius =
          parseFloat(style.borderTopLeftRadius) +
          parseFloat(style.borderBottomRightRadius);
        const boxed =
          style.borderTopWidth !== "0px" ||
          style.backgroundColor !== "rgba(0, 0, 0, 0)";
        return boxed && radius === 0;
      })
      .map(
        (el) =>
          `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)}`,
      ),
  );
}

/**
 * Layout sanity for the current page: horizontal overflow, interactive elements that overlap each
 * other and elements that stick out of the viewport (outside deliberate scroll containers).
 */
export async function findLayoutProblems(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const problems: string[] = [];
    const vw = window.innerWidth;
    const label = (el: Element) =>
      `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}.${String(el.className).slice(0, 50)} "${(el.textContent ?? "").trim().slice(0, 30)}"`;
    if (document.documentElement.scrollWidth > vw + 1)
      problems.push(
        `poziome przewijanie: ${document.documentElement.scrollWidth} > ${vw}`,
      );

    const fixedLike = (el: Element) => {
      for (let node: Element | null = el; node; node = node.parentElement) {
        const position = getComputedStyle(node).position;
        if (position === "fixed" || position === "sticky") return true;
      }
      return false;
    };
    const visible = (el: Element) => {
      const box = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return (
        box.width > 2 &&
        box.height > 2 &&
        style.visibility !== "hidden" &&
        style.display !== "none" &&
        style.opacity !== "0"
      );
    };
    const insideScroller = (el: Element) => {
      for (let node = el.parentElement; node; node = node.parentElement) {
        const overflow = getComputedStyle(node).overflowX;
        if (
          (overflow === "auto" ||
            overflow === "scroll" ||
            overflow === "hidden") &&
          node.scrollWidth > node.clientWidth
        )
          return true;
      }
      return false;
    };

    const interactive = [
      ...document.querySelectorAll(
        "a[href], button, input:not([type=hidden]):not([type=radio]):not([type=checkbox]), select, textarea",
      ),
    ]
      .filter(visible)
      .filter(
        (el) =>
          !fixedLike(el) &&
          !el.closest("dialog:not([open])") &&
          !el.closest("[hidden]") &&
          !el.closest(".sr-only"),
      );
    for (const el of interactive) {
      const box = el.getBoundingClientRect();
      if (!insideScroller(el) && (box.right > vw + 1 || box.left < -1))
        problems.push(`poza ekranem: ${label(el)}`);
    }
    const boxes = interactive.map((el) => ({
      el,
      box: el.getBoundingClientRect(),
    }));
    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) {
        const a = boxes[i];
        const b = boxes[j];
        if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
        // Deliberate compositions: a button inset in its own field, and rotated hero cards.
        const inset = (x: Element, y: Element) =>
          getComputedStyle(x).position === "absolute" &&
          x.parentElement?.contains(y);
        if (inset(a.el, b.el) || inset(b.el, a.el)) continue;
        if (
          getComputedStyle(a.el).transform !== "none" ||
          getComputedStyle(b.el).transform !== "none"
        )
          continue;
        const w =
          Math.min(a.box.right, b.box.right) - Math.max(a.box.left, b.box.left);
        const h =
          Math.min(a.box.bottom, b.box.bottom) - Math.max(a.box.top, b.box.top);
        if (w > 4 && h > 4)
          problems.push(`nakładanie: ${label(a.el)} ⟷ ${label(b.el)}`);
      }
    }
    return problems.slice(0, 20);
  });
}
