"""PostgreSQL migration round-trip test against a dedicated `_test` database."""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

API_ROOT = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "0001_initial_baseline"
FOUNDATION_REVISION = "0002_database_foundation"
PRODUCT_REVISION = "2cd55ccecab2"
TAXONOMY_REVISION = "08f9476a46d2"
PRICE_HISTORY_REVISION = "f31a9d4b"
CATALOG_INDEXES_REVISION = "a15c0f3d2e71"
CATALOG_SEARCH_REVISION = "b16f0a9c7d31"
PRODUCT_MEDIA_REVISION = "e920_product_media"
PRODUCT_SAMPLES_REVISION = "f021_product_samples"
CART_REVISION = "c24a19d7b802"
DISCOUNT_REVISION = "d26000000001"
DELIVERY_REVISION = "f32000000001"
CHECKOUT_REVISION = "a29000000001"
PICKUP_SNAPSHOT_REVISION = "c30_pickup_point_snapshots"
VOUCHER_REVISION = "aa4500000001"
VOUCHER_EXTENSION_REQUEST_REVISION = "f48000000001"
STOCK_LEDGER_REVISION = "f51000000001"
VOUCHER_REMINDERS_REVISION = "f49000000001"
VOUCHER_GIFTS_REVISION = "f50000000001"
ORDER_SHIPMENTS_REVISION = "f52000000001"
ACCOUNT_AUTH_REVISION = "f54000000001"
LOGIN_LINK_REVISION = "f55000000001"
GUEST_PURCHASE_LINKING_REVISION = "f56000000001"
ORDER_PUBLIC_NUMBER_REVISION = "f57000000001"
CART_REORDER_REVISION = "f58000000001"
ACCOUNT_PROFILE_REVISION = "f59000000001"
ACCOUNT_PRIVACY_REVISION = "f60000000001"
PAYMENTS_REVISION = "f61000000001"
DIGITAL_LIBRARY_REVISION = "f62000000001"
SALES_DOCUMENTS_REVISION = "f63000000001"
MAIL_OUTBOX_REVISION = "f64000000001"


def _alembic_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


async def _migration_state(database_url: str) -> tuple[bool, str | None, list[str]]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:

            def inspect_tables(sync_connection: Connection) -> tuple[bool, list[str]]:
                inspector = inspect(sync_connection)
                return inspector.has_table("alembic_version"), inspector.get_table_names()

            has_version_table, table_names = await connection.run_sync(inspect_tables)
            if not has_version_table:
                return False, None, table_names
            revision = await connection.exec_driver_sql("SELECT version_num FROM alembic_version")
            return True, revision.scalar_one_or_none(), table_names
    finally:
        await engine.dispose()


async def _product_index_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: {
                    name
                    for item in inspect(sync_connection).get_indexes("products")
                    if isinstance((name := item.get("name")), str)
                }
            )
    finally:
        await engine.dispose()


async def _table_index_names(database_url: str, table_name: str) -> set[str]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: {
                    name
                    for item in inspect(sync_connection).get_indexes(table_name)
                    if isinstance((name := item.get("name")), str)
                }
            )
    finally:
        await engine.dispose()


async def _column_names(database_url: str, table_name: str) -> set[str]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: {
                    str(column["name"])
                    for column in inspect(sync_connection).get_columns(table_name)
                }
            )
    finally:
        await engine.dispose()


