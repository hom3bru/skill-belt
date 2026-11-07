"""Messages shown after checkout."""


def payment_message(count):
    return "Payment recieved: %d items" % count


def goodbye_message(name):
    return "Thanks, %s. See you soon." % name
