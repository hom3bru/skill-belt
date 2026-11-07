# tdd-fixture: the production mailer talks to a real SMTP server
import smtplib


class SmtpMailer:
    def __init__(self, host="smtp.internal.example", port=587):
        self.host, self.port = host, port

    def send(self, to, subject, body):
        with smtplib.SMTP(self.host, self.port, timeout=10) as server:
            server.sendmail("hello@example.com", [to], "Subject: %s\n\n%s" % (subject, body))
