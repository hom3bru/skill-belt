<!-- readme-c2b -->
# gridcalc

Fast spreadsheet formulas for Python.

```python
from gridcalc import Sheet
Sheet({"A1": 2, "A2": "=A1*3"}).value("A2")  # 6
```

## Licence

MIT. Use it anywhere.
