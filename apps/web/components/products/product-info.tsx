import Link from "next/link";
import type { ReactNode } from "react";

/** Honest note shown before buying digital content (checkout records the consent). */
export function DigitalConsentNotice() {
  return (
    <p className="rounded-card border border-border bg-surface-muted p-4 text-body-small text-ink">
      Treści cyfrowe udostępniamy od razu po opłaceniu. Przy płatności
      potwierdzasz zgodę na natychmiastowe udostępnienie, co oznacza utratę
      prawa do odstąpienia od umowy.{" "}
      <Link className="font-semibold underline" href="/pomoc/odstapienie">
        Szczegóły
      </Link>
    </p>
  );
}

export function TrustList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-3 border-y border-border py-5 text-body-small text-ink">
      {items.map((item) => (
        <li className="flex items-start gap-3" key={item}>
          <svg
            aria-hidden="true"
            className="mt-1 h-4 w-4 shrink-0 text-accent-action"
            fill="none"
            viewBox="0 0 16 16"
          >
            <path
              d="M3 8.5l3 3 7-7"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
            />
          </svg>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export const digitalTrust = [
  "Plik w Twojej bibliotece od razu po opłaceniu — bez czekania",
  "Czytasz w przeglądarce albo pobierasz PDF oznaczony Twoim numerem zamówienia",
  "Płatność BLIK, kartą, Google Pay lub Apple Pay",
];

export const audioTrust = [
  "Słuchasz w przeglądarce od razu po opłaceniu, z zapamiętaniem miejsca",
  "Rozdziały, zmiana prędkości i wznawianie na każdym urządzeniu",
  "Płatność BLIK, kartą, Google Pay lub Apple Pay",
];

export function digitalFaq(kind: "ebook" | "audio" | "course"): {
  id: string;
  title: string;
  content: ReactNode;
}[] {
  const what =
    kind === "audio" ? "audiobooka" : kind === "course" ? "kursu" : "e-booka";
  return [
    {
      id: "delivery",
      title: `Kiedy dostanę dostęp do ${what}?`,
      content: (
        <p>
          Od razu po opłaceniu. Materiał pojawia się w{" "}
          <Link className="underline" href="/konto/biblioteka">
            bibliotece
          </Link>
          , a link dostajesz też w wiadomości e-mail. Konto nie jest wymagane —
          dostęp działa z linku w mailu.
        </p>
      ),
    },
    {
      id: "device",
      title:
        kind === "audio" ? "Na czym mogę słuchać?" : "Na czym mogę czytać?",
      content: (
        <p>
          {kind === "audio"
            ? "Odtwarzacz działa w przeglądarce na telefonie, tablecie i komputerze."
            : "Czytnik działa w przeglądarce na każdym urządzeniu, a plik PDF możesz pobrać i otworzyć w dowolnym programie."}
        </p>
      ),
    },
    {
      id: "invoice",
      title: "Czy dostanę fakturę?",
      content: (
        <p>
          Paragon wystawiamy automatycznie. Fakturę VAT na firmę wystawimy,
          jeśli podasz NIP w zamówieniu — obie wersje pobierzesz ze strony
          zamówienia.
        </p>
      ),
    },
    {
      id: "return",
      title: `Czy mogę zwrócić ${what}?`,
      content: (
        <p>
          Przy treściach cyfrowych prawo odstąpienia wygasa po rozpoczęciu
          udostępniania, na co wyrażasz zgodę w zamówieniu. Jeśli plik jest
          uszkodzony lub niezgodny z opisem, złóż{" "}
          <Link className="underline" href="/pomoc/zwroty-i-reklamacje">
            reklamację
          </Link>
          .
        </p>
      ),
    },
  ];
}

export function AuthorBlurb() {
  return (
    <section
      aria-labelledby="product-author-title"
      className="grid gap-4 rounded-card bg-surface-muted p-6 md:grid-cols-[1fr_auto] md:items-center md:p-8"
    >
      <div>
        <p className="uppercase-label text-accent-action">O autorce</p>
        <h2
          className="mt-2 font-display text-subtitle font-extrabold text-ink"
          id="product-author-title"
        >
          Anna Parakiewicz
        </h2>
        <p className="mt-3 max-w-content text-body-small text-ink-muted">
          Terapeutka i autorka materiałów Sensoria — od lat pracuje z dziećmi,
          młodzieżą i dorosłymi w Instytucie Diagnozy i Terapii w Olsztynie.
        </p>
      </div>
      <Link
        className="inline-flex min-h-control-md items-center justify-center rounded-pill border border-accent-action bg-surface px-6 font-interface text-button font-semibold text-accent-action hover:bg-surface"
        href="/o-autorce"
      >
        Poznaj autorkę
      </Link>
    </section>
  );
}
