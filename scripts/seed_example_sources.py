#!/usr/bin/env python3
"""Naplní vybranú pracovnú plochu ukážkovými zdrojmi a prílohami.

Skript je opakovateľný: používa stabilné identifikátory a nepridá tie isté
ukážky viackrát. Prílohy vznikajú priamo v bezpečnom úložisku aplikácie.
"""

from __future__ import annotations

import argparse
import io
import sqlite3
import sys
import uuid
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_NAMESPACE = uuid.UUID("12b998f9-26e8-4cc1-a507-7fbb2ad8c040")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import Database
from backend.files import FileStore


def stable_id(name: str) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, name))


def make_pdf() -> bytes:
    stream = b"BT /F1 20 Tf 72 720 Td (Poznamkovnik - ukazkovy odborny clanok) Tj ET\nBT /F1 12 Tf 72 684 Td (Tato kratka PDF priloha sluzi na overenie nahladov a vazieb zdrojov.) Tj ET\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, content in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode())
        document.extend(content)
        document.extend(b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(document)


def make_docx() -> bytes:
    document_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body><w:p><w:r><w:t>Ukazkovy pracovny brief</w:t></w:r></w:p><w:p><w:r><w:t>Tato DOCX priloha sluzi na overenie nahravania a stahovania suborov.</w:t></w:r></w:p><w:sectPr/></w:body></w:document>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/></Types>""")
        archive.writestr("_rels/.rels", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/></Relationships>""")
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def make_epub() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", """<?xml version=\"1.0\"?><container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\"><rootfiles><rootfile full-path=\"OEBPS/content.opf\" media-type=\"application/oebps-package+xml\"/></rootfiles></container>""")
        archive.writestr("OEBPS/content.opf", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" unique-identifier=\"book-id\"><metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\"><dc:identifier id=\"book-id\">ukazkovy-epub</dc:identifier><dc:title>Ukazkova elektronicka kniha</dc:title><dc:language>sk</dc:language></metadata><manifest><item id=\"chapter\" href=\"text/chapter.xhtml\" media-type=\"application/xhtml+xml\"/></manifest><spine><itemref idref=\"chapter\"/></spine></package>""")
        archive.writestr("OEBPS/text/chapter.xhtml", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><html xmlns=\"http://www.w3.org/1999/xhtml\"><head><title>Ukazka</title></head><body><h1>Ukazkova elektronicka kniha</h1><p>Krátky EPUB subor na overenie priloh.</p></body></html>""")
    return buffer.getvalue()


def make_xlsx() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/><Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/></Types>""")
        archive.writestr("_rels/.rels", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/></Relationships>""")
        archive.writestr("xl/workbook.xml", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets><sheet name=\"Zaznamy\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>""")
        archive.writestr("xl/_rels/workbook.xml.rels", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/><Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/></Relationships>""")
        archive.writestr("xl/styles.xml", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><fonts count=\"1\"><font><sz val=\"11\"/><name val=\"Calibri\"/></font></fonts><fills count=\"1\"><fill><patternFill patternType=\"none\"/></fill></fills><borders count=\"1\"><border/></borders><cellStyleXfs count=\"1\"><xf/></cellStyleXfs><cellXfs count=\"1\"><xf xfId=\"0\"/></cellXfs></styleSheet>""")
        archive.writestr("xl/worksheets/sheet1.xml", """<?xml version=\"1.0\" encoding=\"UTF-8\"?><worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData><row r=\"1\"><c r=\"A1\" t=\"inlineStr\"><is><t>Datum</t></is></c><c r=\"B1\" t=\"inlineStr\"><is><t>Minuty sustredenia</t></is></c></row><row r=\"2\"><c r=\"A2\" t=\"inlineStr\"><is><t>2026-07-20</t></is></c><c r=\"B2\"><v>85</v></c></row><row r=\"3\"><c r=\"A3\" t=\"inlineStr\"><is><t>2026-07-21</t></is></c><c r=\"B3\"><v>110</v></c></row></sheetData></worksheet>""")
    return buffer.getvalue()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pridá ukážkové zdroje do Poznámkovníka.")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--user", default="", help="Meno používateľa; pri jednom účte netreba zadávať.")
    parser.add_argument("--library", default="", help="Názov knižnice na prepojenie ukážok.")
    return parser.parse_args()


