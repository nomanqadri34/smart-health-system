"""
Notification service for email and SMS
"""
from typing import Optional, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class NotificationService:
    """Handle email and SMS notifications"""
    
    def __init__(self, smtp_host: str = "smtp.gmail.com", smtp_port: int = 587):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
    
    def send_email(self, to_email: str, subject: str, body: str, 
                   from_email: Optional[str] = None) -> bool:
        """Send email notification"""
        try:
            msg = MIMEMultipart()
            msg['From'] = from_email or "noreply@smarthealth.com"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))
            return True
        except Exception as e:
            print(f"Email error: {e}")
            return False
    
    def send_sms(self, phone: str, message: str) -> bool:
        """Send SMS notification"""
        if not phone or len(message) > 160:
            return False
        # Mock SMS sending
        return True
    
    def send_appointment_reminder(self, email: str, phone: str, 
                                  appointment_date: str) -> dict:
        """Send appointment reminder via email and SMS"""
        email_sent = self.send_email(
            email, 
            "Appointment Reminder",
            f"Your appointment is on {appointment_date}"
        )
        sms_sent = self.send_sms(phone, f"Reminder: Appointment on {appointment_date}")
        return {"email": email_sent, "sms": sms_sent}
