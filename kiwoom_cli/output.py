"""Shared console instances for consistent output control.

All modules should import console/err_console from here
instead of creating their own Console instances.
"""

from rich.console import Console

console = Console()
err_console = Console(stderr=True)
