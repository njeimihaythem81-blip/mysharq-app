# SECURITY.md (owner checklist and incident response)

## Harden your accounts (not optional)
Whoever controls your GitHub account controls the whole system.
1. GitHub: strong unique password + **two-factor authentication** (authenticator app or passkey). Save the recovery codes offline. Add no collaborators you do not fully trust. Check Settings > Security log now and then.
2. Alerts: keep the ntfy topic name secret (it acts like a password). If it leaks, choose a new topic, subscribe to it, and change `NTFY_TOPIC` in Secrets. If you use Telegram, enable Two-Step Verification and never share the bot token.
3. The email account behind GitHub and Streamlit also needs two-factor authentication.
4. Store Manager password: unique, 12+ characters, saved in a password manager. Operators: unique passwords, never shared.
5. Keep tokens only in Streamlit Secrets. Never put them in files, chats or screenshots. Tokens expire every 90 days: renew them.

## If something may be exposed (token in a screenshot, lost phone, ex-employee...)
1. Sign in as **manager** > Account > change the password (this signs everyone out).
2. Streamlit > App > Settings > Secrets: change **SESSION_SECRET** (signs everyone out) and **SETUP_CODE**.
3. GitHub > Settings > Developer settings > Fine-grained tokens: **Delete** both tokens, create new ones, paste them into Secrets.
4. Change the ntfy topic (new random name) or the Gmail App Password (Google Account > Security > App passwords > delete and recreate) and update Secrets. Telegram users: @BotFather > `/revoke`.
5. Manager > Operators: deactivate or delete people who left; reset passwords if needed.
6. Manager > **Activity**: review who did what; also review the commit history of `mysharq-data`.
7. In Streamlit, **Reboot** the app.
8. If customer data may have been exposed, inform the affected customers as required by law.

## What the app already does
bcrypt-class password hashing (scrypt), progressive login throttling, signed expiring sessions, server-side role checks, password re-entry for dangerous actions,
rebuilding orders from the server catalogue (never trusting the browser), escaping of all user text, spreadsheet-formula neutralisation, image re-encoding
(removes GPS/EXIF), upload and import limits, order flood limits with a global circuit breaker, plain-text aggregated alerts without phone numbers,
audit trail in commit messages, no secrets in code or logs, no stack traces shown to users.
