"""Unit and PostgreSQL integration coverage for shared schema primitives."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sensoria.database import Base
from sensoria.seed import SettingSeed, seed_settings
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.types import (
    Currency,
    CurrencyType,
    Money,
    VatRate,
    VatRateType,
    format_money,
)
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    delete,
    func,
    insert,
    inspect,
    select,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection, Dialect
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TestOnlyBase(DeclarativeBase):
    """Separate metadata for transient integration-only tables."""

    __test__ = False
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)


class TestMoneyModel(TestOnlyBase):
    """Temporary integration-only model for exercising Money's DB bind path."""

    __test__ = False

    __tablename__ = "test_money_typecheck"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    amount: Mapped[int | None] = mapped_column(Money(), nullable=True)


class TestForeignKeyParent(TestOnlyBase):
    """Temporary metadata parent used only to verify foreign-key naming."""

    __tablename__ = "test_fk_parent"
    __test__ = False

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class TestForeignKeyChild(TestOnlyBase):
    """Temporary metadata child used only to verify foreign-key naming."""

    __tablename__ = "test_fk_child"
    __test__ = False

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    parent_id: Mapped[UUID] = mapped_column(ForeignKey("test_fk_parent.id"), nullable=False)


@pytest.fixture
def postgres_dialect() -> Dialect:
    return cast(Dialect, postgresql.dialect())  # type: ignore[no-untyped-call]


def test_money_accepts_integer_grosz(postgres_dialect: Dialect) -> None:
    money = Money()
    assert money.process_bind_param(44700, postgres_dialect) == 44700
    assert money.process_bind_param(None, postgres_dialect) is None
    assert isinstance(money.impl, BigInteger)


def test_money_rejects_values_outside_postgresql_bigint(postgres_dialect: Dialect) -> None:
    with pytest.raises(ValueError):
        Money().process_bind_param(2**63, postgres_dialect)


@pytest.mark.parametrize("amount", [100.0, 1.25])
def test_money_rejects_floats(amount: float, postgres_dialect: Dialect) -> None:
    with pytest.raises(TypeError):
        Money().process_bind_param(amount, postgres_dialect)  # type: ignore[arg-type]


def test_money_rejects_bool(postgres_dialect: Dialect) -> None:
    with pytest.raises(TypeError):
        Money().process_bind_param(True, postgres_dialect)


def test_money_formatting_uses_integer_arithmetic() -> None:
    assert format_money(44700) == "447,00 zł"
    assert format_money(-1) == "-0,01 zł"


def test_vat_exempt_is_distinct_from_zero_rate(postgres_dialect: Dialect) -> None:
    assert len(set(VatRate)) == 5
    assert len({rate.name for rate in VatRate}) == 5
    assert VatRateType().process_bind_param(VatRate.EXEMPT, postgres_dialect) == "EXEMPT"
    with pytest.raises(TypeError):
        VatRateType().process_bind_param(cast(VatRate, "RATE_0"), postgres_dialect)
    assert isinstance(VatRateType().impl_instance, String)


def test_currency_allows_only_pln(postgres_dialect: Dialect) -> None:
    assert CurrencyType().process_bind_param(Currency.PLN, postgres_dialect) == "PLN"
    with pytest.raises(ValueError):
        Currency("USD")
    with pytest.raises(TypeError):
        CurrencyType().process_bind_param(cast(Currency, "USD"), postgres_dialect)


