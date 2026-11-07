"""Summary statistics for request latencies (microseconds)."""


def mean(values):
    """Arithmetic mean of a non-empty iterable."""
    values = list(values)
    return sum(values) / len(values)


def variance(values):
    """Population variance of a non-empty iterable."""
    values = list(values)
    centre = mean(values)
    return sum((value - centre) ** 2 for value in values) / len(values)
