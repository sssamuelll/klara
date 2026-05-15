"""multilanguage: user target_language + generic story/vocab fields

Revision ID: 20260515_0003
Revises: 20260502_0002
Create Date: 2026-05-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_0003"
down_revision: Union[str, None] = "20260502_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "target_language",
            sa.String(8),
            nullable=False,
            server_default="de",
        ),
    )
    op.add_column(
        "users",
        sa.Column("learning_context", sa.Text(), nullable=True),
    )

    # --- stories -------------------------------------------------------------
    op.add_column(
        "stories",
        sa.Column(
            "target_language",
            sa.String(8),
            nullable=False,
            server_default="de",
        ),
    )
    op.add_column(
        "stories",
        sa.Column(
            "native_language",
            sa.String(8),
            nullable=False,
            server_default="es",
        ),
    )
    # Backfill story content: rename keys de->target, es->native, q_de/q_es/options_de.
    # Use COALESCE(..., '') so the target/native keys always exist as strings —
    # StorySentenceOut requires them non-null, and jsonb_strip_nulls would have
    # dropped a missing key entirely.
    op.execute(
        """
        UPDATE stories SET content = jsonb_build_object(
            'sentences', COALESCE(
                (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'target', COALESCE(s->>'de', ''),
                            'native', COALESCE(s->>'es', ''),
                            'new_words', COALESCE(s->'new_words', '[]'::jsonb)
                        )
                    )
                    FROM jsonb_array_elements(COALESCE(content->'sentences', '[]'::jsonb)) AS s
                ),
                '[]'::jsonb
            ),
            'comprehension_questions', COALESCE(
                (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'q_target', COALESCE(q->>'q_de', ''),
                            'q_native', COALESCE(q->>'q_es', ''),
                            'options_target', COALESCE(q->'options_de', '[]'::jsonb),
                            'correct_index', COALESCE((q->>'correct_index')::int, 0)
                        )
                    )
                    FROM jsonb_array_elements(COALESCE(content->'comprehension_questions', '[]'::jsonb)) AS q
                ),
                '[]'::jsonb
            )
        )
        """
    )
    # Drop server_default after backfill so future inserts must be explicit.
    op.alter_column("stories", "target_language", server_default=None)
    op.alter_column("stories", "native_language", server_default=None)

    # --- vocab_items ---------------------------------------------------------
    op.add_column(
        "vocab_items",
        sa.Column(
            "translations",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # Backfill translations from translation_es / translation_en (skip nulls).
    op.execute(
        """
        UPDATE vocab_items
        SET translations = translations || jsonb_strip_nulls(jsonb_build_object(
            'es', translation_es,
            'en', translation_en
        ))
        """
    )
    op.alter_column("vocab_items", "example_de", new_column_name="example_target")
    op.drop_column("vocab_items", "translation_es")
    op.drop_column("vocab_items", "translation_en")
    op.drop_column("vocab_items", "example_es")


def downgrade() -> None:
    # --- vocab_items ---------------------------------------------------------
    op.add_column(
        "vocab_items",
        sa.Column("translation_es", sa.String(255), nullable=True),
    )
    op.add_column(
        "vocab_items",
        sa.Column("translation_en", sa.String(255), nullable=True),
    )
    op.add_column(
        "vocab_items",
        sa.Column("example_es", sa.String(500), nullable=True),
    )
    op.execute(
        """
        UPDATE vocab_items SET
            translation_es = translations->>'es',
            translation_en = translations->>'en'
        """
    )
    op.alter_column("vocab_items", "example_target", new_column_name="example_de")
    op.drop_column("vocab_items", "translations")

    # --- stories -------------------------------------------------------------
    op.execute(
        """
        UPDATE stories SET content = jsonb_build_object(
            'sentences', COALESCE(
                (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'de', COALESCE(s->>'target', ''),
                            'es', COALESCE(s->>'native', ''),
                            'new_words', COALESCE(s->'new_words', '[]'::jsonb)
                        )
                    )
                    FROM jsonb_array_elements(COALESCE(content->'sentences', '[]'::jsonb)) AS s
                ),
                '[]'::jsonb
            ),
            'comprehension_questions', COALESCE(
                (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'q_de', COALESCE(q->>'q_target', ''),
                            'q_es', COALESCE(q->>'q_native', ''),
                            'options_de', COALESCE(q->'options_target', '[]'::jsonb),
                            'correct_index', COALESCE((q->>'correct_index')::int, 0)
                        )
                    )
                    FROM jsonb_array_elements(COALESCE(content->'comprehension_questions', '[]'::jsonb)) AS q
                ),
                '[]'::jsonb
            )
        )
        """
    )
    op.drop_column("stories", "native_language")
    op.drop_column("stories", "target_language")

    # --- users ---------------------------------------------------------------
    op.drop_column("users", "learning_context")
    op.drop_column("users", "target_language")
