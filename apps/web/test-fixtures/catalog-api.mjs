import http from "node:http";
import { readFileSync } from "node:fs";

const pdfSample = readFileSync(
  new URL(
    "../../api/tests/fixtures/sample-fragment-fixture.pdf",
    import.meta.url,
  ),
);
const audioSample = readFileSync(
  new URL("../../api/tests/fixtures/sample-audio-fixture.mp3", import.meta.url),
);

const facets = {
  categories: [
    ["vouchery", "Vouchery na wizyty"],
    ["ksiazki-papierowe", "Książki papierowe"],
    ["audiobooki", "Audiobooki"],
    ["kursy-pdf", "Kursy PDF"],
  ],
  kinds: [
    ["VOUCHER", "Voucher"],
    ["BOOK", "Książka papierowa"],
    ["AUDIOBOOK", "Audiobook"],
    ["DIGITAL", "Produkt cyfrowy"],
  ],
  audiences: [
    ["rodzice", "Rodzice"],
    ["dorosli", "Dorośli"],
    ["specjalisci", "Specjaliści"],
  ],
  deliveries: [
    ["digital", "Dostawa cyfrowa"],
    ["parcel", "Przesyłka"],
  ],
  prices: [
    ["up_to_5000", "Do 50 zł"],
    ["5001_to_15000", "Powyżej 50 do 150 zł"],
    ["over_15000", "Powyżej 150 zł"],
  ],
};

const options = (values) =>
  values.map(([value, label], index) => ({
    value,
    label,
    count: index === 0 ? 12 : 6,
  }));

const voucherProduct = {
  id: "00000000-0000-4000-8000-000000000901",
  slug: "konsultacja-z-psychologiem",
  name: "Konsultacja z psychologiem",
  kind: "VOUCHER",
  digital_label: null,
  vat_rate: "EXEMPT",
  is_available: true,
  short_description: "Czterdzieści pięć minut na dobry początek",
  description:
    "Pierwsze spotkanie, na którym nazywamy problem i ustalamy, czego naprawdę potrzeba.",
  price: 25000,
  compare_at_price: null,
  image: null,
  images: [],
  categories: [
    {
      name: "Vouchery na wizyty",
      slug: "vouchery-na-wizyty",
      parent_name: null,
      parent_slug: null,
    },
  ],
  audience_tags: [],
  meta_title: "Konsultacja z psychologiem — Sensoria",
  meta_description: "Voucher na konsultację z psychologiem.",
  voucher: {
    validity_months: 12,
    service_name: "Konsultacja z psychologiem",
    variants: [
      {
        id: "00000000-0000-4000-8000-000000000911",
        kind: "IN_PERSON",
        price: 25000,
      },
      {
        id: "00000000-0000-4000-8000-000000000912",
        kind: "ONLINE",
        price: 22000,
      },
    ],
  },
  book: null,
  audiobook: null,
  digital: null,
  related_products: [],
  published_at: "2026-01-01T00:00:00Z",
};

const digitalProduct = {
  id: "00000000-0000-4000-8000-000000000931",
  slug: "ebook-testowy",
  name: "E-book demonstracyjny",
  kind: "DIGITAL",
  digital_label: "EBOOK_PDF",
  vat_rate: "RATE_5",
  is_available: true,
  short_description: "Podtytuł pobrany z danych testowych.",
  description: "Opis demonstracyjny dostarczony przez fixture.",
  price: 7900,
  compare_at_price: 9900,
  image: null,
  images: [],
  categories: [
    {
      name: "Rozwój osobisty",
      slug: "rozwoj-osobisty",
      parent_name: "Doradztwo i rozwój osobisty",
      parent_slug: "doradztwo-i-rozwoj-osobisty",
    },
  ],
  audience_tags: ["Dorośli"],
  meta_title: "E-book demonstracyjny — test",
  meta_description: "Opis SEO e-booka testowego.",
  voucher: null,
  book: null,
  audiobook: null,
  digital: {
    page_count: 148,
    file_format: "PDF",
    edition: "2026",
    label: "EBOOK_PDF",
    lowest_price_before_discount: 8900,
    discount_started_at: "2026-09-01T00:00:00Z",
    sample_available: true,
    sample_pages: 2,
  },
  related_products: [],
  published_at: "2026-01-01T00:00:00Z",
};

