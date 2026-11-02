#!/usr/bin/env python3
"""The tracking sweep has enough time without overlapping its next run."""

import pathlib
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class OrderTrackingSweepConfigTest(unittest.TestCase):
    def test_sweep_override_keeps_bounded_retention_and_non_overlapping_cadence(self):
        with (ROOT / "city.toml").open("rb") as config_file:
            config = tomllib.load(config_file)

        overrides = [
            override
            for override in config["orders"]["overrides"]
            if override["name"] == "order-tracking-sweep"
        ]
        self.assertEqual(1, len(overrides))
        self.assertEqual("30m", overrides[0]["interval"])
        self.assertEqual("20m", overrides[0]["timeout"])
        self.assertGreater(
            int(overrides[0]["interval"].removesuffix("m")),
            int(overrides[0]["timeout"].removesuffix("m")),
        )
        self.assertTrue(overrides[0]["check"].endswith(" order-tracking-sweep 1800"))
        self.assertEqual(
            "6h", config["beads"]["policies"]["order_tracking"]["delete_after_close"]
        )


if __name__ == "__main__":
    unittest.main()
