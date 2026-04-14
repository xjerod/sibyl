from collections.abc import Callable

from sibyl_cli.client import SibylClientError, get_client
from sibyl_cli.common import ELECTRIC_PURPLE, NEON_CYAN, console, error, print_json, run_async


def show_source_status(
    source_id: str,
    *,
    json_out: bool,
    handle_client_error: Callable[[SibylClientError], None],
) -> None:
    @run_async
    async def _status() -> None:
        client = get_client()

        try:
            source = await client.get_crawl_source(source_id)
            status_response = await client.get_crawl_status(source_id)

            if json_out:
                status_data = {
                    "id": source.get("id"),
                    "name": source.get("name"),
                    "url": source.get("url"),
                    "crawl_status": status_response.get(
                        "crawl_status", source.get("crawl_status", "pending")
                    ),
                    "document_count": status_response.get(
                        "document_count", source.get("document_count", 0)
                    ),
                    "chunk_count": status_response.get("chunk_count", source.get("chunk_count", 0)),
                    "current_job_id": status_response.get("current_job_id"),
                    "last_crawled_at": status_response.get("last_crawled_at"),
                    "last_error": status_response.get("last_error"),
                }
                print_json(status_data)
                return

            console.print(f"\n[{ELECTRIC_PURPLE}]Source Status[/{ELECTRIC_PURPLE}]\n")
            console.print(f"  Name: [{NEON_CYAN}]{source.get('name', '')}[/{NEON_CYAN}]")
            console.print(f"  URL: {source.get('url', '-')}")
            console.print(
                f"  Status: {status_response.get('crawl_status', source.get('crawl_status', 'pending'))}"
            )
            console.print(
                f"  Documents: {status_response.get('document_count', source.get('document_count', 0))}"
            )
            console.print(
                f"  Chunks: {status_response.get('chunk_count', source.get('chunk_count', 0))}"
            )
            console.print(
                f"  Last Crawled: {status_response.get('last_crawled_at', source.get('last_crawled_at', 'never')) or 'never'}"
            )

            if status_response.get("current_job_id"):
                console.print(f"  Job ID: {status_response['current_job_id']}")
            if status_response.get("last_error"):
                error(f"Last Error: {status_response['last_error']}")

        except SibylClientError as e:
            handle_client_error(e)

    _status()
