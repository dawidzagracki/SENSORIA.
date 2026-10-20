"""Typed catalog input and output shapes; no HTTP endpoints are exposed yet."""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from sensoria.shared.types import VatRate

from .types import DigitalLabel, ProductKind, ProductStatus, VoucherVariantKind


class PublicImage(BaseModel):
    url: str
    alt: str


class PublicOffer(BaseModel):
    name: str | None = None
    price: int


class PublicCategoryRef(BaseModel):
    name: str
    slug: str
    parent_name: str | None = None
    parent_slug: str | None = None


class PublicProduct(BaseModel):
    id: UUID
    kind: ProductKind
    digital_label: DigitalLabel | None = None
    name: str
    slug: str
    short_description: str | None
    description: str | None
    price: int | None
    compare_at_price: int | None
    vat_rate: VatRate | None
    is_available: bool
    images: list[PublicImage]
    offers: list[PublicOffer]
    categories: list[PublicCategoryRef]
    audience_tags: list[str]
    meta_title: str
    meta_description: str
    og_image: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime


class PublicCategory(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    parent_slug: str | None
    parent_name: str | None
    position: int
    published_product_count: int
    meta_title: str
    meta_description: str
    og_image: str | None
    created_at: datetime
    updated_at: datetime


class PublicCategoryPage(PublicCategory):
    products: list[PublicProduct]


class SitemapEntry(BaseModel):
    kind: Literal["product", "category"]
    slug: str
    last_modified: datetime


class PublicSitemap(BaseModel):
    entries: list[SitemapEntry]


class CatalogFacetOption(BaseModel):
    """One available facet option; zero-count options remain present."""

    value: str
    label: str
    count: int


class CatalogFacets(BaseModel):
    categories: list[CatalogFacetOption]
    kinds: list[CatalogFacetOption]
    audiences: list[CatalogFacetOption]
    deliveries: list[CatalogFacetOption]
    prices: list[CatalogFacetOption]


class CatalogListItem(BaseModel):
    """Safe product-card data; protected downloadable files are never exposed."""

    id: UUID
    slug: str
    name: str
    kind: ProductKind
    vat_rate: VatRate | None = None
    is_available: bool
    digital_label: DigitalLabel | None = None
    short_description: str | None
    price: int
    compare_at_price: int | None
    # Omnibus: lowest price in the 30 days before the current reduction, when one is advertised.
    lowest_price_before_discount: int | None = None
    discount_started_at: datetime | None = None
    image: PublicImage | None
    book: "CatalogBookDetails | None" = None
    audiobook: "CatalogAudiobookDetails | None" = None
    digital: "CatalogDigitalDetails | None" = None
    voucher: "CatalogVoucherDetails | None" = None


class CatalogBookDetails(BaseModel):
    stock_quantity: int
    available_quantity: int
    weight_grams: int | None
    length_mm: int | None
    width_mm: int | None
    height_mm: int | None
    isbn: str | None
    binding: str | None = None
    shipping_business_days: int | None = None
    shipping_method: str | None = None


class CatalogBookProductDetails(CatalogBookDetails):
    pass


class CatalogAudiobookChapter(BaseModel):
    title: str
    length_seconds: int
    position: int


class CatalogAudiobookDetails(BaseModel):
    duration_seconds: int | None
    narrator: str | None
    chapters: list[CatalogAudiobookChapter]
    file_format: str | None = None
    sample_available: bool = False
    sample_duration_seconds: int | None = None


class CatalogDigitalDetails(BaseModel):
    page_count: int | None
    file_format: str
    edition: str | None
    label: DigitalLabel
    lowest_price_before_discount: int | None = None
    discount_started_at: datetime | None = None
    sample_available: bool = False
    sample_pages: int | None = None


class CatalogVoucherVariant(BaseModel):
    id: UUID
    kind: VoucherVariantKind
    price: int


class CatalogVoucherDetails(BaseModel):
    validity_months: int
    service_name: str
    variants: list[CatalogVoucherVariant]


class CatalogSearchSuggestions(BaseModel):
    """Separate no-result guidance; suggestion products are not search matches."""

    popular_queries: list[str]
    related_products: list[CatalogListItem]


class CatalogListResponse(BaseModel):
    items: list[CatalogListItem]
    total: int
    page: int
    per_page: int
    total_pages: int
    facets: CatalogFacets
    suggestions: CatalogSearchSuggestions | None = None


class CatalogProductDetail(CatalogListItem):
    description: str | None
    meta_title: str
    meta_description: str
    og_image: str | None = None
    audience_tags: list[str] = Field(default_factory=list)
    images: list[PublicImage]
    categories: list[PublicCategoryRef]
    book: CatalogBookProductDetails | None = None
    related_products: list[CatalogListItem]
    published_at: datetime


class ProductImageData(BaseModel):
    """Image reference in stable gallery order."""

    url: str = Field(min_length=1, max_length=2048)
    alt: str = Field(min_length=1, max_length=500)
    position: int = Field(default=0, ge=0)


class ProductVoucherVariantInput(BaseModel):
    """Voucher price option; amount remains an integer number of grosz."""

    kind: VoucherVariantKind
    price: StrictInt = Field(ge=0)


class ProductVoucherInput(BaseModel):
    """Draft voucher data with optional incompleteness before publication."""

    validity_months: int = Field(default=12, gt=0)
    service_name: str = ""
    variants: list[ProductVoucherVariantInput] = Field(default_factory=list)


class ProductBookInput(BaseModel):
    """Physical book data; incomplete drafts can omit shipping measurements."""

    stock_quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=0, ge=0)
    weight_grams: int | None = Field(default=None, gt=0)
    length_mm: int | None = Field(default=None, gt=0)
    width_mm: int | None = Field(default=None, gt=0)
    height_mm: int | None = Field(default=None, gt=0)
    isbn: str | None = Field(default=None, max_length=20)
    binding: str | None = Field(default=None, max_length=80)
    shipping_business_days: int | None = Field(default=None, gt=0)
    shipping_method: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_dimensions(self) -> Self:
        dimensions = (self.length_mm, self.width_mm, self.height_mm)
        if any(value is not None for value in dimensions) and any(
            value is None for value in dimensions
        ):
            raise ValueError("Podaj wszystkie trzy wymiary książki albo pozostaw je puste.")
        return self


