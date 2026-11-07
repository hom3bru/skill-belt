# ISSUE-12: an item exactly at the threshold is not reported as low stock

`low_stock(items, threshold=5)` leaves out an item with exactly 5 in stock. The warehouse rule is "5 or fewer is low", so an item at the threshold must be reported.
