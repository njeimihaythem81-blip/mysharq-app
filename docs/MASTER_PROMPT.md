# MASTER PROMPT: BUILD "MY SHARQ RFQ's" (STREAMLIT + GITHUB, 100% FREE)

## ROLE

You are a senior software engineer (Python, Streamlit, GitHub REST / Git Data API, performance, security) pair-working with an engineer specialised in AI-assisted development. Deliver the COMPLETE, production-ready source code of the system described below, plus beginner-proof deployment instructions.

The owner is NOT a programmer. He will copy your files into GitHub and click through setup screens. Therefore:

- Deliver EVERY file in full. No "...", no "rest of the code here", no stubs, no placeholders, no TODOs.
- Explain every manual step click by click, assuming zero technical knowledge.
- Do not ask me questions. Where something is unspecified, choose the simplest safe option and list it in the README under "Assumptions".
- Work in this order: (1) short file tree, (2) every file in dependency order, (3) README + deployment guide, (4) a self-review against the acceptance tests in section 21, fixing anything that fails. If the answer is too long for one message, continue in further messages without omitting anything.

---

## 0. ATTACHED FILES AND LANGUAGE RULE

### 0.1 Attached files (project pack zip)

| Path in the pack | Purpose |
|---|---|
| `02_ASSETS/bg-mobile.jpg` | Phone background (portrait 896x1200). Goes to the PUBLIC repo as `assets/bg-mobile.jpg`. |
| `02_ASSETS/bg-desktop.jpg` | Desktop background (landscape 1376x768). Goes to the PUBLIC repo as `assets/bg-desktop.jpg`. |
| `03_DATA/MY_SHARQ_Items_Template.xlsx` | Reference for the items import format (6 columns). Ship an equivalent template inside your project. All rows are SAMPLE data. |
| `03_DATA/categories_seed.json` | Seed of the category tree (matches section 13). You may restructure the JSON schema, but names and order must not change. |
| `04_REFERENCE/MY_SHARQ_Categories_Tree.pdf` | Visual tree of all sections, branches and sub-branches, for checking your work. |

The logo is NOT attached: the Store Manager uploads it inside the app. Nothing in the code may hard-code a logo.

### 0.2 Language rule: ENGLISH ONLY

- Every UI string, message, button, label, PDF text, Excel header, WhatsApp text, Telegram message, README, code comment and docstring is in English.
- No Arabic words appear anywhere in the interface or in generated documents.
- The only non-English content the system must handle is data entered by customers: names may be written in Arabic, and phone numbers may be typed with Arabic-Indic digits (see section 7). The PDF must render such names correctly (section 8).
- Keep all UI strings in ONE translations module (section 5) so another language can be added later without code changes.

---

## 1. PROJECT SUMMARY AND HARD CONSTRAINTS

Name: MY SHARQ RFQ's (the name is editable by the Store Manager).

Purpose: a mobile-first web app for REQUESTING QUOTATIONS (RFQ) on Schneider Electric electrical products (contactors, overload relays, breakers, MCCB/ACB, enclosures, drives, relays, busbars, transfer switches, etc.).

- NO prices anywhere. NO checkout. NO payment. NO customer accounts.
- A customer browses a catalogue like a selection guide, builds a basket of several items (each with its own quantity), and sends ONE order (RFQ).
- Staff then reply to the customer on WhatsApp with a price offer.

Customers are in Libya (mobile numbers +218). Staff work mainly from phones.

Hard constraints:

- 100% FREE stack: Streamlit Community Cloud (hosting) + GitHub (storage) + Telegram Bot API (staff alerts) + optional free UptimeRobot + free GitHub Actions. NO Supabase, Firebase, paid APIs, paid SMS/OTP, or custom domain.
- Python 3.11+, pinned versions in `requirements.txt`, must run within Streamlit Community Cloud limits (about 1 GB RAM).
- Catalogue size: 4,000 to 5,000 items. Staff: 5 to 10. Customers: many.

---

## 2. ROLES AND NAMING (IMPORTANT)

