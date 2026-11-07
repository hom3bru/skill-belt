# app-src-3f6
"""Sort messages into folders by the sender's domain."""


def domain_of(address):
    return address.rsplit("@", 1)[-1].lower()
