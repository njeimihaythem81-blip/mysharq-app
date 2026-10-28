# MY SHARQ RFQ's

Mobile-first Request-for-Quotation store for Schneider Electric products. No prices, no payments, no customer accounts.
Stack: Streamlit Community Cloud + GitHub (as the database) + ntfy / e-mail alerts (Telegram optional). 100% free.

This is the **complete, current build** (through v2.6): the base system, manual item/category management with images
at every level, the secret staff link, live item-number search, the owner's 20-section classification tree, and the
intelligent (relevance-ranked, typo- and synonym-tolerant) search box. Nothing below requires any later editing —
follow it once, start to finish, on a fresh setup.

> **Honest status.** The business logic (`core/`) is covered by 44 automated Python tests plus 2 JavaScript test
> files, all passing. The Streamlit screens were written and statically checked but could not be run end-to-end in
> the build environment (no internet there to install Streamlit). Expect to run the smoke test in Part 4 and report
> any red error box; small fixes are normal for a first deployment.

---

## Part 1 — What you need (all free)

- A GitHub account with **two-factor authentication** turned on (Settings → Password and authentication →
  Two-factor authentication → Authenticator app). Save the recovery codes somewhere safe, off this computer.
- A Streamlit Community Cloud account (you sign in with the GitHub account above).
- A phone with the **ntfy** app (free push notifications, no account needed).
- A plain text file on your Desktop, call it `secrets.txt`, to privately collect the values below as you create
  them. It never gets uploaded anywhere; it is just your own notepad.

---

## Part 2 — Create three GitHub repositories

GitHub → **+** (top right) → **New repository**. For each one, tick **Add a README file**.

| Name | Visibility | Contains |
|---|---|---|
| `mysharq-app` | **Public** (it holds no secrets, and it must be public for the app to deploy) | this project's code |
| `mysharq-images` | **Public** | product photos, category images, backgrounds, logo |
| `mysharq-data` | **Private** | orders, items, categories, settings, users — personal/business data |

---

## Part 3 — Upload the code

The folder structure (subfolders like `core/`, `ui/`, `.streamlit/`) must be preserved exactly. Plain drag-and-drop
on github.com sometimes flattens folders, so use **GitHub Desktop** instead:

1. Install GitHub Desktop (desktop.github.com) and sign in with the same GitHub account.
2. **File → Clone repository** → pick `mysharq-app` → clone it to your computer.
3. Open this project's folder (the one you unzipped) and the cloned `mysharq-app` folder in two windows.
4. Select **everything** inside this project's folder (`Ctrl+A`, including the hidden `.streamlit` folder — enable
   "Hidden items" in File Explorer's View tab if you don't see it) and copy it into the cloned `mysharq-app` folder,
   replacing the placeholder `README.md`.
5. In GitHub Desktop, check the changed-files list: you must see paths like `core/catalog.py` and
   `.streamlit/config.toml` (with their folders), not bare file names. If folders are missing, something was
   flattened — redo step 4.
6. Write a commit summary (e.g. `Initial upload`), **Commit to main**, then **Push origin**.
7. Confirm on github.com that `mysharq-app` now shows the `core`, `ui`, `components`, `.streamlit`, `fonts`,
   `assets`, `seed`, `templates`, `tests` folders and the files `app.py`, `requirements.txt`, `README.md`,
   `SECURITY.md`.

---

## Part 4 — Two GitHub access tokens (least privilege: one repo each)

Repeat twice. GitHub → profile picture → **Settings** → **Developer settings** → **Personal access tokens** →
**Fine-grained tokens** → **Generate new token**.

1. **Data token** — Name `mysharq-data-token` · **Expiration: 90 days** (never "No expiration") · Repository access:
   **Only select repositories** → `mysharq-data` only · Permissions → Repository permissions → **Contents: Read and
   write** → **Generate token** (confirm). Copy the value (starts `github_pat_`) into `secrets.txt` as
   `GITHUB_TOKEN_DATA`. It is shown once only.