class ProductAudiobookChapterInput(BaseModel):
    """Ordered chapter metadata without the underlying paid audio file."""

    title: str = Field(min_length=1, max_length=200)
    length_seconds: int = Field(gt=0)
    position: int = Field(ge=0)


class ProductAudiobookInput(BaseModel):
    """Audiobook details; publication requires duration, narrator, and chapters."""

    duration_seconds: int | None = Field(default=None, gt=0)
    narrator: str | None = None
    file_format: str | None = Field(default=None, max_length=30)
    sample_file_path: str | None = Field(
        default=None,
        max_length=41,
        pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.mp3$",
    )
    sample_duration_seconds: int | None = Field(default=None, gt=0)
    sample_enabled: bool = False
    chapters: list[ProductAudiobookChapterInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_chapter_duration(self) -> Self:
        """Reject a supplied chapter list that does not match total duration."""

        if self.duration_seconds is not None and self.chapters:
            chapter_total = sum(chapter.length_seconds for chapter in self.chapters)
            if chapter_total != self.duration_seconds:
                raise ValueError(
                    "Suma czasów rozdziałów musi być równa całkowitemu czasowi audiobooka."
                )
        if self.sample_enabled and (
            not self.sample_file_path or self.sample_duration_seconds is None
        ):
            raise ValueError("Włączona próbka audio wymaga pliku i czasu trwania.")
        return self


class ProductDigitalInput(BaseModel):
    """Course/e-book label within the single DIGITAL product kind."""

    page_count: int | None = Field(default=None, gt=0)
    file_format: str = "PDF"
    edition: str | None = Field(default=None, max_length=100)
    label: DigitalLabel = DigitalLabel.EBOOK_PDF
    sample_file_path: str | None = Field(
        default=None,
        max_length=41,
        pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.pdf$",
    )
    sample_pages: int | None = Field(default=None, gt=0)
    sample_enabled: bool = False

    @model_validator(mode="after")
    def validate_sample(self) -> Self:
        """Require a separate prepared PDF and page count when enabling a sample."""

        if self.sample_enabled and (not self.sample_file_path or self.sample_pages is None):
            raise ValueError("Włączony fragment PDF wymaga pliku i liczby stron.")
        return self


class ProductDraftInput(BaseModel):
    """Common draft shape; publication completeness is checked by catalog service."""

    kind: ProductKind
    name: str = ""
    slug: str | None = None
    short_description: str | None = Field(default=None, max_length=500)
    description: str | None = None
    meta_title: str | None = Field(default=None, max_length=200)
    meta_description: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=2048)
    price: StrictInt | None = Field(default=None, ge=0)
    compare_at_price: StrictInt | None = Field(default=None, ge=0)
    vat_rate: VatRate | None = None
    sort_order: int = 0
    images: list[ProductImageData] = Field(default_factory=list)
    voucher: ProductVoucherInput | None = None
    book: ProductBookInput | None = None
    audiobook: ProductAudiobookInput | None = None
    digital: ProductDigitalInput | None = None

    @model_validator(mode="after")
    def validate_draft(self) -> Self:
        """Allow incomplete drafts while enforcing kind and price relationships."""

        allowed = {
            ProductKind.VOUCHER: "voucher",
            ProductKind.BOOK: "book",
            ProductKind.AUDIOBOOK: "audiobook",
            ProductKind.DIGITAL: "digital",
        }[self.kind]
        for name in ("voucher", "book", "audiobook", "digital"):
            if name != allowed and getattr(self, name) is not None:
                raise ValueError("Szczegóły szkicu muszą odpowiadać rodzajowi produktu.")
        if self.compare_at_price is not None and (
            self.price is None or self.compare_at_price <= self.price
        ):
            raise ValueError("Cena porównawcza musi być wyższa od ceny produktu.")
        return self


class ProductSummary(BaseModel):
    """Common product fields returned to future catalog consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: ProductKind
    name: str
    slug: str
    short_description: str | None
    price: int | None
    compare_at_price: int | None
    vat_rate: VatRate | None
    status: ProductStatus
    published_at: datetime | None
    sort_order: int
