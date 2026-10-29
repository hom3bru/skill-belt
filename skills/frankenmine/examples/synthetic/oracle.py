"""Frozen independent requirements for the new ReplayTotal slice; no donor imports."""
# Canonical spelling matters across the language boundary: JavaScript BigInt('') is 0n and
# BigInt(' 12 ') is 12n, while Python int() accepts '٣' (3), '1_000' and ' 12'.
NONCANONICAL = [True, 1.5, None, "1.0", "", "NaN", "  ", " 12", "12 ", "0x10", "٣", "1_000", "+1", "007", "-0"]


def acceptance(factory):
    ledger = factory()
    assert ledger.total() == "0", "empty ledger must total '0'"
    ledger.add("a", "9007199254740993")
    ledger.add("b", "-2")
    assert ledger.total() == "9007199254740991", "exact decimal sum required"
    assert ledger.add("a", "9007199254740993") is False, "replay must be idempotent"
    assert ledger.total() == "9007199254740991", "replay changed sum"
    before = ledger.snapshot()
    for invalid in NONCANONICAL:
        try:
            ledger.add("invalid", invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("noncanonical or non-integer amount accepted: " + repr(invalid))
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
    return 9