def test_migration_upgrade_downgrade_and_reupgrade(
    test_database_url: str,
) -> None:
    config = _alembic_config()
    initial_state = asyncio.run(_migration_state(test_database_url))
    expected_tables = {
        "alembic_version",
        "app_settings",
        "audit_log",
        "products",
        "product_images",
        "product_voucher",
        "product_voucher_variants",
        "product_book",
        "product_audiobook",
        "product_audiobook_chapters",
        "product_digital",
        "categories",
        "audience_tags",
        "product_categories",
        "product_audience_tags",
        "price_history",
        "search_queries",
        "sample_rate_windows",
        "sample_access_sessions",
        "carts",
        "cart_items",
        "cart_reorder_operations",
        "discount_codes",
        "discount_redemptions",
        "orders",
        "order_items",
        "order_consents",
        "stock_reservations",
        "stock_movements",
        "low_stock_alerts",
        "stock_fulfillment_conflicts",
        "shipments",
        "shipment_history",
        "shipment_notification_jobs",
        "discount_use_reservations",
        "stored_files",
        "vouchers",
        "voucher_pdf_jobs",
        "voucher_gift_delivery_jobs",
        "voucher_reminders",
        "voucher_reminder_runs",
        "voucher_verification_windows",
        "voucher_extension_requests",
        "customers",
        "account_sessions",
        "account_action_tokens",
        "auth_attempts",
        "auth_email_jobs",
        "login_links",
        "customer_addresses",
        "customer_billing_profiles",
        "account_privacy_jobs",
        "consent_guest_imports",
        "consent_text_versions",
        "customer_consents",
        "deleted_email_suppressions",
        "payments",
        "payment_events",
        "product_files",
        "ebook_chapters",
        "entitlements",
        "download_links",
        "watermarked_files",
        "content_progress",
        "document_counters",
        "sales_documents",
        "mail_outbox",
    }
    assert set(initial_state[2]).issubset(expected_tables), (
        "TEST_DATABASE_URL musi wskazywać dedykowaną bazę testową bez obcych tabel."
    )
    assert initial_state[1] in (
        None,
        BASELINE_REVISION,
        FOUNDATION_REVISION,
        PRODUCT_REVISION,
        TAXONOMY_REVISION,
        PRICE_HISTORY_REVISION,
        CATALOG_INDEXES_REVISION,
        CATALOG_SEARCH_REVISION,
        PRODUCT_MEDIA_REVISION,
        PRODUCT_SAMPLES_REVISION,
        CART_REVISION,
        DISCOUNT_REVISION,
        DELIVERY_REVISION,
        CHECKOUT_REVISION,
        PICKUP_SNAPSHOT_REVISION,
        VOUCHER_REVISION,
        VOUCHER_EXTENSION_REQUEST_REVISION,
        VOUCHER_REMINDERS_REVISION,
        VOUCHER_GIFTS_REVISION,
        STOCK_LEDGER_REVISION,
        ORDER_SHIPMENTS_REVISION,
        ACCOUNT_AUTH_REVISION,
        LOGIN_LINK_REVISION,
        GUEST_PURCHASE_LINKING_REVISION,
        ORDER_PUBLIC_NUMBER_REVISION,
        CART_REORDER_REVISION,
        ACCOUNT_PROFILE_REVISION,
        ACCOUNT_PRIVACY_REVISION,
        PAYMENTS_REVISION,
        DIGITAL_LIBRARY_REVISION,
        SALES_DOCUMENTS_REVISION,
        MAIL_OUTBOX_REVISION,
    )

    if initial_state[1] in (FOUNDATION_REVISION, PRODUCT_REVISION, TAXONOMY_REVISION):
        has_rows = asyncio.run(_foundation_tables_have_rows(test_database_url))
        assert not has_rows, "Migracja nie może usuwać rekordów istniejących w bazie testowej."
    if initial_state[1] in (
        PRODUCT_REVISION,
        TAXONOMY_REVISION,
        PRICE_HISTORY_REVISION,
        CATALOG_INDEXES_REVISION,
        CATALOG_SEARCH_REVISION,
        PRODUCT_MEDIA_REVISION,
        PRODUCT_SAMPLES_REVISION,
        CART_REVISION,
        DISCOUNT_REVISION,
        DELIVERY_REVISION,
        CHECKOUT_REVISION,
        PICKUP_SNAPSHOT_REVISION,
    ):
        assert not asyncio.run(_catalog_tables_have_rows(test_database_url)), (
            "Test migracji wymaga pustych tabel katalogu; nie usuwa danych testowych."
        )
    if initial_state[1] in (
        CATALOG_SEARCH_REVISION,
        PRODUCT_MEDIA_REVISION,
        PRODUCT_SAMPLES_REVISION,
        CART_REVISION,
        DISCOUNT_REVISION,
        DELIVERY_REVISION,
        CHECKOUT_REVISION,
        PICKUP_SNAPSHOT_REVISION,
    ):
        assert not asyncio.run(_search_queries_have_rows(test_database_url)), (
            "Test migracji nie może usuwać zapisanej historii wyszukiwań."
        )
    if initial_state[1] == TAXONOMY_REVISION:
        assert not asyncio.run(_taxonomy_tables_have_rows(test_database_url)), (
            "Test migracji wymaga pustych tabel kategorii; nie usuwa przypisań testowych."
        )
    if initial_state[1] in (
        CART_REVISION,
        DISCOUNT_REVISION,
        DELIVERY_REVISION,
        CHECKOUT_REVISION,
        PICKUP_SNAPSHOT_REVISION,
        VOUCHER_REVISION,
        VOUCHER_EXTENSION_REQUEST_REVISION,
        VOUCHER_REMINDERS_REVISION,
        VOUCHER_GIFTS_REVISION,
        STOCK_LEDGER_REVISION,
        ORDER_SHIPMENTS_REVISION,
        ACCOUNT_AUTH_REVISION,
        LOGIN_LINK_REVISION,
        GUEST_PURCHASE_LINKING_REVISION,
        ORDER_PUBLIC_NUMBER_REVISION,
        CART_REORDER_REVISION,
        ACCOUNT_PROFILE_REVISION,
        ACCOUNT_PRIVACY_REVISION,
        PAYMENTS_REVISION,
        DIGITAL_LIBRARY_REVISION,
        SALES_DOCUMENTS_REVISION,
        MAIL_OUTBOX_REVISION,
    ):
        assert not asyncio.run(_transactional_tables_have_rows(test_database_url)), (
            "Test downgrade wymaga pustych tabel zamówień/voucherów; nie może usuwać danych."
        )

    extension_existed_before = asyncio.run(_pgcrypto_installed(test_database_url))

    try:
        command.upgrade(config, "head")
        assert asyncio.run(_migration_state(test_database_url))[:2] == (
            True,
            MAIL_OUTBOX_REVISION,
        )
        assert {
            "ix_products_status_price",
            "ix_products_catalog_recommended",
        }.issubset(asyncio.run(_product_index_names(test_database_url)))
        assert {
            "ix_products_search_vector_gin",
            "ix_products_search_vector_unaccented_gin",
        }.issubset(asyncio.run(_product_index_names(test_database_url)))
        assert "search_queries" in asyncio.run(_migration_state(test_database_url))[2]
        assert asyncio.run(_search_extensions_installed(test_database_url))
        assert {"binding", "shipping_business_days", "shipping_method"}.issubset(
            asyncio.run(_column_names(test_database_url, "product_book"))
        )
        assert "file_format" in asyncio.run(_column_names(test_database_url, "product_audiobook"))
        assert "sample_open_count" in asyncio.run(_column_names(test_database_url, "products"))
        assert {
            "sample_file_path",
            "sample_pages",
            "sample_enabled",
        }.issubset(asyncio.run(_column_names(test_database_url, "product_digital")))
        assert {
            "sample_file_path",
            "sample_duration_seconds",
            "sample_enabled",
        }.issubset(asyncio.run(_column_names(test_database_url, "product_audiobook")))
        assert {"sample_rate_windows", "sample_access_sessions"}.issubset(
            set(asyncio.run(_migration_state(test_database_url))[2])
        )
        assert {"carts", "cart_items"}.issubset(
            set(asyncio.run(_migration_state(test_database_url))[2])
        )
        assert {"discount_codes", "discount_redemptions"}.issubset(
            set(asyncio.run(_migration_state(test_database_url))[2])
        )
        assert "discount_code_id" in asyncio.run(_column_names(test_database_url, "carts"))
        assert "delivery_method" in asyncio.run(_column_names(test_database_url, "carts"))
        assert "delivery_point_snapshot" in asyncio.run(_column_names(test_database_url, "carts"))
        assert "delivery_point_snapshot" in asyncio.run(_column_names(test_database_url, "orders"))
        assert "public_number" in asyncio.run(_column_names(test_database_url, "orders"))
        assert "customer_id" in asyncio.run(_column_names(test_database_url, "orders"))
        assert {"customer_addresses", "customer_billing_profiles"}.issubset(
            set(asyncio.run(_migration_state(test_database_url))[2])
        )
        assert {
            "orders",
            "order_items",
            "order_consents",
            "stock_reservations",
            "discount_use_reservations",
        }.issubset(set(asyncio.run(_migration_state(test_database_url))[2]))
        assert {
            "stored_files",
            "vouchers",
            "voucher_pdf_jobs",
            "voucher_verification_windows",
            "voucher_extension_requests",
        }.issubset(set(asyncio.run(_migration_state(test_database_url))[2]))
        assert {
            "stock_movements",
            "low_stock_alerts",
            "stock_fulfillment_conflicts",
        }.issubset(set(asyncio.run(_migration_state(test_database_url))[2]))
        assert {
            "low_stock_threshold",
        }.issubset(asyncio.run(_column_names(test_database_url, "product_book")))
        assert "shipping_snapshot" in asyncio.run(_column_names(test_database_url, "order_items"))
        assert {
            "fulfillment_status",
            "fulfillment_ready_at",
            "pickup_ready_at",
            "picked_up_at",
        }.issubset(asyncio.run(_column_names(test_database_url, "orders")))
        assert {
            "email",
            "password_hash",
            "first_name",
            "last_name",
            "email_verified_at",
            "last_login_at",
        }.issubset(asyncio.run(_column_names(test_database_url, "customers")))
        assert {"ix_carts_guest_expiry", "uq_carts_customer_id"}.issubset(
            asyncio.run(_table_index_names(test_database_url, "carts"))
        )
        assert "ix_cart_items_product_id" in asyncio.run(
            _table_index_names(test_database_url, "cart_items")
        )

        command.downgrade(config, PRODUCT_REVISION)
        downgraded = asyncio.run(_migration_state(test_database_url))
        assert downgraded[:2] == (True, PRODUCT_REVISION)
        assert {"app_settings", "audit_log", "products", "alembic_version"}.issubset(downgraded[2])
        assert "price_history" not in downgraded[2]
        assert "search_queries" not in downgraded[2]
        assert not {"carts", "cart_items"} & set(downgraded[2])
        assert not {"discount_codes", "discount_redemptions"} & set(downgraded[2])
        assert not {
            "orders",
            "order_items",
            "order_consents",
            "stock_reservations",
            "discount_use_reservations",
        } & set(downgraded[2])
        assert not {
            "stock_movements",
            "low_stock_alerts",
            "stock_fulfillment_conflicts",
        } & set(downgraded[2])
        assert not {"shipments", "shipment_history", "shipment_notification_jobs"} & set(
            downgraded[2]
        )
        assert not {
            "customers",
            "account_sessions",
            "account_action_tokens",
            "auth_attempts",
            "auth_email_jobs",
            "customer_addresses",
            "customer_billing_profiles",
            "login_links",
        } & set(downgraded[2])
        assert not {"binding", "shipping_business_days", "shipping_method"} & asyncio.run(
            _column_names(test_database_url, "product_book")
        )
        assert "low_stock_threshold" not in asyncio.run(
            _column_names(test_database_url, "product_book")
        )
        assert "file_format" not in asyncio.run(
            _column_names(test_database_url, "product_audiobook")
        )
        assert "sample_open_count" not in asyncio.run(_column_names(test_database_url, "products"))
        assert not {"sample_file_path", "sample_pages", "sample_enabled"} & asyncio.run(
            _column_names(test_database_url, "product_digital")
        )
        assert not {
            "sample_file_path",
            "sample_duration_seconds",
            "sample_enabled",
        } & asyncio.run(_column_names(test_database_url, "product_audiobook"))
        assert not {"sample_rate_windows", "sample_access_sessions"} & set(downgraded[2])
        assert not {
            "ix_products_status_price",
            "ix_products_catalog_recommended",
        } & asyncio.run(_product_index_names(test_database_url))
        assert not {
            "ix_products_search_vector_gin",
            "ix_products_search_vector_unaccented_gin",
        } & asyncio.run(_product_index_names(test_database_url))
        assert not (
            {"categories", "audience_tags", "product_categories", "product_audience_tags"}
            & set(downgraded[2])
        )
        assert "products" in downgraded[2]
        assert asyncio.run(_pgcrypto_installed(test_database_url))
        assert extension_existed_before or asyncio.run(_pgcrypto_installed(test_database_url))
        assert asyncio.run(_search_extensions_installed(test_database_url))

        command.upgrade(config, "head")
        reupgraded = asyncio.run(_migration_state(test_database_url))
        assert reupgraded[:2] == (
            True,
            MAIL_OUTBOX_REVISION,
        )
        assert {
            "carts",
            "cart_items",
            "cart_reorder_operations",
            "customer_addresses",
            "customers",
            "discount_codes",
            "discount_redemptions",
        }.issubset(reupgraded[2])
        assert {
            "pending_email",
        }.issubset(asyncio.run(_column_names(test_database_url, "customers")))
        assert {
            "label",
            "address_type",
            "is_default",
            "updated_at",
        }.issubset(asyncio.run(_column_names(test_database_url, "customer_addresses")))
        assert "price_history" in reupgraded[2]
        assert "delivery_method" in asyncio.run(_column_names(test_database_url, "carts"))
        assert "delivery_point_snapshot" in asyncio.run(_column_names(test_database_url, "carts"))
        assert "delivery_point_snapshot" in asyncio.run(_column_names(test_database_url, "orders"))
        assert "public_number" in asyncio.run(_column_names(test_database_url, "orders"))
        assert "shipping_snapshot" in asyncio.run(_column_names(test_database_url, "order_items"))
        assert "low_stock_threshold" in asyncio.run(
            _column_names(test_database_url, "product_book")
        )
        assert {"binding", "shipping_business_days", "shipping_method"}.issubset(
            asyncio.run(_column_names(test_database_url, "product_book"))
        )
        assert {
            "ix_products_status_price",
            "ix_products_catalog_recommended",
        }.issubset(asyncio.run(_product_index_names(test_database_url)))
        assert {
            "ix_products_search_vector_gin",
            "ix_products_search_vector_unaccented_gin",
        }.issubset(asyncio.run(_product_index_names(test_database_url)))
    finally:
        has_version_table, current_revision, _table_names = asyncio.run(
            _migration_state(test_database_url)
        )
        if has_version_table and current_revision != PRICE_HISTORY_REVISION:
            command.upgrade(config, "head")