const courseProduct = {
  ...digitalProduct,
  id: "00000000-0000-4000-8000-000000000932",
  slug: "kurs-testowy",
  name: "Kurs testowy PDF",
  digital_label: "COURSE_PDF",
  price: 12000,
  compare_at_price: null,
  digital: {
    page_count: null,
    file_format: "PDF",
    edition: null,
    label: "COURSE_PDF",
    lowest_price_before_discount: null,
    discount_started_at: null,
    sample_available: false,
    sample_pages: null,
  },
  related_products: [],
};

const bookProduct = {
  id: "00000000-0000-4000-8000-000000000941",
  slug: "produkt-ksiazka-testowa",
  name: "Książka testowa",
  kind: "BOOK",
  digital_label: null,
  vat_rate: "RATE_5",
  is_available: false,
  short_description: "Opis fizycznej książki.",
  description: "Treść testowa książki papierowej.",
  price: 5000,
  compare_at_price: null,
  image: null,
  images: [],
  categories: [
    {
      name: "Książki papierowe",
      slug: "ksiazki-papierowe",
      parent_name: null,
      parent_slug: null,
    },
  ],
  audience_tags: [],
  meta_title: "Książka testowa",
  meta_description: "Dane testowe.",
  voucher: null,
  digital: null,
  audiobook: null,
  book: {
    stock_quantity: 0,
    available_quantity: 0,
    weight_grams: 250,
    length_mm: 210,
    width_mm: 148,
    height_mm: 18,
    isbn: null,
    binding: "Oprawa miękka",
    shipping_business_days: 2,
    shipping_method: "Paczkomat InPost",
  },
  related_products: [],
  published_at: "2026-01-01T00:00:00Z",
};

const audiobookProduct = {
  ...bookProduct,
  id: "00000000-0000-4000-8000-000000000942",
  slug: "audiobook-testowy",
  name: "Audiobook testowy",
  kind: "AUDIOBOOK",
  is_available: true,
  short_description: "Audiobook w danych demonstracyjnych.",
  meta_title: "Audiobook testowy",
  meta_description: "Dane testowe.",
  book: null,
  audiobook: {
    duration_seconds: 15120,
    narrator: "Lektorka testowa",
    file_format: "MP3",
    sample_available: true,
    sample_duration_seconds: 8,
    chapters: [
      { title: "Pierwszy rozdział", length_seconds: 7200, position: 0 },
      { title: "Drugi rozdział", length_seconds: 7920, position: 1 },
    ],
  },
};

const lowStockBookProduct = {
  ...bookProduct,
  id: "00000000-0000-4000-8000-000000000943",
  slug: "ksiazka-ostatnie-egzemplarze",
  name: "Książka — ostatnie egzemplarze",
  is_available: true,
  book: {
    ...bookProduct.book,
    stock_quantity: 3,
    available_quantity: 3,
  },
};

const products = Array.from({ length: 25 }, (_, index) => {
  const kind = ["VOUCHER", "BOOK", "AUDIOBOOK", "DIGITAL"][index % 4];
  const digitalLabel = index % 4 === 3 ? "COURSE_PDF" : null;
  return {
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    slug: `produkt-testowy-${index + 1}`,
    name: `Produkt testowy ${index + 1}`,
    kind,
    digital_label: digitalLabel,
    short_description: "Opis z jawnie testowych danych API.",
    price: 7900 + index * 100,
    compare_at_price: null,
    image: null,
    book:
      kind === "BOOK"
        ? {
            weight_grams: 200,
            length_mm: null,
            width_mm: null,
            height_mm: null,
            isbn: "9780000000000",
          }
        : null,
    audiobook:
      kind === "AUDIOBOOK"
        ? { duration_seconds: 15120, narrator: "Lektor testowy", chapters: [] }
        : null,
    digital:
      kind === "DIGITAL"
        ? {
            page_count: 148,
            file_format: "PDF",
            edition: null,
            label: digitalLabel,
          }
        : null,
    voucher:
      kind === "VOUCHER"
        ? { validity_months: 12, service_name: "Wizyta testowa", variants: [] }
        : null,
  };
});

digitalProduct.related_products = products
  .filter((product) => product.kind === "DIGITAL")
  .slice(0, 3);

