"""Email and in-system notification service.
Safely dispatches student-facing emails post-transaction without rolling back core assignments.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.complaint import Complaint
from app.models.enums import DeliveryStatus, NotificationType
from app.models.notification import EmailNotification
from app.utils.time import utcnow

logger = logging.getLogger("complaint_agent.notifications")


class NotificationService:
    @staticmethod
    def send_assignment_notification(
        db: Session,
        complaint: Complaint,
        student_facing_response: Optional[str] = None,
        assigned_department: Optional[str] = None,
    ) -> EmailNotification:
        """Create and queue/send an assignment update email to the student."""
        settings = get_settings()
        recipient_email = (complaint.email or "").strip()
        recipient_name = complaint.student_name

        subject = f"[University Portal] Update on Complaint {complaint.complaint_number}"
        
        dept_info = f"Your complaint has been assigned to the **{assigned_department}** department for review." if assigned_department else "Your complaint has been reviewed and assigned for formal processing."
        custom_response = f"\n\nOfficial Note from Administration:\n\"{student_facing_response}\"" if student_facing_response and student_facing_response.strip() else ""

        body = (
            f"Dear {recipient_name},\n\n"
            f"This is an automated update regarding your complaint reference #{complaint.complaint_number} (\"{complaint.title}\").\n\n"
            f"Status: {complaint.status}\n"
            f"{dept_info}"
            f"{custom_response}\n\n"
            f"Next Step:\n"
            f"The assigned department is reviewing the details. You can check the current progress anytime on your Student Portal dashboard under 'My Complaints'.\n\n"
            f"Regards,\n"
            f"Campus Complaint Administration\n"
            f"University Portal"
        )

        notif = EmailNotification(
            recipient_email=recipient_email or "no-email-provided@portal",
            recipient_name=recipient_name,
            related_complaint_id=complaint.id,
            notification_type=NotificationType.COMPLAINT_ASSIGNED.value,
            subject=subject,
            body_preview=body[:500],
            delivery_status=DeliveryStatus.QUEUED.value,
            created_at=utcnow(),
        )
        db.add(notif)
        db.commit()

        # Attempt SMTP delivery if enabled
        if settings.smtp_enabled and recipient_email and "@" in recipient_email:
            try:
                NotificationService._deliver_smtp(
                    host=settings.smtp_host,
                    port=settings.smtp_port,
                    user=settings.smtp_user,
                    password=settings.smtp_password,
                    from_addr=settings.smtp_from_email,
                    to_addr=recipient_email,
                    subject=subject,
                    body=body,
                    use_tls=settings.smtp_use_tls,
                )
                notif.delivery_status = DeliveryStatus.SENT.value
                notif.sent_at = utcnow()
                db.commit()
                logger.info("Assignment email sent to %s for complaint %s", recipient_email, complaint.complaint_number)
            except Exception as e:
                notif.delivery_status = DeliveryStatus.FAILED.value
                notif.error_message = str(e)[:400]
                db.commit()
                logger.warning("SMTP delivery failed for complaint %s: %s", complaint.complaint_number, e)
        else:
            # Marked as queued / recorded in environment without active external SMTP
            notif.delivery_status = DeliveryStatus.SENT.value
            notif.sent_at = utcnow()
            db.commit()
            logger.info("Notification logged for student %s (SMTP simulation active)", recipient_email)

        return notif

    @staticmethod
    def send_resolution_pending_notification(db: Session, complaint: Complaint) -> EmailNotification:
        """Notify student that complaint is marked resolved and awaiting their confirmation."""
        settings = get_settings()
        recipient_email = (complaint.email or "").strip()
        recipient_name = complaint.student_name

        subject = f"[Action Required] Resolution Confirmation for Complaint {complaint.complaint_number}"
        body = (
            f"Dear {recipient_name},\n\n"
            f"The administration has marked your complaint #{complaint.complaint_number} (\"{complaint.title}\") as Resolved.\n\n"
            f"Please log in to your Student Portal -> My Complaints to review the resolution and verify whether your issue has been satisfactorily resolved:\n"
            f"1. Select 'Issue Resolved' to confirm closure.\n"
            f"2. Select 'Issue Not Resolved' if the problem persists so our team can immediately take further action.\n\n"
            f"Regards,\n"
            f"Campus Complaint Administration"
        )

        notif = EmailNotification(
            recipient_email=recipient_email or "no-email@portal",
            recipient_name=recipient_name,
            related_complaint_id=complaint.id,
            notification_type=NotificationType.RESOLUTION_AWAITING_CONFIRMATION.value,
            subject=subject,
            body_preview=body[:500],
            delivery_status=DeliveryStatus.SENT.value,
            sent_at=utcnow(),
        )
        db.add(notif)
        db.commit()
        return notif

    @staticmethod
    def send_unresolved_feedback_notification(
        db: Session,
        complaint: Complaint,
        feedback: Any,
    ) -> EmailNotification:
        """Notify the administrator responsible that a student reported an issue as unresolved."""
        settings = get_settings()
        recipient_email = "admin@example.edu"
        from app.models.user import User
        from app.models.enums import UserRole
        campus_admin = db.query(User).filter(
            User.role == UserRole.ADMIN.value,
            User.campus == complaint.originating_campus
        ).first()
        if campus_admin and campus_admin.email:
            recipient_email = campus_admin.email

        student_display = "[Confidential Student]" if complaint.is_confidential else complaint.student_name
        remarks = getattr(feedback, "feedback_remarks", "") or "No remarks provided"
        subject = f"[Action Required] Unresolved Issue Reported on Complaint {complaint.complaint_number}"
        body = (
            f"Dear Administrator,\n\n"
            f"Student {student_display} has verified Complaint #{complaint.complaint_number} (\"{complaint.title}\") "
            f"and reported that the issue remains UNRESOLVED.\n\n"
            f"Student Explanatory Remarks:\n"
            f"\"{remarks}\"\n\n"
            f"The complaint has been reopened and placed in PENDING_ADMIN_REVIEW queue for further action.\n\n"
            f"Regards,\n"
            f"University Grievance Monitoring System"
        )

        notif = EmailNotification(
            recipient_email=recipient_email,
            recipient_name="Campus Administrator",
            related_complaint_id=complaint.id,
            notification_type=NotificationType.COMPLAINT_REOPENED.value,
            subject=subject,
            body_preview=body[:500],
            delivery_status=DeliveryStatus.SENT.value,
            sent_at=utcnow(),
        )
        db.add(notif)
        db.commit()
        logger.info("Administrator notified regarding unresolved complaint %s to %s", complaint.complaint_number, recipient_email)
        return notif

    @staticmethod
    def _deliver_smtp(host, port, user, password, from_addr, to_addr, subject, body, use_tls=True):
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(host, port, timeout=10) as server:
            if use_tls:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(msg)
