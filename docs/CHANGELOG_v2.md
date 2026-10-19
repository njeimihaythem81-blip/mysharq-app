# v2 changes
1. "Product families" renamed to "Sections"; item counts removed from tiles.
2. Image tile (image + name, whole tile opens the level) for sections, branches and sub-branches; grey tile with the first two letters when no image.
3. Category images: single upload per level and ZIP upload by path names; downloadable list of expected file names.
4. Manual items: add, edit (description, quantity, category), delete (password).
5. Excel with two sheets (Items + Categories); import reads the Categories sheet (creates missing nodes, never deletes).
6. Import: summary before saving; automatic backup (newest 10) before import, item delete, category rename/delete; restore screen.
7. Secret staff link (STAFF_KEY): the Staff button is gone from the public page.
New required secret: STAFF_KEY (20+ characters).
