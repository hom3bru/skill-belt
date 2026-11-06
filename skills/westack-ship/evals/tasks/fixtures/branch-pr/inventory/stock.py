"""Stock levels."""
from collections import namedtuple

Item = namedtuple("Item", "sku qty")


def low_stock(items, threshold=5):
    """The items that need reordering, in their original order."""
    return [item for item in items if item.qty < threshold]
