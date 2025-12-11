"""
KYC Agents Module

This module contains all LangChain-based agents for the KYC workflow.
All agents use HTTP MCP architecture (inherit from BaseKYCAgentHTTP).
"""

from agents.base_http import BaseKYCAgentHTTP
from agents.intake import IntakeAgent
from agents.verification import VerificationAgent
from agents.eligibility import EligibilityAgent
from agents.recommendation import RecommendationAgent
from agents.compliance import ComplianceAgent
from agents.action import ActionAgent

# Agent registry for easy lookup by step name
AGENT_REGISTRY = {
    "intake": IntakeAgent,
    "verification": VerificationAgent,
    "eligibility": EligibilityAgent,
    "recommendation": RecommendationAgent,
    "compliance": ComplianceAgent,
    "action": ActionAgent,
}

__all__ = [
    "BaseKYCAgentHTTP",
    "IntakeAgent",
    "VerificationAgent", 
    "EligibilityAgent",
    "RecommendationAgent",
    "ComplianceAgent",
    "ActionAgent",
    "AGENT_REGISTRY",
]
