/** Resolve the private API origin for Server Components and route handlers. */
export function getServerApiUrl(): string | null {
  const configured = process.env.API_URL?.trim();
  if (configured) return configured;

  // Standalone `npm run dev` runs outside Compose and does not read the root
  // .env file. Keep the fallback development-only; production must configure
  // API_URL explicitly so container/service DNS is never guessed.
  return process.env.NODE_ENV === "development"
    ? "http://localhost:8000"
    : null;
}
