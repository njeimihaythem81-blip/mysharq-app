# MY SHARQ RFQ's

Mobile-first Request-for-Quotation store for Schneider Electric products. No prices, no payments, no customer accounts.
Stack: Streamlit Community Cloud + GitHub (as the database) + ntfy / e-mail alerts (Telegram optional). 100% free.

> **Read this first (honest status).** The business logic (`core/`) is covered by 22 automated tests that pass
> (phone rules, search, import, orders, claiming, export/purge, points, sessions, uploads, formula/HTML injection...).
> The Streamlit screens (`ui/`, `app.py`) were written and statically checked, but **could not be executed in the build
> environment** (no internet to install Streamlit). Expect to run the smoke test in section 8 and send me any error text
> you see; small UI fixes are normal for a first deployment.

## 1. What you need (all free)
A GitHub account, a Streamlit Community Cloud account (sign in with GitHub), and a phone with the ntfy app.
Turn on **two-factor authentication** on GitHub first (see SECURITY.md).

## 2. Create three GitHub repositories
GitHub > **+** (top right) > **New repository**. For each one tick **Add a README file** (the app needs the repo to be non-empty).
| Name | Visibility | Contains |
|---|---|---|
| `mysharq-app` | **Public** (recommended: it contains no secrets, and it makes the app publicly viewable) | this project's code |
| `mysharq-images` | **Public** | product photos, backgrounds, logo |
| `mysharq-data` | **Private** | orders, items, users (personal data) |

