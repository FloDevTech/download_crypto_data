"""Tests for the Binance parquet fetcher."""
from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import mock_open
from unittest.mock import patch

import polars as pl

sys.modules.setdefault("ccxt", SimpleNamespace(binance=Mock()))

from src.binance_fetcher import BinanceParquetFetcher
from src.binance_fetcher import load_config


class TestBinanceParquetFetcher(unittest.TestCase):
    def test_init_creates_base_dir_and_configures_exchange(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.binance_fetcher.ccxt.binance") as mock_binance:
                fetcher = BinanceParquetFetcher(base_dir=tmpdir)

        mock_binance.assert_called_once_with({"enableRateLimit": True})
        self.assertEqual(fetcher.base_dir, Path(tmpdir))

    def test_verify_symbol_returns_true_when_market_exists(self):
        with patch("src.binance_fetcher.ccxt.binance") as mock_binance:
            exchange = Mock()
            exchange.markets = {"BTC/USDT": {}, "ETH/USDT": {}}
            mock_binance.return_value = exchange

            fetcher = BinanceParquetFetcher()

            self.assertTrue(fetcher._verify_symbol("BTC/USDT"))
            exchange.load_markets.assert_called_once()

    def test_verify_symbol_returns_false_when_market_is_missing(self):
        with patch("src.binance_fetcher.ccxt.binance") as mock_binance:
            exchange = Mock()
            exchange.markets = {"BTC/USDT": {}}
            mock_binance.return_value = exchange

            fetcher = BinanceParquetFetcher()

            self.assertFalse(fetcher._verify_symbol("ADA/USDT"))

    def test_verify_symbol_returns_false_when_exchange_fails(self):
        with patch("src.binance_fetcher.ccxt.binance") as mock_binance:
            exchange = Mock()
            exchange.load_markets.side_effect = RuntimeError("network down")
            mock_binance.return_value = exchange

            fetcher = BinanceParquetFetcher()

            self.assertFalse(fetcher._verify_symbol("BTC/USDT"))

    def test_save_incremental_writes_partitioned_parquet_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.binance_fetcher.ccxt.binance"):
                fetcher = BinanceParquetFetcher(base_dir=tmpdir)
                df = pl.DataFrame(
                    {
                        "timestamp": ["2024-01-01T12:00:00"],
                        "open": [100.0],
                        "high": [110.0],
                        "low": [90.0],
                        "close": [105.0],
                        "volume": [10.0],
                    }
                ).with_columns(pl.col("timestamp").str.to_datetime())

                fetcher._save_incremental(df, "BTC/USDT")

                parquet_path = (
                    Path(tmpdir)
                    / "BTC-USDT"
                    / "year=2024"
                    / "month=1"
                    / "day=1"
                    / "data.parquet"
                )
                saved = pl.read_parquet(parquet_path)
                parquet_exists = parquet_path.exists()

        self.assertTrue(parquet_exists)
        self.assertEqual(saved.height, 1)
        self.assertEqual(saved["close"][0], 105.0)

    def test_save_incremental_deduplicates_existing_timestamps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.binance_fetcher.ccxt.binance"):
                fetcher = BinanceParquetFetcher(base_dir=tmpdir)
                df = pl.DataFrame(
                    {
                        "timestamp": ["2024-01-01T12:00:00"],
                        "open": [100.0],
                        "high": [110.0],
                        "low": [90.0],
                        "close": [105.0],
                        "volume": [10.0],
                    }
                ).with_columns(pl.col("timestamp").str.to_datetime())

                fetcher._save_incremental(df, "BTC/USDT")
                fetcher._save_incremental(df, "BTC/USDT")

                parquet_path = (
                    Path(tmpdir)
                    / "BTC-USDT"
                    / "year=2024"
                    / "month=1"
                    / "day=1"
                    / "data.parquet"
                )
                saved = pl.read_parquet(parquet_path)

        self.assertEqual(saved.height, 1)

    def test_fetch_and_store_downloads_ohlcv_and_persists_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.binance_fetcher.ccxt.binance") as mock_binance:
                exchange = Mock()
                exchange.parse8601.side_effect = [
                    1_704_067_200_000,
                    1_704_067_200_001,
                ]
                exchange.fetch_ohlcv.return_value = [
                    [1_704_067_200_000, 100.0, 110.0, 90.0, 105.0, 10.0],
                ]
                mock_binance.return_value = exchange

                with patch.object(BinanceParquetFetcher, "_verify_symbol", return_value=True):
                    with patch("src.binance_fetcher.time.sleep"):
                        fetcher = BinanceParquetFetcher(base_dir=tmpdir)
                        fetcher.fetch_and_store(
                            "BTC/USDT",
                            "1m",
                            "2024-01-01T00:00:00Z",
                            "2024-01-01T00:00:00.001Z",
                        )

                parquet_path = (
                    Path(tmpdir)
                    / "BTC-USDT"
                    / "year=2024"
                    / "month=1"
                    / "day=1"
                    / "data.parquet"
                )
                parquet_exists = parquet_path.exists()

        exchange.fetch_ohlcv.assert_called_once_with(
            "BTC/USDT",
            "1m",
            since=1_704_067_200_000,
            limit=1000,
        )
        self.assertTrue(parquet_exists)

    def test_fetch_and_store_skips_stale_ohlcv_without_hanging(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.binance_fetcher.ccxt.binance") as mock_binance:
                exchange = Mock()
                exchange.parse8601.side_effect = [
                    1_704_067_200_000,
                    1_704_070_800_000,
                ]
                exchange.fetch_ohlcv.return_value = [
                    [1_704_067_200_000, 100.0, 110.0, 90.0, 105.0, 10.0],
                ]
                mock_binance.return_value = exchange

                with patch.object(BinanceParquetFetcher, "_verify_symbol", return_value=True):
                    with patch("src.binance_fetcher.time.sleep"):
                        fetcher = BinanceParquetFetcher(base_dir=tmpdir)
                        fetcher.fetch_and_store(
                            "BTC/USDT",
                            "1m",
                            "2024-01-01T00:00:00Z",
                            "2024-01-01T01:00:00Z",
                        )

        self.assertEqual(exchange.fetch_ohlcv.call_count, 2)


class TestLoadConfig(unittest.TestCase):
    def test_load_config_reads_yaml_file(self):
        config_content = """
symbols:
  - BTC/USDT
  - ETH/USDT
start_date: "2024-01-01"
end_date: "2024-01-02"
"""

        with patch("builtins.open", mock_open(read_data=config_content)):
            config = load_config("config.yaml")

        self.assertEqual(config["symbols"], ["BTC/USDT", "ETH/USDT"])
        self.assertEqual(config["start_date"], "2024-01-01")
        self.assertEqual(config["end_date"], "2024-01-02")
