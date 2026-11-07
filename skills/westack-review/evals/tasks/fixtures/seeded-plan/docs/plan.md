# Plan: split users.name into first_name and last_name

## 1. Goal

Support sorting customers by surname in the admin list. Today `users.name` holds the full name as one string.

## 2. Context

Only the profile page reads `users.name` (`app/profile.py`). Nothing else depends on the column, so the change is local.

## 3. Changes

1. Migration `0042_split_name`, in one deploy:
   - add `first_name` and `last_name` (both `TEXT NOT NULL DEFAULT ''`);
   - backfill them by splitting `name` on the last space;
   - drop the `name` column.
2. Update `app/profile.py` to show `first_name + " " + last_name`.
3. Admin list: sort by `last_name`, then `first_name`.
4. While we are in the profile code, redesign the profile page and add avatar uploads (S3 bucket, image resizing).

## 4. Rollout

Ship the migration and the code together on Tuesday. The table has about 4 million rows.

## 5. Verification

- Unit tests for the name-splitting function: one word, two words, three words, empty string.
- A migration test on a copy of the staging database: row counts match before and after.
- Manual check of the admin list sort order.
