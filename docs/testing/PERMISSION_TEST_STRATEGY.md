# Permission System Test Strategy

Comprehensive testing strategy for Sibyl's multi-tier permission system.

## Permission Tiers Overview

```
Global Admin (future)
    |
Organization
    |-- Owner (exactly 1, can transfer)
    |-- Admin (many)
    |-- Member
    |-- Viewer
    |
Team (within org)
    |-- Lead
    |-- Member
    |-- Viewer
    |
Project
    |-- Private (user-only)
    |-- Project-wide
    |-- Org-wide
```

## Test Categories

### 1. Unit Tests (Python/pytest)

**Location:** `/apps/api/tests/auth/`

**Files:**

- `test_permission_checker.py` - Core permission logic
- `conftest.py` - Shared fixtures and factories

**Coverage:**

- Role hierarchy logic
- Permission evaluation functions
- Grant aggregation from multiple sources
- API key scope enforcement
- Edge cases (no org context, revoked access)

**Example:**

```python
@pytest.mark.parametrize("role,action,expected", [
    (OrganizationRole.OWNER, "delete", True),
    (OrganizationRole.ADMIN, "delete", False),
    (OrganizationRole.MEMBER, "delete", False),
])
def test_org_delete_permission(role, action, expected):
    ctx = AuthContext(user=mock_user, org=mock_org, org_role=role)
    assert can(ctx, "org:delete") == expected
```

**Run:**

```bash
moon run api:test -- tests/auth/
```

### 2. Integration Tests (API)

**Location:** `/apps/api/tests/auth/test_api_permissions.py`

**Coverage:**

- Every endpoint with all role combinations
- Cross-org access denial
- Owner-only operations (billing, transfer, delete org)
- Admin vs member operations
- API key scope enforcement

**Test Matrix:**

| Endpoint                 | Owner | Admin | Member | Viewer |
| ------------------------ | ----- | ----- | ------ | ------ |
| DELETE /orgs/:slug       | 200   | 403   | 403    | 403    |
| POST /orgs/:slug/members | 200   | 200   | 403    | 403    |
| GET /orgs/:slug/billing  | 200   | 403   | 403    | 403    |
| POST /tasks              | 200   | 200   | 200    | 403    |
| GET /tasks               | 200   | 200   | 200    | 200    |

**Example:**

```python
@pytest.mark.asyncio
async def test_admin_cannot_delete_org(authenticated_client_factory, org_factory):
    org, members = await org_factory.create_with_members(admin_count=1)
    admin = members["admin"][0][0]
    client = authenticated_client_factory(admin, org, OrganizationRole.ADMIN)

    response = await client.delete(f"/api/orgs/{org.slug}")
    assert response.status_code == 403
```

**Run:**

```bash
moon run api:test -- tests/auth/test_api_permissions.py
```

### 3. E2E Tests (Frontend/Playwright)

**Location:** `/apps/e2e/tests/test_permissions.py`

**Coverage:**

- UI elements shown/hidden by role
- Navigation guards
- Permission-denied handling
- Real-time permission updates

**Test Scenarios:**

1. **Owner-only elements:**
   - Delete Organization button
   - Billing settings link
   - Transfer Ownership option

2. **Admin elements:**
   - Add Member button
   - Role change dropdown

3. **Member elements:**
   - Create Task button
   - Add Knowledge button

4. **Viewer elements:**
   - Read-only indicator
   - No edit buttons

**Example:**

```python
@pytest.mark.asyncio
async def test_delete_org_button_hidden_from_admin(logged_in_admin):
    page = logged_in_admin
    await page.goto(f"{FRONTEND_URL}/settings/danger")

    delete_button = page.locator('button:has-text("Delete Organization")')
    await expect(delete_button).not_to_be_visible()
```

**Run:**

```bash
moon run e2e:test -- tests/test_permissions.py
```

### 4. WebSocket Tests

**Location:** `/apps/api/tests/auth/test_websocket_permissions.py`

**Coverage:**

- Permission invalidation events
- Cache invalidation timing
- Connection lifecycle with permission changes
- Multi-tab synchronization

**Test Scenarios:**

1. **Permission invalidation:**
   - Role change broadcasts event
   - Org removal notifies user
   - Team changes notify affected users

2. **Timing:**
   - Invalidation sent before cache clear
   - Client receives before stale request
   - Rapid changes coalesce

3. **Connection lifecycle:**
   - Rejected without auth
   - Closed on org removal
   - Survives role downgrade

**Example:**

