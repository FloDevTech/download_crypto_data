import ccxt
import math
import random
import time
from pathlib import Path

import polars as pl
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)


class BinanceParquetFetcher:
    def __init__(self, base_dir="data"):
        self.exchange = ccxt.binance({"enableRateLimit": True})
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.console = Console()

    def _verify_symbol(self, symbol):
        """Verifica si el símbolo existe en Binance."""
        try:
            self.exchange.load_markets()
            if symbol not in self.exchange.markets:
                self.console.print(
                    f"[red]Error: El símbolo {symbol} no existe en Binance.[/red]"
                )
                return False
            return True
        except Exception as e:
            self.console.print(
                f"[red]Error al conectar con Binance para verificar símbolos: {e}[/red]"
            )
            return False

    def _save_incremental(self, df_new, symbol):
        """
        Guarda usando Polars y gestiona la deduplicación diaria.
        """
        safe_symbol = symbol.replace("/", "-")

        # Añadimos columnas de partición
        df_new = df_new.with_columns(
            [
                df_new["timestamp"].dt.year().alias("year"),
                df_new["timestamp"].dt.month().alias("month"),
                df_new["timestamp"].dt.day().alias("day"),
            ]
        )

        # Iteramos por particiones de fecha únicas
        partitions = df_new.select(["year", "month", "day"]).unique()

        for row in partitions.iter_rows():
            y, m, d = row
            df_day = df_new.filter(
                (pl.col("year") == y) & (pl.col("month") == m) & (pl.col("day") == d)
            )

            partition_path = (
                self.base_dir / safe_symbol / f"year={y}" / f"month={m}" / f"day={d}"
            )
            partition_path.mkdir(parents=True, exist_ok=True)
            file_path = partition_path / "data.parquet"

            if file_path.exists():
                # Leemos, concatenamos y deduplicamos
                df_old = pl.read_parquet(file_path)
                df_combined = pl.concat([df_old, df_day]).unique(subset=["timestamp"])
                df_combined.write_parquet(file_path)
            else:
                # Archivo nuevo
                df_day.write_parquet(file_path)

        self.console.print(f"Datos para [green]{symbol}[/green] actualizados.")

    def fetch_and_store(self, symbol, timeframe, start_date, end_date):
        if not self._verify_symbol(symbol):
            return

        start_ts = self.exchange.parse8601(start_date)
        end_ts = self.exchange.parse8601(end_date)
        current_ts = start_ts
        ONE_HOUR_MS = 3600 * 1000

        total_hours = math.ceil((end_ts - start_ts) / ONE_HOUR_MS)

        self.console.print(
            Panel(
                f"Descargando [bold green]{symbol}[/bold green] ({start_date} a {end_date})",
                expand=False,
            )
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(f"Progreso {symbol}...", total=total_hours)

            while current_ts < end_ts:
                chunk_end = min(current_ts + ONE_HOUR_MS, end_ts)
                try:
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol, timeframe, since=current_ts, limit=1000
                    )
                    if ohlcv:
                        # Crear DataFrame de Polars
                        df = pl.DataFrame(
                            ohlcv,
                            schema=[
                                "timestamp",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                            ],
                            orient="row",
                        )
                        # Convertir timestamp a datetime
                        df = df.with_columns(pl.from_epoch("timestamp", time_unit="ms"))

                        # Filtrar fuera del rango del chunk
                        df = df.filter(
                            pl.col("timestamp") < pl.lit(chunk_end).cast(pl.Datetime)
                        )

                        if not df.is_empty():
                            self._save_incremental(df, symbol)

                        current_ts = ohlcv[-1][0] + 1
                    else:
                        current_ts = chunk_end

                    progress.update(task, advance=1)
                    time.sleep(random.uniform(10, 30))
                except Exception as e:
                    self.console.print(
                        f"[bold red]API Error para {symbol}:[/bold red] {e}"
                    )
                    self.console.print(
                        "[yellow]Esperando 60s antes de reintentar...[/yellow]"
                    )
                    time.sleep(60)


def load_config(config_path="config.yaml"):
    with open(config_path) as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    config = load_config()
    fetcher = BinanceParquetFetcher()

    for symbol in config["symbols"]:
        fetcher.fetch_and_store(symbol, "1m", config["start_date"], config["end_date"])
