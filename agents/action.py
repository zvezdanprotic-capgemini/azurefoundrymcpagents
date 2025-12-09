"""
Action Agent

Completes the final onboarding steps:
- Policy issuance preparation
- Welcome package generation
- Next steps communication
- Follow-up scheduling if needed
"""

from typing import Dict, Any
from agents.base import BaseKYCAgent


class ActionAgent(BaseKYCAgent):
    """Final Action Agent for the KYC workflow."""
    
    @property
    def step_name(self) -> str:
        return "action"
    
    @property
    def available_tools(self) -> list:
        """MCP tools this agent can use for final actions."""
        return [
            "email.send_kyc_approved_email",
            "email.send_kyc_pending_email",
            "email.send_kyc_rejected_email",
            "email.send_follow_up_email",
            "postgres.save_kyc_session_state",
        ]
    
    @property
    def system_prompt(self) -> str:
        return """You are the **Final Action** agent in an insurance KYC workflow.

## ROLE
- Complete the customer onboarding process
- Prepare policy issuance
- Generate welcome package details
- Determine next steps for the customer
- Schedule follow-ups if needed

## INTERACTION MODEL
- Insurance agent confirms all prior steps are complete
- Finalize the application and determine actions
- Provide clear completion status and next steps

## DECISION CRITERIA

**PASS** when:
- All prior KYC steps completed successfully
- Application ready for policy issuance
- Customer onboarding can proceed
- No outstanding issues

**REVIEW** when:
- Minor items need follow-up
- Additional signatures or confirmations needed
- Scheduling coordination required
- Manual processing step needed

**FAIL** when:
- Critical steps incomplete
- Application cannot proceed
- Fundamental issues unresolved
- Customer has withdrawn

## OUTPUT FORMAT

Respond with ONLY this JSON (no other text, no markdown):

{
  "stage": "action",
  "decision": "PASS" | "REVIEW" | "FAIL",
  "reason": "Brief explanation",
  "user_message": "A friendly, conversational message explaining the final status to the customer in plain language",
  "checks": [
    {"name": "application_complete", "status": "PASS"|"FAIL", "detail": "..."},
    {"name": "policy_ready", "status": "PASS"|"FAIL", "detail": "..."},
    {"name": "welcome_package", "status": "PASS"|"FAIL", "detail": "..."},
    {"name": "next_steps_defined", "status": "PASS"|"FAIL", "detail": "..."},
    {"name": "followup_scheduled", "status": "PASS"|"FAIL", "detail": "..."}
  ],
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "next_action": "complete" | "need_more_info" | "stop"
}

## USER_MESSAGE GUIDELINES
- Write as if speaking directly to the customer
- Be warm, professional, and clear
- For REVIEW/FAIL: explain what's needed to complete (e.g., "We're almost there! We still need your identity documents to finalize your application.")
- For PASS: celebrate completion and explain next steps (e.g., "Congratulations! Your application is complete. Your policy documents will be sent to your email within 24 hours.")
- Avoid technical jargon and JSON field names

## KEY POINTS
- This is the final step in the KYC workflow
- Confirm all prior steps are complete
- Provide clear next steps for policy issuance
- A PASS here means the application is complete
- Always output ONLY the JSON, no other text"""

    def build_user_prompt(
        self,
        customer_data: Dict[str, Any],
        latest_message: str,
        conversation_history: list,
    ) -> str:
        customer_info = self.format_customer_data(customer_data)
        history = self.format_conversation_history(conversation_history)
        
        customer_name = customer_data.get('name', 'Customer')
        insurance_needs = customer_data.get('insurance_needs', 'Not specified')
        
        return f"""CUSTOMER: {customer_name}
Insurance Needs: {insurance_needs}

CUSTOMER PROFILE:
{customer_info}

CONVERSATION HISTORY:
{history}

LATEST MESSAGE FROM INSURANCE AGENT:
"{latest_message}"

INSTRUCTIONS:
This is the final step. Review the completed application and determine:
1. Is the application complete and ready for policy issuance?
2. What are the next steps for the customer?
3. Are there any follow-up items needed?

Respond with ONLY the JSON decision (no other text)."""
