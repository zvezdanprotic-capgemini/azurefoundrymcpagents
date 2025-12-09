"""
Unit tests for main.py - FastAPI application logic
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Import the main application
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, sessions, CustomerInput

client = TestClient(app)


class TestMainApplication:
    """Test suite for main FastAPI application"""
    
    def setup_method(self):
        """Setup before each test"""
        # Clear sessions before each test
        sessions.clear()
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "services" in data
        assert "active_sessions" in data
    
    def test_start_session_valid_input(self):
        """Test starting a session with valid customer input"""
        customer_data = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "insurance_needs": "Business liability insurance"
        }
        
        response = client.post("/start-session", json=customer_data)
        assert response.status_code == 200
        data = response.json()
        
        assert "session_id" in data
        assert data["next_step"] == "intake"
        assert "welcome_message" in data
        assert data["status"] == "started"
        
        # Verify session was created
        session_id = data["session_id"]
        assert session_id in sessions
        assert sessions[session_id]["customer"]["name"] == "John Doe"
    
    def test_start_session_invalid_input(self):
        """Test starting a session with invalid customer input"""
        invalid_data = {
            "name": "John Doe",
            # Missing required email and insurance_needs
        }
        
        response = client.post("/start-session", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_get_session_existing(self):
        """Test getting an existing session"""
        # First create a session
        customer_data = {
            "name": "Jane Smith",
            "email": "jane.smith@example.com",
            "insurance_needs": "Health insurance"
        }
        
        create_response = client.post("/start-session", json=customer_data)
        session_id = create_response.json()["session_id"]
        
        # Now get the session
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["session_id"] == session_id
        assert data["customer"]["name"] == "Jane Smith"
        assert data["current_step"] == "intake"
        assert data["status"] == "in_progress"
    
    def test_get_session_nonexistent(self):
        """Test getting a non-existent session"""
        response = client.get("/session/non-existent-id")
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]
    
    def test_get_workflow_steps(self):
        """Test getting workflow steps"""
        response = client.get("/steps")
        assert response.status_code == 200
        data = response.json()
        
        assert "steps" in data
        steps = data["steps"]
        assert len(steps) == 6  # Expected number of workflow steps
        
        expected_steps = ["intake", "verification", "eligibility", "recommendation", "compliance", "action"]
        actual_step_ids = [step["id"] for step in steps]
        assert actual_step_ids == expected_steps


if __name__ == "__main__":
    pytest.main([__file__, "-v"])