## 3. Upload the code
Open `mysharq-app` > **Add file** > **Upload files**. Unzip this project on a computer, drag **all files and folders**
(including the hidden `.streamlit` folder) into the page, then **Commit changes**.
(Phone users: use a computer for this one step; GitHub's phone site cannot upload folders.)

## 4. Create the two access tokens
GitHub > profile picture > **Settings** > **Developer settings** > **Personal access tokens** > **Fine-grained tokens** > **Generate new token**.
Make **two** tokens:
1. Name `mysharq-data-token`. Expiration **90 days**. Repository access > **Only select repositories** > `mysharq-data`.
   Permissions > Repository permissions > **Contents: Read and write**. Generate and copy it somewhere private.
2. Name `mysharq-images-token`. Same settings but select only `mysharq-images`.

Put a reminder in your calendar to renew them every 90 days (create new tokens, paste them into Secrets, delete the old ones).
**Never post a token in a chat, screenshot or file.**

## 5. Staff alerts (free, instant): ntfy (recommended), e-mail, Telegram (optional)
Use at least one. All are optional to the app: orders are never lost if alerts fail.
**ntfy (no account, 5 minutes):**
1. Invent a private topic name: `mysharq-` followed by 20 random letters and digits, for example `mysharq-k7q2x9m4tw8r3p5zv6nb`. It works like a password: anyone who knows it can read the alerts, so never share it.
2. Install the **ntfy** app (Play Store / App Store), open it, tap **+** (Subscribe to topic), type your topic name, **Subscribe**. On a computer you can also open `https://ntfy.sh/app` and subscribe there.
3. Test: open `https://ntfy.sh/YOUR_TOPIC/publish?message=test` in a browser; the alert arrives within a second or two.
4. Put `NTFY_TOPIC = "your-topic"` in Secrets (section 6).
**E-mail (optional backup):** Google Account > Security > turn on 2-Step Verification > search "App passwords" > create one named `mysharq` > copy the 16 characters. Secrets: `EMAIL_USER` (your Gmail), `EMAIL_APP_PASSWORD`, `EMAIL_TO`.
**Telegram (optional):** still supported via `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_IDS` if it works for you.
Alerts contain only the order number, customer name and number of lines, never the phone number.

## 6. Deploy on Streamlit
1. Go to share.streamlit.io > **Continue with GitHub** > **Create app** > "Deploy a public app from GitHub".
2. Repository `mysharq-app`, Branch `main`, Main file path `app.py`. If you made the repo private, after deploying open the app's **Share** menu and set it to public, otherwise customers cannot open it.
3. **Advanced settings** > Python **3.12** > paste the Secrets below (replace every value), then **Deploy**.
```
GITHUB_TOKEN_DATA   = "github_pat_..."
GITHUB_TOKEN_IMAGES = "github_pat_..."
GITHUB_OWNER  = "your-github-username"
IMAGES_REPO   = "mysharq-images"
DATA_REPO     = "mysharq-data"
BRANCH        = "main"
NTFY_TOPIC = "mysharq-k7q2x9m4tw8r3p5zv6nb"
SESSION_SECRET = "<at least 32 random characters>"
SETUP_CODE     = "<a random code only you know>"
STAFF_KEY      = "<20+ random letters and digits: the secret of the staff link>"
APP_URL        = "https://your-app.streamlit.app"
```
Later edits: App > **Settings** > **Secrets**. The app refuses to start while any secret is missing or still a placeholder.

## 7. First run
1. Open your **secret staff link**: `https://your-app.streamlit.app/?k=YOUR_STAFF_KEY`. (There is no Staff button on the public page.) Because no Store Manager exists, you see "First-time setup".
2. Enter the **SETUP_CODE**, choose a strong password (12+ chars). Sign in as **manager**.
3. **Settings**: store name, support number (shown in the footer as "Support:"), working hours, upload **logo**, **phone background** and **desktop background**, press **Send test alert**.
4. **Items**: download the Excel template, fill it with your items (columns: Section, Branch, Sub-Branch, Item No, Description, Quantity), upload, **Check file**, read the report, **Save import**.
5. **Operators**: add each Operator with a temporary password (they must change it at first login).
6. Optional reminders: in `mysharq-data` > Add file > Create new file, name it `.github/workflows/reminder.yml`, paste the content of `data_repo_files/.github/workflows/reminder.yml`.
   Then `mysharq-data` > Settings > Secrets and variables > Actions > add `NTFY_TOPIC` (and/or the three `EMAIL_*` secrets). (GitHub pauses scheduled workflows after 60 days of no repo activity.)

Recovery if you forget the manager password: in `mysharq-data` delete `manager.json`; the setup screen returns and again needs `SETUP_CODE`.

## 7b. What is new in v2
- **Staff entry:** only through the secret link above. Save it in your browser favourites / phone home screen. If it leaks, change `STAFF_KEY` in Secrets.
- **Sections:** customers see image tiles (image + name; the whole tile opens the level) for every level: section, branch, sub-branch. No item counts.
- **Images for all levels:** Manager > **Categories**: upload one image for the selected level, or one **ZIP** for all levels. Name files `SECTION.jpg`, `SECTION__BRANCH.jpg`, `SECTION__BRANCH__SUB.jpg` (use the Excel list of file names the app gives you).
- **Items:** Manager > **Items**: Import (with a summary before saving, and an automatic backup), Add item, Edit / delete, and **Excel** (download the newest file with sheets Items + Categories).
- **Rule:** the app is the master. Download the newest Excel from the app, edit it, upload it with **Merge**.
- **Backups:** Manager > Backup > Automatic backups (newest 10, restorable).
- **Live item-number search** (customer page, Photos screen, Manager > Items > Edit/delete): type characters and a list of up to 6 matching items appears and updates with every key; arrows scroll the rest. Items whose number starts with the typed characters come first, then items that contain them.

## 8. Smoke test (10 minutes)
1. Customer: open the app, search `lc1 d09-m7`, add to basket, send with name + `0912345678`. See the confirmation and download the PDF and Excel.
2. An alert arrives on your phone (name and number of lines only, never the phone number).
3. Operator login: the order is under **Orders**; open it; it disappears for other Operators; it is in **My Orders**; **Reply on WhatsApp** opens a chat.
4. **Photos**: take a photo of an item; it earns +1 point; after about a minute customers see it.
5. Manager: **Export** > Generate > Download > check the file > enter password > **Delete exported orders**.
Anything unexpected: copy the red error text (never tokens) and send it to your assistant.

## 9. Routines
- Daily: check **Orders**; reply to customers on WhatsApp.
- Every ~9 days (or when the reminder arrives): **Export**, check the file, save it to Google Drive, then delete.
- Every 90 days: renew the two GitHub tokens.

## 10. Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| "The store is not configured yet" | A secret is missing/placeholder | Fix Secrets (names are listed) |
| "GitHub token rejected (401)" | Token expired/wrong | Create new token, update Secrets |
| "Git Repository is empty" | A repo has no README | Add a README to that repo |
| No alert arrives | Wrong topic name, or the app is not subscribed | Re-subscribe in the ntfy app, use the browser test in section 5 |
| New photo not visible | CDN delay | Wait 1 to 2 minutes |
| First visit slow | Streamlit put the idle app to sleep | Wait a few seconds; optional free UptimeRobot ping every 5 min (reduces, may not prevent) |
| "Service busy" | More than 60 orders/hour (abuse breaker) | Settings > max orders per hour |

## 11. Assumptions and known limits
- **Password hashing uses scrypt from the Python standard library** (strong, memory-hard, no extra package) instead of bcrypt.
- The "common passwords" list is short (about 60 entries) plus length/repetition rules. Extend `core/common_passwords.txt` if you wish.
- Phone numbers are checked for **format only** (Libyan mobile 91/92/93/94), not ownership. No SMS/OTP.
- Basket saving in the browser is best effort. Customers' names are stored only in the private repo; deleted orders remain in that repo's Git history.
- Streamlit apps sleep when idle; many simultaneous customers on the free tier may slow it. Rate limits (per session, IP, phone, global) are in memory and reset when the app restarts; IP is best-effort.
- Streamlit cannot set HttpOnly cookies; sessions are short-lived and all user text is escaped.
- Using Schneider Electric names and images requires you to hold the right to do so; do not claim "authorised distributor" unless true.

## 12. Developer notes
`core/` (no Streamlit dependency): `ghstore` (GitHub API), `store` (data layer), `catalog`, `orders`, `auth`, `security`, `validators`, `imaging`, `docs`, `telegram`.
`ui/`: `customer`, `staff`, `staff_manager`, `theme`, `common`. Run tests: `python -m unittest tests.test_core`.
