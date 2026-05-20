"""Tests for data validation."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import mock_open
from unittest.mock import patch

import polars as pl

from src.validator import DataValidator
from src.validator import load_config


class TestDataValidator(unittest.TestCase):
    def test_init_sets_data_dir(self):
        validator = DataValidator(data_dir="custom_data")

        self.assertEqual(validator.data_dir, Path("custom_data"))

    def test_get_symbol_data_returns_none_when_symbol_dir_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = DataValidator(data_dir=tmpdir)

            result = validator._get_symbol_data("BTC/USDT")

        self.assertIsNone(result)

    def test_get_symbol_data_scans_partitioned_parquet_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            symbol_dir = Path(tmpdir) / "BTC-USDT"
            symbol_dir.mkdir()
            validator = DataValidator(data_dir=tmpdir)

            with patch("src.validator.pl.scan_parquet") as mock_scan:
                lazy_frame = Mock()
                mock_scan.return_value = lazy_frame

                result = validator._get_symbol_data("BTC/USDT")

        self.assertIs(result, lazy_frame)
        mock_scan.assert_called_once_with(str(symbol_dir / "**" / "*.parquet"))

    def test_check_gaps_returns_none_when_no_symbol_data_exists(self):
        validator = DataValidator()

        with patch.object(validator, "_get_symbol_data", return_value=None):
            result = validator.check_gaps("BTC/USDT")

        self.assertIsNone(result)

    def test_check_gaps_returns_empty_frame_for_contiguous_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_symbol_data(
                tmpdir,
                "BTC-USDT",
                [
                    datetime(2024, 1, 1, 0, 0),
                    datetime(2024, 1, 1, 0, 1),
                    datetime(2024, 1, 1, 0, 2),
                ],
            )
            validator = DataValidator(data_dir=tmpdir)

            gaps = validator.check_gaps("BTC/USDT", timeframe_minutes=1)

        self.assertTrue(gaps.is_empty())

    def test_check_gaps_reports_timestamp_before_gap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_symbol_data(
                tmpdir,
                "BTC-USDT",
                [
                    datetime(2024, 1, 1, 0, 0),
                    datetime(2024, 1, 1, 0, 1),
                    datetime(2024, 1, 1, 0, 5),
                ],
            )
            validator = DataValidator(data_dir=tmpdir)

            gaps = validator.check_gaps("BTC/USDT", timeframe_minutes=1)

        self.assertEqual(gaps.height, 1)
        self.assertEqual(gaps["timestamp"][0], datetime(2024, 1, 1, 0, 1))
        self.assertEqual(gaps["delta"][0], timedelta(minutes=4))

    def test_run_report_continues_when_symbol_has_no_data(self):
        validator = DataValidator()
        validator.console = Mock()

        with patch.object(validator, "check_gaps", return_value=None):
            validator.run_report(["BTC/USDT"])

        self.assertGreaterEqual(validator.console.print.call_count, 3)

    @staticmethod
    def _write_symbol_data(tmpdir, symbol_dir_name, timestamps):
        symbol_dir = Path(tmpdir) / symbol_dir_name
        partition_dir = symbol_dir / "year=2024" / "month=1" / "day=1"
        partition_dir.mkdir(parents=True)
        df = pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": [1.0] * len(timestamps),
                "high": [1.0] * len(timestamps),
                "low": [1.0] * len(timestamps),
                "close": [1.0] * len(timestamps),
                "volume": [1.0] * len(timestamps),
            }
        )
        df.write_parquet(partition_dir / "data.parquet")


class TestLoadConfig(unittest.TestCase):
    def test_load_config_reads_yaml_file(self):
        config_content = """
symbols:
  - BTC/USDT
  - ETH/USDT
"""

        with patch("builtins.open", mock_open(read_data=config_content)):
            config = load_config("config.yaml")

        self.assertEqual(config["symbols"], ["BTC/USDT", "ETH/USDT"])
