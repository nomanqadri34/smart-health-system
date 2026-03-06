"""
Email service for sending OTP emails via Gmail SMTP
"""
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# Gmail SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
GMAIL_USER = "shoaibahmed12222234@gmail.com"
GMAIL_APP_PASSWORD = "itdnhcopipjopnus"  # App password without spaces

def generate_otp():
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

def send_otp_email(to_email: str, otp: str, purpose: str = "verification"):
    """Send OTP email via Gmail SMTP"""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"Smart Health <{GMAIL_USER}>"
        msg['To'] = to_email
        
        if purpose == "verification":
            msg['Subject'] = "🔐 Verify Your Smart Health Account"
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; background: #0f172a; color: white; padding: 40px;">
                <div style="max-width: 500px; margin: 0 auto; background: rgba(255,255,255,0.05); padding: 40px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);">
                    <h1 style="color: #60a5fa; margin-bottom: 20px;">Smart Health</h1>
                    <h2>Verify Your Email</h2>
                    <p>Your verification code is:</p>
                    <div style="background: linear-gradient(90deg, #3b82f6, #10b981); padding: 20px; border-radius: 12px; text-align: center; margin: 20px 0;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px;">{otp}</span>
                    </div>
                    <p style="color: #94a3b8;">This code expires in 10 minutes.</p>
                    <p style="color: #94a3b8; font-size: 12px; margin-top: 30px;">If you didn't request this, please ignore this email.</p>
                </div>
            </body>
            </html>
            """
        else:  # Password reset
            msg['Subject'] = "🔑 Reset Your Smart Health Password"
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; background: #0f172a; color: white; padding: 40px;">
                <div style="max-width: 500px; margin: 0 auto; background: rgba(255,255,255,0.05); padding: 40px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);">
                    <h1 style="color: #60a5fa; margin-bottom: 20px;">Smart Health</h1>
                    <h2>Password Reset</h2>
                    <p>Your password reset code is:</p>
                    <div style="background: linear-gradient(90deg, #ef4444, #f97316); padding: 20px; border-radius: 12px; text-align: center; margin: 20px 0;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px;">{otp}</span>
                    </div>
                    <p style="color: #94a3b8;">This code expires in 10 minutes.</p>
                    <p style="color: #94a3b8; font-size: 12px; margin-top: 30px;">If you didn't request this, please ignore this email.</p>
                </div>
            </body>
            </html>
            """
        
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ OTP email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        return False
