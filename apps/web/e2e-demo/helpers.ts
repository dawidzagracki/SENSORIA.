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
