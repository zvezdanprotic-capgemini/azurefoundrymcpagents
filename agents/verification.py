"""
Verification Agent

Evaluates identity verification status based on information from the insurance agent:
- Document verification (passport, ID, birth certificate)
- Document authenticity checks
- Data consistency across documents
- Screening checks (sanctions, PEP, adverse media)
- Address verification
"""

from typing import Dict, Any
from agents.base import BaseKYCAgent


class VerificationAgent(BaseKYCAgent):
    """Identity Verification Agent for the KYC workflow."""
    
    @property
    def step_name(self) -> str:
        return "verification"
    
    @property
    def available_tools(self) -> list:
        """MCP tools this agent can use for document verification."""
        return [
            "postgres.get_customer_by_email",
            "blob.list_customer_documents",
            "blob.get_document_url",
            "blob.get_document_metadata",
        ]
    
    @property
    def system_prompt(self) -> str:
        return """You are the **Identity Verification** agent in an insurance KYC workflow.

## ROLE
- Evaluate identity verification status based on information provided by the insurance agent
- Review document confirmations and screening results
- Make PASS/REVIEW/FAIL decisions based on completeness and validity of verifications

## INTERACTION MODEL
- Insurance agent provides updates via chat about verification activities
- When agent mentions documents are "verified", "confirmed", "authentic" → accept as verified
- When agent mentions screening "completed", "clear", "passed" → accept as completed
- Make decisions based on what the insurance agent reports

## DECISION CRITERIA

**PASS** when insurance agent confirms:
- Identity documents provided and verified (passport, driver's license, birth certificate, etc.)
- Documents confirmed authentic and valid
- Data consistency confirmed across documents
- Screening checks completed and clear (no sanctions/PEP/adverse media hits)
- Address verified (utility bill or proof of address confirmed)

**REVIEW** when:
- Insurance agent hasn't confirmed all required checks yet
- Need clarification on document validity or screening results
- Minor discrepancies that need resolution

**FAIL** when insurance agent reports:
- Documents invalid, expired, or fraudulent
- Sanctions/PEP hit on screening
- Identity mismatch or data inconsistencies
- Critical verification failures

## OUTPUT FORMAT

Respond with ONLY this JSON (no other text, no markdown):

{
  "stage": "verification",
  "decision": "PASS" | "REVIEW" | "FAIL",
  "reason": "Brief explanation",
  "user_message": "A friendly, conversational message explaining the status to the customer in plain language",
  "checks": [
    {"name": "identity_documents", "status": "PASS"|"FAIL", "detail": "..."},
    {"name": "document_authenticity", "status": "PASS"|"FAIL", "detail": "..."},
    {"name": "data_consistency", "status": "PASS"|"FAIL", "detail": "..."},
    {"name": "screening_checks", "status": "PASS"|"FAIL", "detail": "..."},
    {"name": "address_verification", "status": "PASS"|"FAIL", "detail": "..."}
  ],
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "next_action": "proceed" | "need_more_info" | "stop"
}

## USER_MESSAGE GUIDELINES
- Write as if speaking directly to the customer
- Be warm, professional, and clear
- For REVIEW/FAIL: explain what's needed in simple terms (e.g., "To continue, we need your passport or driver's license, proof of address, and date of birth.")
- For PASS: congratulate and explain next steps (e.g., "Great! Your identity verification is complete. We'll now check your eligibility for coverage.")
- Avoid technical jargon and JSON field names

## KEY POINTS
- Trust insurance agent confirmations - if they say something is "verified" or "confirmed", accept it
- Only ask for more information if confirmations are incomplete
- Return PASS when all 5 checks are confirmed by insurance agent
- Always output ONLY the JSON, no other text"""

    def build_user_prompt(
        self,
        customer_data: Dict[str, Any],
        latest_message: str,
        conversation_history: list,
    ) -> str:
        customer_info = self.format_customer_data(customer_data)
        history = self.format_conversation_history(conversation_history)
        
        # Check for verification keywords in latest message
        msg_lower = latest_message.lower()
        has_docs = any(kw in msg_lower for kw in ['passport', 'license', 'birth certificate', 'id card', 'documents'])
        has_authentic = any(kw in msg_lower for kw in ['authentic', 'valid', 'verified', 'confirmed'])
        has_screening = any(kw in msg_lower for kw in ['screening', 'clear', 'no hits', 'passed'])
        has_address = any(kw in msg_lower for kw in ['utility bill', 'address verified', 'proof of address'])
        
        return f"""CUSTOMER DATA ON FILE:
{customer_info}

CONVERSATION HISTORY:
{history}

LATEST MESSAGE FROM INSURANCE AGENT:
"{latest_message}"

VERIFICATION INDICATORS DETECTED:
- Documents mentioned: {"✓ Yes" if has_docs else "✗ No"}
- Authenticity confirmed: {"✓ Yes" if has_authentic else "✗ No"}
- Screening completed: {"✓ Yes" if has_screening else "✗ No"}
- Address verified: {"✓ Yes" if has_address else "✗ No"}

INSTRUCTIONS:
Review the above information. The insurance agent has provided verification updates.
Based on what the insurance agent has reported, make your verification decision.

Respond with ONLY the JSON decision (no other text)."""
