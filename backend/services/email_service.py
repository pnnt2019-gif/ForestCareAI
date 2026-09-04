import os
import smtplib
from email.message import EmailMessage


class EmailService:
    def __init__(self):
        self.host = os.getenv("SMTP_HOST")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.username = os.getenv("SMTP_USERNAME")
        self.password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM") or self.username
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes"}
        self.allow_dev_reset_link = os.getenv("ALLOW_DEV_RESET_LINK", "false").strip().lower() in {"1", "true", "yes"}

    @property
    def is_configured(self):
        return bool(self.host and self.username and self.password)

    @property
    def is_dev_reset_enabled(self):
        return self.allow_dev_reset_link and not self.is_configured

    def send_reset_email(self, recipient_email, reset_link):
        if not self.is_configured:
            raise RuntimeError(
                "SMTP chưa được cấu hình. Vui lòng thiết lập SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD và SMTP_FROM."
            )

        subject = "Đặt lại mật khẩu ForestCare AI"
        body = (
            "Xin chào,\n\n"
            "Bạn đã yêu cầu đặt lại mật khẩu cho tài khoản ForestCare AI.\n"
            f"Nhấn vào liên kết sau để tiếp tục: {reset_link}\n\n"
            "Nếu bạn không yêu cầu thao tác này, vui lòng bỏ qua email này.\n\n"
            "Trân trọng,\n"
            "ForestCare AI"
        )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = recipient_email
        message.set_content(body)

        try:
            with smtplib.SMTP(self.host, self.port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(message)
            return True
        except Exception as exc:
            raise RuntimeError(f"Không thể gửi email: {exc}") from exc