const server = http.createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  const cartToken = (request.headers.cookie ?? "")
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("cart_token="))
    ?.slice("cart_token=".length);
  const cartCounts = server.cartCounts;
  const currentCartCount = cartToken ? (cartCounts.get(cartToken) ?? 0) : 0;
  response.setHeader("Access-Control-Allow-Origin", "http://127.0.0.1:3102");
  response.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "X-Sample-Open-Id, Range");
  response.setHeader(
    "Access-Control-Expose-Headers",
    "Content-Type, Content-Length, Content-Range, Accept-Ranges",
  );
  if (request.method === "OPTIONS") {
    response.writeHead(204).end();
    return;
  }
  if (url.pathname === "/health") {
    response.writeHead(200).end("ok");
    return;
  }
  if (url.pathname === "/catalog/public/homepage") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        eyebrow: "INSTYTUT DIAGNOZY I TERAPII SENSORIA",
        headline: {
          before_emphasis: "Terapia",
          emphasis: "nie kończy się",
          after_emphasis: "w gabinecie.",
        },
        paragraph:
          "Vouchery na wizyty, książki, audiobooki i kursy przygotowane przez zespół, który od ponad dwudziestu lat pracuje z dziećmi, młodzieżą i dorosłymi.",
        catalog_button_label: "Zobacz materiały",
        voucher_button_label: "Kup voucher na wizytę",
        catalog_button_target: "/sklep",
        benefits: [
          { icon: "payment", text: "Płatność w 15 sekund" },
          { icon: "email", text: "Pliki od razu na mailu" },
          { icon: "parcel", text: "Paczkomat 24/7" },
          { icon: "voucher", text: "Voucher ważny 12 miesięcy" },
        ],
        product_selection: {
          voucher_id: null,
          audiobook_id: null,
          course_id: null,
        },
      }),
    );
    return;
  }
  if (url.pathname === "/catalog/public/search-presentation") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        suggested_queries: [
          "integracja sensoryczna",
          "terapia ręki",
          "nadwrażliwość",
          "voucher",
        ],
        contact_email: "kontakt@example.invalid",
        contact_phone: "+48 111 222 333",
      }),
    );
    return;
  }
  if (url.pathname === "/cart" && request.method === "GET") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        items: [],
        item_count: currentCartCount,
        expires_at: null,
        delivery: {
          requires_shipping: false,
          selected_method: null,
          available_quotes: [],
          requires_method_selection: false,
          threshold_basis_grosz: 0,
          free_shipping_threshold_grosz: null,
          remaining_amount_grosz: null,
          free_shipping_qualified: false,
          show_incentive: false,
          message: null,
        },
        discount_code: null,
        discount_notice: null,
        calculation: {
          items: [],
          vat_groups: [],
          exempt: {
            vat_rate: "EXEMPT",
            vat_label: "zw.",
            gross_grosz: 0,
            net_grosz: 0,
            tax_grosz: 0,
          },
          products_gross_grosz: 0,
          products_gross_before_discount_grosz: 0,
          discount_grosz: 0,
          discount_code: null,
          delivery: {
            resolved: true,
            gross_grosz: 0,
            net_grosz: 0,
            tax_grosz: 0,
            vat_rate: null,
            vat_label: null,
          },
          amount_due_grosz: 0,
          amount_due_is_final: true,
        },
      }),
    );
    return;
  }
  if (url.pathname === "/cart/items" && request.method === "POST") {
    const token = cartToken ?? `fixture-cart-${++server.nextCartToken}`;
    const itemCount = (cartCounts.get(token) ?? 0) + 1;
    cartCounts.set(token, itemCount);
    if (!cartToken) {
      response.setHeader(
        "Set-Cookie",
        `cart_token=${token}; Path=/api/cart; HttpOnly; SameSite=Lax`,
      );
    }
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ item_count: itemCount }));
    return;
  }
  if (url.pathname === "/products/konsultacja-z-psychologiem") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(voucherProduct));
    return;
  }
  if (url.pathname === "/products/produkt-ksiazka-testowa") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(bookProduct));
    return;
  }
  if (url.pathname === "/products/audiobook-testowy") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(audiobookProduct));
    return;
  }
  if (url.pathname === "/products/ksiazka-ostatnie-egzemplarze") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(lowStockBookProduct));
    return;
  }
  if (url.pathname === "/products/ebook-testowy") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(digitalProduct));
    return;
  }
  const sampleOpen = url.pathname.match(/^\/products\/([^/]+)\/sample\/open$/);
  if (sampleOpen && request.method === "POST") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        sample_url: `/products/${sampleOpen[1]}/sample?grant=fixture-sample-grant-000000000000000000000000`,
        content_type:
          sampleOpen[1] === "ebook-testowy" ? "application/pdf" : "audio/mpeg",
        pages: sampleOpen[1] === "ebook-testowy" ? 2 : null,
        duration_seconds: sampleOpen[1] === "audiobook-testowy" ? 8 : null,
        expires_in_seconds: 1800,
      }),
    );
    return;
  }
  if (url.pathname.endsWith("/sample") && url.searchParams.has("grant")) {
    const isPdf = url.pathname.includes("ebook-testowy");
    const body = isPdf ? pdfSample : audioSample;
    const range = request.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
    const start = range ? Number(range[1]) : 0;
    const end =
      range && range[2]
        ? Math.min(Number(range[2]), body.length - 1)
        : body.length - 1;
    if (start >= body.length || start > end) {
      response
        .writeHead(416, { "content-range": `bytes */${body.length}` })
        .end();
      return;
    }
    const chunk = body.subarray(start, end + 1);
    response.writeHead(range ? 206 : 200, {
      "content-type": isPdf ? "application/pdf" : "audio/mpeg",
      "content-length": String(chunk.length),
      "accept-ranges": "bytes",
      "content-disposition": `inline; filename="sample.${isPdf ? "pdf" : "mp3"}"`,
      ...(range
        ? { "content-range": `bytes ${start}-${end}/${body.length}` }
        : {}),
    });
    response.end(chunk);
    return;
  }
  if (url.pathname === "/products/kurs-testowy") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(courseProduct));
    return;
  }
  if (url.pathname === "/catalog/public/products/produkt-ksiazka-testowa") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        id: "00000000-0000-4000-8000-000000000921",
        kind: "BOOK",
        digital_label: null,
        name: "Książka testowa",
        slug: "produkt-ksiazka-testowa",
        short_description: "Dane przykładowe.",
        description: "Opis testowej książki.",
        price: 5000,
        compare_at_price: null,
        vat_rate: "RATE_5",
        is_available: true,
        images: [],
        offers: [{ name: null, price: 5000 }],
        categories: [],
        audience_tags: [],
        meta_title: "Książka testowa",
        meta_description: "Dane testowe.",
        og_image: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        published_at: "2026-01-01T00:00:00Z",
      }),
    );
    return;
  }
  if (url.pathname.startsWith("/products/")) {
    response.writeHead(404, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        error: {
          code: "PRODUCT_NOT_FOUND",
          message: "Nie znaleziono produktu.",
        },
      }),
    );
    return;
  }
  if (url.pathname === "/products" && url.searchParams.get("q") === "error") {
    response.writeHead(503, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        error: {
          code: "CATALOG_UNAVAILABLE",
          message: "Katalog jest chwilowo niedostępny.",
        },
      }),
    );
    return;
  }
  const page = Number(url.searchParams.get("page") || 1);
  const perPage = Number(url.searchParams.get("per_page") || 12);
  const searchValue = url.searchParams.get("q") || "";
  const emptySearch = searchValue === "brak" || searchValue.startsWith("<");
  const emptyFilters = url.searchParams.get("category") === "brak-produktow";
  const empty = emptySearch || emptyFilters;
  const body = {
    items: empty ? [] : products.slice((page - 1) * perPage, page * perPage),
    total: empty ? 0 : products.length,
    page,
    per_page: perPage,
    total_pages: empty ? 0 : Math.ceil(products.length / perPage),
    facets: Object.fromEntries(
      Object.entries(facets).map(([name, values]) => [name, options(values)]),
    ),
    suggestions: emptySearch
      ? {
          popular_queries: ["integracja sensoryczna"],
          related_products: products.slice(0, 3),
        }
      : null,
  };
  const send = () => {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(body));
  };
  if (url.searchParams.get("q") === "delay") setTimeout(send, 1200);
  else send();
});

server.cartCounts = new Map();
server.nextCartToken = 0;
server.listen(Number(process.env.PORT || 8017), "127.0.0.1");
