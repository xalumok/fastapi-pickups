"""End-to-end tests for pickup API endpoints with full integration.

IMPORTANT: These tests require running PostgreSQL and Redis services.
- PostgreSQL: Required for database operations (uses ARRAY, JSONB types)
- Redis: Required for notification scheduling via ARQ

To run these tests:
    1. Start PostgreSQL (e.g., via Docker):
       docker run --name test-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=postgres -p 5432:5432 -d postgres:15

    2. Start Redis (e.g., via Docker):
       docker run --name test-redis -p 6379:6379 -d redis:7

    3. Set environment variables in src/.env or export them:
       POSTGRES_USER=postgres
       POSTGRES_PASSWORD=postgres
       POSTGRES_SERVER=localhost
       POSTGRES_PORT=5432
       POSTGRES_DB=postgres
       REDIS_QUEUE_HOST=localhost
       REDIS_QUEUE_PORT=6379

    4. Run tests:
       pytest tests/test_pickup_e2e.py -v

    5. Stop containers when done:
       docker stop test-postgres test-redis && docker rm test-postgres test-redis

Note: Tests will be skipped if PostgreSQL or Redis are not available.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from faker import Faker
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.app.core.config import settings
from src.app.core.db.database import Base
from src.app.main import app
from src.app.models.pickup import Pickup
from src.app.models.pickup_address import PickupAddress

fake = Faker()


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


# Test database connection
try:
    DATABASE_URI = settings.POSTGRES_URI
    ASYNC_DATABASE_PREFIX = settings.POSTGRES_ASYNC_PREFIX
    TEST_ASYNC_DATABASE_URL = f"{ASYNC_DATABASE_PREFIX}{DATABASE_URI}"
except Exception as e:
    pytest.skip(f"Database configuration not available: {e}", allow_module_level=True)




@pytest.fixture(scope="module")
async def test_async_engine():
    """Create an async engine for FastAPI dependency override and tests.

    This fixture:
    1. Creates an async SQLAlchemy engine with connection timeout
    2. Verifies the database is reachable
    3. Creates all required tables
    4. Yields the engine for tests
    5. Drops tables and disposes the engine on teardown
    """
    import asyncio

    # Create engine with connection timeout to avoid hanging indefinitely
    engine = create_async_engine(
        TEST_ASYNC_DATABASE_URL,
        echo=False,
        future=True,
        connect_args={
            "timeout": 5,  # Connection timeout in seconds
            "command_timeout": 10,  # Query timeout
        },
    )

    # Test connection and create tables - skip tests if DB is unavailable
    try:
        async with asyncio.timeout(15):  # Overall timeout for setup
            async with engine.begin() as conn:
                # Verify we can actually query the database
                await conn.execute(text("SELECT 1"))
                # Create all tables
                await conn.run_sync(Base.metadata.create_all)
                print(f"[E2E Tests] Database connection successful, tables created")
    except asyncio.TimeoutError:
        await engine.dispose()
        pytest.skip("Database connection timed out - is PostgreSQL running?")
    except Exception as e:
        await engine.dispose()
        pytest.skip(f"Cannot connect to test database: {type(e).__name__}: {e}")

    # Yield engine for tests
    yield engine

    # Teardown - drop tables and dispose
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception as e:
        print(f"[E2E Tests] Warning: Failed to drop tables during teardown: {e}")
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def test_async_session_factory(test_async_engine):
    """Create an async session factory for API dependency override."""
    return async_sessionmaker(
        bind=test_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
async def db_session(test_async_session_factory) -> AsyncSession:
    """Async database session for e2e tests."""
    async with test_async_session_factory() as session:
        yield session


@pytest.fixture(scope="module")
async def check_redis():
    """Check if Redis is available, skip tests if not."""
    import asyncio

    import redis.asyncio as redis

    from src.app.core.config import settings

    try:
        async with asyncio.timeout(5):
            client = redis.Redis(
                host=settings.REDIS_QUEUE_HOST,
                port=settings.REDIS_QUEUE_PORT,
            )
            await client.ping()
            await client.aclose()
            print(
                f"[E2E Tests] Redis connection successful: {settings.REDIS_QUEUE_HOST}:{settings.REDIS_QUEUE_PORT}"
            )
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture
async def client_e2e(test_async_session_factory, check_redis) -> AsyncClient:
    """Async test client for e2e tests with real database and Redis.

    This fixture:
    - Overrides the database session with a test database
    - Requires Redis to be running for notification scheduling
    - Disables the app lifespan to prevent startup/shutdown side effects
    """
    from src.app.core.db.database import async_get_db

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    async def override_get_db():
        """Override database dependency with async test database session."""
        async with test_async_session_factory() as session:
            yield session

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = noop_lifespan
    app.dependency_overrides[async_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides = {}
    app.router.lifespan_context = original_lifespan


async def cleanup_pickup_data(db_session: AsyncSession):
    """Clean up pickup and address data from database."""
    try:
        await db_session.execute(text("DELETE FROM pickup"))
        await db_session.execute(text("DELETE FROM pickup_address"))
        await db_session.commit()
    except Exception:
        await db_session.rollback()


@pytest.mark.anyio("asyncio")
class TestPickupE2E:
    """End-to-end tests for pickup endpoints with real database."""

    @pytest.fixture(autouse=True)
    async def setup_method(self, db_session):
        """Clean up before and after each test."""
        await cleanup_pickup_data(db_session)
        yield
        await cleanup_pickup_data(db_session)

    async def test_create_pickup_e2e(self, client_e2e, db_session):
        """Test creating a pickup with database persistence."""
        # Prepare test data
        start_time = datetime.now(UTC) + timedelta(hours=3)
        end_time = start_time + timedelta(hours=2)

        pickup_data = {
            "label_ids": ["se-28529731", "se-28529732"],
            "contact_details": {
                "name": "Jane Smith",
                "email": "jane@example.com",
                "phone": "+1 555-0100",
            },
            "pickup_notes": "Call before arriving",
            "pickup_window": {
                "start_at": start_time.isoformat(),
                "end_at": end_time.isoformat(),
            },
            "pickup_address": {
                "name": "Jane Smith",
                "phone": "+1 555-0100",
                "email": "jane@example.com",
                "company_name": "Acme Corp",
                "address_line1": "123 Main Street",
                "address_line2": "Suite 100",
                "city_locality": "New York",
                "state_province": "NY",
                "postal_code": "10001",
                "country_code": "US",
            },
        }

        # Create pickup via API
        response = await client_e2e.post("/api/v1/pickups/", json=pickup_data)

        # Verify response
        assert response.status_code == 201
        response_data = response.json()
        assert "pickup_id" in response_data
        assert response_data["pickup_id"].startswith("pik_")
        assert response_data["label_ids"] == pickup_data["label_ids"]
        assert response_data["pickup_notes"] == pickup_data["pickup_notes"]

        # Verify data in database
        pickup_id = response_data["pickup_id"]
        pickup_result = await db_session.execute(
            select(Pickup).filter_by(pickup_id=pickup_id)
        )
        pickup_record = pickup_result.scalar_one_or_none()
        assert pickup_record is not None
        assert pickup_record.label_ids == pickup_data["label_ids"]
        assert pickup_record.is_deleted is False
        assert pickup_record.notification_sent is False

        # Verify address in database
        address_result = await db_session.execute(
            select(PickupAddress).filter_by(id=pickup_record.pickup_address_id)
        )
        address_record = address_result.scalar_one_or_none()
        assert address_record is not None
        assert address_record.name == "Jane Smith"
        assert address_record.address_line1 == "123 Main Street"
        assert address_record.city_locality == "New York"

    async def test_get_pickup_e2e(self, client_e2e, db_session):
        """Test retrieving a pickup from database."""
        # Create pickup via API first
        start_time = datetime.now(UTC) + timedelta(hours=3)
        end_time = start_time + timedelta(hours=2)

        pickup_data = {
            "label_ids": ["se-12345"],
            "contact_details": {
                "name": "Bob Johnson",
                "email": "bob@example.com",
                "phone": "+1 555-0200",
            },
            "pickup_notes": "Use back entrance",
            "pickup_window": {
                "start_at": start_time.isoformat(),
                "end_at": end_time.isoformat(),
            },
            "pickup_address": {
                "name": "Bob Johnson",
                "phone": "+1 555-0200",
                "address_line1": "456 Oak Avenue",
                "city_locality": "Los Angeles",
                "state_province": "CA",
                "postal_code": "90001",
                "country_code": "US",
            },
        }

        create_response = await client_e2e.post("/api/v1/pickups/", json=pickup_data)
        assert create_response.status_code == 201
        pickup_id = create_response.json()["pickup_id"]

        # Retrieve pickup via API
        get_response = await client_e2e.get(f"/api/v1/pickups/{pickup_id}")

        # Verify response
        assert get_response.status_code == 200
        response_data = get_response.json()
        assert response_data["pickup_id"] == pickup_id
        assert response_data["label_ids"] == pickup_data["label_ids"]
        assert response_data["pickup_notes"] == pickup_data["pickup_notes"]
        assert response_data["pickup_address"]["name"] == "Bob Johnson"
        assert response_data["pickup_address"]["city_locality"] == "Los Angeles"

    async def test_get_all_pickups_e2e(self, client_e2e, db_session):
        """Test retrieving all pickups with pagination."""
        # Create multiple pickups
        start_time = datetime.now(UTC) + timedelta(hours=3)
        end_time = start_time + timedelta(hours=2)

        for i in range(3):
            pickup_data = {
                "label_ids": [f"se-{10000 + i}"],
                "contact_details": {
                    "name": f"User {i}",
                    "email": f"user{i}@example.com",
                    "phone": f"+1 555-{i:04d}",
                },
                "pickup_notes": f"Notes for pickup {i}",
                "pickup_window": {
                    "start_at": (start_time + timedelta(hours=i)).isoformat(),
                    "end_at": (end_time + timedelta(hours=i)).isoformat(),
                },
                "pickup_address": {
                    "name": f"User {i}",
                    "phone": f"+1 555-{i:04d}",
                    "address_line1": f"{100 + i} Test Street",
                    "city_locality": "Test City",
                    "state_province": "TS",
                    "postal_code": f"0000{i}",
                    "country_code": "US",
                },
            }
            response = await client_e2e.post("/api/v1/pickups/", json=pickup_data)
            assert response.status_code == 201

        # Retrieve all pickups
        list_response = await client_e2e.get(
            "/api/v1/pickups/?page=1&items_per_page=10"
        )

        # Verify response
        assert list_response.status_code == 200
        response_data = list_response.json()
        assert "data" in response_data
        assert "total_count" in response_data
        assert response_data["total_count"] == 3
        assert len(response_data["data"]) == 3
        assert response_data["page"] == 1

        # Verify database has 3 pickups
        count_result = await db_session.execute(
            select(func.count()).select_from(Pickup).where(Pickup.is_deleted.is_(False))
        )
        pickup_count = count_result.scalar_one()
        assert pickup_count == 3

    async def test_delete_pickup_e2e(self, client_e2e, db_session):
        """Test soft deleting a pickup."""
        # Create pickup first
        start_time = datetime.now(UTC) + timedelta(hours=3)
        end_time = start_time + timedelta(hours=2)

        pickup_data = {
            "label_ids": ["se-99999"],
            "contact_details": {
                "name": "Delete Test",
                "email": "delete@example.com",
                "phone": "+1 555-9999",
            },
            "pickup_notes": "To be deleted",
            "pickup_window": {
                "start_at": start_time.isoformat(),
                "end_at": end_time.isoformat(),
            },
            "pickup_address": {
                "name": "Delete Test",
                "phone": "+1 555-9999",
                "address_line1": "999 Delete Road",
                "city_locality": "Delete City",
                "state_province": "DC",
                "postal_code": "99999",
                "country_code": "US",
            },
        }

        create_response = await client_e2e.post("/api/v1/pickups/", json=pickup_data)
        assert create_response.status_code == 201
        pickup_id = create_response.json()["pickup_id"]

        # Delete pickup
        delete_response = await client_e2e.delete(f"/api/v1/pickups/{pickup_id}")

        # Verify response
        assert delete_response.status_code == 200
        assert "cancelled successfully" in delete_response.json()["message"]

        # Verify soft deletion in database
        pickup_result = await db_session.execute(
            select(Pickup).filter_by(pickup_id=pickup_id)
        )
        pickup_record = pickup_result.scalar_one_or_none()
        assert pickup_record is not None
        assert pickup_record.is_deleted is True
        assert pickup_record.deleted_at is not None
        assert pickup_record.cancelled_at is not None

        # Verify pickup is not returned in list
        list_response = await client_e2e.get("/api/v1/pickups/")
        response_data = list_response.json()
        deleted_pickup_ids = [p["pickup_id"] for p in response_data["data"]]
        assert pickup_id not in deleted_pickup_ids

        # Verify cannot retrieve deleted pickup
        get_response = await client_e2e.get(f"/api/v1/pickups/{pickup_id}")
        assert get_response.status_code == 404

    async def test_pagination_e2e(self, client_e2e, db_session):
        """Test pagination works correctly with database."""
        # Create 15 pickups
        start_time = datetime.now(UTC) + timedelta(hours=3)
        end_time = start_time + timedelta(hours=2)

        for i in range(15):
            pickup_data = {
                "label_ids": [f"se-page-{i}"],
                "contact_details": {
                    "name": f"Page User {i}",
                    "email": f"page{i}@example.com",
                    "phone": f"+1 555-{i:04d}",
                },
                "pickup_notes": f"Pagination test {i}",
                "pickup_window": {
                    "start_at": start_time.isoformat(),
                    "end_at": end_time.isoformat(),
                },
                "pickup_address": {
                    "name": f"Page User {i}",
                    "phone": f"+1 555-{i:04d}",
                    "address_line1": f"{i} Page Street",
                    "city_locality": "Page City",
                    "state_province": "PG",
                    "postal_code": f"{i:05d}",
                    "country_code": "US",
                },
            }
            response = await client_e2e.post("/api/v1/pickups/", json=pickup_data)
            assert response.status_code == 201

        # Test page 1 with 10 items
        page1_response = await client_e2e.get(
            "/api/v1/pickups/?page=1&items_per_page=10"
        )
        assert page1_response.status_code == 200
        page1_data = page1_response.json()
        assert page1_data["total_count"] == 15
        assert len(page1_data["data"]) == 10
        assert page1_data["page"] == 1
        assert page1_data["has_more"] is True

        # Test page 2 with 10 items
        page2_response = await client_e2e.get(
            "/api/v1/pickups/?page=2&items_per_page=10"
        )
        assert page2_response.status_code == 200
        page2_data = page2_response.json()
        assert page2_data["total_count"] == 15
        assert len(page2_data["data"]) == 5
        assert page2_data["page"] == 2
        assert page2_data["has_more"] is False

        # Verify no overlap between pages
        page1_ids = {p["pickup_id"] for p in page1_data["data"]}
        page2_ids = {p["pickup_id"] for p in page2_data["data"]}
        assert len(page1_ids.intersection(page2_ids)) == 0

    async def test_get_nonexistent_pickup_e2e(self, client_e2e):
        """Test getting a pickup that doesn't exist."""
        response = await client_e2e.get("/api/v1/pickups/pik_nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_delete_nonexistent_pickup_e2e(self, client_e2e):
        """Test deleting a pickup that doesn't exist."""
        response = await client_e2e.delete("/api/v1/pickups/pik_nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
