from __future__ import annotations

import io
import platform
import sys
from typing import Any, Callable

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.traceback import Traceback

def sys_info() -> dict[str, Any]:
    return {
        "Platform": platform.platform(),
        "Python": sys.version,
        "Commandline": sys.argv,
    }

def get_table(title: str, data: dict[str, Any]) -> Table:
    table = Table(title=title, highlight=True)
    table.add_column(" ", justify="right", style="dim")
    table.add_column("Value")
    for key, value in data.items():
        if not isinstance(value, str):
            value = repr(value)
        table.add_row(key, value)

    return table


def rich_traceback(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        string = io.StringIO()
        width = Console().width
        width = width - 4 if width > 4 else None
        console = Console(file=string, force_terminal=True, width=width)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            tables = [
                get_table(title, data)
                for title, data in [
                    ("System info", sys_info()),
                ]
                if data
            ]
            tables.append(Traceback())

            console.print(Panel(Group(*tables)))
            output = "\n" + string.getvalue()

            try:
                error = e.__class__(output)
            except Exception:
                error = RuntimeError(output)
            raise error from None
        except KeyboardInterrupt as e:
            tables = [
                get_table(title, data)
                for title, data in [
                    ("System info", sys_info()),
                ]
                if data
            ]
            tables.append(Traceback())

            console.print(Panel(Group(*tables)))
            output = "\n" + string.getvalue()

            exit(1)

    return wrapper