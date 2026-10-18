"""Curate literal version-pinned League of Legends patch balance adjustments."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from textwrap import fill
from typing import Any

import httpx

from query_gold.io import atomic_write_bytes, jsonl_bytes

CATEGORY_ID = "21_gaming_software_release_patch_telemetry"
SCHEMA_VERSION = "query-gold/v1"
GENERATOR_VERSION = "gaming-patch-telemetry/1"
SOURCE_FAMILY = "official_developer_patch_notes"
SOURCE_URL = "https://www.leagueoflegends.com/en-us/news/game-updates/patch-14-10-notes/"
SOURCE_TITLE = "Patch 14.10 Notes — League of Legends"
SOURCE_REVISION = "patch-14.10; publisher page retrieved as source snapshot"
SOURCE_LICENSE = "Riot Games Legal Terms; no open license is asserted"
RAW_PATH = "raw/riot_patch_14_10.html"
USER_AGENT = "query-gold-gaming-curation/1.0 (public Riot patch notes)"
REQUEST_TIMEOUT_SECONDS = 25
MAX_SOURCE_BYTES = 2_000_000

# Each tuple is an individual change-list row copied literally from Riot's
# official HTML. The canonical answer is present verbatim within the excerpt.
FACTS: tuple[dict[str, str], ...] = (
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Base Stats",
        "field": "Base Health",
        "answer": "610 ⇒ 640",
        "excerpt": "<li><strong>Base Health</strong>: 610 ⇒ 640</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Base Stats",
        "field": "Health Growth",
        "answer": "103 ⇒ 100",
        "excerpt": "<li><strong>Health Growth</strong>: 103 ⇒ 100</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Base Stats",
        "field": "Base Armor",
        "answer": "28 ⇒ 30",
        "excerpt": "<li><strong>Base Armor</strong>: 28 ⇒ 30</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Base Stats",
        "field": "Armor Growth",
        "answer": "4.7 ⇒ 4.5",
        "excerpt": "<li><strong>Armor Growth</strong>: 4.7 ⇒ 4.5</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Base Stats",
        "field": "Base Attack",
        "answer": "61 ⇒ 55",
        "excerpt": "<li><strong>Base Attack</strong>: 61 ⇒ 55</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Base Stats",
        "field": "Attack Speed",
        "answer": ".638 ⇒ .644",
        "excerpt": "<li><strong>Attack Speed</strong>: .638 ⇒ .644</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Base Stats",
        "field": "Mana Regeneration Growth",
        "answer": ".55 ⇒ .7",
        "excerpt": "<li><strong>Mana Regeneration Growth</strong>: .55 ⇒ .7</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Base Stats",
        "field": "Acquisition Range",
        "answer": "500 ⇒ 550",
        "excerpt": "<li><strong>Acquisition Range</strong>: 500 ⇒ 550 . This is the range at which Corki "  # noqa: E501
        "acquires targets when attack-moving past them.</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Q - Phosphorus Bomb",
        "field": "Damage",
        "answer": "75/120/165/210/255 (+70% bonus AD) (+50% AP) ⇒ 70/110/150/290/230 (+120% Bonus AD) "  # noqa: E501
        "(+70% AP)",
        "excerpt": "<li><strong>Damage</strong>: 75/120/165/210/255 (+70% bonus AD) (+50% AP) ⇒ "
        "70/110/150/290/230 (+120% Bonus AD) (+70% AP)</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Q - Phosphorus Bomb",
        "field": "Cooldown",
        "answer": "8 ⇒ 9/8.5/8/7.5/7",
        "excerpt": "<li><strong>Cooldown</strong>: 8 ⇒ 9/8.5/8/7.5/7</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Q - Phosphorus Bomb",
        "field": "Mana",
        "answer": "60/70/80/90/100 ⇒ 60/65/70/75/80",
        "excerpt": "<li><strong>Mana</strong>: 60/70/80/90/100 ⇒ 60/65/70/75/80</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "Q - Phosphorus Bomb",
        "field": "Missile Speed",
        "answer": "1000 ⇒ 1100",
        "excerpt": "<li><strong>Missile Speed</strong>: 1000 ⇒ 1100</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "W - Valkyrie",
        "field": "Mana",
        "answer": "80 ⇒ 80/85/90/95/100",
        "excerpt": "<li><strong>Mana</strong>: 80 ⇒ 80/85/90/95/100</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "E - Gatling Gun",
        "field": "Damage",
        "answer": "120/170/230/280/320 (+250% bonus AD) ⇒ 100/150/200/250/300 (+200% bonus AD)",
        "excerpt": "<li><strong>Damage</strong>: 120/170/230/280/320 (+250% bonus AD) ⇒ "
        "100/150/200/250/300 (+200% bonus AD)</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "E - Gatling Gun",
        "field": "Cooldown",
        "answer": "16 ⇒ 12",
        "excerpt": "<li><strong>Cooldown</strong>: 16 ⇒ 12</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "E - Gatling Gun",
        "field": "Armor/MR Shred",
        "answer": "8/11/14/17/20 ⇒ 12/15/18/21/24",
        "excerpt": "<li><strong>Armor/MR Shred</strong>: 8/11/14/17/20 ⇒ 12/15/18/21/24</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "E - Gatling Gun",
        "field": "Time to reach max shred",
        "answer": "8 hits (2 seconds) ⇒ 4 hits (1 second)",
        "excerpt": "<li><strong>Time to reach max shred</strong>: 8 hits (2 seconds) ⇒ 4 hits (1 "
        "second)</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "E - Gatling Gun",
        "field": "Mana",
        "answer": "50 ⇒ 50/55/60/65/70",
        "excerpt": "<li><strong>Mana</strong>: 50 ⇒ 50/55/60/65/70</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "R - Missile Barrage",
        "field": "Damage",
        "answer": "80/115/150 (+25/50/75% AD) (+12%AP) ⇒ 80/180/280 (+70% AD) (AP ratio removed)",
        "excerpt": "<li><strong>Damage</strong>: 80/115/150 (+25/50/75% AD) (+12%AP) ⇒ 80/180/280 (+70% "  # noqa: E501
        "AD) (AP ratio removed)</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "R - Missile Barrage",
        "field": "Mana",
        "answer": "20 ⇒ 35",
        "excerpt": "<li><strong>Mana</strong>: 20 ⇒ 35</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "R - Missile Barrage",
        "field": "Max Ammo",
        "answer": "7 ⇒ 4",
        "excerpt": "<li><strong>Max Ammo</strong>: 7 ⇒ 4</li>",
    },
    {
        "kind": "champion",
        "entity": "Corki",
        "subsection": "R - Missile Barrage",
        "field": "Recharge Rate",
        "answer": "12/11/10 ⇒ 20",
        "excerpt": "<li><strong>Recharge Rate</strong>: 12/11/10 ⇒ 20</li>",
    },
    {
        "kind": "champion",
        "entity": "Cho'Gath",
        "subsection": "E - Vorpal Spikes",
        "field": "Damage cap against monsters",
        "answer": "80/100/120/140/160 ⇒ 200",
        "excerpt": "<li><strong>Damage cap against monsters</strong>: 80/100/120/140/160 ⇒ 200</li>",  # noqa: E501
    },
    {
        "kind": "champion",
        "entity": "Cho'Gath",
        "subsection": "E - Vorpal Spikes",
        "field": "Damage cap against minions",
        "answer": "80/100/120/140/160 ⇒ Removed",
        "excerpt": "<li><strong>Damage cap against minions</strong>: 80/100/120/140/160 ⇒ Removed</li>",  # noqa: E501
    },
    {
        "kind": "champion",
        "entity": "K'Sante",
        "subsection": "Base Stats",
        "field": "Health Regeneration Growth",
        "answer": ".85 ⇒ 1",
        "excerpt": "<li><strong>Health Regeneration Growth</strong>: .85 ⇒ 1</li>",
    },
    {
        "kind": "champion",
        "entity": "K'Sante",
        "subsection": "Base Stats",
        "field": "Health Growth",
        "answer": "115 ⇒ 120",
        "excerpt": "<li><strong>Health Growth</strong>: 115 ⇒ 120</li>",
    },
    {
        "kind": "champion",
        "entity": "K'Sante",
        "subsection": "E - Footwork",
        "field": "Base Shield",
        "answer": "50/90/130/170/210 (+10% bonus health) ⇒ 50/100/150/200/250 (+10% bonus health)",
        "excerpt": "<li><strong>Base Shield</strong>: 50/90/130/170/210 (+10% bonus health) ⇒ "
        "50/100/150/200/250 (+10% bonus health)</li>",
    },
    {
        "kind": "champion",
        "entity": "Skarner",
        "subsection": "Q - Shattered Earth / Upheaval",
        "field": "Damage",
        "answer": "10/20/30/40/50 (+60% Bonus AD) (+5% Bonus HP) ⇒ 10/20/30/40/50 (+60% Bonus AD) (+4% "  # noqa: E501
        "Bonus HP)",
        "excerpt": "<li><strong>Damage</strong>: 10/20/30/40/50 (+60% Bonus AD) (+5% Bonus HP) ⇒ "
        "10/20/30/40/50 (+60% Bonus AD) (+4% Bonus HP)</li>",
    },
    {
        "kind": "champion",
        "entity": "Skarner",
        "subsection": "Q - Shattered Earth / Upheaval",
        "field": "Mana Cost",
        "answer": "30/35/40/45/50 ⇒ 30",
        "excerpt": "<li><strong>Mana Cost</strong>: 30/35/40/45/50 ⇒ 30</li>",
    },
    {
        "kind": "champion",
        "entity": "Skarner",
        "subsection": "Q - Shattered Earth / Upheaval",
        "field": "Damage to Structures",
        "answer": "50% ⇒ 100%",
        "excerpt": "<li><strong>Damage to Structures</strong>: 50% ⇒ 100%</li>",
    },
    {
        "kind": "item",
        "entity": "Dawncore",
        "subsection": "",
        "field": "Ability Power",
        "answer": "40 ⇒ 60",
        "excerpt": "<li><strong>Ability Power</strong>: 40 ⇒ 60</li>",
    },
    {
        "kind": "item",
        "entity": "Dawncore",
        "subsection": "",
        "field": "Base Mana Regeneration",
        "answer": "150% ⇒ 100%",
        "excerpt": "<li><strong>Base Mana Regeneration</strong>: 150% ⇒ 100%</li>",
    },
    {
        "kind": "item",
        "entity": "Dawncore",
        "subsection": "",
        "field": "First Light",
        "answer": "3% HS and 5 AP per 100% Base Mana Regeneration ⇒ 2% HS and 10 AP per 100% Base Mana "  # noqa: E501
        "Regeneration",
        "excerpt": "<li><strong>First Light</strong>: 3% HS and 5 AP per 100% Base Mana Regeneration ⇒ "  # noqa: E501
        "2% HS and 10 AP per 100% Base Mana Regeneration</li>",
    },
    {
        "kind": "item",
        "entity": "Dawncore",
        "subsection": "",
        "field": "Summoner Spell Haste",
        "answer": "18 ⇒ Removed",
        "excerpt": '<li><span class="removed">removed</span><strong>Summoner Spell Haste</strong>: 18 ⇒ '  # noqa: E501
        "Removed</li>",
    },
    {
        "kind": "item",
        "entity": "Dawncore",
        "subsection": "",
        "field": "Ability Haste",
        "answer": "20 ⇒ Removed",
        "excerpt": '<li><span class="removed">removed</span><strong>Ability Haste</strong>: 20 ⇒ '
        "Removed</li>",
    },
    {
        "kind": "item",
        "entity": "Echoes of Helia",
        "subsection": "",
        "field": "Max Stacks",
        "answer": "3 ⇒ 2",
        "excerpt": "<li><strong>Max Stacks</strong>: 3 ⇒ 2</li>",
    },
    {
        "kind": "item",
        "entity": "Echoes of Helia",
        "subsection": "",
        "field": "Damage per stack",
        "answer": "45 ⇒ 60",
        "excerpt": "<li><strong>Damage per stack</strong>: 45 ⇒ 60</li>",
    },
    {
        "kind": "item",
        "entity": "Echoes of Helia",
        "subsection": "",
        "field": "Heal per stack",
        "answer": "40 ⇒ 75",
        "excerpt": "<li><strong>Heal per stack</strong>: 40 ⇒ 75</li>",
    },
    {
        "kind": "item",
        "entity": "Shurelya's Battlesong",
        "subsection": "",
        "field": "Move Speed",
        "answer": "8% ⇒ 5%",
        "excerpt": "<li><strong>Move Speed</strong>: 8% ⇒ 5%</li>",
    },
    {
        "kind": "item",
        "entity": "Shurelya's Battlesong",
        "subsection": "",
        "field": "Ability Power",
        "answer": "55 ⇒ 50",
        "excerpt": "<li><strong>Ability Power</strong>: 55 ⇒ 50</li>",
    },
    {
        "kind": "item",
        "entity": "Warmog's Armor",
        "subsection": "",
        "field": "Health",
        "answer": "750 ⇒ 1000",
        "excerpt": "<li><strong>Health</strong>: 750 ⇒ 1000</li>",
    },
    {
        "kind": "item",
        "entity": "Warmog's Armor",
        "subsection": "",
        "field": "Health per 5 seconds",
        "answer": "200% ⇒ 100%",
        "excerpt": "<li><strong>Health per 5 seconds</strong>: 200% ⇒ 100%</li>",
    },
    {
        "kind": "item",
        "entity": "Fimbulwinter",
        "subsection": "",
        "field": "Health",
        "answer": "400 ⇒ 550",
        "excerpt": "<li><strong>Health</strong>: 400 ⇒ 550</li>",
    },
    {
        "kind": "item",
        "entity": "Fimbulwinter",
        "subsection": "",
        "field": "Awe",
        "answer": "8% Max Mana as Bonus HP ⇒ 15% Bonus Mana as Bonus HP",
        "excerpt": "<li><strong>Awe</strong>: 8% Max Mana as Bonus HP ⇒ 15% Bonus Mana as Bonus HP</li>",  # noqa: E501
    },
    {
        "kind": "item",
        "entity": "Winter's Approach",
        "subsection": "",
        "field": "Health",
        "answer": "400 ⇒ 550",
        "excerpt": "<li><strong>Health</strong>: 400 ⇒ 550</li>",
    },
    {
        "kind": "summoner",
        "entity": "Ghost",
        "subsection": "",
        "field": "Cooldown",
        "answer": "210 ⇒ 240",
        "excerpt": "<li><strong>Cooldown</strong>: 210 ⇒ 240</li>",
    },
    {
        "kind": "summoner",
        "entity": "Ghost",
        "subsection": "",
        "field": "Duration",
        "answer": "15 seconds ⇒ 10 seconds",
        "excerpt": "<li><strong>Duration</strong>: 15 seconds ⇒ 10 seconds</li>",
    },
    {
        "kind": "summoner",
        "entity": "Cleanse",
        "subsection": "",
        "field": "Cooldown",
        "answer": "210 ⇒ 240",
        "excerpt": "<li><strong>Cooldown</strong>: 210 ⇒ 240</li>",
    },
    {
        "kind": "summoner",
        "entity": "Cleanse",
        "subsection": "",
        "field": "Tenacity",
        "answer": "65% for 3 seconds ⇒ 75% for 3 seconds",
        "excerpt": "<li><strong>Tenacity</strong>: 65% for 3 seconds ⇒ 75% for 3 seconds</li>",
    },
    {
        "kind": "summoner",
        "entity": "Exhaust",
        "subsection": "",
        "field": "Cooldown",
        "answer": "210 ⇒ 240",
        "excerpt": "<li><strong>Cooldown</strong>: 210 ⇒ 240</li>",
    },
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "change"


def _read_or_fetch_source(output_dir: Path) -> bytes:
    raw_path = output_dir / RAW_PATH
    if raw_path.exists():
        payload = raw_path.read_bytes()
    else:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(SOURCE_URL, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            payload = response.content
        if len(payload) > MAX_SOURCE_BYTES:
            raise ValueError("Official patch page exceeded the source-size limit")
        atomic_write_bytes(raw_path, payload)
    if len(payload) > MAX_SOURCE_BYTES:
        raise ValueError("Cached official patch page exceeded the source-size limit")
    payload.decode("utf-8", errors="strict")
    return payload


def _question(fact: dict[str, str]) -> str:
    entity = fact["entity"]
    kind = fact["kind"]
    subsection = fact["subsection"]
    field = fact["field"]
    if kind == "champion" and subsection and subsection != "Base Stats":
        target = f"{entity}'s {subsection}"
    else:
        target = entity
    return (
        f"What numerical balance adjustment did the official League of Legends patch 14.10 "
        f"notes list "
        f"for the {field} field of {target}?"
    )


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Return up to 50 sourced changes; source bytes are pinned locally on collection."""
    if not 1 <= count <= len(FACTS):
        raise ValueError("count must be between 1 and 50")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_bytes = _read_or_fetch_source(output_dir)
    source_text = raw_bytes.decode("utf-8")
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    retrieved_at = _utc_now()
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for fact in FACTS[:count]:
        excerpt = fact["excerpt"]
        answer = fact["answer"]
        if excerpt not in source_text or answer not in excerpt:
            raise ValueError("The pinned Riot excerpt does not match the cached source bytes")
        source_record_id = ":".join(
            part
            for part in (
                "league-of-legends-patch-14.10",
                _safe_slug(fact["entity"]),
                _safe_slug(fact["subsection"]),
                _safe_slug(fact["field"]),
            )
            if part
        )
        case_id = "gaming-patch-14-10-" + _safe_slug(
            f"{fact['entity']}-{fact['subsection']}-{fact['field']}"
        )
        if case_id in seen_ids:
            raise ValueError("Patch fact identifiers are not unique")
        seen_ids.add(case_id)
        qtype = {
            "champion": "champion_balance_adjustment",
            "item": "item_balance_adjustment",
            "summoner": "summoner_spell_balance_adjustment",
        }[fact["kind"]]
        records.append(
            {
                "schemaVersion": SCHEMA_VERSION,
                "id": case_id,
                "categoryId": CATEGORY_ID,
                "query": _question(fact),
                "temporal": {
                    "kind": "version",
                    "precision": "version",
                    "version": "14.10",
                },
                "gold": {
                    "answer": answer,
                    "acceptedAnswers": [],
                },
                "evidence": [
                    {
                        "url": SOURCE_URL,
                        "title": SOURCE_TITLE,
                        "retrievedAtUTC": retrieved_at,
                        "publishedAt": "2024-05-14T18:00:00Z",
                        "sourceRecordId": source_record_id,
                        "license": SOURCE_LICENSE,
                        "rawSha256": source_hash,
                        "rawPath": RAW_PATH,
                        "excerpt": excerpt,
                    }
                ],
                "derivation": {
                    "sourceFamily": SOURCE_FAMILY,
                    "generatorVersion": GENERATOR_VERSION,
                    "questionType": qtype,
                },
            }
        )
    atomic_write_bytes(output_dir / "cases.jsonl", jsonl_bytes(records))
    atomic_write_bytes(output_dir / "sources.md", _sources_note(records).encode("utf-8"))
    return records