@pytest_asyncio.fixture
async def db_session_factory(
    postgres_client: tuple[object, AsyncEngine],
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    _client, engine = postgres_client
    yield async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_foundation_schema_types_constraints_and_indexes(
    postgres_client: tuple[object, AsyncEngine],
) -> None:
    _client, engine = postgres_client

    def inspect_schema(connection: Connection) -> tuple[dict[str, Any], dict[str, Any]]:
        inspector = inspect(connection)
        return (
            {column["name"]: column for column in inspector.get_columns("app_settings")},
            {column["name"]: column for column in inspector.get_columns("audit_log")},
        )

    async with engine.connect() as connection:
        app_columns, audit_columns = await connection.run_sync(inspect_schema)
        assert isinstance(app_columns["value"]["type"], JSONB)
        assert isinstance(app_columns["id"]["type"], postgresql.UUID)
        assert isinstance(app_columns["created_at"]["type"], DateTime)
        assert app_columns["created_at"]["type"].timezone is True
        assert app_columns["id"]["nullable"] is False
        assert app_columns["value"]["nullable"] is False
        assert isinstance(audit_columns["payload"]["type"], JSONB)
        assert isinstance(audit_columns["actor_id"]["type"], postgresql.UUID)
        assert audit_columns["actor_id"]["nullable"] is True
        assert audit_columns["created_at"]["type"].timezone is True

        def inspect_names(
            sync_connection: Connection,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
            sync_inspector = inspect(sync_connection)
            return (
                cast(Any, sync_inspector.get_unique_constraints("app_settings")),
                cast(Any, sync_inspector.get_check_constraints("app_settings")),
                cast(Any, sync_inspector.get_indexes("audit_log")),
            )

        unique, checks, indexes = await connection.run_sync(inspect_names)
        assert unique[0]["name"] == "uq_app_settings_key"
        assert {check["name"] for check in checks} == {"ck_app_settings_nonempty_key"}
        index_names = {index["name"] for index in indexes}
        assert {
            "ix_audit_log_actor_created_at",
            "ix_audit_log_entity_created_at",
            "ix_audit_log_action_created_at",
            "ix_audit_log_payload",
        }.issubset(index_names)
        assert (
            next(index for index in indexes if index["name"] == "ix_audit_log_payload")[
                "dialect_options"
            ]["postgresql_using"]
            == "gin"
        )

        def foreign_keys(
            sync_connection: Connection,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            sync_inspector = inspect(sync_connection)
            return (
                cast(Any, sync_inspector.get_foreign_keys("app_settings")),
                cast(Any, sync_inspector.get_foreign_keys("audit_log")),
            )

        assert await connection.run_sync(foreign_keys) == ([], [])


@pytest.mark.asyncio
async def test_foreign_key_naming_convention_in_test_only_tables(
    postgres_client: tuple[object, AsyncEngine],
) -> None:
    _client, engine = postgres_client
    parent_table = cast(Table, TestForeignKeyParent.__table__)
    child_table = cast(Table, TestForeignKeyChild.__table__)
    async with engine.begin() as connection:
        await connection.run_sync(parent_table.create)
        await connection.run_sync(child_table.create)
        foreign_keys = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_foreign_keys("test_fk_child")
        )
        assert foreign_keys[0]["name"] == "fk_test_fk_child_parent_id_test_fk_parent"
        await connection.run_sync(child_table.drop)
        await connection.run_sync(parent_table.drop)


@pytest.mark.asyncio
async def test_created_at_uuid_and_updated_at_are_database_backed(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    setting_id: UUID | None = None
    original_created_at: datetime | None = None
    original_updated_at: datetime | None = None
    try:
        async with db_session_factory.begin() as session:
            setting = AppSetting(key=f"timestamp-{uuid4()}", value={"x": 1}, description="test")
            session.add(setting)
            await session.flush()
            setting_id = setting.id
            original_created_at = setting.created_at
            original_updated_at = setting.updated_at
            assert setting_id is not None
            assert setting.created_at.tzinfo is not None
            assert setting.updated_at.tzinfo is not None

        await asyncio.sleep(0.02)
        async with db_session_factory.begin() as session:
            await session.execute(text("SELECT 1"))
            edited = await session.get(AppSetting, setting_id)
            assert edited is not None
            edited.description = "updated"

        async with db_session_factory() as session:
            retrieved = await session.get(AppSetting, setting_id)
            assert retrieved is not None
            assert original_created_at is not None and original_updated_at is not None
            assert retrieved.created_at == original_created_at
            assert retrieved.updated_at > original_updated_at

        async with db_session_factory.begin() as session:
            await session.execute(
                text("DELETE FROM app_settings WHERE id = :id"), {"id": setting_id}
            )
    finally:
        if setting_id is not None:
            async with db_session_factory.begin() as session:
                await session.execute(
                    text("DELETE FROM app_settings WHERE id = :id"), {"id": setting_id}
                )


@pytest.mark.asyncio
async def test_uuid_defaults_create_distinct_application_ids(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ids: list[UUID] = []
    try:
        async with db_session_factory.begin() as session:
            first = AppSetting(key=f"uuid-a-{uuid4()}", value=1, description="test")
            second = AppSetting(key=f"uuid-b-{uuid4()}", value=2, description="test")
            session.add_all([first, second])
            await session.flush()
            ids = [first.id, second.id]
            assert all(isinstance(item, UUID) for item in ids)
            assert ids[0] != ids[1]
    finally:
        if ids:
            async with db_session_factory.begin() as session:
                await session.execute(delete(AppSetting).where(AppSetting.id.in_(ids)))


@pytest.mark.asyncio
async def test_money_column_rejects_float_in_postgresql(
    postgres_client: tuple[object, AsyncEngine],
) -> None:
    _client, engine = postgres_client
    async with engine.begin() as connection:
        test_table = cast(Table, TestMoneyModel.__table__)
        await connection.run_sync(test_table.create)
        try:
            with pytest.raises(StatementError):
                await connection.execute(insert(TestMoneyModel).values(amount=100.0))
            await connection.execute(insert(TestMoneyModel).values(amount=100))
        finally:
            await connection.run_sync(test_table.drop)


@pytest.mark.asyncio
async def test_audit_jsonb_scalars_null_and_content_search(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    event_ids = [uuid4() for _ in range(4)]
    entity_id = uuid4()
    payloads: list[object] = [{"marker": "jsonb-test"}, [1, "x"], 7, None]
    try:
        async with db_session_factory.begin() as session:
            for event_id, payload in zip(event_ids, payloads, strict=True):
                session.add(
                    AuditLog(
                        id=event_id,
                        actor_type=ActorType.SYSTEM,
                        actor_id=None,
                        entity_type="test",
                        entity_id=entity_id,
                        action="test.recorded",
                        payload=payload,
                    )
                )

        async with db_session_factory() as session:
            found = await session.scalar(
                select(AuditLog).where(AuditLog.payload.contains({"marker": "jsonb-test"}))
            )
            assert found is not None and found.id == event_ids[0]
            loaded = await session.scalars(
                select(AuditLog.payload).where(AuditLog.id.in_(event_ids)).order_by(AuditLog.id)
            )
            assert len(list(loaded)) == 4
            null_event = await session.scalar(select(AuditLog).where(AuditLog.id == event_ids[3]))
            assert null_event is not None and null_event.payload is None
            assert (
                await session.scalar(
                    select(AuditLog.payload.is_(None)).where(AuditLog.id == event_ids[3])
                )
                is False
            )
            assert (
                await session.scalar(
                    select(func.jsonb_typeof(AuditLog.payload)).where(AuditLog.id == event_ids[3])
                )
                == "null"
            )
    finally:
        async with db_session_factory.begin() as session:
            await session.execute(delete(AuditLog).where(AuditLog.id.in_(event_ids)))


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_preserves_operator_changes(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = f"test-seed-{uuid4()}"
    defaults = (SettingSeed(key=key, value={"enabled": True}, description="test default"),)
    try:
        async with db_session_factory() as session:
            audit_count_before = await session.scalar(select(func.count()).select_from(AuditLog))
        assert await seed_settings(db_session_factory, defaults) == 1
        assert await seed_settings(db_session_factory, defaults) == 0
        async with db_session_factory.begin() as session:
            setting = await session.scalar(select(AppSetting).where(AppSetting.key == key))
            assert setting is not None
            setting.value = {"enabled": False}
        assert await seed_settings(db_session_factory, defaults) == 0
        async with db_session_factory() as session:
            setting = await session.scalar(select(AppSetting).where(AppSetting.key == key))
            assert setting is not None and setting.value == {"enabled": False}
            assert (
                await session.scalar(select(func.count()).select_from(AuditLog))
                == audit_count_before
            )
    finally:
        async with db_session_factory.begin() as session:
            await session.execute(text("DELETE FROM app_settings WHERE key = :key"), {"key": key})
