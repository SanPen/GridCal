"""
Unit and integration tests for VeraGridWeb Authentication, Organizations, and Google OAuth.
"""

import pytest
from starlette.testclient import TestClient

from VeraGridWeb.auth.google_auth import GoogleAuthVerifier
from VeraGridWeb.auth.models import Organization, User
from VeraGridWeb.auth.password import hash_password, verify_password
from VeraGridWeb.auth.tokens import JwtTokenService
from VeraGridWeb.auth.user_store import UserStore, UserStoreRegistry
from VeraGridWeb.main import app


def test_password_hasher_and_verification() -> None:
    """
    Test PBKDF2-HMAC-SHA256 password hashing and constant-time verification.
    """
    raw_pass: str = "CorrectHorseBatteryStaple123!"
    hashed: str = hash_password(raw_pass)

    assert hashed.startswith("pbkdf2:sha256:100000:")
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_service_lifecycle() -> None:
    """
    Test HS256 JWT encoding, decoding, payload extraction, and expiration.
    """
    service: JwtTokenService = JwtTokenService(secret_key="unit-test-secret-key")

    payload = {
        "sub": "usr_test_123",
        "email": "tester@example.com",
        "org": "org_test_company",
        "role": "admin",
    }

    # Valid token
    token: str = service.encode(payload, expires_in_seconds=3600)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    decoded = service.decode(token)
    assert decoded is not None
    assert decoded["sub"] == "usr_test_123"
    assert decoded["email"] == "tester@example.com"
    assert decoded["org"] == "org_test_company"
    assert decoded["role"] == "admin"
    assert "exp" in decoded

    # Expired token
    expired_token: str = service.encode(payload, expires_in_seconds=-10)
    assert service.decode(expired_token) is None

    # Tampered signature
    parts = token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.tampered_signature"
    assert service.decode(tampered_token) is None


def test_google_auth_verifier_mock_token() -> None:
    """
    Test Google ID token verification using test-prefixed mock tokens.
    """
    import asyncio

    verifier: GoogleAuthVerifier = GoogleAuthVerifier(client_id=None)

    token = "test-google-token:alice@example.com:Alice Walker"
    result = asyncio.run(verifier.verify_id_token(token))

    assert result is not None
    assert result["email"] == "alice@example.com"
    assert result["name"] == "Alice Walker"
    assert "sub" in result
    assert result["email_verified"] is True

    # Empty token fails
    assert asyncio.run(verifier.verify_id_token("")) is None


def test_user_store_operations() -> None:
    """
    Test Organization and User persistence in UserStore.
    """
    store: UserStore = UserStore()

    # Default admin exists
    admin = store.get_user_by_id("admin")
    assert admin is not None
    assert admin.name == "Administrator"
    assert verify_password("admin", admin.password_hash) is True

    default_org = store.get_organization("org_default")
    assert default_org is not None
    assert default_org.name == "Default Organization"

    # Create new organization and user
    org = store.create_organization(idtag="org_acme", name="Acme Grid Power")
    assert org.idtag == "org_acme"
    assert org.name == "Acme Grid Power"

    user = store.create_user(
        idtag="usr_bob",
        name="Bob Vance",
        email="bob@acme.com",
        password_hash=hash_password("refrigeration"),
        organization_idtag="org_acme",
        google_id="g_12345",
        role="member",
    )

    assert store.get_user_by_id("usr_bob") is not None
    assert store.get_user_by_email("bob@acme.com") is not None
    assert store.get_user_by_email("BOB@ACME.COM") is not None  # Case-insensitive
    assert store.get_user_by_google_id("g_12345") is not None

    org_members = store.list_users_for_organization("org_acme")
    assert len(org_members) == 1
    assert org_members[0].idtag == "usr_bob"


def test_auth_registration_and_login_api_flow() -> None:
    """
    Test registration and login flow via FastAPI endpoints.
    """
    client: TestClient = TestClient(app)

    # 1. Check initial anonymous status
    res_me_anon = client.get("/api/auth/me")
    assert res_me_anon.status_code == 200
    assert res_me_anon.json()["authenticated"] is False

    # 2. Register new user
    reg_payload = {
        "email": "carol@energy.corp",
        "name": "Carol Danvers",
        "password": "super-secure-password-123",
        "organization_name": "Carol Energy Labs",
    }
    res_reg = client.post("/api/auth/register", json=reg_payload)
    assert res_reg.status_code == 200
    reg_data = res_reg.json()
    assert "token" in reg_data
    assert reg_data["user"]["email"] == "carol@energy.corp"
    assert reg_data["organization"]["name"] == "Carol Energy Labs"

    jwt_token = reg_data["token"]

    # 3. Check me using Bearer token
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["email"] == "carol@energy.corp"
    assert me_data["organization"]["name"] == "Carol Energy Labs"

    # 4. Check me using Cookie
    res_me_cookie = client.get("/api/auth/me", cookies={"access_token": jwt_token})
    assert res_me_cookie.status_code == 200
    assert res_me_cookie.json()["authenticated"] is True

    # 5. Check duplicate registration rejection
    res_dup = client.post("/api/auth/register", json=reg_payload)
    assert res_dup.status_code == 409

    # 6. Login with registered credentials
    res_login = client.post(
        "/api/auth/login",
        json={"email": "carol@energy.corp", "password": "super-secure-password-123"},
    )
    assert res_login.status_code == 200
    assert "token" in res_login.json()

    # 7. Login with invalid password
    res_bad = client.post(
        "/api/auth/login",
        json={"email": "carol@energy.corp", "password": "WrongPassword!"},
    )
    assert res_bad.status_code == 401

    # 8. List organization members
    res_members = client.get(
        "/api/auth/organization/users",
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    assert res_members.status_code == 200
    assert len(res_members.json()["members"]) >= 1

    # 9. Logout
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200


def test_google_login_auto_provisioning_api_flow() -> None:
    """
    Test Google login endpoint with auto-creation of personal organization.
    """
    client: TestClient = TestClient(app)

    # Google Sign-in with test token
    google_token = "test-google-token:david@gridtech.io:David Hasselhoff"
    res_google = client.post("/api/auth/google", json={"id_token": google_token})
    assert res_google.status_code == 200
    g_data = res_google.json()

    assert "token" in g_data
    assert g_data["user"]["email"] == "david@gridtech.io"
    assert g_data["user"]["name"] == "David Hasselhoff"
    assert g_data["organization"]["name"] == "David Hasselhoff's Personal Organization"

    token = g_data["token"]

    # Verify session is active
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["authenticated"] is True
    assert res_me.json()["user"]["email"] == "david@gridtech.io"
