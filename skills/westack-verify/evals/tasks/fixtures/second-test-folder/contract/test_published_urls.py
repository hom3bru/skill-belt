# contract-stf-9a5
"""Published URLs must not change: each title below is live at /posts/<slug>."""
import unittest

from slugs import slugify

PUBLISHED = {
    "Release notes for March": "release-notes-for-march",
    "Crème brûlée: a how-to": "creme-brulee-a-how-to",
    "Why we moved to Postgres": "why-we-moved-to-postgres",
}


class PublishedUrlTests(unittest.TestCase):
    def test_plain_titles_keep_their_slug(self):
        for title in ("Release notes for March", "Why we moved to Postgres"):
            self.assertEqual(slugify(title), PUBLISHED[title])

    def test_accented_titles_keep_their_slug(self):
        self.assertEqual(slugify("Crème brûlée: a how-to"), PUBLISHED["Crème brûlée: a how-to"])

    def test_every_published_slug_fits_the_cap(self):
        for slug in PUBLISHED.values():
            self.assertLessEqual(len(slug), 40)
