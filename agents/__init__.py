"""
Local KYC Agents Module

This module contains all the local LangChain-based agents for the KYC workflow.
These agents replace the previous Azure AI Foundry Agents for better control.
"""

from agents.base import BaseKYCAgent
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
    "BaseKYCAgent",
    "IntakeAgent",
    "VerificationAgent", 
    "EligibilityAgent",
    "RecommendationAgent",
    "ComplianceAgent",
    "ActionAgent",
    "AGENT_REGISTRY",
]
