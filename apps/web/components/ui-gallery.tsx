"use client";

import { useState } from "react";
import { Accordion } from "./ui/accordion";
import { Alert } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Breadcrumbs } from "./ui/breadcrumbs";
import { Button } from "./ui/button";
import { Checkbox } from "./ui/checkbox";
import { Modal } from "./ui/modal";
import { Price } from "./ui/price";
import { ProductCard } from "./ui/product-card";
import { Radio } from "./ui/radio";
import { RadioCard } from "./ui/radio-card";
import { Select } from "./ui/select";
import { Textarea } from "./ui/textarea";
import { TextField } from "./ui/text-field";

const questions = [
  {
    id: "digital-delivery",
    title: "Kiedy otrzymam materiały cyfrowe?",
    content:
      "To demonstracyjna odpowiedź przykładowa. Rzeczywiste informacje poda później właściwa treść sklepu.",
  },
  {
    id: "book-shipping",
    title: "Jak wysyłana jest książka?",
    content:
      "Przykład treści panelu. Accordion nie pobiera danych ani odpowiedzi z API.",
  },
];

export function UiGallery() {
  const [selectedShipping, setSelectedShipping] = useState("courier");
  const [selectedPayment, setSelectedPayment] = useState("card");
  const [isModalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [demoMessage, setDemoMessage] = useState("");

  return (
    <div className="space-y-8">
      <section aria-labelledby="ui-buttons-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="ui-buttons-title"
        >
          Button — warianty, rozmiary i stany
        </h2>
        {(["primary", "secondary", "text"] as const).map((variant) => (
          <div className="space-y-2" key={variant}>
            <h3 className="font-interface text-label font-bold">{variant}</h3>
            <div className="flex flex-wrap items-center gap-3">
              {(["sm", "md", "lg"] as const).map((size) => (
                <Button
                  key={size}
                  onClick={() =>
                    setDemoMessage(`Kliknięto ${variant}, rozmiar ${size}.`)
                  }
                  size={size}
                  variant={variant}
                >
                  {size}
                </Button>
              ))}
              <Button disabled size="md" variant={variant}>
                Wyłączony
              </Button>
              <Button loading size="md" variant={variant}>
                Zapisuję
              </Button>
            </div>
          </div>
        ))}
        <div className="flex flex-wrap gap-3">
          <Button
            loading={loading}
            onClick={() => {
              setLoading(true);
              window.setTimeout(() => setLoading(false), 900);
            }}
          >
            Pokaż ładowanie
          </Button>
          <Button onClick={() => setModalOpen(true)} variant="secondary">
            Otwórz Modal
          </Button>
        </div>
        <p aria-live="polite" className="text-body-small text-ink-muted">
          {demoMessage}
        </p>
      </section>

      <section aria-labelledby="ui-fields-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="ui-fields-title"
        >
          Input, Textarea, Select
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <TextField
            autoComplete="email"
            hint="Użyj adresu, do którego masz dostęp."
            label="Adres e-mail"
            name="email"
            required
            type="email"
          />
          <TextField
            aria-describedby="external-email-note"
            error="Wpisz poprawny numer telefonu."
            hint="Podaj numer z prefiksem kraju."
            label="Telefon"
            name="phone"
            type="tel"
          />
          <p className="text-caption text-ink-muted" id="external-email-note">
            Dodatkowy opis przekazany przez rodzica pola.
          </p>
          <TextField
            disabled
            label="Pole wyłączone"
            name="disabled"
            value="Wartość przykładowa"
            readOnly
          />
          <Textarea
            hint="Możesz wpisać kilka zdań."
            label="Wiadomość"
            name="message"
            rows={3}
          />
          <Textarea
            error="To pole wymaga uzupełnienia."
            label="Uwagi wymagane"
            name="notes"
            required
          />
          <Select
            hint="Wybierz jedną z przykładowych opcji."
            label="Rodzaj materiału"
            name="material"
            defaultValue="ebook"
          >
            <option value="ebook">E-book PDF</option>
            <option value="book">Książka papierowa</option>
          </Select>
          <Select
            disabled
            label="Niedostępny wybór"
            name="disabled-select"
            defaultValue="none"
          >
            <option value="none">Brak opcji</option>
          </Select>
        </div>
      </section>

      <section aria-labelledby="ui-checks-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="ui-checks-title"
        >
          Checkboxy, zgody i radio
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Checkbox
            label="Chcę otrzymywać materiały e-mailem"
            name="newsletter"
          />
          <Checkbox
            checked
            label="Akceptuję regulamin"
            name="terms"
            onChange={() => undefined}
            required
            description="Zgoda demonstracyjna z dodatkowym objaśnieniem wielowierszowym."
          />
          <Checkbox
            disabled
            label="Zgoda niedostępna"
            name="disabled-consent"
          />
          <Checkbox
            error="Ta zgoda jest wymagana."
            hint="Możesz sprawdzić, że oba opisy są powiązane."
            label="Zgoda z błędem"
            name="error-consent"
            required
          />
        </div>
        <fieldset className="space-y-2">
          <legend className="font-interface text-label font-bold">
            Typ kupującego
          </legend>
          <Radio label="Osoba prywatna" name="customer" value="private" />
          <Radio
            label="Firma"
            name="customer"
            value="business"
            description="Dane firmowe zostaną podane w kolejnym kroku."
          />
        </fieldset>
        <fieldset className="space-y-3">
          <legend className="font-interface text-label font-bold">
            Wybierz dostawę
          </legend>
          <RadioCard
            checked={selectedShipping === "courier"}
            description="Dostawa pod wskazany adres."
            name="shipping"
            onChange={() => setSelectedShipping("courier")}
            required
            title="Kurier"
            trailingContent="14,99 zł"
            value="courier"
          />
          <RadioCard
            checked={selectedShipping === "pickup"}
            description="Odbiór w wybranym punkcie."
            name="shipping"
            onChange={() => setSelectedShipping("pickup")}
            title="Punkt odbioru"
            trailingContent="9,99 zł"
            value="pickup"
          />
        </fieldset>
        <fieldset className="space-y-3">
          <legend className="font-interface text-label font-bold">
            Wybierz płatność
          </legend>
          <RadioCard
            checked={selectedPayment === "card"}
            description="Przykładowa karta wyboru bez integracji płatniczej."
            name="payment"
            onChange={() => setSelectedPayment("card")}
            title="Karta płatnicza"
            trailingContent="Karta"
            value="card"
          />
          <RadioCard
            checked={selectedPayment === "transfer"}
            description="Wybór pojedynczej opcji przez wspólne name."
            name="payment"
            onChange={() => setSelectedPayment("transfer")}
            title="BLIK"
            trailingContent="BLIK"
            value="transfer"
          />
        </fieldset>
        <Checkbox
          description="Zgoda ma wielowierszową etykietę; cały wiersz jest klikalny."
          label="Potwierdzam, że przed zakupem zapoznam się z warunkami korzystania z wybranego produktu oraz informacjami o dostawie."
          name="long-consent"
          variant="card"
        />
      </section>

      <section aria-labelledby="ui-badges-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="ui-badges-title"
        >
          Badge — typy i statusy
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          {(
            [
              "VOUCHER",
              "KSIĄŻKA",
              "AUDIOBOOK",
              "KURS PDF",
              "E-BOOK PDF",
              "AKTYWNY",
              "WYGASA WKRÓTCE",
              "ZREALIZOWANY",
              "BESTSELLER",
              "OPŁACONE",
              "WYSYŁKA W TOKU",
            ] as const
          ).map((label) => (
            <Badge key={label} label={label} />
          ))}
        </div>
      </section>

      <section aria-labelledby="ui-prices-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="ui-prices-title"
        >
          Price — kwoty przekazywane w groszach
        </h2>
        <div className="flex flex-wrap gap-6 rounded-card border border-border p-4">
          <Price amountInGrosze={44700} />
          <Price amountInGrosze={0} />
          <Price amountInGrosze={5} />
          <Price amountInGrosze={44700} previousAmountInGrosze={49900} />
          <Price amountInGrosze={44700} vatRate="EXEMPT" />
          <Price amountInGrosze={44700} vatRate="RATE_0" />
        </div>
      </section>

      <section aria-labelledby="ui-products-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="ui-products-title"
        >
          ProductCard — lokalne dane demonstracyjne
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <ProductCard
            description="Przewodnik w formacie PDF. Nazwa i opis mogą zajmować kilka wierszy."
            href="/sklep/ebook"
            image={
              <span className="flex h-full items-center justify-center font-interface text-label font-bold text-ink">
                Podgląd okładki e-booka
              </span>
            }
            imageAlt="Obszar demonstracyjny okładki e-booka"
            isBestseller
            metric="PDF · 148 stron"
            onAddToCart={() =>
              setDemoMessage("Podgląd: akcja przycisku e-booka.")
            }
            priceInGrosze={44700}
            title="Świadoma sensoryczność — przewodnik"
            type="E-BOOK PDF"
          />
          <ProductCard
            description="Książka papierowa z przykładową metryką wysyłki."
            href="/sklep/ksiazka"
            image={
              <span className="flex h-full items-center justify-center font-interface text-label font-bold text-ink-muted">
                Podgląd okładki książki
              </span>
            }
            imageAlt="Obszar demonstracyjny okładki książki"
            metric="Wysyłka w 2 dni"
            onAddToCart={() =>
              setDemoMessage("Podgląd: akcja przycisku książki.")
            }
            priceInGrosze={5900}
            title="Integracja sensoryczna w codzienności"
            type="KSIĄŻKA"
          />
          <ProductCard
            description="Przykładowy voucher z poprzednią ceną."
            href="/sklep/voucher"
            image={
              <span className="flex h-full items-center justify-center font-interface text-label font-bold text-ink-muted">
                Obraz demonstracyjny vouchera
              </span>
            }
            imageAlt="Obszar demonstracyjny vouchera"
            metric="Ważny 12 miesięcy"
            onAddToCart={() =>
              setDemoMessage("Podgląd: akcja przycisku vouchera.")
            }
            previousPriceInGrosze={49900}
            priceInGrosze={44700}
            title="Voucher na konsultację"
            type="VOUCHER"
          />
        </div>
      </section>

      <section aria-labelledby="ui-accordion-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="ui-accordion-title"
        >
          Accordion — „Zanim kupisz”
        </h2>
        <p className="text-caption text-ink-muted">
          Tryb pojedynczy: otwarcie jednego panelu zamyka poprzedni. Użyj
          strzałek góra/dół lub Home/End, by przenieść fokus.
        </p>
        <Accordion items={questions} />
        <h3 className="font-interface text-label font-bold">
          Przykład otwartego panelu
        </h3>
        <Accordion
          defaultExpandedIds={["digital-delivery"]}
          items={questions}
        />
      </section>

      <section aria-labelledby="ui-alerts-title" className="space-y-3">
        <h2
          className="font-interface text-subtitle font-bold"
          id="ui-alerts-title"
        >
          Alerty
        </h2>
        <Alert title="Informacja" variant="info">
          Przykładowa wiadomość informacyjna.
        </Alert>
        <Alert title="Sukces" variant="success">
          Zmiany zapisano w tym lokalnym podglądzie.
        </Alert>
        <Alert title="Ostrzeżenie" variant="warning">
          Jeden z Twoich voucherów wygasa za 47 dni.
        </Alert>
        <Alert title="Błąd" variant="error">
          Nie udało się wykonać przykładowej czynności.
        </Alert>
      </section>

      <section aria-labelledby="ui-breadcrumb-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="ui-breadcrumb-title"
        >
          Breadcrumbs
        </h2>
        <Breadcrumbs
          items={[
            { href: "/sklep", label: "Sklep" },
            { href: "/sklep/vouchery", label: "Vouchery" },
            { label: "Konsultacja z psychologiem" },
          ]}
        />
      </section>

      <Modal
        onOpenChange={setModalOpen}
        open={isModalOpen}
        title="Przykładowe okno"
      >
        <p className="text-body-small">
          Natywny dialog ogranicza fokus do okna, zamyka się klawiszem Escape i
          przywraca fokus do elementu otwierającego. Tło nie przewija się
          podczas otwarcia.
        </p>
      </Modal>
    </div>
  );
}
