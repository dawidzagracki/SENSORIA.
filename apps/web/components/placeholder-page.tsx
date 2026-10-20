type PlaceholderPageProps = {
  title: string;
};

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <h1 className="font-display text-title font-bold">{title}</h1>
      <p className="mt-4">
        Ta część aplikacji będzie dostępna w kolejnym etapie.
      </p>
    </main>
  );
}
