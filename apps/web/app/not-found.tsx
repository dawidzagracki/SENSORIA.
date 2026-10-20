import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <h1 className="font-display text-title font-bold">
        Nie znaleziono strony (404)
      </h1>
      <p className="mt-4">Podany adres nie prowadzi do dostępnej strony.</p>
      <Link className="mt-4 inline-block underline" href="/">
        Wróć na stronę główną
      </Link>
    </main>
  );
}
