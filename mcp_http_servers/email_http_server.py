"""
Email MCP HTTP Server

Exposes email notification tools over HTTP using FastMCP.
Run: python -m mcp_http_servers.email_http_server

Server listens on http://127.0.0.1:8003/mcp
"""
import os
from typing import Optional, List
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Create FastMCP server with JSON response mode
mcp = FastMCP("EmailKYC", json_response=True)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse
    return JSONResponse({
        "service": "Email MCP Server",
        "status": "healthy",
        "port": 8003
    })


# Global configuration
_sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
_smtp_host = os.getenv("SMTP_HOST")
_smtp_port = int(os.getenv("SMTP_PORT", "587"))
_smtp_user = os.getenv("SMTP_USER")
_smtp_password = os.getenv("SMTP_PASSWORD")
_from_email = os.getenv("EMAIL_FROM", "kyc@insurance.com")
_from_name = os.getenv("EMAIL_FROM_NAME", "Insurance KYC")


def send_email(to_email: str, subject: str, html_content: str, text_content: str) -> dict:
    """Send email using configured provider (SendGrid or SMTP)."""
    if _sendgrid_api_key:
        return send_via_sendgrid(to_email, subject, html_content, text_content)
    elif _smtp_host:
        return send_via_smtp(to_email, subject, html_content, text_content)
    else:
        # Mock mode for development
        return {
            "sent": False,
            "mode": "mock",
            "to": to_email,
            "subject": subject,
            "message": "Email not configured - logged for development"
        }


def send_via_sendgrid(to_email: str, subject: str, html_content: str, text_content: str) -> dict:
    """Send email via SendGrid API."""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email=(_from_email, _from_name),
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
            plain_text_content=text_content
        )
        
        sg = SendGridAPIClient(_sendgrid_api_key)
        response = sg.send(message)
        
        return {
            "sent": True,
            "provider": "sendgrid",
            "to": to_email,
            "status_code": response.status_code
        }
    except Exception as e:
        raise ValueError(f"SendGrid error: {str(e)}")


def send_via_smtp(to_email: str, subject: str, html_content: str, text_content: str) -> dict:
    """Send email via SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{_from_name} <{_from_email}>"
        msg["To"] = to_email
        
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        with smtplib.SMTP(_smtp_host, _smtp_port) as server:
            server.starttls()
            if _smtp_user and _smtp_password:
                server.login(_smtp_user, _smtp_password)
            server.send_message(msg)
        
        return {
            "sent": True,
            "provider": "smtp",
            "to": to_email
        }
    except Exception as e:
        raise ValueError(f"SMTP error: {str(e)}")


@mcp.tool()
def send_kyc_approved_email(
    to_email: str,
    customer_name: str,
    policy_type: str = "insurance",
    next_steps: str = "Our team will contact you shortly with policy details."
) -> dict:
    """Send KYC approval notification to customer."""
    subject = f"Welcome! Your {policy_type} Application Has Been Approved"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #28a745;">Congratulations, {customer_name}!</h2>
        <p>We are pleased to inform you that your KYC verification has been <strong>approved</strong>.</p>
        <p>Your application for <strong>{policy_type}</strong> has successfully passed all verification checks.</p>
        <h3>Next Steps:</h3>
        <p>{next_steps}</p>
        <p>Thank you for choosing us!</p>
        <p style="color: #666; font-size: 0.9em;">Best regards,<br>{_from_name}</p>
    </body>
    </html>
    """
    
    text_content = f"""
Congratulations, {customer_name}!

We are pleased to inform you that your KYC verification has been approved.
Your application for {policy_type} has successfully passed all verification checks.

Next Steps:
{next_steps}

Thank you for choosing us!

Best regards,
{_from_name}
    """
    
    return send_email(to_email, subject, html_content, text_content)


@mcp.tool()
def send_kyc_pending_email(
    to_email: str,
    customer_name: str,
    reason: str = "additional verification required",
    estimated_time: str = "2-3 business days"
) -> dict:
    """Send notification that KYC is pending review."""
    subject = "Your KYC Application is Under Review"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #ffc107;">Hello, {customer_name}</h2>
        <p>Your KYC application is currently <strong>under review</strong>.</p>
        <h3>Reason:</h3>
        <p>{reason}</p>
        <h3>Estimated Completion Time:</h3>
        <p>{estimated_time}</p>
        <p>We will notify you once the review is complete.</p>
        <p style="color: #666; font-size: 0.9em;">Best regards,<br>{_from_name}</p>
    </body>
    </html>
    """
    
    text_content = f"""
Hello, {customer_name}

Your KYC application is currently under review.

Reason: {reason}
Estimated Completion Time: {estimated_time}

We will notify you once the review is complete.

Best regards,
{_from_name}
    """
    
    return send_email(to_email, subject, html_content, text_content)


@mcp.tool()
def send_kyc_rejected_email(
    to_email: str,
    customer_name: str,
    rejection_reasons: List[str],
    appeal_instructions: str = "Please contact our support team for more information."
) -> dict:
    """Send KYC rejection notification with reasons."""
    subject = "KYC Application - Additional Information Required"
    
    reasons_html = "".join([f"<li>{reason}</li>" for reason in rejection_reasons])
    reasons_text = "\n".join([f"- {reason}" for reason in rejection_reasons])
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #dc3545;">Hello, {customer_name}</h2>
        <p>Unfortunately, we need additional information to complete your KYC verification.</p>
        <h3>Reasons:</h3>
        <ul>{reasons_html}</ul>
        <h3>What to do next:</h3>
        <p>{appeal_instructions}</p>
        <p style="color: #666; font-size: 0.9em;">Best regards,<br>{_from_name}</p>
    </body>
    </html>
    """
    
    text_content = f"""
Hello, {customer_name}

Unfortunately, we need additional information to complete your KYC verification.

Reasons:
{reasons_text}

What to do next:
{appeal_instructions}

Best regards,
{_from_name}
    """
    
    return send_email(to_email, subject, html_content, text_content)


@mcp.tool()
def send_follow_up_email(
    to_email: str,
    customer_name: str,
    required_documents: List[str],
    deadline: str = "7 days",
    upload_link: str = "https://portal.example.com/upload"
) -> dict:
    """Request additional documents from customer."""
    subject = "Action Required: Additional Documents Needed"
    
    docs_html = "".join([f"<li>{doc}</li>" for doc in required_documents])
    docs_text = "\n".join([f"- {doc}" for doc in required_documents])
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #007bff;">Hello, {customer_name}</h2>
        <p>To complete your KYC verification, we need the following documents:</p>
        <ul>{docs_html}</ul>
        <h3>Deadline:</h3>
        <p>{deadline}</p>
        <p><a href="{upload_link}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Upload Documents</a></p>
        <p style="color: #666; font-size: 0.9em;">Best regards,<br>{_from_name}</p>
    </body>
    </html>
    """
    
    text_content = f"""
Hello, {customer_name}

To complete your KYC verification, we need the following documents:
{docs_text}

Deadline: {deadline}

Upload your documents here: {upload_link}

Best regards,
{_from_name}
    """
    
    return send_email(to_email, subject, html_content, text_content)


if __name__ == "__main__":
    # Start the HTTP server on port 8003
    import uvicorn
    uvicorn.run(mcp.streamable_http_app, host="127.0.0.1", port=8003)
