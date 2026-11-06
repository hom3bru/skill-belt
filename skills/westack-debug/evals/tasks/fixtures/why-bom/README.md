# Billing totals

<!-- bom-readme-2f6 -->

`python -B report.py <export.csv>` prints the total of the amount column. Exports come from the billing portal as
UTF-8 CSV files with a header row; data/sample.csv is yesterday's export. Tests run with `python -B -m unittest -v`.
