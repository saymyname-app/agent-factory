#!/usr/bin/env python3
"""The versioned Codex profiles keep the approved model/role split."""

import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def city_providers():
    return tomllib.loads((ROOT / "city.toml").read_text(encoding="utf-8"))["providers"]


def model(profile):
    return profile["option_defaults"]["model"]


class CityCodexProfilesTest(unittest.TestCase):
    EXPECTED = {
        "codex": ("gpt-6.1-sol", "medium", False),
        "codex-astra": ("gpt-6-astra", "high", False),
        "codex-astra-readonly": ("gpt-6-astra", "high", True),
        "codex-luna": ("gpt-6-luna", "high", False),
    }

    def test_profiles_pin_the_approved_models_effort_and_standard_tier(self):
        profiles = city_providers()
        for name, (expected_model, effort, read_only) in self.EXPECTED.items():
            profile = profiles[name]
            self.assertEqual(expected_model, model(profile), name)
            self.assertEqual(effort, profile["option_defaults"]["effort"], name)
            self.assertNotIn("--model", profile.get("args_append", []), name)
            self.assertNotIn("-m", profile.get("args_append", []), name)
            self.assertNotIn("service_tier=fast", str(profile), name)
            self.assertNotIn("service_tier=priority", str(profile), name)
            self.assertEqual(read_only, profile.get("command", "").endswith("delivery-role-sandbox"), name)

    def test_only_the_existing_read_only_roles_get_read_only_codex_profiles(self):
        policy = json.loads((ROOT / "config" / "provider-policy.json").read_text(encoding="utf-8"))
        self.assertEqual("codex", policy["targets"]["delivery-author"]["chain"][0])
        self.assertEqual("codex-astra-readonly", policy["targets"]["delivery-reviewer"]["chain"][0])
        self.assertEqual(["claude-readonly"], policy["targets"]["delivery-evaluator"]["chain"])
        self.assertEqual("codex-astra", policy["targets"]["ux-reviewer"]["chain"][0])
        self.assertNotEqual(model(city_providers()["codex"]), model(city_providers()["codex-astra-readonly"]))

    def test_sol_authors_keep_a_declared_evaluator_from_another_supplier(self):
        policy = json.loads((ROOT / "config" / "provider-policy.json").read_text(encoding="utf-8"))
        author = policy["targets"]["delivery-author"]["chain"][0]
        evaluator = policy["targets"]["delivery-evaluator"]["chain"][0]
        self.assertEqual(("openai", "anthropic"),
                         (policy["providers"][author]["pool"], policy["providers"][evaluator]["pool"]))
        self.assertFalse(any("luna" in provider
                             for provider in policy["targets"]["delivery-evaluator"]["chain"]))

    def test_catalog_matches_each_codex_profile(self):
        catalog = json.loads((ROOT / "config" / "model-catalog.json").read_text(encoding="utf-8"))["providers"]
        for name, (expected_model, _effort, _read_only) in self.EXPECTED.items():
            self.assertEqual([expected_model], catalog[name]["recommended"], name)


if __name__ == "__main__":
    unittest.main()
