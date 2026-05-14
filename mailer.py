#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이메일 발송 - HTML 파일을 첨부 or 인라인으로 발송"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os


class Mailer:
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username  = username
        self.password  = password

    def send(self, to_list: list[str], subject: str, html_path: str):
        """HTML 파일을 본문으로 발송 (인라인 HTML 메일)"""
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = self.username
        msg["To"]      = ", ".join(to_list)

        # HTML 본문
        part = MIMEText(html_content, "html", "utf-8")
        msg.attach(part)

        # 파일도 첨부
        with open(html_path, "rb") as f:
            attach = MIMEBase("application", "octet-stream")
            attach.set_payload(f.read())
        encoders.encode_base64(attach)
        attach.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(html_path)}"
        )
        msg.attach(attach)

        # 발송
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.username, to_list, msg.as_string())

        print(f"[MAIL] 발송 완료 → {to_list}")
