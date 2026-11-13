from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo

import yaml


CATALOGUE_PLACEHOLDER = "<!-- PROCEDURE_CATALOGUE -->"
PERTH_TIME_ZONE = ZoneInfo("Australia/Perth")
REQUIRED_FIELDS = (
    "document_id",
    "title",
    "topic",
    "version",
    "owner",
    "last_reviewed",
    "next_review_due",
)


class ProcedureMetadataError(ValueError):
    pass


@dataclass(frozen=True)
class Procedure:
    source_path: Path
    relative_path: PurePosixPath
    document_id: str
    title: str
    topic: str
    version: str
    owner: str
    last_reviewed: date
    next_review_due: date


_procedures: dict[str, Procedure] = {}
_build_date: date | None = None


def parse_iso_date(value: object, field: str, source_path: Path) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ProcedureMetadataError(
                f"{source_path}: '{field}' must use YYYY-MM-DD format"
            ) from error
        if value != parsed.isoformat():
            raise ProcedureMetadataError(
                f"{source_path}: '{field}' must use YYYY-MM-DD format"
            )
        return parsed
    raise ProcedureMetadataError(
        f"{source_path}: '{field}' must use YYYY-MM-DD format"
    )


def format_australian_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def local_build_date(now: datetime | None = None) -> date:
    if now is None:
        return datetime.now(PERTH_TIME_ZONE).date()
    if now.tzinfo is None:
        now = now.replace(tzinfo=PERTH_TIME_ZONE)
    return now.astimezone(PERTH_TIME_ZONE).date()


def is_overdue(next_review_due: date, today: date) -> bool:
    return today > next_review_due


def read_front_matter(source_path: Path) -> dict[str, Any]:
    lines = source_path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    try:
        closing_index = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration as error:
        raise ProcedureMetadataError(
            f"{source_path}: YAML front matter is not closed"
        ) from error

    metadata = yaml.safe_load("\n".join(lines[1:closing_index])) or {}
    if not isinstance(metadata, dict):
        raise ProcedureMetadataError(
            f"{source_path}: YAML front matter must be a mapping"
        )
    return metadata


def load_procedure(source_path: Path, docs_dir: Path) -> Procedure | None:
    metadata = read_front_matter(source_path)
    procedure_markers = set(REQUIRED_FIELDS) - {"title"}
    if not procedure_markers.intersection(metadata):
        return None

    missing = [field for field in REQUIRED_FIELDS if not metadata.get(field)]
    if missing:
        fields = ", ".join(missing)
        raise ProcedureMetadataError(
            f"{source_path}: missing required procedure metadata: {fields}"
        )

    relative_path = PurePosixPath(source_path.relative_to(docs_dir).as_posix())
    return Procedure(
        source_path=source_path,
        relative_path=relative_path,
        document_id=str(metadata["document_id"]).strip(),
        title=str(metadata["title"]).strip(),
        topic=str(metadata["topic"]).strip(),
        version=str(metadata["version"]).strip(),
        owner=str(metadata["owner"]).strip(),
        last_reviewed=parse_iso_date(
            metadata["last_reviewed"], "last_reviewed", source_path
        ),
        next_review_due=parse_iso_date(
            metadata["next_review_due"], "next_review_due", source_path
        ),
    )


def discover_procedures(docs_dir: Path) -> list[Procedure]:
    procedures = []
    for source_path in sorted(docs_dir.rglob("*.md")):
        procedure = load_procedure(source_path, docs_dir)
        if procedure is not None:
            procedures.append(procedure)
    return procedures


def render_status(procedure: Procedure, today: date) -> str:
    if is_overdue(procedure.next_review_due, today):
        return '<span class="review-status review-status--overdue">Overdue</span>'
    return '<span class="review-status review-status--current">Current</span>'


def render_metadata_panel(procedure: Procedure, today: date) -> str:
    values = {
        "owner": escape(procedure.owner),
        "version": escape(procedure.version),
        "last_reviewed": format_australian_date(procedure.last_reviewed),
        "next_review_due": format_australian_date(procedure.next_review_due),
    }
    return f"""<section class="procedure-meta" aria-label="Document control">
  <dl>
    <div><dt>Owner</dt><dd>{values['owner']}</dd></div>
    <div><dt>Version</dt><dd>{values['version']}</dd></div>
    <div><dt>Last reviewed</dt><dd>{values['last_reviewed']}</dd></div>
    <div><dt>Next review due</dt><dd>{values['next_review_due']}</dd></div>
  </dl>
  <p class="procedure-meta__status"><span>Review status</span>{render_status(procedure, today)}</p>
</section>"""


def inject_metadata_panel(markdown: str, panel: str) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            lines[index + 1:index + 1] = ["", panel]
            return "\n".join(lines)
    return f"{panel}\n\n{markdown}"


def render_catalogue(procedures: list[Procedure], today: date) -> str:
    grouped: dict[str, list[Procedure]] = defaultdict(list)
    for procedure in procedures:
        grouped[procedure.topic].append(procedure)

    sections = ['<div class="procedure-catalogue">']
    for topic in sorted(grouped, key=str.casefold):
        sections.append(f"  <h2>{escape(topic)}</h2>")
        sections.append("  <ul>")
        for procedure in sorted(grouped[topic], key=lambda item: item.title.casefold()):
            path = procedure.relative_path.with_suffix("").as_posix() + "/"
            sections.extend(
                (
                    "    <li>",
                    f'      <a href="{escape(path, quote=True)}">{escape(procedure.title)}</a>',
                    '      <span class="procedure-catalogue__details">',
                    f"        {escape(procedure.document_id)} · Version {escape(procedure.version)} · Owner: {escape(procedure.owner)}",
                    "      </span>",
                    f"      {render_status(procedure, today)}",
                    "    </li>",
                )
            )
        sections.append("  </ul>")
    sections.append("</div>")
    return "\n".join(sections)


def on_config(config: Any) -> Any:
    global _build_date, _procedures

    docs_dir = Path(config.docs_dir)
    procedures = discover_procedures(docs_dir)
    _procedures = {
        procedure.relative_path.as_posix(): procedure for procedure in procedures
    }
    _build_date = local_build_date()
    return config


def on_page_markdown(markdown: str, page: Any, **_: Any) -> str:
    today = _build_date or local_build_date()
    source_uri = page.file.src_uri

    if source_uri == "index.md":
        if CATALOGUE_PLACEHOLDER not in markdown:
            raise ProcedureMetadataError(
                f"index.md: missing catalogue placeholder {CATALOGUE_PLACEHOLDER}"
            )
        return markdown.replace(
            CATALOGUE_PLACEHOLDER,
            render_catalogue(list(_procedures.values()), today),
        )

    procedure = _procedures.get(source_uri)
    if procedure is None:
        return markdown
    return inject_metadata_panel(markdown, render_metadata_panel(procedure, today))