2. **Images token** — same steps, name `mysharq-images-token`, repository `mysharq-images` only. Save as
   `GITHUB_TOKEN_IMAGES`.

Put a reminder 85 days from now to renew both (new token → update Secrets → delete the old one).

---

## Part 5 — Staff alerts: ntfy (free, instant, no account)

1. Invent a private topic name: `mysharq-` followed by about 20 random letters and digits, e.g.
   `mysharq-k7q2x9m4tw8r3p5zv6nb`. Treat it like a password — never share or publish it. Save it in `secrets.txt` as
   `NTFY_TOPIC`.
2. Install the **ntfy** app on your phone → tap **+** (Subscribe to topic) → type your exact topic name →
   **Subscribe**.
3. Test from a browser: `https://ntfy.sh/YOUR_TOPIC/publish?message=test` (all lower-case path, exactly as written)
   — a push should arrive within seconds.
4. Optional backup channel: Gmail → enable 2-Step Verification → create an **App password** → set `EMAIL_USER`,
   `EMAIL_APP_PASSWORD`, `EMAIL_TO` in Secrets later (Part 6). Telegram is also still supported via
   `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_IDS` if you prefer it.

---

## Part 6 — Three secret values you generate yourself

In `secrets.txt`, add these (English letters and digits only, no spaces, no quotes inside the value):

- `SESSION_SECRET` — 40+ random characters (signs login sessions).
- `SETUP_CODE` — 12+ random characters (needed once, to create the Store Manager password).
- `STAFF_KEY` — 20+ random characters (the secret staff-login link uses this).

---

## Part 7 — Deploy on Streamlit Community Cloud

1. **share.streamlit.io** → **Continue with GitHub** → authorize.
2. **Create app** → **Deploy a public app from GitHub**.
3. Repository: `your-username/mysharq-app` · Branch: `main` · Main file path: `app.py`.
4. App URL: pick a unique name, e.g. `mysharq-store` → your app becomes `https://mysharq-store.streamlit.app`. Save
   this as `APP_URL` in `secrets.txt` (with `https://` and no trailing slash).
5. **Advanced settings** → Python **3.12** → paste into **Secrets**, replacing every value with your own from
   `secrets.txt` (keep the quote marks):

   ```
   GITHUB_TOKEN_DATA   = "github_pat_..."
   GITHUB_TOKEN_IMAGES = "github_pat_..."
   GITHUB_OWNER  = "your-github-username"
   IMAGES_REPO   = "mysharq-images"
   DATA_REPO     = "mysharq-data"
   BRANCH        = "main"
   NTFY_TOPIC    = "mysharq-your-random-topic"
   SESSION_SECRET = "your 40+ character value"
   SETUP_CODE     = "your 12+ character value"
   STAFF_KEY      = "your 20+ character value"
   APP_URL        = "https://mysharq-store.streamlit.app"
   ```

6. **Save** → **Deploy**. Wait 2–5 minutes.
7. If the app ever looks private to others, go to **Manage app → Settings → Sharing** and set it to public — a
   customer must never see a GitHub sign-in wall.
8. Any red error box: copy its text (never a secret) — that's the fastest way to get help fixing it.

---

## Part 8 — First run

1. Open your **secret staff link**: `https://your-app.streamlit.app/?k=YOUR_STAFF_KEY` (exact match, no spaces).
   There is no "Staff" button on the public page — customers never see this entry point. Bookmark it.
2. First time only: **First-time setup** screen asks for `SETUP_CODE`, then a new Store Manager password (12+
   characters) — write it down. This screen disappears forever after.
3. Sign in: username `manager`, your new password.
4. **Settings**: store name, support number (any country, shown as "Support:" in the footer), working hours,
   export-reminder days, upload the **logo** and the **phone / desktop backgrounds** (from this project's `assets/`
   folder), **Send test alert** (confirms ntfy/e-mail works).
