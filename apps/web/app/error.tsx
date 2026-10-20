"use client";

type ErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ErrorPage({ reset }: ErrorPageProps) {
  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <h1 className="font-display text-title font-bold">Coś poszło nie tak</h1>
      <p className="mt-4">Nie udało się wyświetlić tej strony.</p>
      <button className="mt-4 underline" onClick={reset} type="button">
        Spróbuj ponownie
      </button>
    </main>
  );
}
