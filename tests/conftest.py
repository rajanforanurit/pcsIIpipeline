import os
import pytest
from httpx import AsyncClient, ASGITransport
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test_db")
os.environ.setdefault("ADMIN_ID", "testadmin")
os.environ.setdefault("ADMIN_PASS", "testpass123")
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_minimum_32_chars_long_abc")
os.environ.setdefault("PSC2", "")
os.environ.setdefault("PCS2_API", "")
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
