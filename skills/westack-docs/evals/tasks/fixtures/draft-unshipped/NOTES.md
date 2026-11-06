<!-- notes-2f7 -->
Notes for the 2.3 user guide:

- CSV export shipped in 2.3: `ledger export --format csv FILE` writes FILE.csv beside the input.
- Export refuses an input over 50 MB with ExportTooLarge. Workaround: `ledger split --rows 100000 FILE`, then export each part.
- PDF export: in progress for 2.4 on the pdf-export branch; not merged.
