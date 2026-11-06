# Tags, note labels and export dedupe

- `app/tags.py`: an `add_tag` helper for the tag picker.
- `app/notes.py`: `new_note` gives every note the "note" label.
- `app/export.py`: `export_rows` skips rows it already wrote, so a retried export does not repeat lines.
- README: a section on tags.

Tests: `python -m unittest` passes.