1. **Customer**: anonymous, no login.
2. **Operator** (staff). Naming rule:
   - INTERNAL screens (login page, menus, leaderboard, the manager's staff-management screen): "Operator".
   - EXTERNAL text (anything the customer sees, the customer PDF/Excel, the WhatsApp reply text, export files): "Sales Operator".
3. **Store Manager** (admin): a generic role, not a person's name. Login username is `manager`. UI label: "Store Manager". It is NOT called "admin" anywhere in the UI.

---

## 3. ARCHITECTURE AND STORAGE (GITHUB IS THE DATABASE)

The app (Streamlit) stores nothing locally because Streamlit Cloud wipes its disk on restart. All persistent data lives in two GitHub repositories, accessed through the GitHub REST/Git Data API with a fine-grained token kept in `st.secrets`.

### PUBLIC repo `mysharq-images` (images and look-and-feel assets)

```
images/thumb/<KEY>.jpg      thumbnail, about 300 px wide, about 15 to 25 KB
images/full/<KEY>.jpg       detail image, max 900 px on the long side, about 60 to 100 KB
assets/bg-mobile.jpg        phone background (portrait)
assets/bg-desktop.jpg       desktop background (landscape)
assets/logo.png             logo uploaded by the Store Manager
```

`<KEY>` = a safe file key derived deterministically from the Item No: uppercase; unsafe characters such as `/ \ space # ? %` encoded reversibly (for example `/` becomes `_2F_`); collision-free.

Customers load images directly from the CDN (jsDelivr) or raw GitHub, NEVER through the Streamlit server. New or replaced photos must appear for customers within about 1 to 2 minutes: avoid stale CDN caching (for example pin URLs to a commit SHA or use the jsDelivr purge API) and fall back to `raw.githubusercontent.com` if the CDN fails.

### PRIVATE repo `mysharq-data` (all business data and personal data)

```
items.json                       all items (see section 12)
categories.json                  category tree (see section 13), editable
settings.json                    store settings (see below)
manager.json                     Store Manager credentials (created at first run)
users.json                       Operators
orders/<ORDER_ID>.json           ONE FILE PER ORDER (no shared order file)
photolog/<KEY>.json              who uploaded the first photo of each item (points)
exports/pending.json             the single export batch awaiting deletion
exports/log.json                 export history (no customer data inside)
.github/workflows/reminder.yml   daily export reminder (section 15)
```

### Concurrency rules (several people write at the same time)

- Never rely on a single shared file for frequently written data.
- Every update uses the file's current SHA (optimistic concurrency); on conflict (409/422) re-read and retry, or report cleanly.
- Order creation uses create-only semantics; if the ID exists, generate a new one.
- Commit messages contain ONLY: actor username, action and object id (this is the audit trail, see 17.10). NEVER personal data, never secrets.
- Respect the GitHub API rate limit (5,000 requests/hour authenticated): cache reads, batch writes, and use a single commit via the Git Data API when writing or deleting several files (photo pair, batch deletion of orders).

### `settings.json` (all editable by the Store Manager in the app)

```json
{
  "store_name": "MY SHARQ RFQ's",
  "support_number": "",
  "working_hours_text": "",
  "export_reminder_days": 9,
  "timezone": "Africa/Tripoli",
  "overlay_opacity": 0.76,
  "whatsapp_reply_template": "<English default, see section 9>",
  "leaderboard_reset_at": null
}
```

`support_number` is stored normalised as `+2189XXXXXXXX`; `working_hours_text` is free text shown to customers after an order.

### Order file schema (`orders/<ORDER_ID>.json`)

```json
{
  "order_id": "MS-261012-K7QD",
  "created_at": "2026-10-12T09:15:00Z",
  "customer": {"name": "...", "phone": "+218912345678"},
  "project_name": "",
  "lines": [
    {"item_no": "LC1D09M7", "description": "...", "section": "TESYS",
     "branch": "CONTACTORS TO 60A 30KW", "sub_branch": "", "qty": 10, "note": ""}
  ],
  "opened_by": null, "opened_by_display": null, "opened_at": null,
  "notified": true
}
```

`order_id` = `MS-YYMMDD-` plus 4 random characters (no 0/O/1/I). Store timestamps in UTC; DISPLAY them in the configured timezone (Africa/Tripoli).

---

## 4. SECRETS AND CONFIGURATION (`st.secrets` ONLY, never in code or logs)

```
GITHUB_TOKEN_DATA     fine-grained token: Contents read/write on the PRIVATE data repo ONLY
GITHUB_TOKEN_IMAGES   fine-grained token: Contents read/write on the PUBLIC images repo ONLY
GITHUB_OWNER, IMAGES_REPO, DATA_REPO, BRANCH
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_IDS     comma-separated (a personal chat or a group, e.g. -100...)
SESSION_SECRET        at least 32 random bytes, used to sign session tokens
SETUP_CODE            one-time code required to create the Store Manager password (section 11)
APP_URL               public URL of the app
```

Least privilege: the two GitHub tokens are different, each limited to ONE repository, with an expiry of at most 90 days (see 17.7).

Provide a ready `secrets.toml` EXAMPLE (fake values) and the exact click path to paste real values into Streamlit Cloud > App > Settings > Secrets.

---

## 5. VISUAL DESIGN (keep the look of the owner's previous app)

Style: metallic chrome + neon green, industrial, professional, mobile-first.

- Headings: neon green `#39ff14`.
- Main panel: centred, max width about 720 px, glass effect (semi-transparent chrome, backdrop blur, thin light-metal border, rounded corners).
- BUTTONS: dark chrome gradient (about `#2b3236` to `#11161a`), 1 px metallic border, NEON-GREEN TEXT, soft neon glow on hover/press. Primary and secondary buttons share this look.
- Destructive buttons (remove item, delete, purge): same chrome, RED border and red text (`#ff3b3b`).
- Disabled buttons: dull grey, no glow.
- Do NOT use blue buttons (the previous app's royal blue is retired).
- BACKGROUNDS: ONE background per device class, covering the whole app:
  - `bg-mobile.jpg` (portrait, 896x1200) for viewports up to 768 px wide.
  - `bg-desktop.jpg` (landscape, 1376x768) above 768 px.
  - The browser must download only the one it needs (CSS media queries).
  - Full-viewport, cover, centred, fixed. A dark translucent overlay (default opacity 0.76, adjustable in settings) keeps text readable.
  - Replacing a background = uploading a new file under the same name. Provide BOTH ways: (a) upload in Store Manager settings (auto-compress mobile to under 300 KB, desktop to under 400 KB), (b) overwrite the file in GitHub.
- Logo: uploaded by the Store Manager (png/jpg, auto-resized to max height 120 px), shown at the top of pages and in the PDF header. No logo is hard-coded.
- Browser tab title and page header = `store_name` from settings.
- Hide Streamlit's default menu, footer and "Deploy" button.
- Touch targets at least 44 px; large readable text; no horizontal scroll.
- FOOTER on every page: the small label "Support:" followed by the support number (entered by the Store Manager) as a `wa.me` link. Hidden if no number is set.
- All UI strings live in ONE translations module (English only for now; see section 0.2).

---

## 6. CUSTOMER EXPERIENCE (no account)

### Navigation = selection guide

- Home: the sections as large cards (2 columns on phone) in tree order.
- Opening a level shows its child categories first, then the items that sit DIRECTLY at that level (items with an empty branch / empty sub-branch).
- Breadcrumb at the top; a Back button; a search bar on every page.
- Categories (and sections) containing no items are hidden from customers (visible to the Store Manager).
- Item lists: cards with thumbnail (placeholder with the section icon when no photo exists), Item No (bold), description, availability badge, quantity stepper (integer, 1 to 9,999, default 1), "Add to basket" button. Pagination: 24 items per page, Previous/Next.
- Item detail: larger image (lazy-loaded), Item No, description, availability.

### Search

Normalise both the query and the Item No by uppercasing and removing every non-alphanumeric character (spaces, dashes, dots, slashes), so "lc1 d09-m7" finds "LC1D09M7". Match order: exact > prefix > contains on Item No, then description words (all words must match, case-insensitive). Instant, served from an in-memory index.

Items can be requested regardless of availability; stock never limits the quantity.

### Basket

- Always reachable (sticky bar at the bottom with line count and a "View basket" button).
- In the basket the customer can change the quantity of each line, remove a line (red button), add an optional note per line (max 120 characters), and fill one optional "Project name" (max 80).
- Limit: max 150 lines per order.
- Persistence is best-effort: keep it in session state AND in the browser's localStorage (expiry 7 days) so a page refresh does not lose it; degrade gracefully if localStorage is unavailable.
- Anything restored from localStorage is UNTRUSTED (the customer can edit it): re-validate it exactly as described in 17.4.

### Sending

- When the customer presses "Send RFQ", ask ONLY: Name (required, 2 to 60 characters) and Phone (required). Nothing else.
- Anti-abuse: honeypot field, minimum form-fill time and the rate limits of 17.5. Duplicate phone numbers and duplicate orders are accepted silently (no warning, by owner decision) as long as the rate limits are respected.
- Show a privacy notice next to the send button: "Your name and phone number are used only to reply to your request. We never publish them."
- After a successful send show: the order number, a confirmation message, the Store Manager's working-hours text, and download buttons for the PDF and Excel copy. If saving fails: keep the basket, show a clear error, allow retry. NEVER lose an order silently.

---

## 7. PHONE VALIDATION (Libyan mobile only; validate FORMAT only)

- Accept mobile numbers only, prefixes 91, 92, 93, 94. No landlines.
- Accepted input styles: `091XXXXXXX`, `91XXXXXXX`, `+21891XXXXXXX`, `0021891XXXXXXX`, with spaces/dashes/dots/parentheses tolerated, and Arabic-Indic or Persian digits converted to Western digits.
- National number = 9 digits: `[91-94]` followed by 7 digits. Reference regex after cleaning: `^(?:\+?218|00218|0)?(9[1-4]\d{7})$`
- Store normalised as `+218` + 9 digits. Display as `+218 9X XXX XXXX`.
- Reject anything else with a clear message ("Invalid number") and do NOT send the order. No SMS/OTP verification (it would cost money); state this limit in the README.
- The same validator is used for the support number set by the Store Manager.

---

## 8. ORDER DOCUMENTS

On submit, create the order file, notify Telegram (section 14), then offer two documents generated IN MEMORY (not stored).

### A) PDF (A4, professional)

- Header: logo, store name, order number, date/time (store timezone).
- Customer name, customer phone, project name (if any).
- Table, one row per line: #, Photo (thumbnail, placeholder if missing), Item No, Description (+ line note if any), Quantity. Correct pagination for 200+ lines, repeated table header on each page, page numbers.
- Footer: store name, "Support:" + support number, working hours.
- MUST render Arabic correctly, because customer names may be Arabic: use `arabic-reshaper` + `python-bidi` and an embedded Arabic-capable font (for example Noto Naskh Arabic / Noto Sans) bundled in the repo. Latin text uses a clean embedded font.
- Fetch thumbnails in parallel with timeouts; on failure use a placeholder. Generate in under about 5 seconds for 100 lines.

### B) Excel (.xlsx), customer/order copy with EXACTLY THREE columns in this order

`Item No | Item Name | Quantity`

Header row, one item per row, Item No stored as text, no extra columns.

---

## 9. OPERATOR AND ORDER HANDLING

Operators log in with a username and a personal password given by the Store Manager. Menu: "Orders", "My Orders", "Photos", "Leaderboard" (own points).

### Order visibility and claiming

- "Orders" shows ONLY new, unopened orders (`opened_by` is null), oldest first, each with order ID, customer NAME, line count and waiting time. The customer's PHONE NUMBER is shown only after the Operator opens (claims) the order, and every claim is audit-logged (17.10).
- When any Operator opens an order, it is claimed atomically (conditional write using the file SHA). It disappears from every other Operator's "Orders" list and appears in that Operator's "My Orders". If two Operators open it at the same moment, only the first wins; the second sees "Already opened by <name>".
- "My Orders": orders this Operator opened, newest first.
- Operators CANNOT edit a customer's order (no editing of lines or quantities).
- The Store Manager always sees ALL orders, each with its state (New / Opened by <name> at <time>). Opening an order as Store Manager also removes it from the Operators' list (`opened_by` = "Store Manager").

### Order detail screen

Customer name, phone, project name, lines with thumbnails, and these buttons:

- "Reply on WhatsApp": opens `https://wa.me/<number without +>?text=<URL-encoded prefilled text>` using the editable template. Default:
  `Hello {customer_name}, this is {operator_name} (Sales Operator) from {store_name} regarding your order {order_id}.`
  (URL-encoding must handle Arabic customer names.)
- "Download PDF" and "Download Excel" for that order (same formats as section 8).

---

## 10. PHOTOS (Operators and Store Manager) AND POINTS

### Photos screen (designed for phones)

- Find an item by Item No (same normalised search) or browse the list "Items without photo" (paginated, searchable) with a progress counter ("1,240 of 4,850 items have photos").
- Take a photo with the phone camera (`st.camera_input`) OR choose from gallery/files (`st.file_uploader`); show a preview, then "Save".
- Processing: fix EXIF orientation, convert to RGB, strip EXIF, resize and compress to the two sizes (thumb about 300 px, full about 900 px), reject files over 15 MB or non-images. Commit both files in one commit.
- Replacing an existing photo is allowed.

### Points (motivation only, no money)

- +1 point for each photo uploaded for an item that had NO photo before. Replacing an existing photo gives no point.
- 1 star per 100 points (floor). The Operator sees points, stars, and how many points remain to the next star.
- Points are derived from `photolog/<KEY>.json` files created with CREATE-ONLY semantics, so there is no double counting and no write conflict.
- The Store Manager sees an "Operator Leaderboard" (all Operators, ranked) and can reset it (confirmation required). Reset only moves `leaderboard_reset_at`; logs are not deleted. The leaderboard can be exported.

---

## 11. STORE MANAGER FEATURES

### Authentication

First run (no Store Manager yet) is a TAKEOVER RISK, so it is protected:

- The "Create Store Manager password" screen requires the one-time `SETUP_CODE` from Secrets, plus a password of at least 12 characters with a confirm field. Wrong codes are throttled (17.1).
- The setup screen appears ONLY when GitHub answers a clear "404 file not found" for `manager.json`. Any other answer (timeout, 5xx, rate limit, auth error) must show a neutral error page and NEVER the setup screen (17.14).
- After creation the setup screen is permanently unavailable.
- Recovery (document it in the README and SECURITY.md): delete `manager.json` in the private repo; the setup screen then reappears and again requires `SETUP_CODE`. Recommend changing `SETUP_CODE` after setup.
- Never ship a default password.
- Sensitive Store Manager actions require password re-entry (17.2).

### Screens

1. **All Orders** (all, with filters New/Opened, search by order number, customer name, phone).
2. **Manage Operators**: add (username, display name, temporary password), deactivate/delete, reset password. Temporary and reset passwords must be changed by the Operator at first login. Deactivating or resetting invalidates that Operator's sessions.
3. **Items**: import Excel (section 12), see counts (items, with/without photos).
4. **Categories editor**: add, rename, delete, reorder sections / branches / sub-branches. Renaming updates the items that reference it (with confirmation); deleting a category that still has items is blocked unless the items are moved.
5. **Settings**: store name, logo upload, support number, working-hours text, export reminder days (default 9), WhatsApp reply template, background uploads, overlay opacity, timezone, and a "Send test Telegram message" button.
6. **Export and purge** (section 15).
7. **Operator Leaderboard** (section 10).
8. **Backup**: one button downloads a ZIP with items, categories, settings and the operator list WITHOUT password hashes or secrets.

---

## 12. ITEMS FILE (EXCEL IMPORT) AND AVAILABILITY

The Store Manager uploads an `.xlsx` (also accept `.csv`). The file has EXACTLY these 6 columns, in this order, header names as below (match case-insensitively and ignore extra spaces):

| # | Column |
|---|---|
| 1 | Section |
| 2 | Branch |
| 3 | Sub-Branch |
| 4 | Item No |
| 5 | Description |
| 6 | Quantity |

- Branch and Sub-Branch are left EMPTY when not applicable.
- Item No is the UNIQUE KEY (read as text, trimmed, never converted to a number or date; keep leading zeros).
- Quantity is an integer stock count. Empty or invalid = 0.

### Import flow with a REPORT BEFORE SAVING (nothing is saved until the manager confirms)

- Duplicate Item No in the file, empty Item No, empty Description, non-integer Quantity: listed by row number.
- Section/Branch/Sub-Branch values that do not match the category tree (case/space-insensitive): listed with closest suggestions; the manager chooses per name to map to an existing category, create it, or skip the rows. No item is lost silently.
- Two modes: "Merge" (default: add new Item Nos, update existing ones, leave absent ones untouched) and "Replace all" (delete items not in the file; needs explicit confirmation). Photos are never deleted by an import.
- Summary: added / updated / unchanged / skipped counts.
- Safety limits (17.6): max 10 MB, max 20,000 rows, `.xlsx` / `.csv` only, cell VALUES only (never formulas), macro files rejected.

### Availability (customer-facing)

- Quantity > 0 shows the green badge **"Available"**.
- Quantity = 0 or empty shows the amber badge **"Waiting"**.
- THE QUANTITY NUMBER MUST NEVER REACH THE CUSTOMER: compute the status on the server and never include the number in any customer-visible payload, widget, hidden field, table, or JSON.

The attached `MY_SHARQ_Items_Template.xlsx` shows the structure; ship an equivalent template in the repo.

---

## 13. CATEGORY TREE (seed `categories.json` EXACTLY as below, in this order)

Names are written exactly as the owner wants them (keep spelling, including "LUTSH" as written). The same tree is attached as `categories_seed.json` and as a PDF.

```
1  IDE BOXES
   - Small
   - Medium
   - Big
   - Cell
2  TESYS
   - CONTACTORS TO 60A 30KW
   - CONTACTORS D 37 TO 75KW
   - CONTACTORS F TO 400KW
   - CONTACTORS GIGA TO 400KW
   - CAP BANK CONTACTORS
   - OVERLOADS
       - LRD
       - LR9D
       - LR9F
   - PNEUMATIC TIMERS
   - AUXILIARIES FOR CT
3  ACTI 9
   - 1 POLE
   - 2 POLES
   - 3 POLES
   - 4 POLES
   - IDPN
   - FUSE HOLDERS
   - TIMERS
   - LUTSH RELAYS
   - LAMPS RAIL
   - DIN METERS
   - RESIDUAL CURRENT DEVICES
       - RCB
       - RCBO
       - RCBO 1P UK
       - VIGI NORMAL
       - VIGI DPN
   - AUXILIARYS
   - SILENT CONTACTORS
       - 1P CT
       - 2P CT
       - 3P CT
       - 4P CT
       - AUXILIARI CT
4  BUSBARS
   - MULTI STAGE
   - PIN BUSBAR
5  MCCBS
   - NSX 10 TO NSX 400
   - NSXM TO NSXM 160
   - NS 800 TO 2500
6  ACB (AIR CIRCUIT BREAKERS)
   - MTZ 1 TO 2500
   - MTZ2 TO 6300
   - ENW TO 3200
7  HARMONY
   - PUSH BUTTONS
   - SIGNAL LAMPS
   - SELECTORS
   - CAM SWITCHES
8  ALTIVAR
   - ALTIVAR 12
   - ALTIVAR 320
   - ALTIVAR 630
   - ALTIVAR 930
9  SOFT START
   - ATS 01
   - ATS 480
10 BUSBARS FR            (no branches)
11 EARTHING SYSTEMS
   - RAYCHEM
   - TUR
12 TRUNK                 (no branches)
13 ZELIO
   - PLC SMART RELAY
   - ZELIO PLUG IN RELAYS
   - ZELIO TIMERS
   - ZELIO PHASE PROTECTION
   - ZELIO LEVEL LIQUID
   - ZELIO TEMPERATURE CONTROL
14 MONITORS
   - MULTIMETERS
   - CAPACITOR BANK CONTROL
   - CURRENT TRANSFORMERS
15 ATS, ATCBs AND MTS
   - ATCBs AND MTS SCHNEIDER
       - MTS
       - ENCLOSED MTS
       - ENCLOSED MTS WITH BUSBAR
       - MOTOR MECHANISM
       - ATCBs SCHNEIDER
       - ENCLOSED ATCBs SCHNEIDER WITHOUT CONTROL NOR BUSBAR
       - ENCLOSED ATCBs SCHNEIDER WITH CONTROL
       - ENCLOSED ATCBs SCHNEIDER WITH CONTROL AND BUSBAR
   - TELERGON
       - MTS
       - ENCLOSED MTS
       - ENCLOSED MTS WITH BUSBAR
       - MOTOR MECHANISM
       - ATS
       - ENCLOSED ATS WITHOUT CONTROL NOR BUSBAR
       - ENCLOSED ATS WITH CONTROL
       - ENCLOSED ATS WITH CONTROL AND BUSBAR
```

The tree is editable later by the Store Manager (section 11).

---

## 14. TELEGRAM NOTIFICATIONS

- On every new order send ONE message to every ID in `TELEGRAM_CHAT_IDS`: order number, customer NAME, number of lines, and a link to the app. NEVER include the customer's phone number (Telegram is an external service).
- Send PLAIN TEXT only (no parse_mode), strip control characters and newlines from the name and truncate it to 40 characters. Aggregate bursts: at most one message per 30 seconds per chat; if several orders arrive in that window send one summary ("N new orders").
- 3 retries with backoff. If it still fails, the order is kept, `notified=false`, the Store Manager sees a red banner and a "Resend notifications" button. A Telegram failure must never block or lose an order.
- README: click-by-click creation of the bot with @BotFather, getting the token and the chat ID (personal chat and group), the required "Start" press, and a browser test URL.

---

## 15. EXPORT THEN PURGE (orders are never auto-deleted)

Orders stay stored until the Store Manager exports them and then confirms deletion. There is NO time-based deletion and NO deletion without a prior export.

1. The Store Manager taps "Export". The app lists ALL current orders, ALL PRE-SELECTED. He may untick any order he wants to keep.
2. The app generates ONE Excel file for the selected orders and saves a pending batch (`exports/pending.json`: batch id, timestamp, order IDs, file name, count). The orders themselves stay untouched. At most one pending batch exists; exporting again replaces it.
   - Excel columns (one row per item line; order fields repeat on every row): `Order ID | Date | Customer Name | Phone | Project Name | Item No | Item Name | Quantity | Line Note | Sales Operator` (who opened it).
   - Formatting: Arial, styled header, frozen header, autofilter, Item No as text.
   - File name: `MySharq_Orders_<YYYYMMDD-HHMM>_<batch>.xlsx`
3. The Store Manager downloads and checks the file (the file must be re-downloadable while the batch is pending).
4. "Delete exported orders" is enabled ONLY if a pending batch exists. It shows batch id, date and number of orders, asks for explicit confirmation, then deletes exactly the orders in that batch in a single commit. Orders that arrived after the export, or were unticked, are NOT deleted.
5. Log every export in `exports/log.json` (batch id, time, count, file name; no customer data).
6. Warn in the UI: "Save the exported file to your phone or Google Drive before deleting. Deletion is final." Document that deleted files remain in the private repo's Git history.

### Reminder

A Telegram message when there are orders older than `export_reminder_days` (default 9, editable) that are not in the pending batch, sent at most once a day, via:

- (a) a daily GitHub Actions workflow in the data repo (provide the YAML; it reads `settings.json` and the orders and uses repo secrets for the Telegram token and chat IDs), and
- (b) a banner on Store Manager login.

Mention in the README that GitHub pauses scheduled workflows after 60 days without repository activity.

---

## 16. PERFORMANCE REQUIREMENTS (the engineer must design for these)

- Streamlit reruns the script on every interaction: minimise cost. Use `st.cache_data` / `st.cache_resource` (items, categories, settings, search index, image listing; sensible TTLs and explicit invalidation after imports/uploads), callbacks (`on_click`/`on_change`) for basket actions, forms for multi-field input, `st.fragment` where available.
- Load `items.json` once per cache period (not per click). Paginate lists (24). Never render 5,000 items at once.
- Images only as thumbnails in lists, lazy-loaded, served by CDN, never proxied through the app.
- Inject the CSS once; backgrounds are CSS-driven and device-specific.
- Reads/writes to GitHub: timeouts, retries with exponential backoff, graceful messages on rate-limit or network errors; no blocking calls during rendering of customer pages beyond the cached data load.
- Target: customer page interactions feel instant after the first load. Document that Streamlit Community Cloud puts idle apps to sleep, that the first visit after sleep takes a few seconds, and give optional UptimeRobot instructions (free monitor hitting the app URL every 5 minutes) with the honest note that it reduces but may not fully prevent sleeping.

---

## 17. SECURITY AND PRIVACY (MANDATORY)

Treat the app as a hostile-internet-facing system. Customer pages are public, and the staff screens live in the same app, so EVERY staff function must be protected server-side. Hiding a button is never protection.

### 17.1 Authentication and passwords

- Hash passwords with bcrypt (cost 12 or higher) or argon2id; never store or log a clear password; use constant-time comparison. For an unknown username still run a dummy hash so timing does not reveal valid usernames.
- One generic error for every failed login: "Invalid username or password".
- Password policy: Store Manager at least 12 characters; Operators at least 8; reject the most common passwords (bundle a list of about 1,000) and a password equal to the username.
- Brute-force protection by PROGRESSIVE THROTTLING per (username, client IP when available): after 5 failures the wait doubles from 10 seconds up to 15 minutes. Do NOT permanently lock accounts, and make sure an attacker cannot lock the Store Manager out (a correct password after the wait always works). Also cap login attempts globally per minute. Counters live in process memory shared across sessions (`st.cache_resource`); document that they reset when the app restarts.
- Client IP is read from forwarded headers (`st.context.headers`) as BEST-EFFORT, untrusted information.

### 17.2 Sessions

- Session token = HMAC-SHA256 (key `SESSION_SECRET`) over user id, role, issued-at, expiry and `token_version`. Verify it on EVERY rerun and compare it with the current user record (active flag and `token_version`; cache users for at most 30 seconds).
- Expiry: Operators 7 days; Store Manager 8 hours. Logout bumps `token_version` for that user.
- Changing a password, deactivating a user, or rotating `SESSION_SECRET` logs the affected users out.
- If the token is kept in a browser cookie use Secure and SameSite=Strict and a short lifetime. Streamlit cannot set HttpOnly cookies, so XSS prevention (17.4) is essential; state this honestly in the README.
- Re-authentication (password re-entry) is required for: deleting exported orders, "Replace all" import, deleting or resetting Operators, downloading the backup, changing the support number, deleting categories.

### 17.3 Authorization (server-side, on every action)

- A single central guard (`require_role()`) is called by EVERY staff function and every page. No staff code path is reachable without a verified session. Prefer one entry point with `st.navigation` built only after authentication; if a `pages/` directory is used, every page file starts with the guard.
- The customer app never selects an order by URL or query parameter. The customer's PDF/Excel are generated only from the order just created in that customer's own session.
- Operators can read only unopened orders or orders they opened themselves, cannot reach Store Manager screens, and cannot read other Operators' orders. Claiming is enforced server-side (section 9).

### 17.4 Input validation, output encoding, injection

- Treat as UNTRUSTED: widget values, query parameters, localStorage contents, uploaded files, Excel cells, and JSON read back from GitHub.
- Re-validate everything on the server: customer name 2 to 60 characters (strip control, zero-width and bidi-override characters), project name at most 80, line note at most 120, quantity integer 1 to 9,999, at most 150 lines, total payload at most 100 KB.
- Rebuild order lines SERVER-SIDE from the catalogue by Item No: description, section, branch and sub-branch come from catalogue data, never from client-supplied values. Unknown Item Nos are rejected. A basket restored from localStorage is parsed as untrusted JSON with a size limit and every line is re-validated; invalid lines are dropped silently.
- NEVER render user-supplied or Excel-supplied text with `unsafe_allow_html=True`, and never put it unescaped into `st.markdown`: HTML-escape it and escape Markdown control characters. Item descriptions come from Excel and are untrusted. Never build CSS or JavaScript from user input. Custom components must be minimal and inlined or vetted and pinned; no third-party scripts and no external CDNs.
- Spreadsheet formula injection: when writing ANY user-controlled string into an .xlsx (customer name, project name, notes, descriptions) force string type and neutralise a leading `=`, `+`, `-`, `@`, tab or carriage return (prefix with a single quote or a space). This applies to the order Excel, the export Excel and the leaderboard export.
- PDF: XML-escape text for ReportLab paragraphs (`& < >`) and truncate very long strings.
- No `eval`, `exec`, `pickle`, unsafe `yaml.load` or shell commands with user data. JSON only. Build repository paths only from validated keys (whitelist `[A-Z0-9._-]` after encoding, no `..`).
- WhatsApp links are URL-encoded; Telegram text is plain (section 14).

### 17.5 Abuse, flooding and DoS (free-tier protection)

Every order is a GitHub write and a possible Telegram message, so a flood can exhaust the GitHub API quota (5,000 requests/hour) and break the app for everyone. Implement, with in-memory counters shared across sessions:

- per-session cooldown 30 seconds;
- per client IP (best effort) at most 5 orders per hour;
- per phone number at most 5 orders per hour (duplicates stay accepted below this limit);
- GLOBAL circuit breaker (default 60 orders per hour, configurable): beyond it show "Service busy, please try again later" and do NOT write to GitHub;
- minimum form-fill time 3 seconds, the honeypot, at most 150 lines and 100 KB per order;
- aggregated Telegram notifications (section 14);
- backoff plus a circuit breaker on GitHub 403/429 responses;
- customer browsing and search served from cached data only (no GitHub call per request).

Optional, documented but not required: Cloudflare Turnstile through a vetted component if abuse appears.

### 17.6 Uploads and imports

- Images: accept JPEG, PNG and WebP only (reject SVG, GIF and anything else), at most 15 MB; set Pillow `Image.MAX_IMAGE_PIXELS` (about 50 megapixels) against decompression bombs; verify with Pillow; ALWAYS re-encode (this strips EXIF, GPS and other metadata); output JPEG for photos and PNG for the logo; file names come ONLY from the Item No key or fixed names, never from the uploaded file name.
- Excel import: at most 10 MB and 20,000 rows, `.xlsx` or `.csv` only, openpyxl in read-only mode with cell VALUES (never formulas), `defusedxml` installed against XML bombs, reject macro files (`.xlsm`, `vbaProject`); CSV through the `csv` module with size limits.
- Backgrounds and logo use the same image pipeline with size caps.

### 17.7 Secrets and tokens (least privilege)

- Two separate fine-grained GitHub tokens: one for the private data repo only, one for the public images repo only; expiry at most 90 days. The README explains renewal and suggests a calendar reminder; the Store Manager screen shows a clear message when GitHub answers 401.
- Secrets only in `st.secrets`; never in code, config, logs, error messages, Git history or screenshots. `secrets.toml` is in `.gitignore`. The app refuses to start if a secret still looks like a placeholder. Redact secrets from any logged exception; never print raw GitHub API errors.
- The Telegram token and chat IDs live only in Secrets (and as GitHub repository secrets for the reminder workflow).
- GitHub Actions workflow: `permissions: contents: read`, third-party actions pinned to a full commit SHA, no echoing of secrets, triggered only by schedule and `workflow_dispatch`.

### 17.8 Streamlit configuration

In `.streamlit/config.toml`: `[server] enableXsrfProtection = true`, `enableCORS = true`, `maxUploadSize = 15`; `[client] showErrorDetails = "none"`, `toolbarMode = "minimal"`; `[browser] gatherUsageStats = false`. Customers never see stack traces: unexpected exceptions show a generic message with an error reference ID, and details go only to server logs without personal data or secrets.

### 17.9 Data protection and privacy

- Customer personal data (name, phone) lives only in the PRIVATE repo. It is not sent to Telegram, not logged, not placed in URLs, not placed in commit messages. PDF and Excel are generated on demand.
- Backup ZIP and exports contain personal data and require Store Manager re-authentication (17.2); the backup excludes password hashes and secrets.
- Stock quantities are never published to any public location.
- Document retention: orders are deleted only after export confirmation; deleted data remains in the private repo's Git history (explain how the owner can rewrite history if legally required).

### 17.10 Audit trail

Staff write actions leave an audit trail in commit messages (actor + action + object id, NO customer data): order claimed, photo uploaded or replaced, items imported, categories changed, settings changed, Operator created / deactivated / password reset, export, purge, backup. The Store Manager gets an "Activity" screen listing the latest events (read from the GitHub Commits API) and the latest failed logins (kept in memory).

### 17.11 Supply chain

`requirements.txt` pins exact versions (preferably with hashes). Use only well-known maintained packages (for example streamlit, requests, pillow, openpyxl, defusedxml, reportlab, arabic-reshaper, python-bidi, bcrypt). Vendor the fonts in the repo; nothing is downloaded at runtime. Enable Dependabot alerts on both repositories (free).

### 17.12 Owner account hardening (README and SECURITY.md)

GitHub account: strong unique password plus two-factor authentication (authenticator app or passkey), recovery codes saved offline, no unnecessary collaborators. Telegram: enable Two-Step Verification, never share the bot token. The email account behind these services also uses two-factor authentication. The Store Manager password is unique, at least 12 characters, kept in a password manager. Anyone who controls the owner's GitHub account controls the whole system, so this is not optional.

### 17.13 Incident response (SECURITY.md, click by click)

If a secret or password may be exposed: (1) change the Store Manager password; (2) rotate `SESSION_SECRET` in Secrets (this logs everyone out); (3) revoke and recreate both GitHub tokens and update Secrets; (4) revoke the Telegram token with @BotFather `/revoke` and update Secrets; (5) deactivate Operators who left; (6) review the Activity screen and the GitHub commit history; (7) reboot the app; (8) if personal data was exposed, inform affected customers as required by law. Include the case "a token appeared in a screenshot or chat".

### 17.14 Fail closed, never open

- Distinguish "file not found" (404) from every other error. An error must NEVER be treated as "missing" (this prevents first-run takeover during a transient GitHub failure).
- If authentication state cannot be verified, deny access.
- No default credentials anywhere.

---

## 18. ERROR HANDLING AND EDGE CASES

Handle explicitly: empty basket send, empty/invalid name or phone, GitHub unreachable, token invalid or expired (clear Store Manager message), Telegram failure, missing image, missing backgrounds/logo (neutral fallback), empty catalogue (friendly message), item removed while in a customer's basket (still sendable using the stored line data), oversized/corrupt uploads, duplicate Item No across imports, order opened by two people at once, browser refresh in the middle of a basket, very long descriptions in PDF cells, non-Latin characters in names, Store Manager lock-out (recovery procedure), GitHub errors during the first-run check, and rate-limit or circuit-breaker activation.

---

## 19. EXPLICITLY OUT OF SCOPE (do NOT build or add)

Prices; payments; customer accounts; a customer list screen; OK/NOT OK order status; order pinning; automatic deletion after a number of days; editing a customer's basket/order by staff; technical filters (amps, poles, voltage); cross-sell suggestions; ready-made bundles; links to the Schneider catalogue; barcode scanning; SMS/OTP verification; a translated or RTL interface (only keep the strings i18n-ready); any paid service.

These may come later; keep the code structure open to them.

---

## 20. DELIVERABLES

1. Full project, modular and readable, for example: `app.py`, `requirements.txt`, `.streamlit/config.toml`, modules (config/secrets, github_store, models, auth, categories, items_import, search, cart, orders, photos, points, documents_pdf, documents_xlsx, telegram, settings, ui/theme, ui/customer, ui/operator, ui/manager, i18n), bundled fonts, seed `categories.json`, empty seed data files, the Items template xlsx, and `.github/workflows/reminder.yml`. Docstrings and comments on non-obvious logic.
2. Unit tests for: phone normalisation/validation, Item No key encoding and search normalisation, import validation, order ID generation, points calculation, availability rule, export/purge rules, and the security helpers (spreadsheet-formula neutralisation, HTML/Markdown escaping, session token signing and verification, rate limiter, upload validation, first-run guard).
   Also deliver a `SECURITY.md` file with the owner hardening checklist (17.12) and the incident response steps (17.13).
3. README (simple English), click by click, for a person who has never used GitHub:
   - a. Create the GitHub account and the two repos (public images, private data).
   - b. Create the TWO fine-grained tokens (one per repository, 90-day expiry) and set their permissions; explain how to renew them.
   - c. Upload the project files and the two backgrounds (drag and drop).
   - d. Create the Telegram bot and get the chat ID(s).
   - e. Deploy on Streamlit Community Cloud and paste the Secrets.
   - f. First run: choose a `SETUP_CODE` (random, kept secret) before deploying, then use it to set the Store Manager password, upload the logo, set the support number and working hours, import the items, add Operators.
   - g. How to replace backgrounds, update items, add photos from a phone.
   - h. Daily and 9-day routines (export, check the file, delete).
   - i. Troubleshooting table (symptom, cause, fix).
   - j. "Assumptions and known limits" list.
   - k. Owner account hardening and incident response (summary plus a pointer to `SECURITY.md`).
4. A final checklist stating, for each acceptance test below, PASS and how it was verified.

---

## 21. ACCEPTANCE TESTS (all must pass)

1. A customer finds `LC1D09M7` by typing "lc1 d09-m7" in under 1 second.
2. Quantity numbers appear nowhere in the customer UI, HTML source, or network payloads; only "Available" or "Waiting".
3. Valid numbers `0912345678`, `912345678`, `+218912345678`, `00218912345678`, and the Arabic-Indic digit form of 0912345678 are accepted and stored as `+218912345678`; `0212345678`, `0951234567`, `091234567`, `09123abc78` are rejected and no order is saved.
4. A basket with items from different sections can be edited (quantity, remove, notes) and sent as ONE order with ONE Telegram message.
5. The PDF shows photos, correct Arabic customer names, and paginates 150 lines; the Excel copy has exactly Item No | Item Name | Quantity.
6. A new order appears for all Operators; once Operator A opens it, it vanishes from Operator B's list and appears in A's "My Orders"; simultaneous opening gives one winner and a clear message to the other.
7. The Store Manager sees all orders with who opened each.
8. Operators cannot edit an order or reach Store Manager screens.
9. An Operator takes a phone photo of an item without a photo; thumb and full images are created, shown to customers within 2 minutes, and the Operator gets exactly +1 point; replacing the photo gives no point; 100 points show 1 star.
10. Import report catches duplicates, empty Item No, unknown categories and bad quantities; nothing is saved before confirmation; Merge and Replace behave as specified; photos survive imports.
11. Export lists all orders pre-selected; unticked orders are kept; the file has the specified columns; "Delete exported orders" is disabled before an export and, once used, deletes only that batch; orders created after the export survive.
12. The reminder fires after 9 days of unexported orders, at most once a day.
13. Telegram failure does not block orders and is shown to the Store Manager with a resend option.
14. Store Manager first-run password creation requires `SETUP_CODE`, works once and is then locked; the recovery procedure works; there is no default password.
15. Backgrounds: the phone loads `bg-mobile.jpg` only, the desktop loads `bg-desktop.jpg` only; replacing them (by upload and by GitHub overwrite) works without code edits; text stays readable.
16. Buttons are chrome with neon-green text; destructive buttons are red; disabled buttons are grey.
17. The footer shows "Support:" + the Store Manager's number as a working `wa.me` link.
18. The app runs on Streamlit Community Cloud with only free services and stays within roughly 1 GB RAM with 5,000 items loaded.
19. Brute-force throttling works; deactivating an Operator ends his session.
20. The backup ZIP contains no password hashes or secrets.
21. No Arabic words appear in any interface text or generated document (other than customer-entered data).

### Security acceptance tests

22. Takeover: without the correct `SETUP_CODE` the Store Manager password cannot be created; a transient GitHub error (timeout, 5xx, 403) never shows the setup screen; wrong codes are throttled.
23. Role bypass: customers and Operators cannot reach any Store Manager function by URL, query parameter, multipage path or session-state tampering; every staff function is covered by a test.
24. Login: an unknown user and a wrong password give the same message and similar timing; throttling starts after 5 failures; a correct password works again after the wait; the Store Manager cannot be permanently locked out.
25. A customer name or note such as `<script>alert(1)</script>`, `"><img src=x onerror=alert(1)>`, a Markdown link, or `=HYPERLINK("http://x","y")` is displayed as plain text everywhere (UI, PDF, Excel).
26. Formula injection: values starting with `=`, `+`, `-`, `@` are stored as text in the order Excel, the export Excel and the leaderboard export.
27. A tampered localStorage basket (unknown Item No, quantity -5 or 99999, altered description, oversized JSON) is cleaned: invalid lines dropped, descriptions taken from the catalogue.
28. Flood: 100 rapid submissions from one session, IP or phone are limited; the global circuit breaker works; Telegram receives aggregated messages, not 100; GitHub API quota stays healthy; a legitimate customer can order afterwards.
29. Upload attacks: an SVG, an executable renamed to `.jpg`, a 30,000 x 30,000 px PNG, a 20 MB file, and an image with GPS EXIF are rejected or sanitised; stored images contain no metadata; the stored file name never comes from the upload.
30. Import attacks: an `.xlsm` file, an XML bomb, 100,000 rows, and cells containing formulas are rejected or sanitised without crashing the app.
31. A Telegram notification for a name containing markup, links or newlines is delivered as plain single-line text, truncated.
32. Secret hygiene: a scan of the repository and the logs finds no secrets; the app refuses to start with placeholder secrets; no error message shows a token or a stack trace to a user.
33. Sessions: after a password change, logout or deactivation the old token is rejected; expired tokens and tokens with a modified role or signature are rejected.
34. Operators never see a customer phone number before opening the order; every claim appears in the Activity screen.
35. Re-authentication is required for purge, "Replace all" import, Operator deletion or reset, backup download, support-number change and category deletion.
36. Dependency versions are pinned; nothing is downloaded at runtime; the Actions workflow has minimal permissions and pinned actions.
37. The privacy notice is visible on the send form; no personal data appears in Telegram messages, logs, URLs or commit messages.
38. Quantity secrecy is re-tested after tampering attempts (HTML source, network payloads, session state exposure).

---

## 22. HONEST LIMITS TO STATE IN THE README

Streamlit apps sleep when idle; Streamlit is less fluid than a classic website and many simultaneous customers on free resources may slow it; the phone number is checked for FORMAT only, not ownership; basket persistence is best-effort; GitHub history keeps deleted data (private repo); the image repository should stay under about 1 GB (compress photos); Streamlit cannot set HttpOnly cookies (mitigated by short sessions and XSS prevention); per-IP limits are best-effort because the client IP comes from proxy headers, and in-memory counters reset when the app restarts; GitHub is not designed as a database under hostile write load, so a determined attacker could still make the order form unavailable for a while (consider Cloudflare Turnstile or a real database later); whoever controls the owner's GitHub account controls the whole system, so two-factor authentication is essential; using Schneider Electric names and images requires the owner to hold the right to do so, and "authorised distributor" wording must not be used unless true.

END OF PROMPT
