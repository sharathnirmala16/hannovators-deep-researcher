"""Write demo source files for the frontend fixtures, so the PDF viewer works in sample mode.

For each source in `frontend/src/test/fixtures/workspace.*.json` this writes, under
`data/workspaces/<workspace_id>/sources/<source_id>/`:

- `raw.pdf`: a small PDF with the source title and each claim quote placed at its highlight rects,
- `highlighted.pdf`: `raw.pdf` with the fixture highlights applied,
- `snapshot.md`: for web sources, the title and the claim quotes.

Run: `uv run python scripts/seed_demo_files.py`
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pymupdf

from hannovators_deep_researcher.configuration.database import project_root
from hannovators_deep_researcher.services.documents import files
from hannovators_deep_researcher.services.documents.highlighter import (
    HighlightSpec,
    write_highlighted_pdf,
)

FIXTURES = project_root() / "frontend" / "src" / "test" / "fixtures"
MIN_PAGES = 2
PAGE_WIDTH, PAGE_HEIGHT = 612, 792
MARGIN = 72

Json = dict[str, Any]


def _place_quote(page: pymupdf.Page, rects: list[list[float]], quote: str) -> None:
    """Write the quote inside the highlight area at the largest font size that fits."""

    box = pymupdf.Rect(rects[0][0], rects[0][1], rects[0][2], rects[-1][3])  # type: ignore[no-untyped-call]
    for size in (9.0, 8.0, 7.0, 6.0, 5.0, 4.0):
        # insert_textbox writes nothing and returns a negative value when the text overflows.
        if page.insert_textbox(box, quote, fontsize=size, fontname="helv") >= 0:
            return


def _build_pdf(source: Json, highlights: list[Json], claims: dict[str, Json]) -> bytes:
    pages = max([MIN_PAGES, *(int(item["page"]) for item in highlights)])
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    for number in range(1, pages + 1):
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_text((MARGIN, 40), f"Demo copy, page {number} of {pages}", fontsize=8)
        if number == 1:
            header = pymupdf.Rect(MARGIN, 60, PAGE_WIDTH - MARGIN, 140)  # type: ignore[no-untyped-call]
            page.insert_textbox(header, source["title"], fontsize=15, fontname="hebo")
    placed: set[tuple[int, str]] = set()
    for item in highlights:
        quote = claims.get(item["claim_id"], {}).get("quote")
        key = (int(item["page"]), json.dumps(item["rects"]))
        if not quote or not item["rects"] or key in placed:
            continue
        placed.add(key)
        _place_quote(document[key[0] - 1], item["rects"], quote)
    data: bytes = document.tobytes()  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]
    return data


def _snapshot(source: Json, claims: list[Json]) -> str:
    quotes = "\n\n".join(claim["quote"] for claim in claims if claim.get("quote"))
    return f"# {source['title']}\n\n{source.get('url') or ''}\n\n{quotes}\n"


def _seed_source(
    workspace_id: str, source: Json, highlights: list[Json], claims: dict[str, Json]
) -> None:
    raw_url: str = source.get("raw_url") or ""
    if raw_url.endswith(files.SNAPSHOT_MD):
        own = [claim for claim in claims.values() if claim["source_id"] == source["id"]]
        path = files.source_path(workspace_id, source["id"], files.SNAPSHOT_MD)
        files.write_bytes(path, _snapshot(source, own).encode("utf-8"))
        return
    if not raw_url.endswith(files.RAW_PDF):
        return
    raw = files.write_bytes(
        files.source_path(workspace_id, source["id"], files.RAW_PDF),
        _build_pdf(source, highlights, claims),
    )
    specs = [
        HighlightSpec(page=item["page"], rects=item["rects"], color=item["color"])
        for item in highlights
        if item["rects"]
    ]
    if source.get("highlighted_url") or specs:
        highlighted = files.resolve_data_path(
            files.source_path(workspace_id, source["id"], files.HIGHLIGHTED_PDF)
        )
        write_highlighted_pdf(raw, highlighted, specs)


def seed_fixture(fixture: Path) -> int:
    state: Json = json.loads(fixture.read_text(encoding="utf-8"))
    workspace_id: str = state["workspace"]["id"]
    claims = {claim["id"]: claim for claim in state["claims"]}
    by_source: defaultdict[str, list[Json]] = defaultdict(list)
    for item in state["highlights"]:
        by_source[item["source_id"]].append(item)
    for source in state["sources"]:
        _seed_source(workspace_id, source, by_source[source["id"]], claims)
    return len(state["sources"])


def main() -> None:
    for fixture in sorted(FIXTURES.glob("workspace.*.json")):
        count = seed_fixture(fixture)
        print(f"{fixture.name}: wrote files for {count} sources")


if __name__ == "__main__":
    main()
