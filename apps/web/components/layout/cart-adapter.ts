export type CartSnapshot = {
  count: number | null;
  source: "integration-pending" | "server-confirmed";
};

/** The secure cart cookie is scoped to /api/cart, so page SSR cannot read it. */
export async function readInitialCartSnapshot(): Promise<CartSnapshot> {
  return { count: null, source: "integration-pending" };
}
