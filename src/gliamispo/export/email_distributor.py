"""
Email distribution service for call sheets (ODG).
Feature 4.1 — Distribuzione ODG via Email
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText


class EmailDistributor:
    """Sends call sheet PDFs via email with optional watermark."""

    def __init__(self, smtp_host: str, smtp_port: int, user: str, password: str):
        self._host = smtp_host
        self._port = smtp_port
        self._user = user
        self._pass = password

    def send_call_sheet(
        self,
        pdf_bytes: bytes,
        recipient_name: str,
        recipient_email: str,
        call_date: str,
    ) -> bool:
        """
        Send a call sheet PDF to a recipient.

        Args:
            pdf_bytes: The PDF content as bytes.
            recipient_name: Name of the recipient (for watermark and greeting).
            recipient_email: Email address to send to.
            call_date: Date string for the call sheet (e.g., "Day 5" or "2026-03-20").

        Returns:
            True if email was sent successfully, False otherwise.
        """
        pdf_wm = self._add_watermark(pdf_bytes, recipient_name)
        msg = MIMEMultipart()
        msg["From"] = self._user
        msg["To"] = recipient_email
        msg["Subject"] = f"Ordine del Giorno — {call_date}"
        msg.attach(
            MIMEText(
                f"Gentile {recipient_name},\n\n"
                f"In allegato l'ODG del {call_date}.\n\n"
                f"Buone riprese,\nProduction",
                "plain",
                "utf-8",
            )
        )
        att = MIMEApplication(pdf_wm, _subtype="pdf")
        att.add_header(
            "Content-Disposition",
            "attachment",
            filename=f"ODG_{call_date.replace(' ', '_')}.pdf",
        )
        msg.attach(att)
        ctx = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL(self._host, self._port, context=ctx) as s:
                s.login(self._user, self._pass)
                s.send_message(msg)
            return True
        except Exception as e:
            print(f"[Email] {e}")
            return False

    def _add_watermark(self, pdf_bytes: bytes, name: str) -> bytes:
        """
        Add a watermark to the PDF with the recipient's name.

        Currently a stub — can be implemented with pypdf for overlay watermark.
        """
        # TODO: Implement watermark overlay using pypdf
        return pdf_bytes
