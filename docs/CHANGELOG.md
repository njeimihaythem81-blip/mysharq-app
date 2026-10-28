# MY SHARQ RFQ's — version history

## v1 — base system
Customer browsing/basket/RFQ submission, Operator order claiming, Store Manager screens, Excel import, PDF/Excel
documents, ntfy/e-mail/Telegram alerts, export-then-purge, security hardening (sessions, rate limits, input
sanitisation, backups-ready architecture).

## v2 — manual management, category images, secret staff link
Manual item add/edit/delete, full category tree editor, per-level (section/branch/sub-branch) images (single upload
or ZIP by path name), two-sheet Items Excel (Items + Categories) as the authoritative export/import file, automatic
backups before risky operations, restore screen, secret `?k=STAFF_KEY` staff entry point (no public Staff button).

## v2.1 — live item-number search component
Small JS component: type-ahead list (up to 6 rows, ▲/▼ to scroll more), updates on every keystroke, prefix results
before "contains" results, no next-letter suggestion. Wired into the customer home page, Photos screen, and
Manager's Edit/delete screen. Fixed a growing-iframe layout-shift bug (height is now measured from real content and
only re-sent when it changes).

## v2.2 — new 20-section classification tree
Replaced the seed category tree with the owner's real classification (20 sections, 98 branches, 95 sub-branches),
derived from the owner's reference file. Added "Replace the whole tree (from Excel)" in Manager → Categories, with
a pre-check that blocks the replacement if existing items would be orphaned, an automatic backup, and automatic
cleanup of images for levels that no longer exist.

## v2.3 — intelligent (relevance) search, button restyle
Customer-facing search renamed "Intelligent search": ranks by relevance across item number, description, and
category names; tolerant of plurals, small typos, split units ("25 a"), and an Arabic/English synonym dictionary
(`core/synonyms.py`); falls back to closest matches when no item satisfies every search word. All buttons restyled
to chrome-gray with neon-green text (delete buttons keep their red accent); the basket button moved to a fixed
top-right position with a basket icon.

## v2.4 — search training, list upload, learning from customer choices
* **Training Excel** (Manager -> Training): sheet *Synonyms* (Arabic | French | English | Other, one row = one group of equal words,
  phrases allowed) and sheet *Scopes* (word -> Section / Branch / Sub-Branch: typing the word, or any synonym of it, limits the
  search to that category). Template + export of the current training. Bad rows are skipped and reported, never the whole file.
  Stored as `training.json` in the DATA repo. French accents are now ignored by the search.
* **Upload a list** (customer home, button under the search box): Excel (with or without a header, Arabic/French/English headers),
  CSV, text, or text-based PDF. Reads quantities such as `2 x contactor 25A`, `relay 24V : 5`, `5 pcs fuse`.
  Each line gets a confidence: sure -> accepted (can be changed); unsure -> two suggestions; not found -> type the item number
  with the live item-number box. Only confirmed lines go to the basket. Scanned PDFs / pictures / handwriting: next version.
* **Learning**: choices the customer makes are saved as small counters (`learned.json`). A choice is used by the search after two
  different customers made it, or when the manager approves it (Training screen: approve / reject / forget).
* Heavy work happens only when the customer presses *Read my list*; normal browsing and search are unchanged.
* Tests: 63 Python tests (19 new) + 2 JavaScript tests.

## v2.5 — customer accounts, approval-only learning
* **Customer accounts** (Manager -> Customers): the manager creates a customer by name; the app generates a code
  (e.g. `K7QM-4XD2`) shown ONCE; only its hash is stored. Customers sign in with name + code (case/space/dash tolerant), and the
  device remembers them for 30 days. The manager can issue a new code, stop/allow, or delete a customer; each takes effect on
  every device. Orders now record the customer's account (shown to staff). Sign-in is throttled like staff login.
* **"Require customer login"** switch (default OFF so an upgrade never locks anyone out). When ON, the store shows only a sign-in
  form until the customer signs in; staff entering by the secret link are not blocked.
* **Security fix:** a customer session token can never be accepted as a staff session, even if a customer shares a name with an operator.
* **Learning is approval-only, always.** Customer choices wait in Training until the manager approves them; many customers choosing
  the same item does NOT activate it (this replaces the v2.4 two-customer rule). Pending choices show how many customers chose them.
* **Approved choices are written into the training Excel** (new sheet *Approved*: Wording | Item No | Description). Downloading
  *Current training* includes them; uploading a file with an Approved sheet re-adds them (unknown item numbers are reported and skipped).
* Tests: 72 Python tests + 2 JavaScript tests.

## v2.6 — functional bundles and default rules
* **Bundles** (new sheet *Bundles* in the training Excel): one name that stands for several items, with quantities. Rows that share the
  same *Choice* text are alternatives the customer picks from (e.g. Door: Transparent / White). Customers see a bundle card above the
  search results (items, a radio for each choice, a quantity, one *Add all to basket* button) and inside an uploaded list
  (a line such as `2 x لوحة زوجية 48` becomes a bundle row). A bundle matches by its name or any alias in Arabic / French / English; if the
  customer typed a number it must belong to the bundle's range. Items missing from the catalogue are reported on upload and hidden.
* **Template ships with the modular panels by number of rows**: 2 rows 48-72, 3 rows 72-96, 4 rows 96-120, 5 rows 120-168, 6 rows 144-192.
  Each = enclosure `40ENL<range>` + door choice `PT40SUP<range>` (transparent) / `PO40SUP<range>` (white); the 2-row panel also has the
  lids kit `S48M200`. Codes for the other ranges follow the same pattern: the upload report lists any that are not in your catalogue.
* **Defaults** (new sheet *Defaults*: When | Unless | Leave out): e.g. when *contactor* is typed and *dc* is not, items containing DC are
  hidden (AC is the default). Works in Arabic/French/English through the synonym groups, understands codes such as `24VDC`, shows a note,
  and never hides everything. Also applies to uploaded lists, so `contactor 25` finds the AC one automatically.
* Manager *Try the search* shows bundles and applied default rules.
* Tests: 87 Python tests + 2 JavaScript tests.

