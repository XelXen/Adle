"""Passages for a lesson are found by the words of a concept in any of their forms.

Revision: 0009
Previous: 0008
Created:  2026-11-21

A second full-text index over a course's passages, with the Porter stemmer in front of the
tokenizer (ADR-041): "weights" finds "weight", "learned" finds "learning". The passages
grounding a lesson or an answer are looked up in it. Searching the materials keeps the
index it had, because there the last word is matched as a prefix while it is typed, and a
stemmed index cannot match the beginning of a word ("learni" is no stem of "learning").

Both are indexes only: the text lives once, in ``source_chunks``, and the new one is built
from it here and kept in step by triggers of its own.
"""

from __future__ import annotations

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIRTUAL TABLE source_chunks_stems USING fts5(
            text,
            content='source_chunks',
            content_rowid='id',
            tokenize='porter unicode61 remove_diacritics 2'
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_chunks_stems_after_insert AFTER INSERT ON source_chunks BEGIN
            INSERT INTO source_chunks_stems(rowid, text) VALUES (new.id, new.text);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_chunks_stems_after_delete AFTER DELETE ON source_chunks BEGIN
            INSERT INTO source_chunks_stems(source_chunks_stems, rowid, text)
            VALUES ('delete', old.id, old.text);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_chunks_stems_after_update AFTER UPDATE OF text ON source_chunks
        BEGIN
            INSERT INTO source_chunks_stems(source_chunks_stems, rowid, text)
            VALUES ('delete', old.id, old.text);
            INSERT INTO source_chunks_stems(rowid, text) VALUES (new.id, new.text);
        END
        """
    )
    op.execute("INSERT INTO source_chunks_stems(source_chunks_stems) VALUES ('rebuild')")


def downgrade() -> None:
    op.execute("DROP TRIGGER source_chunks_stems_after_update")
    op.execute("DROP TRIGGER source_chunks_stems_after_delete")
    op.execute("DROP TRIGGER source_chunks_stems_after_insert")
    op.execute("DROP TABLE source_chunks_stems")
