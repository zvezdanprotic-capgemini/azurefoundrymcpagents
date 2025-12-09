import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage
from graph import app_graph, AgentState
from langgraph.errors import GraphRecursionError

@pytest.mark.asyncio
async def test_graph_orchestration_pass():
    """
    Test that the orchestrator advances the step when an agent returns PASS.
    """
    # Mock the agent's invoke method
    mock_result_intake = {
        "status": "success",
        "step": "intake",
        "response": '{"decision": "PASS", "reason": "Intake complete"}',
        "parsed_decision": {"decision": "PASS", "reason": "Intake complete"}
    }
    mock_result_verification = {
        "status": "success",
        "step": "verification",
        "response": '{"decision": "REVIEW", "reason": "Need more info"}',
        "parsed_decision": {"decision": "REVIEW", "reason": "Need more info"}
    }
    
    with patch("agents.IntakeAgent") as MockIntakeAgent, \
         patch("agents.VerificationAgent") as MockVerificationAgent:
        
        # Setup mocks
        mock_intake_instance = MagicMock()
        mock_intake_instance.invoke = AsyncMock(return_value=mock_result_intake)
        MockIntakeAgent.return_value = mock_intake_instance
        
        mock_verification_instance = MagicMock()
        mock_verification_instance.invoke = AsyncMock(return_value=mock_result_verification)
        MockVerificationAgent.return_value = mock_verification_instance
        
        # Patch the AGENT_REGISTRY
        with patch("graph.AGENT_REGISTRY", {
            "intake": MockIntakeAgent,
            "verification": MockVerificationAgent,
            "eligibility": MagicMock,
            "recommendation": MagicMock,
            "compliance": MagicMock,
            "action": MagicMock,
        }):
            initial_state = {
                "messages": [HumanMessage(content="Here is my ID")],
                "customer_data": {},
                "next_step": "intake",
                "step_results": {},
                "session_id": "test_session",
                "thread_ids": {},
                "final_response": ""
            }
            
            try:
                final_state = await app_graph.ainvoke(initial_state, {"recursion_limit": 5})
            except GraphRecursionError:
                pass
            
            # Check that intake was called
            assert mock_intake_instance.invoke.called
            
            # Check that verification was also called (because intake passed)
            assert mock_verification_instance.invoke.called

@pytest.mark.asyncio
async def test_graph_orchestration_review():
    """
    Test that the orchestrator stays on the same step when an agent returns REVIEW.
    """
    mock_result = {
        "status": "success",
        "step": "intake",
        "response": '{"decision": "REVIEW", "reason": "Missing docs"}',
        "parsed_decision": {"decision": "REVIEW", "reason": "Missing docs"}
    }
    
    with patch("agents.IntakeAgent") as MockIntakeAgent:
        mock_intake_instance = MagicMock()
        mock_intake_instance.invoke = AsyncMock(return_value=mock_result)
        MockIntakeAgent.return_value = mock_intake_instance
        
        with patch("graph.AGENT_REGISTRY", {
            "intake": MockIntakeAgent,
            "verification": MagicMock,
            "eligibility": MagicMock,
            "recommendation": MagicMock,
            "compliance": MagicMock,
            "action": MagicMock,
        }):
            initial_state = {
                "messages": [HumanMessage(content="Hi")],
                "customer_data": {},
                "next_step": "intake",
                "step_results": {},
                "session_id": "test_session",
                "thread_ids": {},
                "final_response": ""
            }
            
            try:
                await app_graph.ainvoke(initial_state, {"recursion_limit": 5})
            except GraphRecursionError:
                pass
            
            # Should have called intake exactly once because we STOP on review
            assert mock_intake_instance.invoke.call_count == 1

@pytest.mark.asyncio
async def test_graph_orchestration_fail():
    """
    Test that the orchestrator stops when an agent returns FAIL.
    """
    mock_result = {
        "status": "success",
        "step": "intake",
        "response": '{"decision": "FAIL", "reason": "Customer refused consent"}',
        "parsed_decision": {"decision": "FAIL", "reason": "Customer refused consent"}
    }
    
    with patch("agents.IntakeAgent") as MockIntakeAgent:
        mock_intake_instance = MagicMock()
        mock_intake_instance.invoke = AsyncMock(return_value=mock_result)
        MockIntakeAgent.return_value = mock_intake_instance
        
        with patch("graph.AGENT_REGISTRY", {
            "intake": MockIntakeAgent,
            "verification": MagicMock,
            "eligibility": MagicMock,
            "recommendation": MagicMock,
            "compliance": MagicMock,
            "action": MagicMock,
        }):
            initial_state = {
                "messages": [HumanMessage(content="Customer refuses consent")],
                "customer_data": {},
                "next_step": "intake",
                "step_results": {},
                "session_id": "test_session",
                "thread_ids": {},
                "final_response": ""
            }
            
            try:
                await app_graph.ainvoke(initial_state, {"recursion_limit": 5})
            except GraphRecursionError:
                pass
            
            # Should have called intake exactly once because we STOP on fail
            assert mock_intake_instance.invoke.call_count == 1
