"""
Test SendGrid Email Sending
Uses SendGrid's Python Library: https://github.com/sendgrid/sendgrid-python
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Get API key from environment
api_key = os.environ.get('SENDGRID_API_KEY')
print(f"Using SendGrid API key: SG.{'*' * 20}...{api_key[-4:] if api_key else 'NOT SET'}")

message = Mail(
    from_email='zvezdan.protic@capgemini.com',
    to_emails='zvezdanprotic@gmail.com',
    subject='Sending with Twilio SendGrid is Fun',
    html_content='<strong>and easy to do anywhere, even with Python</strong>')

try:
    sg = SendGridAPIClient(api_key)
    response = sg.send(message)
    print(f"\n✅ SUCCESS! Email sent.")
    print(f"Status Code: {response.status_code}")
    print(f"Body: {response.body}")
    print(f"Headers: {dict(response.headers)}")
except Exception as e:
    print(f"\n❌ ERROR: {e}")