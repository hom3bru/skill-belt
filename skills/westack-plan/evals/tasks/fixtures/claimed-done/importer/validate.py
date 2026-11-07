# validate-src-2c9


def valid_email(address):
    local, at, domain = address.partition("@")
    return bool(at and local and domain)
