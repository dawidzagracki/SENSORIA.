export type AxeImpact = { impact?: string | null };

export function blockingAxeViolations<T extends AxeImpact>(violations: T[]) {
  return violations.filter(
    ({ impact }) => impact === "critical" || impact === "serious",
  );
}