async def _catalog_tables_have_rows(database_url: str) -> bool:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.exec_driver_sql(
                "SELECT EXISTS (SELECT 1 FROM products) OR "
                "EXISTS (SELECT 1 FROM product_images) OR "
                "EXISTS (SELECT 1 FROM product_voucher) OR "
                "EXISTS (SELECT 1 FROM product_book) OR "
                "EXISTS (SELECT 1 FROM product_audiobook) OR "
                "EXISTS (SELECT 1 FROM product_digital)"
            )
            return bool(result.scalar_one())
    finally:
        await engine.dispose()


async def _taxonomy_tables_have_rows(database_url: str) -> bool:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.exec_driver_sql(
                "SELECT EXISTS (SELECT 1 FROM categories) OR "
                "EXISTS (SELECT 1 FROM audience_tags) OR "
                "EXISTS (SELECT 1 FROM product_categories) OR "
                "EXISTS (SELECT 1 FROM product_audience_tags)"
            )
            return bool(result.scalar_one())
    finally:
        await engine.dispose()


async def _foundation_tables_have_rows(database_url: str) -> bool:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            settings = await connection.exec_driver_sql(
                "SELECT EXISTS (SELECT 1 FROM app_settings)"
            )
            audit = await connection.exec_driver_sql("SELECT EXISTS (SELECT 1 FROM audit_log)")
            return bool(settings.scalar_one() or audit.scalar_one())
    finally:
        await engine.dispose()


