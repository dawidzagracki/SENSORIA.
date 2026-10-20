"""Catalog products with one shared row and one-to-one kind details."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    event,
    func,
    inspect,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship

from sensoria.database import Base, TimestampMixin, UUIDMixin
from sensoria.shared.types import Money, VatRate, VatRateType

from .slug import slugify
from .types import (
    DigitalLabel,
    DigitalLabelType,
    ProductKind,
    ProductKindType,
    ProductStatus,
    ProductStatusType,
    VoucherVariantKind,
    VoucherVariantKindType,
)

product_categories = Table(
    "product_categories",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_product_categories_category_id", "category_id"),
)

product_audience_tags = Table(
    "product_audience_tags",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("audience_tag_id", ForeignKey("audience_tags.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_product_audience_tags_audience_tag_id", "audience_tag_id"),
)


class Product(UUIDMixin, TimestampMixin, Base):
    """Shared catalog data; exactly one details row is used for its kind."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("slug"),
        CheckConstraint("length(btrim(slug)) > 0", name="nonempty_slug"),
        CheckConstraint("price IS NULL OR price >= 0", name="nonnegative_price"),
        CheckConstraint(
            "compare_at_price IS NULL OR compare_at_price >= 0",
            name="nonnegative_compare_at_price",
        ),
        CheckConstraint(
            "compare_at_price IS NULL OR (price IS NOT NULL AND compare_at_price > price)",
            name="compare_at_price_above_price",
        ),
        CheckConstraint("kind IN ('VOUCHER', 'BOOK', 'AUDIOBOOK', 'DIGITAL')", name="valid_kind"),
        CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'WITHDRAWN')", name="valid_status"),
        CheckConstraint(
            "meta_title IS NULL OR length(btrim(meta_title)) > 0", name="nonempty_meta_title"
        ),
        Index("ix_products_status_sort_order", "status", "sort_order"),
        Index("ix_products_status_price", "status", "price"),
        Index("ix_products_catalog_recommended", "status", "sort_order", "published_at"),
        Index("ix_products_kind_status_sort_order", "kind", "status", "sort_order"),
        Index("ix_products_published_at", "published_at"),
        CheckConstraint("sample_open_count >= 0", name="nonnegative_sample_open_count"),
        Index("ix_products_search_vector_gin", "search_vector", postgresql_using="gin"),
        Index(
            "ix_products_search_vector_unaccented_gin",
            "search_vector_unaccented",
            postgresql_using="gin",
        ),
    )

    kind: Mapped[ProductKind] = mapped_column(ProductKindType(), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    short_description: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[int | None] = mapped_column(Money(), nullable=True, active_history=True)
    compare_at_price: Mapped[int | None] = mapped_column(
        Money(), nullable=True, active_history=True
    )
    vat_rate: Mapped[VatRate | None] = mapped_column(
        VatRateType(), nullable=True, active_history=True
    )
    status: Mapped[ProductStatus] = mapped_column(
        ProductStatusType(),
        nullable=False,
        default=ProductStatus.DRAFT,
        server_default=ProductStatus.DRAFT.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    meta_title: Mapped[str | None] = mapped_column(String(200))
    meta_description: Mapped[str | None] = mapped_column(String(500))
    og_image: Mapped[str | None] = mapped_column(String(2048))
    search_vector: Mapped[str] = mapped_column(TSVECTOR(), nullable=False)
    search_vector_unaccented: Mapped[str] = mapped_column(TSVECTOR(), nullable=False)
    sample_open_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="ProductImage.position",
    )
    voucher: Mapped[ProductVoucher | None] = relationship(
        back_populates="product", cascade="all, delete-orphan", uselist=False, lazy="raise"
    )
    book: Mapped[ProductBook | None] = relationship(
        back_populates="product", cascade="all, delete-orphan", uselist=False, lazy="raise"
    )
    audiobook: Mapped[ProductAudiobook | None] = relationship(
        back_populates="product", cascade="all, delete-orphan", uselist=False, lazy="raise"
    )
    digital: Mapped[ProductDigital | None] = relationship(
        back_populates="product", cascade="all, delete-orphan", uselist=False, lazy="raise"
    )
    categories: Mapped[list[Category]] = relationship(
        secondary=product_categories,
        back_populates="products",
        lazy="raise",
        passive_deletes=True,
    )
    audience_tags: Mapped[list[AudienceTag]] = relationship(
        secondary=product_audience_tags,
        back_populates="products",
        lazy="raise",
        passive_deletes=True,
    )

    @property
    def is_physical(self) -> bool:
        """Books ship physically; service vouchers are neither physical nor digital."""

        return self.kind is ProductKind.BOOK

    @property
    def is_digital(self) -> bool:
        """Audio and downloadable products are digital; service vouchers are not."""

        return self.kind in (ProductKind.AUDIOBOOK, ProductKind.DIGITAL)

    @property
    def requires_shipping(self) -> bool:
        """Only a physical book requires shipment in this model."""

        return self.kind is ProductKind.BOOK

    @property
    def is_available(self) -> bool:
        """Return availability without triggering implicit async relationship loads."""

        if self.status is not ProductStatus.PUBLISHED:
            return False
        state = inspect(self)
        if self.kind is ProductKind.BOOK:
            if "book" not in state.dict:
                if state.transient:
                    return False
                raise RuntimeError("Eager-load Product.book before reading its availability.")
            book = state.dict["book"]
            return book is not None and cast(ProductBook, book).stock_quantity > 0
        if state.transient:
            expected = {
                ProductKind.VOUCHER: "voucher",
                ProductKind.AUDIOBOOK: "audiobook",
                ProductKind.DIGITAL: "digital",
            }[self.kind]
            return state.dict.get(expected) is not None
        return True


class ProductImage(UUIDMixin, Base):
    """Image reference ordered within a product gallery; no upload is performed."""

    __tablename__ = "product_images"
    __table_args__ = (
        UniqueConstraint("product_id", "position"),
        CheckConstraint("position >= 0", name="nonnegative_position"),
        CheckConstraint("length(btrim(url)) > 0", name="nonempty_url"),
        CheckConstraint("length(btrim(alt)) > 0", name="nonempty_alt"),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    alt: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    product: Mapped[Product] = relationship(back_populates="images", lazy="raise")


class ProductVoucher(Base):
    """One-to-one details for a service voucher."""

    __tablename__ = "product_voucher"
    __table_args__ = (
        CheckConstraint("validity_months > 0", name="positive_validity_months"),
        CheckConstraint("length(btrim(service_name)) > 0", name="nonempty_service_name"),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    validity_months: Mapped[int] = mapped_column(
        Integer, nullable=False, default=12, server_default="12"
    )
    service_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    product: Mapped[Product] = relationship(back_populates="voucher", lazy="raise")
    variants: Mapped[list[ProductVoucherVariant]] = relationship(
        back_populates="voucher",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="ProductVoucherVariant.kind",
    )


class ProductVoucherVariant(UUIDMixin, Base):
    """Price-bearing in-person or online option of one voucher product."""

    __tablename__ = "product_voucher_variants"
    __table_args__ = (
        UniqueConstraint("voucher_id", "kind"),
        CheckConstraint("price >= 0", name="nonnegative_price"),
        CheckConstraint("kind IN ('IN_PERSON', 'ONLINE')", name="valid_kind"),
    )

    voucher_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_voucher.product_id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[VoucherVariantKind] = mapped_column(VoucherVariantKindType(), nullable=False)
    price: Mapped[int] = mapped_column(Money(), nullable=False)
    voucher: Mapped[ProductVoucher] = relationship(back_populates="variants", lazy="raise")


class ProductBook(Base):
    """One-to-one physical-book details."""

    __tablename__ = "product_book"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="nonnegative_stock_quantity"),
        CheckConstraint("low_stock_threshold >= 0", name="nonnegative_low_stock_threshold"),
        CheckConstraint("weight_grams IS NULL OR weight_grams > 0", name="positive_weight"),
        CheckConstraint("length_mm IS NULL OR length_mm > 0", name="positive_length"),
        CheckConstraint("width_mm IS NULL OR width_mm > 0", name="positive_width"),
        CheckConstraint("height_mm IS NULL OR height_mm > 0", name="positive_height"),
        CheckConstraint(
            "shipping_business_days IS NULL OR shipping_business_days > 0",
            name="positive_shipping_days",
        ),
        CheckConstraint(
            "shipping_method IS NULL OR length(btrim(shipping_method)) > 0",
            name="nonempty_shipping_method",
        ),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    stock_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    weight_grams: Mapped[int | None] = mapped_column(Integer)
    binding: Mapped[str | None] = mapped_column(String(80))
    length_mm: Mapped[int | None] = mapped_column(Integer)
    width_mm: Mapped[int | None] = mapped_column(Integer)
    height_mm: Mapped[int | None] = mapped_column(Integer)
    isbn: Mapped[str | None] = mapped_column(String(20))
    shipping_business_days: Mapped[int | None] = mapped_column(Integer)
    shipping_method: Mapped[str | None] = mapped_column(String(120))
    product: Mapped[Product] = relationship(back_populates="book", lazy="raise")


class StockMovement(UUIDMixin, Base):
    """Append-only physical stock ledger; database trigger maintains the aggregate."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("change <> 0", name="nonzero_change"),
        CheckConstraint(
            "reason IN ('purchase', 'return', 'manual_adjustment', 'correction')",
            name="valid_reason",
        ),
        UniqueConstraint("operation_key"),
        Index("ix_stock_movements_product_created", "product_id", "created_at"),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    change: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    order_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    source_reference: Mapped[str | None] = mapped_column(String(100))
    operation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    performed_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    note: Mapped[str | None] = mapped_column(Text)


class LowStockAlert(UUIDMixin, Base):
    """Durable notification intent created on one downward threshold crossing."""

    __tablename__ = "low_stock_alerts"
    __table_args__ = (
        UniqueConstraint("movement_id"),
        CheckConstraint("status IN ('pending', 'queued', 'sent', 'failed')", name="valid_status"),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    movement_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=False
    )
    previous_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProductAudiobook(Base):
    """One-to-one audiobook details with ordered chapter records."""

    __tablename__ = "product_audiobook"
    __table_args__ = (
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0", name="positive_duration"
        ),
        CheckConstraint(
            "file_format IS NULL OR length(btrim(file_format)) > 0",
            name="nonempty_file_format",
        ),
        CheckConstraint(
            "sample_duration_seconds IS NULL OR sample_duration_seconds > 0",
            name="positive_audio_sample_duration",
        ),
        CheckConstraint(
            "sample_file_path IS NULL OR sample_file_path ~ "
            "'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\\.mp3$'",
            name="valid_audio_sample_key",
        ),
        CheckConstraint(
            "sample_file_path IS NULL OR length(btrim(sample_file_path)) > 0",
            name="nonempty_audio_sample_key",
        ),
        CheckConstraint(
            "NOT sample_enabled OR (sample_file_path IS NOT NULL "
            "AND sample_duration_seconds IS NOT NULL)",
            name="enabled_audio_sample_complete",
        ),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    narrator: Mapped[str | None] = mapped_column(String(200))
    file_format: Mapped[str | None] = mapped_column(String(30))
    sample_file_path: Mapped[str | None] = mapped_column(String(80))
    sample_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    sample_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    product: Mapped[Product] = relationship(back_populates="audiobook", lazy="raise")
    chapters: Mapped[list[ProductAudiobookChapter]] = relationship(
        back_populates="audiobook",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="ProductAudiobookChapter.position",
    )


class ProductAudiobookChapter(UUIDMixin, Base):
    """Ordered audiobook chapter metadata; it does not reference audio files."""

    __tablename__ = "product_audiobook_chapters"
    __table_args__ = (
        UniqueConstraint("audiobook_id", "position"),
        CheckConstraint("position >= 0", name="nonnegative_position"),
        CheckConstraint("length_seconds > 0", name="positive_length_seconds"),
        CheckConstraint("length(btrim(title)) > 0", name="nonempty_title"),
    )

    audiobook_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_audiobook.product_id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    length_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    audiobook: Mapped[ProductAudiobook] = relationship(back_populates="chapters", lazy="raise")


class ProductDigital(Base):
    """One-to-one downloadable details; course and e-book remain DIGITAL."""

    __tablename__ = "product_digital"
    __table_args__ = (
        CheckConstraint("page_count IS NULL OR page_count > 0", name="positive_page_count"),
        CheckConstraint("length(btrim(file_format)) > 0", name="nonempty_file_format"),
        CheckConstraint(
            "label IN ('COURSE_PDF', 'EBOOK_PDF')",
            name="valid_label",
        ),
        CheckConstraint(
            "sample_pages IS NULL OR sample_pages > 0",
            name="positive_pdf_sample_pages",
        ),
        CheckConstraint(
            "sample_file_path IS NULL OR sample_file_path ~ "
            "'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\\.pdf$'",
            name="valid_pdf_sample_key",
        ),
        CheckConstraint(
            "sample_file_path IS NULL OR length(btrim(sample_file_path)) > 0",
            name="nonempty_pdf_sample_key",
        ),
        CheckConstraint(
            "NOT sample_enabled OR (sample_file_path IS NOT NULL AND sample_pages IS NOT NULL)",
            name="enabled_pdf_sample_complete",
        ),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    page_count: Mapped[int | None] = mapped_column(Integer)
    file_format: Mapped[str] = mapped_column(String(30), nullable=False, default="PDF")
    edition: Mapped[str | None] = mapped_column(String(100))
    label: Mapped[DigitalLabel] = mapped_column(
        DigitalLabelType(), nullable=False, default=DigitalLabel.EBOOK_PDF
    )
    sample_file_path: Mapped[str | None] = mapped_column(String(80))
    sample_pages: Mapped[int | None] = mapped_column(Integer)
    sample_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    product: Mapped[Product] = relationship(back_populates="digital", lazy="raise")


class SampleRateWindow(Base):
    """PostgreSQL-backed per-client open limiter shared by API workers."""

    __tablename__ = "sample_rate_windows"

    client_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SampleAccessSession(UUIDMixin, Base):
    """Short-lived sample-only bearer grant; never stores a storage path."""

    __tablename__ = "sample_access_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        UniqueConstraint("request_key"),
        CheckConstraint("request_count >= 0", name="nonnegative_request_count"),
        Index("ix_sample_access_sessions_expiry", "expires_at"),
        Index("ix_sample_access_sessions_product", "product_id"),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class Category(UUIDMixin, TimestampMixin, Base):
    """Two-level product taxonomy with optional parent grouping."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("slug"),
        CheckConstraint("length(btrim(name)) > 0", name="nonempty_name"),
        CheckConstraint("length(btrim(slug)) > 0", name="nonempty_slug"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_own_parent"),
        CheckConstraint("position >= 0", name="nonnegative_position"),
        CheckConstraint(
            "meta_title IS NULL OR length(btrim(meta_title)) > 0", name="nonempty_meta_title"
        ),
        Index("ix_categories_parent_position", "parent_id", "position"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    meta_title: Mapped[str | None] = mapped_column(String(200))
    meta_description: Mapped[str | None] = mapped_column(String(500))
    og_image: Mapped[str | None] = mapped_column(String(2048))

    parent: Mapped[Category | None] = relationship(
        remote_side="Category.id", back_populates="children", lazy="raise"
    )
    children: Mapped[list[Category]] = relationship(
        back_populates="parent", lazy="raise", order_by="Category.position"
    )
    products: Mapped[list[Product]] = relationship(
        secondary=product_categories,
        back_populates="categories",
        lazy="raise",
        passive_deletes=True,
    )


class SearchQuery(UUIDMixin, Base):
    """Minimal aggregate-friendly record of an explicitly submitted search."""

    __tablename__ = "search_queries"
    __table_args__ = (
        CheckConstraint("length(btrim(query_text)) > 0", name="nonempty_query"),
        CheckConstraint("length(btrim(normalized_query)) > 0", name="nonempty_normalized_query"),
        CheckConstraint("result_count >= 0", name="nonnegative_result_count"),
        Index("ix_search_queries_popularity", "normalized_query", "searched_at"),
    )

    query_text: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_query: Mapped[str] = mapped_column(String(160), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AudienceTag(UUIDMixin, TimestampMixin, Base):
    """Stable dictionary of people a product is intended for."""

    __tablename__ = "audience_tags"
    __table_args__ = (
        UniqueConstraint("slug"),
        CheckConstraint("length(btrim(name)) > 0", name="nonempty_name"),
        CheckConstraint("length(btrim(slug)) > 0", name="nonempty_slug"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    products: Mapped[list[Product]] = relationship(
        secondary=product_audience_tags,
        back_populates="audience_tags",
        lazy="raise",
        passive_deletes=True,
    )


@event.listens_for(Product, "before_insert")
def _generate_product_slug(
    mapper: Mapper[Product], connection: Connection, target: Product
) -> None:
    """Generate the initial slug once; name updates never rewrite it."""

    del mapper, connection
    if not target.slug:
        target.slug = slugify(target.name) or "product"


def _register_price_history_hooks() -> None:
    """Load the history model after Product exists, then attach ORM listeners."""

    from .price_history import register_price_history_events

    register_price_history_events(Product)


_register_price_history_hooks()
