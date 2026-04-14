from collections.abc import Callable, Sequence

from sibyl_cli.common import console, create_panel, create_table, print_json


def maybe_print_json(data: object, *, json_out: bool) -> bool:
    if not json_out:
        return False
    print_json(data)
    return True


def render_table_or_empty(
    *,
    title: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[str]],
    empty_message: str,
    empty_printer: Callable[[str], None],
    footer: str | None = None,
) -> None:
    if not rows:
        empty_printer(empty_message)
        return

    table = create_table(title, *columns)
    for row in rows:
        table.add_row(*row)
    console.print(table)

    if footer:
        console.print(footer)


def render_detail_panel(
    *,
    title: str,
    lines: Sequence[str],
    footer: str | None = None,
) -> None:
    console.print(create_panel("\n".join(lines), title=title))
    if footer:
        console.print(footer)
