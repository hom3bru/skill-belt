# Welcome email

After a successful registration, send exactly one email to the new user's normalised address with the
subject `Welcome, <name>!`. Send nothing when the address is already taken.

Example: registering `"  Ada@Example.com "` with the name `Ada` sends one email to `ada@example.com`
with the subject `Welcome, Ada!`.

`register` already receives a `mailer`; production passes an `accounts.mailer.SmtpMailer`.
