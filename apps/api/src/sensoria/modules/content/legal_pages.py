# ruff: noqa: E501
"""Draft legal and information pages shipped with the shop (Polish).

Pages are inserted as drafts and never overwrite edits. Items marked [UZUPEŁNIJ] are facts the
code cannot know (tax id, e-mail). The texts follow the shop's actual behaviour but must be reviewed
by a lawyer before publication.

Run: python -m sensoria.modules.content.legal_pages [--publish]
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from sqlalchemy import select

from sensoria.database import SessionFactory
from sensoria.modules.admin import models as _admin_models  # noqa: F401  (registers FK targets)

from .models import ContentPage

SELLER = "Sensoria Terapia — Anna Parakiewicz, ul. Knosały 7B/A, 10-015 Olsztyn, NIP: [UZUPEŁNIJ]"
CONTACT = "adres e-mail: [UZUPEŁNIJ]"


def h(text: str) -> dict[str, Any]:
    return {"type": "h2", "text": text}


def p(text: str) -> dict[str, Any]:
    return {"type": "p", "text": text}


def ul(*items: str) -> dict[str, Any]:
    return {"type": "list", "items": list(items)}


PAGES: dict[str, dict[str, Any]] = {
    "regulamin": {
        "title": "Regulamin sklepu",
        "summary": "Zasady składania zamówień, płatności, dostawy, odstąpienia od umowy i reklamacji.",
        "blocks": [
            h("§1 Postanowienia ogólne"),
            p(
                f"Sklep internetowy dostępny pod adresem sensoria.shop prowadzi: {SELLER}; {CONTACT}."
            ),
            p(
                "Regulamin określa zasady korzystania ze sklepu i zawierania umów sprzedaży na odległość. "
                "Przed złożeniem zamówienia klient zapoznaje się z regulaminem i akceptuje go w formularzu zamówienia."
            ),
            p(
                "Wymagania techniczne: urządzenie z dostępem do internetu, aktualna przeglądarka, obsługa plików "
                "cookies niezbędnych do działania koszyka oraz — dla plików PDF — przeglądarka lub program do ich odczytu."
            ),
            h("§2 Oferta"),
            p("Sklep oferuje cztery rodzaje produktów:"),
            ul(
                "vouchery na wizyty (online lub w gabinecie) — usługa świadczona po zrealizowaniu vouchera;",
                "książki papierowe — towar wysyłany lub odbierany osobiście;",
                "e-booki i kursy w formacie PDF — treści cyfrowe;",
                "audiobooki — treści cyfrowe dostępne do odsłuchu w przeglądarce.",
            ),
            p(
                "Ceny podane w sklepie są cenami brutto w złotych polskich i zawierają podatek VAT według stawki "
                "wskazanej przy produkcie. Przy obniżkach sklep podaje najniższą cenę z 30 dni przed obniżką."
            ),
            h("§3 Składanie zamówień"),
            p(
                "Zamówienie można złożyć bez zakładania konta. Klient wybiera produkty, podaje adres e-mail oraz — dla "
                "książek — dane dostawy, wybiera metodę płatności i akceptuje regulamin. Zamówienie jest wiążące po "
                "kliknięciu przycisku „Zamawiam i płacę”, a umowa zostaje zawarta w chwili potwierdzenia zamówienia."
            ),
            p(
                "Zamówienie oczekujące na płatność jest rezerwowane przez ograniczony czas. Po jego upływie niezapłacone "
                "zamówienie wygasa, a rezerwacja produktów jest zwalniana."
            ),
            h("§4 Płatności"),
            p(
                "Płatności obsługuje Stripe Payments Europe Ltd. Dostępne metody: BLIK, karta płatnicza oraz portfele "
                "Google Pay i Apple Pay. Dane karty są wprowadzane na stronie operatora płatności i nie trafiają do sklepu."
            ),
            p(
                "Zamówienie jest uznawane za opłacone po potwierdzeniu płatności przez operatora. Potwierdzenie "
                "zamówienia oraz paragon lub faktura VAT są dostępne na stronie zamówienia i wysyłane e-mailem. "
                "Fakturę VAT wystawiamy na dane firmy podane w zamówieniu."
            ),
            h("§5 Dostawa i wydanie produktów"),
            ul(
                "Treści cyfrowe (e-booki, kursy PDF, audiobooki) są udostępniane niezwłocznie po potwierdzeniu płatności "
                "w bibliotece klienta i w linku z wiadomości e-mail. Pliki PDF są oznaczane danymi nabywcy.",
                "Vouchery są wystawiane po potwierdzeniu płatności i przesyłane e-mailem w formie pliku PDF z kodem. "
                "Voucher w prezencie wysyłamy obdarowanej osobie w wybranym dniu.",
                "Książki wysyłamy przesyłką InPost (Paczkomat lub kurier) albo wydajemy w gabinecie przy ul. Knosały 7B/A "
                "w Olsztynie. Koszt dostawy jest podawany w koszyku przed złożeniem zamówienia; odbiór w gabinecie jest bezpłatny.",
            ),
            p("O nadaniu przesyłki i o gotowości zamówienia do odbioru informujemy e-mailem."),
            h("§6 Vouchery"),
            p(
                "Voucher jest ważny przez okres wskazany na voucherze, liczony od dnia wystawienia (dla vouchera w prezencie — "
                "od dnia wysyłki obdarowanej osobie), do końca ostatniego dnia ważności. Voucher jest realizowany w gabinecie lub "
                "online po podaniu kodu; nie podlega wymianie na gotówkę. Po upływie ważności można poprosić o jego przedłużenie "
                "w koncie klienta lub wiadomością do sprzedawcy — decyzja należy do sprzedawcy."
            ),
            h("§7 Prawo odstąpienia od umowy"),
            p(
                "Konsument może odstąpić od umowy zawartej na odległość w terminie 14 dni bez podawania przyczyny. "
                "Dla książek termin liczy się od dnia objęcia towaru w posiadanie, dla voucherów — od dnia zawarcia umowy."
            ),
            p(
                "Aby odstąpić od umowy, należy złożyć oświadczenie, np. formularzem na stronie „Odstąpienie od umowy” lub e-mailem."
            ),
            p(
                "Prawo odstąpienia nie przysługuje w odniesieniu do treści cyfrowych niedostarczanych na nośniku materialnym, "
                "jeżeli spełnianie świadczenia rozpoczęło się za wyraźną zgodą konsumenta przed upływem terminu odstąpienia, "
                "po poinformowaniu go o utracie prawa. Taką zgodę klient wyraża w formularzu zamówienia, zaznaczając odpowiednie pole."
            ),
            p(
                "Zwrot płatności następuje w ciągu 14 dni od otrzymania oświadczenia, tą samą metodą płatności, a jeśli "
                "dotyczy książki — nie później niż po otrzymaniu zwróconego towaru lub dowodu jego odesłania. "
                "Koszt odesłania książki ponosi konsument."
            ),
            h("§8 Reklamacje"),
            p(
                "Sprzedawca odpowiada za zgodność towaru, treści cyfrowej i usługi z umową na zasadach określonych w "
                "przepisach prawa. Reklamację można złożyć formularzem „Zwroty i reklamacje” lub e-mailem, opisując wadę."
            ),
            p(
                "Sprzedawca odpowiada na reklamację w ciągu 14 dni od jej otrzymania. Brak odpowiedzi oznacza jej uznanie."
            ),
            h("§9 Opinie"),
            p(
                "Opinie o produktach mogą dodawać wyłącznie osoby, które je kupiły. Opinie są moderowane — nie publikujemy "
                "treści bezprawnych, obraźliwych ani niezwiązanych z produktem. Prośby o opinię wysyłamy tylko za zgodą klienta."
            ),
            h("§10 Dane osobowe"),
            p("Zasady przetwarzania danych osobowych opisuje Polityka prywatności."),
            h("§11 Postanowienia końcowe"),
            p(
                "Konsument może skorzystać z pozasądowych sposobów rozpatrywania sporów, w tym z platformy internetowej "
                "dostępnej pod adresem ec.europa.eu/consumers/odr, oraz z pomocy powiatowego (miejskiego) rzecznika konsumentów."
            ),
            p(
                "Do umów zawieranych w sklepie stosuje się prawo polskie. Regulamin może zostać zmieniony; zmiana nie "
                "wpływa na zamówienia złożone przed jej wprowadzeniem."
            ),
        ],
    },
    "polityka-prywatnosci": {
        "title": "Polityka prywatności",
        "summary": "Jak przetwarzamy dane osobowe klientek sklepu Sensoria.",
        "blocks": [
            h("1. Administrator danych"),
            p(f"Administratorem danych jest {SELLER}; {CONTACT}."),
            h("2. Jakie dane i w jakim celu przetwarzamy"),
            ul(
                "realizacja zamówienia i umowy (adres e-mail, imię i nazwisko, adres dostawy, numer telefonu dla kuriera, "
                "dane do faktury, historia zamówienia) — podstawa: art. 6 ust. 1 lit. b RODO;",
                "obowiązki podatkowe i rachunkowe (paragony, faktury) — art. 6 ust. 1 lit. c RODO; dokumenty przechowujemy "
                "przez okres wymagany przepisami;",
                "założenie i prowadzenie konta klienta (dane konta, historia, biblioteka, adresy) — art. 6 ust. 1 lit. b RODO;",
                "dochodzenie i obrona roszczeń oraz bezpieczeństwo sklepu (dzienniki zdarzeń, ograniczanie prób logowania) — "
                "art. 6 ust. 1 lit. f RODO;",
                "wiadomości o nowych materiałach, przypomnienia o voucherach i prośby o opinię — wyłącznie za Twoją zgodą, "
                "art. 6 ust. 1 lit. a RODO; zgodę możesz wycofać w każdej chwili w ustawieniach konta;",
                "obsługa zgłoszeń (odstąpienie, zwroty, reklamacje) — art. 6 ust. 1 lit. b i c RODO.",
            ),
            h("3. Odbiorcy danych"),
            p("Dane mogą być powierzane lub udostępniane podmiotom, z których usług korzystamy:"),
            ul(
                "operator płatności Stripe Payments Europe Ltd. — obsługa płatności;",
                "InPost S.A. — dostawa książek (imię, nazwisko, telefon, adres lub punkt odbioru);",
                "dostawca poczty transakcyjnej — wysyłka wiadomości o zamówieniu;",
                "dostawca hostingu i kopii zapasowych — utrzymanie sklepu;",
                "biuro rachunkowe i doradcy prawni — w zakresie niezbędnym do obsługi księgowej i prawnej.",
            ),
            p(
                "Nie sprzedajemy danych i nie podejmujemy decyzji w sposób wyłącznie zautomatyzowany."
            ),
            h("4. Okres przechowywania"),
            p(
                "Dane zamówień przechowujemy przez okres wymagany przepisami podatkowymi, a dane konta — do czasu jego usunięcia. "
                "Zgody przechowujemy do czasu ich wycofania, a ślad ich wyrażenia — przez okres przedawnienia roszczeń."
            ),
            h("5. Twoje prawa"),
            p(
                "Masz prawo dostępu do danych, ich sprostowania, usunięcia, ograniczenia przetwarzania, przenoszenia, sprzeciwu "
                "oraz wycofania zgody. W koncie klienta (Dane i zgody) możesz pobrać kopię danych i usunąć konto. "
                "Masz też prawo wniesienia skargi do Prezesa Urzędu Ochrony Danych Osobowych."
            ),
            h("6. Pliki cookies"),
            p("Szczegóły znajdziesz w Polityce cookies."),
            h("7. Bezpieczeństwo"),
            p(
                "Stosujemy szyfrowane połączenia (HTTPS), haszowanie haseł, ograniczanie prób logowania, kontrolę dostępu do "
                "plików oraz szyfrowane kopie zapasowe."
            ),
        ],
    },
    "polityka-cookies": {
        "title": "Polityka cookies",
        "summary": "Jakich plików cookies używamy i jak zmienić swój wybór.",
        "blocks": [
            p(
                "Pliki cookies to małe pliki zapisywane w Twojej przeglądarce. Używamy ich w sposób opisany poniżej."
            ),
            h("Niezbędne (zawsze włączone)"),
            ul(
                "cart_token — zapamiętuje Twój koszyk (do 30 dni);",
                "sensoria_session i sensoria_csrf — logowanie do konta i ochrona przed fałszowaniem żądań;",
                "sensoria_cookie_consent — zapamiętuje Twój wybór dotyczący cookies (do 180 dni).",
            ),
            p("Bez nich koszyk i logowanie nie działają, dlatego nie wymagają zgody."),
            h("Analityczne i marketingowe"),
            p(
                "Obecnie sklep nie używa narzędzi analitycznych ani marketingowych. Jeżeli to się zmieni, uruchomimy je "
                "dopiero po Twojej zgodzie, a ta strona zostanie zaktualizowana."
            ),
            h("Jak zmienić wybór"),
            p(
                "Wybór możesz zmienić w każdej chwili przyciskiem „Ustawienia cookies” w stopce strony. "
                "Cookies możesz też usunąć w ustawieniach przeglądarki — wtedy koszyk zostanie utracony."
            ),
            h("Rejestr zgód"),
            p(
                "Twój wybór zapisujemy razem z datą i wersją polityki, aby wykazać, że zgoda została wyrażona."
            ),
        ],
    },
    "dostawa-i-platnosci": {
        "title": "Dostawa i płatności",
        "summary": "Koszty i czas dostawy oraz dostępne metody płatności.",
        "blocks": [
            h("Płatności"),
            p(
                "Zapłacisz BLIKIEM, kartą oraz przez Google Pay i Apple Pay. Płatność obsługuje Stripe — dane karty nie trafiają do sklepu."
            ),
            h("Materiały cyfrowe i vouchery"),
            p(
                "E-booki, kursy PDF i audiobooki dostajesz od razu po opłaceniu zamówienia — w bibliotece konta i w linku z e-maila. "
                "Voucher przychodzi e-mailem jako plik PDF z kodem."
            ),
            h("Książki papierowe"),
            ul(
                "Paczkomat InPost lub kurier InPost — koszt i próg darmowej dostawy widzisz w koszyku;",
                "odbiór osobisty w gabinecie, ul. Knosały 7B/A w Olsztynie — bezpłatnie; napiszemy, gdy zamówienie będzie gotowe.",
            ),
            p(
                "Gdy paczka zostanie nadana, dostaniesz e-mail z numerem przesyłki i linkiem do śledzenia."
            ),
            h("Faktura"),
            p(
                "Paragon wystawiamy automatycznie. Fakturę VAT dla firmy wystawiamy, gdy podasz NIP w zamówieniu."
            ),
        ],
    },
    "o-autorce": {
        "title": "O autorce",
        "summary": "Anna Parakiewicz i gabinet Sensoria w Olsztynie.",
        "blocks": [
            p(
                "Anna Teresa Parakiewicz prowadzi w Olsztynie gabinet Sensoria — Instytut Diagnozy i Terapii. Materiały w sklepie "
                "powstają z pracy z dziećmi i rodzinami: książki, e-booki, kursy i audiobooki o zmysłach, integracji sensorycznej "
                "i bliskości."
            ),
            p(
                "[UZUPEŁNIJ: krótki życiorys, wykształcenie, doświadczenie i zdjęcie — treść zatwierdza autorka]"
            ),
            h("Gabinet"),
            p("ul. Knosały 7B/A, 10-015 Olsztyn. Wejście bezpośrednio z ulicy, parter."),
        ],
    },
}


async def install(*, publish: bool = False) -> dict[str, str]:
    """Insert missing pages (never overwrites); returns slug -> created|exists."""
    result: dict[str, str] = {}
    async with SessionFactory() as session, session.begin():
        for slug, data in PAGES.items():
            existing = await session.scalar(select(ContentPage).where(ContentPage.slug == slug))
            if existing is not None:
                result[slug] = "exists"
                continue
            session.add(
                ContentPage(
                    slug=slug,
                    title=data["title"],
                    summary=data["summary"],
                    blocks=data["blocks"],
                    status="published" if publish else "draft",
                )
            )
            result[slug] = "created"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Wgraj szkice stron prawnych i informacyjnych.")
    parser.add_argument(
        "--publish", action="store_true", help="opublikuj od razu (po weryfikacji prawnej)"
    )
    args = parser.parse_args()
    for slug, state in asyncio.run(install(publish=args.publish)).items():
        print(f"{slug}: {state}")


if __name__ == "__main__":
    main()
