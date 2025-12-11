"""
Pytest configuration and fixtures for HTTP MCP testing

Provides fixtures to:
1. Start HTTP MCP servers before tests
2. Initialize HTTP MCP client for tests
3. Clean up after tests
"""
import pytest
import asyncio
import subprocess
import time
import httpx
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_client import KYCMCPClient


# MCP Server ports
MCP_SERVERS = {
    "postgres": {"port": 8001, "url": "http://127.0.0.1:8001/mcp"},
    "blob": {"port": 8002, "url": "http://127.0.0.1:8002/mcp"},
    "email": {"port": 8003, "url": "http://127.0.0.1:8003/mcp"},
    "rag": {"port": 8004, "url": "http://127.0.0.1:8004/mcp"},
}


async def wait_for_server(url: str, timeout: int = 30) -> bool:
    """Wait for an HTTP MCP server to become available."""
    async with httpx.AsyncClient() as client:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = await client.get(url.replace("/mcp", "/health"))
                if response.status_code == 200:
                    return True
            except:
                pass
            await asyncio.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def mcp_server_processes(event_loop):
    """
    Start HTTP MCP servers for testing session.
    
    This fixture starts all 4 MCP servers in the background and stops them
    after all tests complete.
    """
    processes = {}
    root_dir = Path(__file__).parent.parent
    
    # Check if servers are already running
    servers_running = True
    for name, config in MCP_SERVERS.items():
        try:
            response = httpx.get(config["url"].replace("/mcp", "/health"), timeout=2.0)
            if response.status_code != 200:
                servers_running = False
                break
        except:
            servers_running = False
            break
    
    if servers_running:
        print("\n✓ HTTP MCP servers already running")
        yield None
        return
    
    print("\nStarting HTTP MCP servers for testing...")
    
    # Start each server
    for name, config in MCP_SERVERS.items():
        script_path = root_dir / f"start_{name}_server.sh"
        
        if not script_path.exists():
            pytest.skip(f"Server script not found: {script_path}")
        
        # Start server in background
        process = subprocess.Popen(
            [str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=root_dir,
            env=os.environ.copy()
        )
        processes[name] = process
        print(f"  Started {name} server (PID: {process.pid})")
    
    # Wait for all servers to be ready
    async def wait_all_servers():
        for name, config in MCP_SERVERS.items():
            print(f"  Waiting for {name} server on {config['url']}...")
            ready = await wait_for_server(config["url"])
            if not ready:
                raise RuntimeError(f"{name} server failed to start")
            print(f"  ✓ {name} server ready")
    
    event_loop.run_until_complete(wait_all_servers())
    print("✓ All HTTP MCP servers ready\n")
    
    yield processes
    
    # Cleanup: stop all servers
    print("\nStopping HTTP MCP servers...")
    for name, process in processes.items():
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        print(f"  Stopped {name} server")


@pytest.fixture(scope="session")
def mcp_client(mcp_server_processes, event_loop):
    """
    Initialize HTTP MCP client for testing (synchronous fixture).
    Ensures servers are running and returns an initialized client instance.
    """
    client = KYCMCPClient(
        postgres_url=MCP_SERVERS["postgres"]["url"],
        blob_url=MCP_SERVERS["blob"]["url"],
        email_url=MCP_SERVERS["email"]["url"],
        rag_url=MCP_SERVERS["rag"]["url"],
    )
    
    event_loop.run_until_complete(client.initialize())
    yield client
    # Close asynchronously
    try:
        event_loop.run_until_complete(client.close())
    except Exception:
        pass


@pytest.fixture
def test_session_data():
    """Provide test session data for tests."""
    return {
        "session_id": "test-session-123",
        "customer_data": {
            "name": "Test User",
            "email": "test@example.com",
            "insurance_needs": "Test insurance"
        },
        "current_step": "intake",
        "status": "in_progress",
        "step_results": {},
        "chat_history": []
    }


@pytest.fixture
def mock_customer_input():
    """Provide mock customer input for tests."""
    return {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "insurance_needs": "Business liability insurance"
    }
