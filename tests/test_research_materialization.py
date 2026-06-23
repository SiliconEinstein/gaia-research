"""Tests for research materialization payload normalization."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from gaia_research.research_materialization import _lkm_materialized_payload


def test_lkm_materialized_payload_indexes_claim_and_question_symbol_refs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "paper-pkg-gaia"
    src = root / "src" / "paper_pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import claim, question\n\n"
        "claim_a = claim(\n"
        "    'Claim A.',\n"
        "    metadata={"
        "'provider': 'lkm', "
        "'source_ref': 'lkm:bohrium:paper:P1', "
        "'node_id': 'global_claim_a', "
        "'local_id': 'claim_a'"
        "},\n"
        ")\n"
        "question_b = question(\n"
        "    'Question B?',\n"
        "    metadata={"
        "'provider': 'lkm', "
        "'source_ref': 'lkm:bohrium:paper:P1', "
        "'node_id': 'global_question_b', "
        "'local_id': 'question_b'"
        "},\n"
        ")\n",
        encoding="utf-8",
    )
    materialized = SimpleNamespace(
        source_ref="lkm:bohrium:paper:P1",
        root=root,
        dist_name="paper-pkg-gaia",
        import_name="paper_pkg",
        claim_count=1,
        question_count=1,
        dependency_count=0,
    )

    payload = _lkm_materialized_payload(materialized)

    assert payload["symbol_refs"] == [
        {
            "node_id": "global_claim_a",
            "local_id": "claim_a",
            "kind": "claim",
            "symbol": "claim_a",
            "ref": "lkm:paper_pkg::claim_a",
            "source_ref": "lkm:bohrium:paper:P1",
        },
        {
            "node_id": "global_question_b",
            "local_id": "question_b",
            "kind": "question",
            "symbol": "question_b",
            "ref": "lkm:paper_pkg::question_b",
            "source_ref": "lkm:bohrium:paper:P1",
        },
    ]
