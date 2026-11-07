from receipt import render_receipt

print(render_receipt([("Coffee", 3.5), ("Bagel", 2.25)]))
for line in render_receipt([("Coffee", 3.5), ("Bagel", 2.25)]).splitlines():
    print(len(line), repr(line))
