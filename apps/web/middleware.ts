import { NextResponse, type NextRequest } from "next/server";

/**
 * Per-request CSP with a nonce. Next.js reads the nonce from the request's CSP header and stamps
 * it on its own inline bootstrap scripts, so no `unsafe-inline` is needed for scripts.
 */
export function middleware(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const development = process.env.NODE_ENV === "development";
  let apiOrigin = "";
  try {
    const configured = process.env.NEXT_PUBLIC_API_URL;
    if (configured && /^https?:\/\//.test(configured))
      apiOrigin = new URL(configured).origin;
  } catch {
    apiOrigin = "";
  }
  const policy = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    // React sets inline style attributes (progress bars, text scaling); styles cannot run code.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data:",
    `connect-src 'self'${apiOrigin ? ` ${apiOrigin}` : ""}${development ? " ws:" : ""}`,
    `media-src 'self'${apiOrigin ? ` ${apiOrigin}` : ""}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "frame-src 'none'",
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api/|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
