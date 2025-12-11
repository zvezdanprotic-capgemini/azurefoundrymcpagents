"""
Email MCP Server

Provides tools for:
- Sending KYC approval notifications
- Sending pending/review notifications
- Sending rejection emails with reasons
- Sending follow-up requests for additional documents
"""

import os
import logging
from typing import Any, Dict, List, Optional

from mcp_servers.base import BaseMCPServer, ToolResult, get_env_or_default
from mcp_servers.http_app import create_mcp_http_app

logger = logging.getLogger("mcp_servers.email")


class EmailMCPServer(BaseMCPServer):
    """MCP Server for email notifications."""
    
    def __init__(self):
        """Initialize email server with configuration from environment."""
        super().__init__()
        self._sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
        self._smtp_host = os.environ.get("SMTP_HOST")
        self._smtp_port = int(get_env_or_default("SMTP_PORT", "587"))
        self._smtp_user = os.environ.get("SMTP_USER")
        self._smtp_password = os.environ.get("SMTP_PASSWORD")
        self._from_email = get_env_or_default("EMAIL_FROM", "kyc@insurance.com")
        self._from_name = get_env_or_default("EMAIL_FROM_NAME", "Insurance KYC")
    
    @property
    def name(self) -> str:
        return "email"
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions for this server."""
        return [
            {
                "name": "send_kyc_approved_email",
                "description": "Send KYC approval notification to customer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to_email": {"type": "string", "description": "Customer email address"},
                        "customer_name": {"type": "string", "description": "Customer name for personalization"},
                        "policy_type": {"type": "string", "description": "Type of insurance approved"},
                        "next_steps": {"type": "string", "description": "Instructions for next steps"}
                    },
                    "required": ["to_email", "customer_name"]
                }
            },
            {
                "name": "send_kyc_pending_email",
                "description": "Send notification that KYC is pending review",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to_email": {"type": "string", "description": "Customer email address"},
                        "customer_name": {"type": "string", "description": "Customer name"},
                        "reason": {"type": "string", "description": "Reason for pending status"},
                        "estimated_time": {"type": "string", "description": "Estimated completion time"}
                    },
                    "required": ["to_email", "customer_name"]
                }
            },
            {
                "name": "send_kyc_rejected_email",
                "description": "Send KYC rejection notification with reasons",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to_email": {"type": "string", "description": "Customer email address"},
                        "customer_name": {"type": "string", "description": "Customer name"},
                        "rejection_reasons": {"type": "array", "items": {"type": "string"}, "description": "List of rejection reasons"},
                        "appeal_instructions": {"type": "string", "description": "How to appeal or reapply"}
                    },
                    "required": ["to_email", "customer_name", "rejection_reasons"]
                }
            },
            {
                "name": "send_follow_up_email",
                "description": "Request additional documents from customer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to_email": {"type": "string", "description": "Customer email address"},
                        "customer_name": {"type": "string", "description": "Customer name"},
                        "required_documents": {"type": "array", "items": {"type": "string"}, "description": "List of required documents"},
                        "deadline": {"type": "string", "description": "Submission deadline"},
                        "upload_link": {"type": "string", "description": "Link to document upload portal"}
                    },
                    "required": ["to_email", "customer_name", "required_documents"]
                }
            }
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool and return the result."""
        try:
            if tool_name == "send_kyc_approved_email":
                return await self._send_kyc_approved_email(arguments)
            elif tool_name == "send_kyc_pending_email":
                return await self._send_kyc_pending_email(arguments)
            elif tool_name == "send_kyc_rejected_email":
                return await self._send_kyc_rejected_email(arguments)
            elif tool_name == "send_follow_up_email":
                return await self._send_follow_up_email(arguments)
            else:
                return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolResult(success=False, error=str(e))
    

    async def _send_email(self, to_email: str, subject: str, html_content: str, text_content: str) -> ToolResult:
        """Send email using configured provider (SendGrid or SMTP)."""
        if self._sendgrid_api_key:
            return await self._send_via_sendgrid(to_email, subject, html_content, text_content)
        elif self._smtp_host:
            return await self._send_via_smtp(to_email, subject, html_content, text_content)
        else:
            # Mock mode for development
            logger.warning(f"Email not configured. Would send to {to_email}: {subject}")
            return ToolResult(success=True, data={
                "sent": False,
                "mode": "mock",
                "to": to_email,
                "subject": subject,
                "message": "Email not configured - logged for development"
            })
    
    async def _send_via_sendgrid(self, to_email: str, subject: str, html_content: str, text_content: str) -> ToolResult:
        """Send email via SendGrid API."""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            
            message = Mail(
                from_email=(self._from_email, self._from_name),
                to_emails=to_email,
                subject=subject,
                html_content=html_content,
                plain_text_content=text_content
            )
            
            sg = SendGridAPIClient(self._sendgrid_api_key)
            response = sg.send(message)
            
            return ToolResult(success=True, data={
                "sent": True,
                "provider": "sendgrid",
                "to": to_email,
                "status_code": response.status_code
            })
        except ImportError:
            return ToolResult(success=False, error="SendGrid library not installed. Run: pip install sendgrid")
        except Exception as e:
            return ToolResult(success=False, error=f"SendGrid error: {str(e)}")
    
    async def _send_via_smtp(self, to_email: str, subject: str, html_content: str, text_content: str) -> ToolResult:
        """Send email via SMTP."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self._from_name} <{self._from_email}>"
            msg["To"] = to_email
            
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))
            
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.starttls()
                if self._smtp_user and self._smtp_password:
                    server.login(self._smtp_user, self._smtp_password)
                server.send_message(msg)
            
            return ToolResult(success=True, data={
                "sent": True,
                "provider": "smtp",
                "to": to_email
            })
        except Exception as e:
            return ToolResult(success=False, error=f"SMTP error: {str(e)}")

    async def _send_kyc_approved_email(self, args: Dict[str, Any]) -> ToolResult:
        """Send KYC approval notification."""
        customer_name = args["customer_name"]
        policy_type = args.get("policy_type", "insurance")
        next_steps = args.get("next_steps", "Our team will contact you shortly with policy details.")
        
        subject = f"Welcome! Your {policy_type} Application Has Been Approved"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #28a745;">Congratulations, {customer_name}!</h2>
            <p>We are pleased to inform you that your KYC verification has been <strong>approved</strong>.</p>
            <p>Your application for <strong>{policy_type}</strong> has successfully passed all verification checks.</p>
            <h3>Next Steps:</h3>
            <p>{next_steps}</p>
            <p>Thank you for choosing us for your insurance needs.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">This is an automated message. Please do not reply directly to this email.</p>
        </body>
        </html>
        """
        
        text_content = f"""
        Congratulations, {customer_name}!
        
        We are pleased to inform you that your KYC verification has been approved.
        Your application for {policy_type} has successfully passed all verification checks.
        
        Next Steps:
        {next_steps}
        
        Thank you for choosing us for your insurance needs.
        """
        
        return await self._send_email(args["to_email"], subject, html_content, text_content)
    
    async def _send_kyc_pending_email(self, args: Dict[str, Any]) -> ToolResult:
        """Send KYC pending notification."""
        customer_name = args["customer_name"]
        reason = args.get("reason", "Your application is under review.")
        estimated_time = args.get("estimated_time", "1-2 business days")
        
        subject = "Your Insurance Application is Under Review"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #ffc107;">Application Under Review</h2>
            <p>Dear {customer_name},</p>
            <p>Your KYC verification is currently <strong>pending review</strong>.</p>
            <p><strong>Reason:</strong> {reason}</p>
            <p><strong>Estimated completion time:</strong> {estimated_time}</p>
            <p>We will notify you as soon as the review is complete. No action is required from you at this time.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">This is an automated message. Please do not reply directly to this email.</p>
        </body>
        </html>
        """
        
        text_content = f"""
        Dear {customer_name},
        
        Your KYC verification is currently pending review.
        
        Reason: {reason}
        Estimated completion time: {estimated_time}
        
        We will notify you as soon as the review is complete.
        """
        
        return await self._send_email(args["to_email"], subject, html_content, text_content)
    
    async def _send_kyc_rejected_email(self, args: Dict[str, Any]) -> ToolResult:
        """Send KYC rejection notification."""
        customer_name = args["customer_name"]
        rejection_reasons = args["rejection_reasons"]
        appeal_instructions = args.get("appeal_instructions", "Please contact our support team for more information.")
        
        reasons_html = "".join([f"<li>{r}</li>" for r in rejection_reasons])
        reasons_text = "\n".join([f"- {r}" for r in rejection_reasons])
        
        subject = "Update on Your Insurance Application"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #dc3545;">Application Update</h2>
            <p>Dear {customer_name},</p>
            <p>We regret to inform you that we are unable to approve your application at this time.</p>
            <h3>Reasons:</h3>
            <ul>{reasons_html}</ul>
            <h3>What You Can Do:</h3>
            <p>{appeal_instructions}</p>
            <p>We appreciate your interest and hope to serve you in the future.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">This is an automated message. Please do not reply directly to this email.</p>
        </body>
        </html>
        """
        
        text_content = f"""
        Dear {customer_name},
        
        We regret to inform you that we are unable to approve your application at this time.
        
        Reasons:
        {reasons_text}
        
        What You Can Do:
        {appeal_instructions}
        """
        
        return await self._send_email(args["to_email"], subject, html_content, text_content)
    
    async def _send_follow_up_email(self, args: Dict[str, Any]) -> ToolResult:
        """Send request for additional documents."""
        customer_name = args["customer_name"]
        required_documents = args["required_documents"]
        deadline = args.get("deadline", "within 7 business days")
        upload_link = args.get("upload_link", "Please reply to this email with the required documents.")
        
        docs_html = "".join([f"<li>{d}</li>" for d in required_documents])
        docs_text = "\n".join([f"- {d}" for d in required_documents])
        
        subject = "Action Required: Additional Documents Needed"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #17a2b8;">Additional Documents Required</h2>
            <p>Dear {customer_name},</p>
            <p>To complete your KYC verification, we need the following additional documents:</p>
            <ul>{docs_html}</ul>
            <p><strong>Deadline:</strong> {deadline}</p>
            <p><strong>How to submit:</strong> {upload_link}</p>
            <p>If you have any questions, please contact our support team.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">This is an automated message. Please do not reply directly to this email.</p>
        </body>
        </html>
        """
        
        text_content = f"""
        Dear {customer_name},
        
        To complete your KYC verification, we need the following additional documents:
        {docs_text}
        
        Deadline: {deadline}
        
        How to submit: {upload_link}
        """
        
        return await self._send_email(args["to_email"], subject, html_content, text_content)


# FastAPI app exposing HTTP MCP endpoints (defined after class)
app = create_mcp_http_app(EmailMCPServer())
