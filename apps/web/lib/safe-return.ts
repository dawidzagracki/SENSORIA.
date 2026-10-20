/** Accept only a local route; reject protocol-relative, backslash and control-character tricks. */
export function safeReturnPath(value: string | null | undefined): string {
  const fallback = "/konto";
  if (!value) return fallback;
  let candidate = value;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (
      !candidate.startsWith("/") ||
      candidate.startsWith("//") ||
      candidate.includes("\\") ||
      /[\u0000-\u001f\u007f]/.test(candidate)
    )
      return fallback;
    try {
      const parsed = new URL(candidate, "https://local.invalid");
      if (parsed.origin !== "https://local.invalid") return fallback;
      const decoded = decodeURIComponent(candidate);
      if (decoded === candidate)
        return `${parsed.pathname}${parsed.search}${parsed.hash}`;
      candidate = decoded;
    } catch {
      return fallback;
    }
  }
  return fallback;
}
