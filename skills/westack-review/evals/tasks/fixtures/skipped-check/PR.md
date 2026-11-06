# Round invoice totals once, at the end

`invoice_total` now rounds once, at the end, instead of per line, which fixes the one-cent drift finance reported (FIN-41).

CI: green, `python -m unittest` passes (ci-log.txt).
