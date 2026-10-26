"""Frozen independent requirements for the new ReplayTotal slice; no donor imports."""
def acceptance(factory):
    ledger = factory()
    ledger.add("a", "9007199254740993")
    ledger.add("b", "-2")
    assert ledger.total() == "9007199254740991", "exact decimal sum required"
    assert ledger.add("a", "9007199254740993") is False, "replay must be idempotent"
    assert ledger.total() == "9007199254740991", "replay changed sum"
    before = ledger.snapshot()
    for invalid in [True, 1.5, None, "1.0", "", "NaN"]:
        try:
            ledger.add("invalid", invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("non-integer-string amount accepted")
    try:
        ledger.add("a", "4")
    except ValueError:
        pass
    else:
        raise AssertionError("conflicting replay accepted")
    assert ledger.snapshot() == before, "failed transaction changed state"
    resumed = factory.restore(before)
    resumed.add("b", "-2")
    resumed.add("c", "3")
    assert resumed.total() == "9007199254740994", "restart changed identity"
    reordered = factory()
    reordered.add("b", "-2")
    reordered.add("a", "9007199254740993")
    assert reordered.total() == ledger.total(), "distinct order changed sum"
    try:
        factory.restore({"version": 2, "entries": {}})
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported schema version accepted")
    return 8
