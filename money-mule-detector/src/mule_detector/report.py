"""
report.py
Renders the scored-account list as a Rich terminal table.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

_CONSOLE = Console()

THRESHOLD_RED = 50.0
THRESHOLD_YELLOW = 20.0


def render_table(results: list[dict]) -> None:
    """
    Print a ranked Rich table to stdout.

    Columns: Rank | Account | Score | Reasons
    Rows with score >= 50  are styled bold red.
    Rows with score >= 20  are styled bold yellow.

    Parameters
    ----------
    results : list[dict]
        Output of ``score_accounts`` — must be pre-sorted descending by score.
    """
    table = Table(
        title="[bold]Money Mule Account Detection Results[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="grey50",
        expand=False,
    )
    table.add_column("Rank", justify="right", width=5)
    table.add_column("Account", min_width=12)
    table.add_column("Score", justify="right", width=7)
    table.add_column("Reasons", min_width=40, overflow="fold")

    if not results:
        _CONSOLE.print("[yellow]No suspicious accounts detected.[/yellow]")
        return

    for rank, row in enumerate(results, start=1):
        score = row["score"]

        if score >= THRESHOLD_RED:
            style = "bold red"
        elif score >= THRESHOLD_YELLOW:
            style = "bold yellow"
        else:
            style = ""

        table.add_row(
            Text(str(rank), style=style),
            Text(row["account"], style=style),
            Text(f"{score:.1f}", style=style),
            Text(row["reasons"], style=style),
        )

    _CONSOLE.print(table)