5. **Categories**: the 20-section tree (from the owner's classification) is already loaded. Upload an image per
   level one at a time, or all at once — see Part 9.
6. **Items**: either import an Excel file (tab **Import**, with a before-you-save report and an automatic backup),
   or add items one by one (tab **Add item**). The empty template and the current tree are both in `templates/`.
7. **Operators**: add each staff member with a temporary password (they must change it at first login).

---

## Part 9 — Category images (section / branch / sub-branch tiles)

Customers see an image + name tile for every level; the whole tile opens it.

- **One level at a time**: Categories → pick the Section/Branch/Sub-branch → upload an image → **Save image**.
- **All at once (ZIP)**: Categories → **Images for all levels (ZIP)** → download the **list of expected file
  names** (Excel) → name each image file exactly that way (e.g. `TESYS.jpg`, `TESYS__OVERLOADS.jpg`,
  `TESYS__OVERLOADS__LRD.jpg` — double underscore between levels) → put them all in one ZIP → upload → **Check
  ZIP** → **Apply images**. Re-uploading a ZIP only touches the levels it contains; everything else keeps its
  current image.

---

## Part 10 — Managing items and the tree day to day

**Rule: the app is the master record.** Always download the newest Excel from the app before editing it offline.

- **Items → Excel** → **Prepare Excel file** → download. It has two sheets: **Items** (6 columns: Section, Branch,
  Sub-Branch, Item No, Description, Quantity) and **Categories** (the tree in order, with expected image names).
  Edit it, then **Items → Import → Merge** (adds new, updates existing, keeps the rest) or **Replace all** (makes
  items exactly match the file — password required).
- **Items → Add item / Edit / delete**: for one-off manual changes, with category pickers (no typos possible).
  Deleting requires your password; an automatic backup is taken first.
- **Categories**: add/rename/move/delete a section, branch or sub-branch directly; renaming updates every item that
  used the old name.
- **Replace the whole tree (from Excel)** (Categories screen, near the bottom): upload a Categories-sheet Excel file
  (e.g. `templates/MY_SHARQ_Tree_20_Sections.xlsx`) to replace the entire tree at once. Blocked if current items
  would not fit the new tree; a backup is saved first; images of levels that disappear are removed automatically.
- **Backup**: Manager → Backup. Manual download any time, plus up to 10 **automatic** backups (kept before every
  import, item delete, or category rename/delete), each restorable from the same screen.

---

## Part 11 — How customers search, and how staff find an item

- **Customer's "Intelligent search" box**: ranks by relevance — item number first (exact, then starts-with, then
  contains), then description and category words, weighting rarer words more. Tolerant of plurals, small spelling
  mistakes, spaces inside units ("25 a"), and Arabic/English synonyms (e.g. `كونتاكتور` finds "contactor"). If no
  query word matches everything, it shows the closest results instead (`core/synonyms.py` can be extended).
- **Live item-number box** (customer home page, Operator/Manager **Photos**, Manager **Items → Edit/delete**): type
  and a list of up to 6 matching items updates with every keystroke, with ▲/▼ to scroll further matches — no
  next-letter suggestion, purely what you typed.
