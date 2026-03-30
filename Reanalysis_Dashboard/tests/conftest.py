import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

# Ensure Reanalysis_Dashboard is on the path so server.py can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
