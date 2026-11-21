"""Offline tests for the evidence rules. Run: python3 -m unittest discover -s tests -v

These tests never touch the network and never need API keys. They test the
part that makes this a Jack fork: no source, no claim; citations must be real.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from research_agent import (  # noqa: E402
    Source,
    answer,
    compose_extractive,
    load_fixture,
    validate_citations,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixture_sources.json")


class TestGapAdmission(unittest.TestCase):
    def test_no_sources_means_gap_not_invention(self):
        result = answer("Anything at all?", [], api_key="unused")
        self.assertTrue(result.text.startswith("Gap:"))
        self.assertEqual(result.sources, [])

    def test_empty_fixture_means_gap(self):
        result = compose_extractive("Anything?", [])
        self.assertTrue(result.text.startswith("Gap:"))


class TestCitations(unittest.TestCase):
    def setUp(self):
        self.sources = load_fixture(FIXTURE)

    def test_fixture_answer_cites_only_real_sources(self):
        result = compose_extractive(
            "What does the hackathon ask participants to build?", self.sources
        )
        self.assertTrue(result.citations_valid, result.problems)
        self.assertIn("[", result.text)
        for s in self.sources:
            self.assertIn(s.url, result.text)

    def test_validator_rejects_invented_citation(self):
        problems = validate_citations("The moon is green cheese [9].", self.sources)
        self.assertTrue(any("[9]" in p for p in problems))

    def test_validator_rejects_uncited_claims(self):
        problems = validate_citations("A confident claim with no source.", self.sources)
        self.assertTrue(problems)

    def test_source_numbering_is_stable(self):
        self.assertEqual([s.index for s in self.sources], [1, 2])
        self.assertTrue(all(isinstance(s, Source) for s in self.sources))


if __name__ == "__main__":
    unittest.main()
