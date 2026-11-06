import logging

lg = logging.getLogger(__name__)


def load(path):
    lg.info("loading %s", path)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def save(path, text):
    lg.info("saving %s", path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
