"""Monthly report lines. report-frozen-4a1"""


def tax_line(invoice):
    return "%s tax %s" % (invoice.number, invoice.calc_tax())
