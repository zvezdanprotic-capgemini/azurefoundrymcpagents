"""
Unit tests for local KYC agents.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json

from agents.base import BaseKYCAgent
from agents.intake import IntakeAgent
from agents.verification import VerificationAgent
from agents.eligibility import EligibilityAgent
from agents.recommendation import RecommendationAgent
from agents.compliance import ComplianceAgent
from agents.action import ActionAgent


class TestBaseAgent:
    """Tests for BaseKYCAgent functionality."""
    
    def test_format_customer_data(self):
        """Test customer data formatting."""
        agent = IntakeAgent.__new__(IntakeAgent)
        
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "date_of_birth": "01/01/1990",
            "address": "123 Main St",
        }
        
        result = agent.format_customer_data(data)
        assert "John Doe" in result
        assert "date_of_birth" in result
        assert "123 Main St" in result
    
    def test_format_empty_customer_data(self):
        """Test formatting when no data provided."""
        agent = IntakeAgent.__new__(IntakeAgent)
        result = agent.format_customer_data({})
        assert "No customer data" in result
    
    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        agent = IntakeAgent.__new__(IntakeAgent)
        agent._step_name = "intake"
        
        response = '{"decision": "PASS", "reason": "All good"}'
        parsed = agent.parse_response(response)
        
        assert parsed["decision"] == "PASS"
        assert parsed["reason"] == "All good"
    
    def test_parse_response_json_in_text(self):
        """Test parsing JSON embedded in text."""
        agent = IntakeAgent.__new__(IntakeAgent)
        agent._step_name = "intake"
        
        response = 'Here is my decision: {"decision": "REVIEW", "reason": "Need more"} end.'
        parsed = agent.parse_response(response)
        
        assert parsed["decision"] == "REVIEW"
    
    def test_parse_response_invalid(self):
        """Test handling invalid JSON response."""
        agent = IntakeAgent.__new__(IntakeAgent)
        
        response = "This is not valid JSON at all"
        parsed = agent.parse_response(response)
        
        # Should return default REVIEW decision
        assert parsed["decision"] == "REVIEW"


class TestIntakeAgent:
    """Tests for IntakeAgent."""
    
    def test_step_name(self):
        """Test step name property."""
        with patch.object(IntakeAgent, '_create_default_llm', return_value=MagicMock()):
            agent = IntakeAgent()
            assert agent.step_name == "intake"
    
    def test_system_prompt_content(self):
        """Test system prompt contains key elements."""
        with patch.object(IntakeAgent, '_create_default_llm', return_value=MagicMock()):
            agent = IntakeAgent()
            prompt = agent.system_prompt
            
            assert "Customer Intake" in prompt
            assert "PASS" in prompt
            assert "REVIEW" in prompt
            assert "consent" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_invoke_success(self):
        """Test successful agent invocation."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"stage": "intake", "decision": "PASS", "reason": "Complete"}'
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        
        with patch.object(IntakeAgent, '_create_default_llm', return_value=mock_llm):
            agent = IntakeAgent()
            
            result = await agent.invoke(
                customer_data={"name": "John"},
                latest_message="DOB is 01/01/1990, address is 123 Main St, consent provided",
                conversation_history=[]
            )
            
            assert result["status"] == "success"
            assert result["parsed_decision"]["decision"] == "PASS"


class TestVerificationAgent:
    """Tests for VerificationAgent."""
    
    def test_step_name(self):
        """Test step name property."""
        with patch.object(VerificationAgent, '_create_default_llm', return_value=MagicMock()):
            agent = VerificationAgent()
            assert agent.step_name == "verification"
    
    def test_system_prompt_content(self):
        """Test system prompt contains verification checks."""
        with patch.object(VerificationAgent, '_create_default_llm', return_value=MagicMock()):
            agent = VerificationAgent()
            prompt = agent.system_prompt
            
            assert "Identity Verification" in prompt
            assert "identity_documents" in prompt
            assert "document_authenticity" in prompt
            assert "screening_checks" in prompt


class TestEligibilityAgent:
    """Tests for EligibilityAgent."""
    
    def test_step_name(self):
        """Test step name property."""
        with patch.object(EligibilityAgent, '_create_default_llm', return_value=MagicMock()):
            agent = EligibilityAgent()
            assert agent.step_name == "eligibility"


class TestRecommendationAgent:
    """Tests for RecommendationAgent."""
    
    def test_step_name(self):
        """Test step name property."""
        with patch.object(RecommendationAgent, '_create_default_llm', return_value=MagicMock()):
            agent = RecommendationAgent()
            assert agent.step_name == "recommendation"


class TestComplianceAgent:
    """Tests for ComplianceAgent."""
    
    def test_step_name(self):
        """Test step name property."""
        with patch.object(ComplianceAgent, '_create_default_llm', return_value=MagicMock()):
            agent = ComplianceAgent()
            assert agent.step_name == "compliance"
    
    def test_system_prompt_content(self):
        """Test system prompt contains compliance checks."""
        with patch.object(ComplianceAgent, '_create_default_llm', return_value=MagicMock()):
            agent = ComplianceAgent()
            prompt = agent.system_prompt
            
            assert "Compliance" in prompt
            assert "AML" in prompt or "aml" in prompt.lower()
            assert "KYC" in prompt or "kyc" in prompt.lower()


class TestActionAgent:
    """Tests for ActionAgent."""
    
    def test_step_name(self):
        """Test step name property."""
        with patch.object(ActionAgent, '_create_default_llm', return_value=MagicMock()):
            agent = ActionAgent()
            assert agent.step_name == "action"
    
    def test_system_prompt_content(self):
        """Test system prompt mentions final step."""
        with patch.object(ActionAgent, '_create_default_llm', return_value=MagicMock()):
            agent = ActionAgent()
            prompt = agent.system_prompt
            
            assert "Final" in prompt
            assert "complete" in prompt.lower()
