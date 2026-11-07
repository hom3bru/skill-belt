# pdf-src-9c4
"""PDF layout of the monthly totals (in progress): one row per account."""


def rows(totals):
    return ["%s  %d.%02d" % (account, cents // 100, cents % 100) for account, cents in totals.items()]
