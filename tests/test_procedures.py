from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath

from hooks.procedures import (
    Procedure,
    ProcedureMetadataError,
    format_australian_date,
    inject_metadata_panel,
    is_overdue,
    load_procedure,
    local_build_date,
    parse_iso_date,
    render_catalogue,
    render_metadata_panel,
)


class ProcedureHookTests(unittest.TestCase):
    def procedure(self, **overrides: object) -> Procedure:
        values: dict[str, object] = {
            "source_path": Path("docs/field-sampling/example.md"),
            "relative_path": PurePosixPath("field-sampling/example.md"),
            "document_id": "SOP-001",
            "title": "Example Procedure",
            "topic": "Field sampling",
            "version": "1.0",
            "owner": "Field Operations",
            "last_reviewed": date(2026, 3, 14),
            "next_review_due": date(2026, 9, 14),
        }
        values.update(overrides)
        return Procedure(**values)  # type: ignore[arg-type]

    def test_overdue_only_after_due_date(self) -> None:
        due = date(2026, 3, 14)
        self.assertFalse(is_overdue(due, date(2026, 3, 13)))
        self.assertFalse(is_overdue(due, due))
        self.assertTrue(is_overdue(due, date(2026, 3, 15)))

    def test_local_build_date_uses_perth_time(self) -> None:
        utc_time = datetime(2026, 3, 14, 16, 30, tzinfo=timezone.utc)
        self.assertEqual(local_build_date(utc_time), date(2026, 3, 15))

    def test_dates_accept_yaml_date_objects_and_strict_iso_strings(self) -> None:
        source = Path("procedure.md")
        self.assertEqual(
            parse_iso_date(date(2026, 3, 14), "next_review_due", source),
            date(2026, 3, 14),
        )
        self.assertEqual(
            parse_iso_date("2026-03-14", "next_review_due", source),
            date(2026, 3, 14),
        )
        with self.assertRaisesRegex(ProcedureMetadataError, "YYYY-MM-DD"):
            parse_iso_date("14/03/2026", "next_review_due", source)

    def test_australian_date_format_has_day_before_month(self) -> None:
        self.assertEqual(format_australian_date(date(2025, 3, 14)), "14 March 2025")

    def test_missing_required_metadata_names_the_file_and_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            docs_dir = Path(temporary_directory)
            source = docs_dir / "procedure.md"
            source.write_text(
                "---\ndocument_id: SOP-001\ntitle: Example\n---\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ProcedureMetadataError, "missing required procedure metadata"
            ) as context:
                load_procedure(source, docs_dir)

            self.assertIn("topic", str(context.exception))
            self.assertIn(str(source), str(context.exception))

    def test_procedure_without_document_id_is_not_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            docs_dir = Path(temporary_directory)
            source = docs_dir / "procedure.md"
            source.write_text(
                "---\n"
                "title: Example\n"
                "topic: Field sampling\n"
                'version: "1.0"\n'
                "owner: Field Operations\n"
                "last_reviewed: 2026-03-14\n"
                "next_review_due: 2027-03-14\n"
                "---\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProcedureMetadataError, "document_id"):
                load_procedure(source, docs_dir)

    def test_metadata_panel_escapes_front_matter_values(self) -> None:
        procedure = self.procedure(owner='<script>alert("x")</script>')
        panel = render_metadata_panel(procedure, date(2026, 9, 15))

        self.assertNotIn("<script>", panel)
        self.assertIn("&lt;script&gt;", panel)
        self.assertIn("Overdue", panel)

    def test_panel_is_inserted_after_page_heading(self) -> None:
        result = inject_metadata_panel("# Example\n\nBody", "<section>Meta</section>")
        self.assertEqual(
            result,
            "# Example\n\n<section>Meta</section>\n\nBody",
        )

    def test_catalogue_groups_topics_and_sorts_titles(self) -> None:
        procedures = [
            self.procedure(title="Zinc sampling"),
            self.procedure(
                title="Acid sulfate soil",
                relative_path=PurePosixPath("field-sampling/acid.md"),
            ),
            self.procedure(
                title="Laboratory receipt",
                topic="Laboratory",
                relative_path=PurePosixPath("laboratory/receipt.md"),
            ),
        ]
        catalogue = render_catalogue(procedures, date(2026, 9, 14))

        self.assertLess(catalogue.index("Field sampling"), catalogue.index("Laboratory"))
        self.assertLess(catalogue.index("Acid sulfate soil"), catalogue.index("Zinc sampling"))
        self.assertIn('href="field-sampling/acid/"', catalogue)
        self.assertIn("Current", catalogue)


if __name__ == "__main__":
    unittest.main()