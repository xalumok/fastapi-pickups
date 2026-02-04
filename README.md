## Pickup Scheduling API

**What it does:** Schedule package pickups with automatic notifications 1 hour before pickup time.

**Reference link** [Package Pickups](https://shipengine.github.io/shipengine-openapi/#tag/package_pickups)

**Structure:**
- **Models** (`src/app/models/`) - `pickup` & `pickup_address` tables
- **CRUD** (`src/app/crud/`) - Database operations via FastCRUD
- **Schemas** (`src/app/schemas/`) - Pydantic validation models
- **Services** (`src/app/services/`) - Business logic (pickup, notification, scheduling)
- **API** (`src/app/api/v1/pickups.py`) - 4 REST endpoints (create, list, get, delete)
- **Workers** (`src/app/core/worker/`) - ARQ background jobs for notifications
- **Tests** (`tests/`) - unit + E2E + service tests