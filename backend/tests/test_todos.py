"""Todo tests."""

import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str = "todo@example.com") -> str:
    """Helper to register and get auth token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_todo(client: AsyncClient):
    """Test creating a new todo."""
    token = await get_auth_token(client, "create@example.com")

    response = await client.post(
        "/api/v1/todos",
        json={"title": "Test Todo", "description": "A test todo item"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["description"] == "A test todo item"
    assert data["completed"] is False


@pytest.mark.asyncio
async def test_get_todos(client: AsyncClient):
    """Test getting todo list."""
    token = await get_auth_token(client, "list@example.com")

    # Create a todo first
    await client.post(
        "/api/v1/todos",
        json={"title": "List Todo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get todos
    response = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_update_todo(client: AsyncClient):
    """Test updating a todo."""
    token = await get_auth_token(client, "update@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Update Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Update it
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Updated Title", "completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_todo(client: AsyncClient):
    """Test deleting a todo."""
    token = await get_auth_token(client, "delete@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Delete Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Delete it
    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_single_todo(client: AsyncClient):
    """Test getting a single todo by ID."""
    token = await get_auth_token(client, "single@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Single Todo", "description": "Get me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Get it
    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Single Todo"

async def get_auth_token_for(client: AsyncClient, email: str) -> str:
    """Helper to register and get auth token for a specific user."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_cannot_access_other_users_todo(client: AsyncClient):
    """Test that a user cannot access another user's todo."""
    # User A creates a todo
    token_a = await get_auth_token_for(client, "usera@example.com")
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "User A's todo"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    todo_id = create_response.json()["id"]

    # User B tries to access User A's todo
    token_b = await get_auth_token_for(client, "userb@example.com")
    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cannot_update_other_users_todo(client: AsyncClient):
    """Test that a user cannot update another user's todo."""
    token_a = await get_auth_token_for(client, "update_a@example.com")
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "User A's todo"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    todo_id = create_response.json()["id"]

    token_b = await get_auth_token_for(client, "update_b@example.com")
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Hacked!"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cannot_delete_other_users_todo(client: AsyncClient):
    """Test that a user cannot delete another user's todo."""
    token_a = await get_auth_token_for(client, "delete_a@example.com")
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "User A's todo"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    todo_id = create_response.json()["id"]

    token_b = await get_auth_token_for(client, "delete_b@example.com")
    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_toggle_completed_false(client: AsyncClient):
    """Test that a completed todo can be set back to incomplete."""
    token = await get_auth_token_for(client, "toggle@example.com")

    # Create and complete a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Toggle Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Set completed=True
    await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Set completed=False (this was the bug)
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["completed"] is False


@pytest.mark.asyncio
async def test_login_wrong_email_returns_401(client: AsyncClient):
    """Test that login with wrong email returns 401, not 404."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "password123"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient):
    """Test that login with wrong password returns 401 with generic message."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpass@example.com", "password": "correctpassword"},
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_todos_are_user_scoped(client: AsyncClient):
    """Test that each user only sees their own todos."""
    token_a = await get_auth_token_for(client, "scope_a@example.com")
    token_b = await get_auth_token_for(client, "scope_b@example.com")

    # User A creates a todo
    await client.post(
        "/api/v1/todos",
        json={"title": "User A's private todo"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # User B should not see User A's todo
    response = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(item["title"] != "User A's private todo" for item in data["items"])