- Availability only ever shows **Available**/**Waiting**; the stock number itself never reaches the browser.

---

## Part 11b — Search training, list upload and learning (v2.4)

**Training file.** Manager -> Training -> *Empty template*. Fill sheet **Synonyms** (one row = words that mean the same, in the
Arabic / French / English columns; several terms per cell separated by commas; phrases like *double row panel* are fine) and
sheet **Scopes** (a word and the Section / Branch / Sub-Branch the search should be limited to). Upload it, read the report
(rows with problems are skipped and listed), press *Save this training*. Use *Try the search* on the same screen to test wordings.
Re-upload the file any time: it replaces the saved training. *Current training* downloads what is saved.

**Customer list upload.** On the home page: *Upload a list (Excel, PDF, text)*. Accepted: .xlsx, .csv, .txt, text-based .pdf up to
5 MB and 150 lines. Quantities written as `2 x ...`, `... x3`, `... : 5` or `5 pcs ...` are understood. The customer checks the
lines (sure ones are already ticked, unsure ones show two suggestions, unknown ones ask for the item number) and presses
*Add ... to basket*. Scanned PDFs, pictures and handwriting are not read yet (planned next, free, inside the customer's browser).

**Learning (always needs your approval).** Every fix a customer makes is remembered as a counter and waits under
Training -> *Customer choices waiting for your approval*, with how many customers chose it. Nothing is used by the search until you
press *Approve*, even if every customer chose the same item. *Reject* blocks it for good. Approved choices are listed in the
*Approved* sheet of the training Excel (download *Current training*), so the file is always your complete master copy; you can also
add rows to that sheet yourself and upload the file. *Forget* removes an approved choice. Nothing personal is stored.

## Part 11c — Customer accounts (v2.5)

1. Manager -> **Customers** -> type the customer's name -> *Create customer and code*. Copy the name and the code and send them to the
   customer (the code is shown once; if lost, press *New code*).
2. Create all your customers, then press **Turn it ON** (Require customer login). From then on the store asks for name + code.
3. The customer's device remembers the sign-in for 30 days; *Sign out* (bottom of the page) forgets it.
4. *Stop* blocks a customer at once on every device (*Allow* restores). *Delete* removes the account. Orders keep the account name.
5. You and your staff are not affected: the secret staff link still works while login is ON.
Note: the app's web address itself stays public; without a name and code a visitor sees only the sign-in form, never the catalogue.

## Part 11d — Bundles and default rules (v2.6)

Both live in the training Excel (Manager -> Training -> download the template; it already contains examples).

**Bundles sheet** — columns: Name | Aliases | Item No | Qty | Choice | Option label. One row per component; write the name and aliases
on the bundle's first row only. Leave *Choice* empty for items that are always added. Give the same *Choice* text (for example `Door`)
to the alternatives; the customer must pick exactly one, and *Option label* is what they read (Transparent door / White door).
The template contains the modular panels by rows: 2 rows = 48-72 modules, 3 = 72-96, 4 = 96-120, 5 = 120-168, 6 = 144-192, each with
enclosure `40ENL<range>` and the door choice `PT40SUP<range>` / `PO40SUP<range>`. Add the lids kit or any other component for the other
ranges by adding rows. After uploading, read the report: rows whose item number is not in the catalogue are skipped and listed.
Customers meet bundles in the search box and in uploaded lists, and add everything with one button times a quantity.

**Defaults sheet** — columns: When | Unless | Leave out. Example: When `contactor`, Unless `dc`, Leave out `dc` means a search for a
contactor shows AC items unless the customer also writes DC (or `24VDC`, or its Arabic/French synonym from the Synonyms sheet).
If the rule would hide every result it does nothing. Use *Try the search* to test wordings.

## Part 12 — Orders, staff roles, and the WhatsApp reply

- Customer builds a basket (sticky **View basket** button, top right, with a basket icon), sends with just a name
  and a **Libyan mobile number** (91/92/93/94 prefixes; format-checked only, no SMS verification).
- **Operators** see new orders, claim one by opening it (it then leaves everyone else's list), reply via a prefilled
  **WhatsApp** link, and can download the order's PDF/Excel. They never edit a customer's basket.
- **Store Manager** sees every order and who opened it, plus **Export then purge**: select orders (all pre-selected,
  untick any to keep), generate one Excel file, download and check it, then — only after that, with your password —
  **Delete exported orders**. Nothing is ever auto-deleted.
- Alerts (ntfy/e-mail) never include the phone number, only order id / customer name / line count, aggregated to at
  most one message per 30 seconds.
- Operators earn a point (and a star per 100 points) for each **first** photo uploaded for an item — pure
  motivation, no payout logic.

---

## Part 13 — Look and feel

Chrome-metal background with neon-green headings. All buttons (including Download/WhatsApp links) are **chrome
gray with neon-green text**; destructive (delete) buttons keep a red outline and red text on purpose; disabled
buttons are dull grey. The basket button sits fixed at the top right with a basket icon. Backgrounds are two
separate images (`bg-mobile.jpg` portrait, `bg-desktop.jpg` landscape) swapped by a CSS media query — replace either
one any time from Settings → Images, no code change needed.

---

## Part 14 — Routine

- **Daily**: Operators check **Orders**, reply on WhatsApp, upload missing item photos.
- **When stock changes**: update quantities (Items → Edit/delete, or re-import Excel with Merge).
- **Every ~9 days** (or when the in-app reminder banner appears): **Export**, check the file, save it safely, then
  **Delete exported orders**.
- **Every 90 days**: renew both GitHub tokens (Part 4) and update Secrets.
- **Occasionally**: Backup, review **Activity** (who changed what), deactivate Operators who left.

---

## Part 15 — Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "The store is not configured yet" | A secret is missing or still a placeholder | Fix Secrets — the missing names are listed |
| "GitHub token rejected (401)" | Token expired or mistyped | Create a new fine-grained token, update Secrets |
| "Git Repository is empty" | A repo has no README | Add a README to that repo |
| Staff link shows "Page not found" | The `?k=` part is missing, lower-cased wrong, or after a `/` instead of `/?k=` | Use exactly `https://your-app.streamlit.app/?k=YOUR_STAFF_KEY` |
| Staff link shows a GitHub sign-in / "You do not have access" page | The Streamlit app's Sharing setting is Private | Manage app → Settings → Sharing → make it Public |
| No ntfy push arrives | Wrong topic name, or the phone never subscribed | Re-check the subscription; retest with the browser URL from Part 5 |
| New photo/image not visible yet | CDN/propagation delay | Wait 1–2 minutes, then hard-refresh (Ctrl+F5) |
| Same image upload "fails" repeatedly then suddenly works | It likely succeeded every time; only the *display* was delayed (not an error) | Wait at least 2 minutes between uploads of the same file; for many images use the ZIP upload (one commit) instead of one-by-one |
| First visit of the day is slow | Streamlit put the idle app to sleep | Wait a few seconds; this is normal on the free tier |
| "Service busy, please try again later" | More than the configured max orders/hour (abuse breaker) | Settings → raise "Maximum orders per hour" if legitimate traffic needs it |

---

## Part 16 — Known limits (read once)

- Phone numbers are checked for **format only**, not ownership (no paid SMS verification).
- Images are served from GitHub directly; this comfortably serves roughly 500 customers/day but is **not** a CDN —
  if traffic grows much further, a dedicated image host should replace it (ask before that becomes a bottleneck).
- Streamlit Community Cloud sleeps idle apps and is slower than a hand-built website under heavy simultaneous load.
- Deleted records leave a technical trace in the private repo's Git history.
- Using Schneider Electric names/images requires you to hold the right to do so; don't claim "authorised
  distributor" unless true.
- Whoever controls your GitHub account controls the whole system — keep two-factor authentication on, always.

See `SECURITY.md` for the full security checklist and incident-response steps.

---

## Developer notes

`core/` (no Streamlit dependency): `ghstore` (GitHub API), `store` (data layer), `catalog` (items/categories/search
logic + `synonyms.py`), `orders`, `auth`, `security`, `validators`, `imaging`, `docs`, `notify`.
`ui/`: `customer`, `staff`, `staff_manager`, `theme`, `common`, `livesearch`. `components/item_search/` is a small
JS component (type-ahead matching; the relevance search itself is in Python/`catalog.py` — the JS only renders the
live item-number dropdown). Run tests: `python -m unittest tests.test_core` and `node tests/matcher_test.js && node
tests/component_harness.js`.