def find_user(connection: sqlite3.Connection, username: str) -> tuple[str, str]:
    rows = connection.execute("SELECT id, username FROM users ORDER BY created_at").fetchall()
    if username:
        row = next((item for item in rows if item[1].casefold() == username.casefold()), None)
        if not row:
            raise SystemExit(f"Používateľ {username!r} neexistuje.")
        return row[0], row[1]
    if len(rows) != 1:
        raise SystemExit("Zadaj --user, pretože databáza obsahuje viac používateľov.")
    return rows[0][0], rows[0][1]


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    database = Database(data_dir / "poznamkovnik.sqlite3")
    database.initialize()
    files = FileStore(data_dir / "files")

    with database.connect() as connection:
        user_id, username = find_user(connection, args.user)
        library_row = None
        if args.library:
            library_row = connection.execute(
                "SELECT id, name FROM libraries WHERE user_id = ? AND name = ? COLLATE NOCASE",
                (user_id, args.library),
            ).fetchone()
            if not library_row:
                raise SystemExit(f"Knižnica {args.library!r} používateľa {username!r} neexistuje.")
        element_ids = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT title, id FROM elements WHERE library_id = ? AND type IN ('note', 'article')",
                (library_row[0],),
            )
        } if library_row else {}

    examples = [
        {
            "key": "focus-paper",
            "title": "Ukážka: odborný článok o sústredení",
            "kind": "article",
            "description": "Skúšobný odborný článok s krátkou PDF prílohou. Slúži na testovanie citácií, náhľadu a prepojení.",
            "metadata": {"author": "Ukážkový autor", "year": "2026", "url": "https://example.org/focus-paper"},
            "files": [("ukazkovy-clanok-o-sustredeni.pdf", make_pdf(), "application/pdf")],
            "libraryNote": "Podklad na skúšanie citácií.",
            "links": [("PPP", "citation", "s. 1–2")],
        },
        {
            "key": "deep-work-book",
            "title": "Ukážka: elektronická kniha o práci",
            "kind": "book",
            "description": "Malá EPUB príloha na skúšanie práce s elektronickou knihou v katalógu zdrojov.",
            "metadata": {"author": "Ukážkový autor", "year": "2026", "url": "https://example.org/ukazkova-kniha"},
            "files": [("ukazkova-elektronicka-kniha.epub", make_epub(), "application/epub+zip")],
            "libraryNote": "Čítanie na neskôr.",
            "links": [("CCC", "reference", "kapitola 1")],
        },
        {
            "key": "project-brief",
            "title": "Ukážka: pracovný brief",
            "kind": "attachment",
            "description": "Pracovný brief v DOCX aj Markdown variante. Môže slúžiť ako vzor pri pripájaní vlastných dokumentov.",
            "metadata": {"author": "Michal", "year": "2026", "url": ""},
            "files": [
                ("ukazkovy-pracovny-brief.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                ("ukazkovy-pracovny-brief.md", b"# Ukazkovy pracovny brief\n\n- ciel: overit prilohy\n- stav: pripraveny na testovanie\n", "text/markdown"),
            ],
            "libraryNote": "Východisko pre článok.",
            "links": [("CCC", "evidence", "časť: Zámer")],
        },
        {
            "key": "focus-dataset",
            "title": "Ukážka: denné záznamy sústredenia",
            "kind": "dataset",
            "description": "Krátka CSV a XLSX tabuľka na skúšanie zdrojov dát a neskorších štatistík.",
            "metadata": {"author": "Poznámkovník", "year": "2026", "url": ""},
            "files": [
                ("denne-zaznamy-sustredenia.csv", b"datum,minuty_sustredenia\n2026-07-20,85\n2026-07-21,110\n", "text/csv"),
                ("denne-zaznamy-sustredenia.xlsx", make_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ],
            "libraryNote": "Dáta na skúšanie štatistík.",
            "links": [("PPP", "evidence", "záznamy 20.–21. 7.")],
        },
        {
            "key": "zotero-guide",
            "title": "Ukážka: webový návod k správe zdrojov",
            "kind": "web",
            "description": "Webový zdroj bez prílohy. Overuje prácu s adresou URL a spätnými väzbami.",
            "metadata": {"author": "Ukážková redakcia", "year": "2026", "url": "https://www.zotero.org/support/adding_items_to_zotero"},
            "files": [],
            "libraryNote": "Návod k organizácii bibliografie.",
            "links": [("CCC", "reference", "sekcia: pridávanie položiek")],
        },
    ]

    created_sources = 0
    created_files = 0
    created_links = 0
    for example in examples:
        source_id = stable_id(f"source:{example['key']}")
        with database.connect() as connection:
            exists = connection.execute("SELECT 1 FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not exists:
            database.create_source(
                user_id,
                {
                    "id": source_id,
                    "title": example["title"],
                    "kind": example["kind"],
                    "description": example["description"],
                    "metadata": example["metadata"],
                },
            )
            created_sources += 1

        if library_row:
            database.link_source_library(user_id, source_id, library_row[0], example["libraryNote"])

        for filename, content, mime_type in example["files"]:
            file_id = stable_id(f"file:{example['key']}:{filename}")
            with database.connect() as connection:
                exists = connection.execute("SELECT 1 FROM source_files WHERE id = ?", (file_id,)).fetchone()
            if not exists:
                file_info = files.store_upload(io.BytesIO(content), filename, mime_type)
                database.add_source_file(user_id, source_id, file_id, file_info)
                created_files += 1

        for title, relation_type, locator in example["links"]:
            element_id = element_ids.get(title)
            if not element_id:
                continue
            link_id = stable_id(f"link:{example['key']}:{element_id}:{relation_type}")
            with database.connect() as connection:
                exists = connection.execute("SELECT 1 FROM element_sources WHERE id = ?", (link_id,)).fetchone()
            if not exists:
                database.link_source_element(
                    user_id,
                    source_id,
                    {
                        "id": link_id,
                        "elementId": element_id,
                        "relationType": relation_type,
                        "locator": locator,
                    },
                )
                created_links += 1

    print(
        f"Hotovo pre používateľa {username}: {created_sources} nových zdrojov, "
        f"{created_files} príloh a {created_links} väzieb."
    )


if __name__ == "__main__":
    main()