```python
@pytest.mark.asyncio
async def test_role_change_broadcasts_invalidation():
    manager = MockConnectionManager()
    ws = MockWebSocket()
    await manager.connect(ws, "user-123", "org-456")

    await manager.broadcast_to_user("user-123", {
        "type": "permission_invalidated",
        "payload": {"reason": "role_changed", "new_role": "member"}
    })

    assert len(ws.messages_sent) == 1
    message = json.loads(ws.messages_sent[0])
    assert message["type"] == "permission_invalidated"
```

### 5. Edge Case Tests

**Location:** `/apps/api/tests/auth/test_edge_cases.py`

**Critical Scenarios:**

1. **Owner Transfer:**
   - Transfer to admin
   - Transfer to member
   - Cannot transfer to non-member
   - Original owner loses privileges

2. **Role Downgrade During Session:**
   - Admin demoted to member
   - Owner demoted (with backup owner)
   - Permissions update immediately

3. **Team Removal Mid-Session:**
   - User removed from team
   - Team deleted entirely
   - Cascade effects

4. **Concurrent Changes:**
   - Simultaneous role changes
   - Removal while role changing

5. **Last Owner Protection:**
   - Cannot demote last owner
   - Cannot remove last owner

## Test Fixtures

### User Factory

```python
@pytest.fixture
def user_factory(db_session):
    return UserFactory(session=db_session)

# Usage
user = await user_factory.create(email="test@example.com")
user, org, membership = await user_factory.create_with_org(role=OrganizationRole.ADMIN)
```

### Organization Factory

```python
@pytest.fixture
def org_factory(db_session, user_factory):
    return OrgFactory(session=db_session, user_factory=user_factory)

# Usage
org, owner = await org_factory.create()
org, members = await org_factory.create_with_members(
    admin_count=2,
    member_count=5,
    viewer_count=3
)
```

### Authenticated Client Factory

```python
@pytest.fixture
def authenticated_client_factory(api_client):
    def create(user, org, role):
        return AuthenticatedClient(...)
    return create

# Usage
client = authenticated_client_factory(user, org, OrganizationRole.ADMIN)
response = await client.get("/api/tasks/")
```

### Multi-Org Setup

```python
@pytest.fixture
async def multi_org_setup(org_factory, user_factory):
    # Creates two orgs with members for cross-org testing
    return MultiOrgSetup(
        org_a=..., org_a_members=...,
        org_b=..., org_b_members=...,
        dual_member=...  # User in both orgs
    )
```

## Running Tests

### All Permission Tests

```bash
# Backend unit + integration
moon run api:test -- tests/auth/

# Frontend unit
moon run web:test -- src/lib/permissions.test.ts

# E2E
moon run e2e:test -- tests/test_permissions.py
```

### Specific Test Categories

```bash
# Unit tests only
moon run api:test -- tests/auth/test_permission_checker.py

# API integration
moon run api:test -- tests/auth/test_api_permissions.py

# Edge cases
moon run api:test -- tests/auth/test_edge_cases.py

# WebSocket
moon run api:test -- tests/auth/test_websocket_permissions.py
```

### Coverage Report

```bash
moon run api:test -- tests/auth/ --cov=sibyl.auth --cov-report=html
```

## CI Integration

Add to `.github/workflows/test.yml`:

```yaml
permission-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Start SurrealDB
      run: docker compose up -d surrealdb
    - name: Run permission tests
      run: |
        moon run api:test -- tests/auth/ -v
        moon run web:test -- src/lib/permissions.test.ts
```

## Test Data Seeding

For E2E tests, seed the database with test users:

```python
# scripts/seed_test_users.py
async def seed_test_users():
    users = [
        {"email": "owner@test.sibyl.dev", "role": "owner"},
        {"email": "admin@test.sibyl.dev", "role": "admin"},
        {"email": "member@test.sibyl.dev", "role": "member"},
        {"email": "viewer@test.sibyl.dev", "role": "viewer"},
    ]
    # Create users and org memberships...
```

## Common Gotchas

1. **Async Session Management:** Always use `await db_session.flush()` after creating test data
2. **Token Creation:** Test tokens bypass real JWT validation - ensure test mode is active
3. **Cross-Org Tests:** Create truly separate orgs, don't reuse fixtures
4. **WebSocket Mocking:** Use MockWebSocket for unit tests, real connections for integration
5. **Permission Matrix Updates:** When adding new permissions, update all test matrices

## Future Enhancements

- [ ] Project-level permission tests (private, project-wide, org-wide)
- [ ] Team grant tests (team membership adding permissions)
- [ ] Global admin role tests
- [ ] Permission audit logging tests
- [ ] Rate limit bypass for admin actions