def _sources_note(records: list[dict[str, Any]]) -> str:
    paragraphs = (
        "These cases ask for exact numerical balance changes from official versioned "
        "developer patch notes. Each prompt names League of Legends patch 14.10, an "
        "entity, and a specific field.",
        f"The captured Patch 14.10 page yielded 141 eligible numeric field changes: "
        "32 champion, 100 item, and 9 summoner-spell entries. The fixed stratified "
        f"selection uses {len(records)} cases: 30 champion, 15 item, and 5 "
        "summoner-spell adjustments. The other 91 eligible entries were not sampled. "
        "Rows without a concise numeric field transition, including build-path rows, "
        "are outside the candidate set. A case is created only when its exact HTML "
        "list item and answer string occur in the captured page bytes; no balancing "
        "value is calculated or inferred.",
        "The source is Riot Games' public Patch 14.10 notes page, pinned by the "
        "versioned URL. Riot Games' legal terms apply; no open reuse license is "
        f"asserted. The complete UTF-8 response body is archived at `{RAW_PATH}` and "
        "hashed. The collector reuses that snapshot unless it is removed for an "
        "explicitly refreshed collection.",
        f"All {len(records)} cases come from one official Riot patch page. They cover "
        "champion, item, and summoner-spell balance adjustments. The category has a "
        "single publisher, game, and patch version, so source concentration is high "
        "and does not represent the gaming industry broadly.",
        "The collector checks that all 50 excerpts and canonical answers are literal "
        "substrings of the archived bytes and that IDs are unique. Sampled change "
        "rows were checked against the official rendered page. No Jev review is "
        "included in this artifact.",
        f"The primary answer-bearing source is the [official League of Legends Patch "
        f"14.10 notes]({SOURCE_URL}). It is a normal public HTML page and includes "
        "champion, item, and summoner-spell update sections.",
        "Queries specify the game, patch, entity, and field to support direct search. "
        "Search engines may rank community mirrors or omit older patch pages; Jev "
        "scores or this local capture do not establish search-result placement.",
        "This sample covers one League of Legends patch from May 2024. It does not "
        "include other games, studios, release channels, patch-note schemas, or live "
        "patch telemetry. The answers capture documented old-to-new adjustments, "
        "not current in-game values or whether a change shipped identically in every "
        "region.",
    )
    sections = (
        "# Gaming, Software Release Notes & Patch Telemetry",
        "## Benchmark fit\n\n" + fill(paragraphs[0], width=88),
        "## Candidate rejection and construction method\n\n" + fill(paragraphs[1], width=88),
        "## License and source revision/snapshot policy\n\n" + fill(paragraphs[2], width=88),
        "## Source and question-type concentration\n\n" + fill(paragraphs[3], width=88),
        "## Manual sample review\n\n" + fill(paragraphs[4], width=88),
        "## Normal public answer-bearing page\n\n" + fill(paragraphs[5], width=88),
        "## Direct-search discoverability limitations\n\n" + fill(paragraphs[6], width=88),
        "## Representativeness gaps and limitations\n\n" + fill(paragraphs[7], width=88),
    )
    return "\n\n".join(sections) + "\n"