async def _pgcrypto_installed(database_url: str) -> bool:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.exec_driver_sql(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto')"
            )
            return bool(result.scalar_one())
    finally:
        await engine.dispose()


async def _search_queries_have_rows(database_url: str) -> bool:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.exec_driver_sql(
                "SELECT EXISTS (SELECT 1 FROM search_queries)"
            )
            return bool(result.scalar_one())
    finally:
        await engine.dispose()


async def _transactional_tables_have_rows(database_url: str) -> bool:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
            transactional_tables = {
                "carts",
                "cart_items",
                "discount_codes",
                "discount_redemptions",
                "orders",
                "order_items",
                "order_consents",
                "stock_reservations",
                "discount_use_reservations",
                "stored_files",
                "vouchers",
                "voucher_pdf_jobs",
                "voucher_verification_windows",
                "voucher_extension_requests",
                "stock_movements",
                "low_stock_alerts",
                "stock_fulfillment_conflicts",
                "customers",
                "account_sessions",
                "account_action_tokens",
                "auth_attempts",
                "auth_email_jobs",
                "customer_addresses",
                "customer_billing_profiles",
            }
            present = sorted(transactional_tables & table_names)
            if not present:
                return False
            predicate = " OR ".join(f"EXISTS (SELECT 1 FROM {name})" for name in present)
            result = await connection.exec_driver_sql(f"SELECT {predicate}")
            return bool(result.scalar_one())
    finally:
        await engine.dispose()


async def _search_extensions_installed(database_url: str) -> bool:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.exec_driver_sql(
                "SELECT count(*) FROM pg_extension WHERE extname IN ('unaccent', 'pg_trgm')"
            )
            return int(result.scalar_one()) == 2
    finally:
        await engine.dispose()
