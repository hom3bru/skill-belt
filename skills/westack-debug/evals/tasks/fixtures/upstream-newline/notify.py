# notify.py - the address a notice goes to (upn-ntf-8a1)
import directory

KNOWN_DOMAINS = {"example.com"}


def address_for(name, people=None):
    people = directory.load() if people is None else people
    email = people[name]
    domain = email.rsplit("@", 1)[-1]
    if domain not in KNOWN_DOMAINS:
        raise ValueError("unknown mail domain: %r" % domain)
    return email
