import pytest
import httpx
import uuid

BASE_URL = "http://127.0.0.1:8000"

@pytest.mark.asyncio
@pytest.mark.integration
async def test_health_check():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"] # Degraded is fine if agents aren't all configured

@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_to_end_flow():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Start Session
        customer_data = {
            "name": "Integration Test User",
            "email": "test@example.com",
            "insurance_needs": "Home Insurance"
        }
        response = await client.post("/start-session", json=customer_data)
        assert response.status_code == 200
        session_data = response.json()
        session_id = session_data["session_id"]
        assert session_id is not None
        assert session_data["next_step"] == "intake"

        # 2. Chat - Provide Info (Intake)
        # We expect this to trigger the Intake agent.
        # Since we are mocking/using real agents, the response depends on the agent.
        # But we can check if the system processes it without error.
        chat_msg = {
            "role": "user",
            "content": "I live at 123 Test St, New York, NY. My DOB is 01/01/1980."
        }
        response = await client.post(f"/chat/{session_id}", json=chat_msg)
        assert response.status_code == 200
        chat_response = response.json()
        
        # Verify basic structure
        assert "response" in chat_response
        assert "current_step" in chat_response
        
        # We don't strictly assert advancement because it depends on the agent's logic/LLM response
        # which might vary. But we check that the call succeeded.
        print(f"Chat Response: {chat_response}")

        # 3. Get Session Status
        response = await client.get(f"/session/{session_id}")
        assert response.status_code == 200
        session_details = response.json()
        assert session_details["session_id"] == session_id
        assert session_details["customer"]["name"] == "Integration Test User"