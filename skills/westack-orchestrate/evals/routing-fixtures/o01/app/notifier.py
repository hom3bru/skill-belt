def send_digest(users, mailer):
    for user in users:
        mailer(user["email"], "Your digest")
