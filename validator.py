import polars as pl
from pathlib import Path
from datetime import timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import yaml


class DataValidator:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.console = Console()

    def _get_symbol_data(self, symbol):
        """Carga todos los datos de un símbolo en modo lazy."""
        safe_symbol = symbol.replace("/", "-")
        symbol_path = self.data_dir / safe_symbol
        if not symbol_path.exists():
            return None
        # Lee todos los archivos parquet del símbolo de forma eficiente
        return pl.scan_parquet(str(symbol_path / "**" / "*.parquet"))

    def check_gaps(self, symbol, timeframe_minutes=1):
        """Detecta huecos en la serie temporal."""
        lf = self._get_symbol_data(symbol)
        if lf is None:
            return None

        # Definimos el delta esperado
        expected_delta = timedelta(minutes=timeframe_minutes)

        # Lógica de detección:
        # 1. Ordenamos por timestamp
        # 2. Calculamos la diferencia con la fila siguiente (diff)
        # 3. Filtramos donde la diferencia > expected_delta
        gaps = (
            lf.sort("timestamp")
            .with_columns([(pl.col("timestamp").diff().shift(-1)).alias("delta")])
            .filter(pl.col("delta") > expected_delta)
            .select(["timestamp", "delta"])
            .collect()
        )

        return gaps

    def run_report(self, symbols, timeframe_minutes=1):
        """Genera un reporte consolidado usando Rich."""
        self.console.print(
            Panel("[bold blue]Reporte de Validación de Datos[/bold blue]", expand=False)
        )

        for symbol in symbols:
            self.console.print(
                f"\n[bold underline]Validando:[/bold underline] [green]{symbol}[/green]"
            )

            gaps = self.check_gaps(symbol, timeframe_minutes)

            if gaps is None:
                self.console.print(
                    "[red]✗ No se encontraron datos para este símbolo.[/red]"
                )
                continue

            if gaps.is_empty():
                self.console.print("[green]✔ Sin gaps detectados.[/green]")
            else:
                table = Table(title=f"Gaps encontrados: {len(gaps)}")
                table.add_column("Timestamp Inicio", style="cyan")
                table.add_column("Duración del Gap", style="magenta")

                # Limitamos a los primeros 10 gaps para no saturar la terminal
                for row in gaps.head(10).iter_rows():
                    table.add_row(str(row[0]), str(row[1]))

                self.console.print(table)
                if len(gaps) > 10:
                    self.console.print(f"...y {len(gaps) - 10} gaps más.")


def load_config(config_path="config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    # Asegúrate de tener instalado rich: pip install rich
    validator = DataValidator()
    config = load_config()

    # Usamos los símbolos del config.yaml
    validator.run_report(config["symbols"], timeframe_minutes=1)
