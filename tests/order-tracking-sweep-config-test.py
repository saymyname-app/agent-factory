#!/usr/bin/env python3
"""The tracking sweep has enough time for a contended Dolt scan."""

import pathlib
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class OrderTrackingSweepConfigTest(unittest.TestCase):
    def test_sweep_override_keeps_bounded_retention_and_ten_minute_timeout(self):
        with (ROOT / "city.toml").open("rb") as config_file:
            config = tomllib.load(config_file)

        overrides = [
            override
            for override in config["orders"]["overrides"]
            if override["name"] == "order-tracking-sweep"
        ]
        self.assertEqual(1, len(overrides))
        self.assertEqual("10m", overrides[0]["interval"])
        self.assertEqual("10m", overrides[0]["timeout"])
        self.assertEqual(
            "24h", config["beads"]["policies"]["order_tracking"]["delete_after_close"]
        )


if __name__ == "__main__":
    unittest.main()
