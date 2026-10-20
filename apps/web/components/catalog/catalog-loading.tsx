export function CatalogLoading() {
  return (
    <main className="page-shell min-h-screen" id="main-content" tabIndex={-1}>
      <p aria-live="polite" className="sr-only" role="status">
        Ładowanie katalogu…
      </p>
      <div className="my-6 grid gap-6 rounded-card bg-surface-muted p-6 md:grid-cols-2 md:items-center md:p-8">
        <div className="space-y-4">
          <div className="h-6 w-24 animate-pulse rounded-pill bg-surface" />
          <div className="h-12 max-w-content animate-pulse rounded-pill bg-surface" />
          <div className="h-12 max-w-content animate-pulse rounded-pill bg-surface" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="h-16 animate-pulse rounded-card bg-surface" />
          <div className="h-16 animate-pulse rounded-card bg-surface" />
          <div className="h-16 animate-pulse rounded-card bg-surface" />
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-4">
        <div className="hidden space-y-6 lg:col-span-1 lg:block">
          <div className="h-48 rounded-card bg-surface-muted" />
          <div className="h-32 rounded-card bg-surface-muted" />
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:col-span-3 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, index) => (
            <div
              className="overflow-hidden rounded-card border border-border"
              key={index}
            >
              <div className="aspect-product-image animate-pulse bg-surface-muted" />
              <div className="space-y-4 p-4">
                <div className="h-6 animate-pulse rounded-pill bg-surface-muted" />
                <div className="h-12 animate-pulse rounded-pill bg-surface-muted" />
                <div className="h-10 animate-pulse rounded-pill bg-surface-muted" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
