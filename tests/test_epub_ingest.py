"""Synthetic, dependency-free EPUB fixtures; no published book content."""

import stat
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from ki_knowledge.integrations import epub_ingest as epub


CONTAINER = """<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OPS/book.opf"
media-type="application/oebps-package+xml"/></rootfiles></container>"""


def xhtml(body, title="Chapter"):
    return (
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops">'
        f"<head><title>{escape(title)}</title></head><body>{body}</body></html>"
    )


def make_epub(tmp_path, *, chapters=None, spine=None, extra=None, manifest="",
              metadata="", opf=None, compression=zipfile.ZIP_STORED):
    chapters = chapters if chapters is not None else {
        "first.xhtml": xhtml("<h1>First</h1><p>First chapter.</p>"),
        "second.xhtml": xhtml("<h1>Second</h1><p>Second chapter.</p>"),
    }
    spine = spine if spine is not None else list(chapters)
    if opf is None:
        items = "".join(
            f'<item id="c{index}" href="{escape(name)}" media-type="application/xhtml+xml"/>'
            for index, name in enumerate(chapters)
        )
        refs = "".join(
            f'<itemref idref="c{list(chapters).index(name)}"/>'
            for name in spine
        )
        opf = f"""<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
        unique-identifier="book-id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>Über Bücher 日本語</dc:title>
        <dc:creator>Änne Author</dc:creator><dc:creator>Second Author</dc:creator>
        <dc:language>de</dc:language><dc:identifier id="other">other-id</dc:identifier>
        <dc:identifier id="book-id">urn:example:test</dc:identifier>
        {metadata}</metadata><manifest>{items}{manifest}</manifest>
        <spine>{refs}</spine></package>"""
    members = {
        "mimetype": b"application/epub+zip",
        "META-INF/container.xml": CONTAINER,
        "OPS/book.opf": opf,
        **{"OPS/" + name: content for name, content in chapters.items()},
        **(extra or {}),
    }
    path = tmp_path / "synthetic.epub"
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, content in members.items():
            archive.writestr(name, content.encode() if isinstance(content, str) else content)
    return path


def test_metadata_spine_order_and_django_neutral_api(tmp_path):
    path = make_epub(
        tmp_path, spine=["second.xhtml", "first.xhtml"],
        metadata='<dc:subject>History</dc:subject><meta property="dcterms:modified">2026-01-01</meta>',
    )
    book = epub.parse_epub(path)
    assert isinstance(book, epub.EpubBook)
    assert book.title == "Über Bücher 日本語"
    assert book.authors == ["Änne Author", "Second Author"]
    assert book.language == "de"
    assert book.identifier == "urn:example:test"
    assert [chapter.title for chapter in book.chapters] == ["Second", "First"]
    assert [chapter.href for chapter in book.chapters] == ["OPS/second.xhtml", "OPS/first.xhtml"]
    assert book.metadata["chapter_files"] == {
        "OPS/second.xhtml": "0001.md", "OPS/first.xhtml": "0002.md",
    }
    assert book.metadata["dc"]["subject"] == ["History"]
    assert book.metadata["meta"][0]["value"] == "2026-01-01"
    assert not book.warnings
    assert issubclass(epub.EpubIngestError, ValueError)


def test_structure_unicode_footnotes_and_numbered_links(tmp_path):
    first = xhtml("""
    <h1 id="intro">Grüße 世界</h1><h2>Section</h2><h6>Deep</h6>
    <p>A <em>gentle</em> and <strong>bold</strong> thought.<br/>Next line.</p>
    <ul><li>Apple</li><li>Pear<ul><li>Nested</li></ul></li></ul>
    <ol start="3"><li>Third</li></ol><blockquote><p>A quote</p></blockquote>
    <table><caption>Numbers</caption><thead><tr><th>Name</th><th>Value</th></tr></thead>
    <tbody><tr><td>One</td><td>1 | 2</td></tr></tbody></table>
    <p><a id="ref" href="#note">note</a> <a href="second.xhtml#part">next</a>
    <a href="https://example.org/a_(b)?q=x&amp;y=z">web</a></p>
    <aside id="note" epub:type="footnote"><p>Footnote <a href="#ref">back</a></p></aside>
    """)
    second = xhtml('<h1 id="part">Part two</h1><p><a href="first.xhtml#intro">back</a></p>')
    book = epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": first, "second.xhtml": second}))
    markdown = book.chapters[0].markdown
    assert "# Grüße 世界" in markdown and "## Section" in markdown and "###### Deep" in markdown
    assert "*gentle*" in markdown and "**bold**" in markdown
    assert "- Apple" in markdown and "3. Third" in markdown
    assert "Nested" in markdown and "> A quote" in markdown
    assert "| Name | Value |" in markdown
    assert "| --- | --- |" in markdown and "1 &#124; 2" in markdown
    assert '[note](./0001.md#epub-6e6f7465)' in markdown
    assert '<a id="epub-6e6f7465"></a>' in markdown
    assert "[next](./0002.md#epub-70617274)" in markdown
    assert "[back](./0001.md#epub-726566)" in markdown
    assert "https://example.org/a_%28b%29?q=x&y=z" in markdown
    assert "[back](./0001.md#epub-696e74726f)" in book.chapters[1].markdown
    assert not book.warnings


def test_safe_output_images_scripts_and_literal_markdown(tmp_path):
    body = """<h1>Safety</h1><script>alert('no')</script><style>body{display:none}</style>
    <nav><p>navigation hidden</p></nav>
    <p>&lt;script&gt;bad&lt;/script&gt; *not bold* [not a link](bad)</p>
    <img src="https://evil.example/track" alt="Diagram"/>
    <p><a href="javascript:alert(1)">bad link</a> <a href="//evil.example">protocol relative</a>
    <a href="data:text/html,test">data link</a></p><iframe src="https://evil.example"/>
    <pre>&lt;script&gt;literal&lt;/script&gt;\n```</pre><p><code>a`b</code></p>"""
    book = epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": xhtml(body)}))
    markdown = book.chapters[0].markdown
    assert "alert" not in markdown and "display:none" not in markdown
    assert "navigation hidden" not in markdown
    assert "&lt;script&gt;bad&lt;/script&gt;" in markdown
    assert r"\*not bold\*" in markdown
    assert r"\[not a link\]\(bad\)" in markdown
    assert "[Image: Diagram]" in markdown and "![" not in markdown
    assert "https://evil" not in markdown and "javascript:" not in markdown
    assert "````\n<script>literal</script>\n```\n````" in markdown
    assert "`` a`b ``" in markdown
    assert any("images" in warning for warning in book.warnings)
    assert any("interactive" in warning for warning in book.warnings)


def test_percent_encoded_paths_unicode_ids_and_same_basename(tmp_path):
    chapters = {
        "one/chapter.xhtml": xhtml('<h1 id="a &quot; ü">One</h1><p><a href="../two/chapter%20two.xhtml#%E6%97%A5">Next</a></p>'),
        "two/chapter two.xhtml": xhtml('<h1 id="日">Two</h1><p><a href="../one/chapter.xhtml#a%20%22%20%C3%BC">Back</a></p>'),
    }
    book = epub.parse_epub(make_epub(tmp_path, chapters=chapters))
    assert "[Next](./0002.md#epub-e697a5)" in book.chapters[0].markdown
    assert '[Back](./0001.md#epub-61202220c3bc)' in book.chapters[1].markdown
    assert '<a id="epub-61202220c3bc"></a>' in book.chapters[0].markdown


def test_epub3_nested_navigation(tmp_path):
    nav = xhtml("""<nav epub:type="toc"><ol><li><a href="first.xhtml">First</a>
    <ol><li><a href="second.xhtml#part">Second</a></li></ol></li></ol></nav>""")
    book = epub.parse_epub(make_epub(
        tmp_path, chapters={"first.xhtml": xhtml("<p>First</p>"), "second.xhtml": xhtml('<h1 id="part">Second</h1>')},
        extra={"OPS/nav.xhtml": nav},
        manifest='<item id="nav" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/>',
    ))
    toc = book.metadata["toc"]
    assert toc[0]["title"] == "First" and toc[0]["target"] == "./0001.md"
    assert toc[0]["children"][0]["target"] == "./0002.md#epub-70617274"


def test_epub2_ncx_and_nonlinear_exclusion(tmp_path):
    opf = """<package version="2.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>EPUB 2</dc:title></metadata><manifest>
    <item id="first" href="first.xhtml" media-type="application/xhtml+xml"/>
    <item id="second" href="second.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    </manifest><spine toc="ncx"><itemref idref="second" linear="no"/>
    <itemref idref="first"/></spine></package>"""
    ncx = """<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap>
    <navPoint><navLabel><text>First</text></navLabel><content src="first.xhtml"/>
    <navPoint><navLabel><text>Nested</text></navLabel><content src="first.xhtml#sub"/>
    </navPoint></navPoint></navMap></ncx>"""
    book = epub.parse_epub(make_epub(
        tmp_path, opf=opf, chapters={"first.xhtml": xhtml('<h1 id="sub">First</h1>')},
        extra={"OPS/toc.ncx": ncx},
    ))
    assert len(book.chapters) == 1
    assert book.metadata["version"] == "2.0"
    assert book.metadata["toc"][0]["children"][0]["target"] == "./0001.md#epub-737562"
    assert any("Nonlinear" in warning for warning in book.warnings)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "OPS/../alias", r"OPS\evil", "C:/bad", "OPS//bad", "OPS/./bad"])
def test_rejects_unsafe_zip_paths(tmp_path, name):
    path = make_epub(tmp_path, extra={name: "x"})
    with pytest.raises(epub.EpubIngestError, match="Unsafe"):
        epub.parse_epub(path)


def test_rejects_duplicate_zip_members_and_symlinks(tmp_path):
    path = make_epub(tmp_path)
    with zipfile.ZipFile(path, "a") as archive, pytest.warns(UserWarning):
        archive.writestr("OPS/first.xhtml", xhtml("<p>replacement</p>"))
    with pytest.raises(epub.EpubIngestError, match="Duplicate ZIP"):
        epub.parse_epub(path)
    path = make_epub(tmp_path)
    info = zipfile.ZipInfo("OPS/link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr(info, "../../outside")
    with pytest.raises(epub.EpubIngestError, match="symlinks"):
        epub.parse_epub(path)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
@pytest.mark.parametrize("declaration", [
    '<!DOCTYPE html []>',
    '<!DOCTYPE html [<!ENTITY x "expansion">]>',
    '<!DOCTYPE html [<!ENTITY x SYSTEM "file:///etc/passwd">]>',
    '<!DOCTYPE html [<!ENTITY % external SYSTEM "https://example.invalid/entities.dtd">%external;]>',
])
def test_rejects_internal_subsets_and_entities_in_every_encoding(tmp_path, encoding, declaration):
    content = (f'<?xml version="1.0" encoding="{encoding}"?>' + declaration + xhtml("<p>text</p>")).encode(encoding)
    path = make_epub(tmp_path, chapters={"first.xhtml": content})
    with pytest.raises(epub.EpubIngestError, match="DTD"):
        epub.parse_epub(path)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
@pytest.mark.parametrize("declaration", [
    '<!DOCTYPE html>',
    '<!DOCTYPE html SYSTEM "https://example.invalid/xhtml.dtd">',
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">',
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "file:///never-read.dtd">',
])
def test_accepts_xhtml_doctype_without_loading_external_dtd(tmp_path, monkeypatch, encoding, declaration):
    import socket
    import urllib.request

    def no_network(*args, **kwargs):
        pytest.fail("XML parsing must not fetch external resources")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    content = (f'<?xml version="1.0" encoding="{encoding}"?>' + declaration + xhtml(
        "<h1>EPUB 2</h1><p>Unicode ü &amp; escaped &#160; text.</p>"
    )).encode(encoding)
    book = epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": content}))
    assert book.chapters[0].title == "EPUB 2"
    assert "Unicode ü &amp; escaped" in book.chapters[0].markdown


@pytest.mark.parametrize("entity", ["nbsp", "external"])
def test_external_doctype_does_not_enable_custom_entities(tmp_path, entity):
    content = '<!DOCTYPE html SYSTEM "https://example.invalid/xhtml.dtd">' + xhtml(f"<p>&{entity};</p>")
    with pytest.raises(epub.EpubIngestError):
        epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": content}))


@pytest.mark.parametrize("resource", ["META-INF/container.xml", "OPS/book.opf", "OPS/first.xhtml"])
def test_rejects_malformed_xml_at_all_required_stages(tmp_path, resource):
    path = make_epub(tmp_path, extra={resource: "<broken>"})
    with pytest.raises(epub.EpubIngestError, match="malformed XML"):
        epub.parse_epub(path)


@pytest.mark.parametrize("body", ["", "<img src='cover.jpg'/>", "<script>not prose</script>", "<nav><p>Only navigation</p></nav>"])
def test_empty_or_nontext_sections_are_not_silently_omitted(tmp_path, body):
    path = make_epub(tmp_path, chapters={"first.xhtml": xhtml("<p>Good</p>"), "second.xhtml": xhtml(body)})
    with pytest.raises(epub.EpubIngestError, match="empty/non-text"):
        epub.parse_epub(path)


def test_missing_spine_resource_is_fatal(tmp_path):
    path = make_epub(tmp_path)
    with zipfile.ZipFile(path) as archive:
        members = {item.filename: archive.read(item) for item in archive.infolist() if item.filename != "OPS/second.xhtml"}
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    with pytest.raises(epub.EpubIngestError, match="Missing EPUB resource"):
        epub.parse_epub(path)


@pytest.mark.parametrize("href,media", [
    ("https://example.org/chapter.xhtml", "application/xhtml+xml"),
    ("../../outside.xhtml", "application/xhtml+xml"),
    ("first.xhtml", "image/svg+xml"),
])
def test_rejects_unsupported_or_unsafe_reading_resources(tmp_path, href, media):
    opf = f"""<package><metadata/><manifest><item id="one" href="{href}" media-type="{media}"/>
    </manifest><spine><itemref idref="one"/></spine></package>"""
    with pytest.raises(epub.EpubIngestError):
        epub.parse_epub(make_epub(tmp_path, opf=opf))


@pytest.mark.parametrize("algorithm", ["http://www.idpf.org/2008/embedding", "http://www.w3.org/2001/04/xmlenc#aes256-cbc"])
def test_rejects_encryption_including_font_obfuscation(tmp_path, algorithm):
    encryption = f"""<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <EncryptedData xmlns="http://www.w3.org/2001/04/xmlenc#"><EncryptionMethod Algorithm="{algorithm}"/>
    <CipherData><CipherReference URI="OPS/font.otf"/></CipherData></EncryptedData></encryption>"""
    with pytest.raises(epub.EpubIngestError, match="encryption/DRM"):
        epub.parse_epub(make_epub(tmp_path, extra={"META-INF/encryption.xml": encryption}))


@pytest.mark.parametrize("limit,value", [
    ("MAX_ARCHIVE_MEMBERS", 2),
    ("MAX_RESOURCE_BYTES", 100),
    ("MAX_TOTAL_UNCOMPRESSED", 100),
    ("MAX_XML_NODES", 2),
    ("MAX_XML_DEPTH", 2),
])
def test_limits_are_enforced(tmp_path, monkeypatch, limit, value):
    path = make_epub(tmp_path)
    monkeypatch.setattr(epub, limit, value)
    with pytest.raises(epub.EpubIngestError, match="limit"):
        epub.parse_epub(path)


def test_compression_bomb_rejected_even_for_unread_assets(tmp_path):
    path = make_epub(tmp_path, extra={"OPS/huge.txt": "a" * (2 * 1024 * 1024)}, compression=zipfile.ZIP_DEFLATED)
    with pytest.raises(epub.EpubIngestError, match="compression ratio"):
        epub.parse_epub(path)


@pytest.mark.parametrize("content", [b"", b"not a zip", b"PK\x03\x04broken"])
def test_bad_zip_never_returns_empty_success(tmp_path, content):
    path = tmp_path / "bad.epub"
    path.write_bytes(content)
    with pytest.raises(epub.EpubIngestError):
        epub.parse_epub(path)


def test_missing_file_is_domain_error(tmp_path):
    with pytest.raises(epub.EpubIngestError):
        epub.parse_epub(tmp_path / "missing.epub")


def test_empty_spine_and_duplicate_ids_rejected(tmp_path):
    with pytest.raises(epub.EpubIngestError, match="no linear"):
        epub.parse_epub(make_epub(tmp_path, spine=[]))
    with pytest.raises(epub.EpubIngestError, match="duplicate XML ID"):
        epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": xhtml('<p id="a">One</p><p id="a">Two</p>')}))


def test_unresolved_and_unsafe_links_preserve_labels_with_warnings(tmp_path):
    body = """<p><a href="missing.xhtml#id">Missing</a>
    <a href="first.xhtml#missing">Fragment</a>
    <a href="../../../outside">Outside</a>
    <a href="file:///etc/passwd">File</a></p>"""
    book = epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": xhtml(body)}))
    markdown = book.chapters[0].markdown
    assert all(label in markdown for label in ["Missing", "Fragment", "Outside", "File"])
    assert "](" not in markdown
    assert len(book.warnings) == 4


def test_xml_base_rejected_instead_of_wrong_link_resolution(tmp_path):
    with pytest.raises(epub.EpubIngestError, match="xml:base"):
        epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": xhtml('<p xml:base="https://evil.example">text</p>')}))


def test_headerless_table_keeps_first_row_and_reports_spans(tmp_path):
    book = epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": xhtml(
        '<table><tr><td colspan="2">first</td><td>second</td></tr><tr><td>third</td></tr></table>'
    )}))
    assert "| first | second |" in book.chapters[0].markdown
    assert "| third |  |" in book.chapters[0].markdown
    assert any("spans flattened" in warning for warning in book.warnings)


def test_fragments_only_resolve_to_emitted_anchors(tmp_path):
    chapter = xhtml("""
    <h1>Anchors</h1><p><a href="#hidden">Hidden</a><a href="#code">Code</a>
    <a href="#group">Table</a><a href="#math-id">Math</a></p>
    <script id="hidden">invisible</script><pre><code id="code">code</code></pre>
    <table><tbody id="group"><tr><td>cell</td></tr></tbody></table>
    <math><mi id="math-id">x</mi></math>
    """)
    book = epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": chapter}))
    markdown = book.chapters[0].markdown
    assert "[Hidden](" not in markdown
    for identifier in ["code", "group", "math-id"]:
        safe = "epub-" + identifier.encode().hex()
        assert f'<a id="{safe}"></a>' in markdown
        assert f"./0001.md#{safe}" in markdown
    assert any("unresolved" in warning for warning in book.warnings)


def test_code_blank_lines_survive_markdown_normalization(tmp_path):
    chapter = xhtml("<pre>one\n\n\n\n two\n\nthree</pre>")
    markdown = epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": chapter})).chapters[0].markdown
    assert "one\n\n\n\n two\n\nthree" in markdown


def test_nested_tables_do_not_duplicate_inner_rows(tmp_path):
    body = "<p>Tables</p><table><tr><td>outer<table><tr><td>inner</td></tr></table></td></tr></table>"
    book = epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": xhtml(body)}))
    assert book.chapters[0].markdown.count("inner") == 1


@pytest.mark.parametrize("wrapper", [
    "<ul><li>{}</li></ul>",
    "<blockquote>{}</blockquote>",
    "<table><tr><td>{}</td></tr></table>",
])
def test_code_in_containers_cannot_turn_into_active_html(tmp_path, wrapper):
    # Markdown is an existing project dependency, used only to verify rendering.
    import markdown

    content = "<p>Example</p>" + wrapper.format("<pre>&lt;script&gt;bad()&lt;/script&gt;\n```</pre>")
    chapter = epub.parse_epub(make_epub(tmp_path, chapters={"first.xhtml": xhtml(content)})).chapters[0]
    rendered = markdown.markdown(chapter.markdown, extensions=["fenced_code", "tables"])
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_corrupt_compressed_resource_raises_domain_error(tmp_path):
    path = make_epub(tmp_path, compression=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("OPS/first.xhtml")
        offset = info.header_offset
    data = bytearray(path.read_bytes())
    filename_length = int.from_bytes(data[offset + 26:offset + 28], "little")
    extra_length = int.from_bytes(data[offset + 28:offset + 30], "little")
    start = offset + 30 + filename_length + extra_length
    data[start:start + info.compress_size] = b"\xff" * info.compress_size
    path.write_bytes(data)
    with pytest.raises(epub.EpubIngestError):
        epub.parse_epub(path)


def test_spine_missing_manifest_id_and_repeated_sections_fail(tmp_path):
    for refs in ['<itemref idref="unknown"/>', '<itemref idref="one"/><itemref idref="one"/>']:
        opf = f"""<package><metadata/><manifest><item id="one" href="first.xhtml"
        media-type="application/xhtml+xml"/></manifest><spine>{refs}</spine></package>"""
        with pytest.raises(epub.EpubIngestError):
            epub.parse_epub(make_epub(tmp_path, opf=opf))


def test_xml_depth_limit_covers_nested_chapter_not_only_package(tmp_path, monkeypatch):
    content = "<div>" * 25 + "<p>Deep</p>" + "</div>" * 25
    path = make_epub(tmp_path, chapters={"first.xhtml": xhtml(content)})
    monkeypatch.setattr(epub, "MAX_XML_DEPTH", 20)
    with pytest.raises(epub.EpubIngestError, match="first.xhtml: XML complexity"):
        epub.parse_epub(path)


def test_unsupported_nonspine_resources_warn_without_network_access(tmp_path):
    book = epub.parse_epub(make_epub(
        tmp_path, manifest=(
            '<item id="attachment" href="appendix.pdf" media-type="application/pdf"/>'
            '<item id="remote" href="https://example.invalid/track.js" media-type="text/javascript"/>'
        ),
    ))
    assert len(book.chapters) == 2
    assert any("appendix.pdf" in warning and "Unsupported" in warning for warning in book.warnings)
    assert any("not fetched" in warning for warning in book.warnings)


@pytest.mark.parametrize("recognition", ["filename", "title", "guide", "property", "epub-type", "svg"])
def test_image_only_cover_filtered_before_numbering_and_navigation(tmp_path, recognition):
    cover_name = "cover.xhtml" if recognition in {"filename", "svg"} else "front.xhtml"
    cover_body = '<img src="cover.jpg" alt="Cover illustration"/>'
    if recognition == "epub-type":
        cover_body = f'<section epub:type="cover">{cover_body}</section>'
    if recognition == "svg":
        cover_body = '<svg xmlns="http://www.w3.org/2000/svg"><image href="cover.jpg"/></svg>'
    cover = xhtml(cover_body, title="Cover" if recognition == "title" else "Illustration")
    guide = f'<guide><reference type="cover" href="{cover_name}"/></guide>' if recognition == "guide" else ""
    properties = 'properties="cover"' if recognition == "property" else ""
    opf = f"""<package version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Cover fixture</dc:title></metadata><manifest>
    <item id="cover" href="{cover_name}" media-type="application/xhtml+xml" {properties}/>
    <item id="first" href="first.xhtml" media-type="application/xhtml+xml"/>
    <item id="second" href="second.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    </manifest><spine><itemref idref="cover"/><itemref idref="first"/>
    <itemref idref="second"/></spine>{guide}</package>"""
    nav = xhtml(f"""<nav epub:type="toc"><ol><li><a href="{cover_name}">Cover</a></li>
    <li><a href="first.xhtml#one">One</a></li><li><a href="second.xhtml#two">Two</a></li></ol></nav>""")
    path = make_epub(tmp_path, opf=opf, chapters={
        cover_name: cover,
        "first.xhtml": xhtml(f'<h1 id="one">One</h1><p><a href="second.xhtml#two">Next</a> <a href="{cover_name}">Cover</a></p>'),
        "second.xhtml": xhtml('<h1 id="two">Two</h1><p><a href="first.xhtml#one">Back</a></p>'),
    }, extra={"OPS/nav.xhtml": nav})
    book = epub.parse_epub(path)
    assert [chapter.title for chapter in book.chapters] == ["One", "Two"]
    assert book.metadata["chapter_files"] == {
        "OPS/first.xhtml": "0001.md", "OPS/second.xhtml": "0002.md",
    }
    assert "[Next](./0002.md#epub-74776f)" in book.chapters[0].markdown
    assert "[Back](./0001.md#epub-6f6e65)" in book.chapters[1].markdown
    assert "[Cover](" not in book.chapters[0].markdown
    toc = book.metadata["toc"]
    assert toc[0]["target"] is None
    assert toc[1]["target"] == "./0001.md#epub-6f6e65"
    assert toc[2]["target"] == "./0002.md#epub-74776f"
    assert book.metadata["skipped_chapters"] == [{"href": f"OPS/{cover_name}", "reason": "image-only cover"}]
    assert any("image-only cover excluded" in warning for warning in book.warnings)
    assert any("unresolved book link" in warning for warning in book.warnings)


def test_image_only_cover_does_not_make_empty_book_successful(tmp_path):
    with pytest.raises(epub.EpubIngestError, match="no linear textual"):
        epub.parse_epub(make_epub(tmp_path, chapters={"cover.xhtml": xhtml('<img src="cover.jpg"/>')}))


def test_substantive_textual_cover_is_kept(tmp_path):
    book = epub.parse_epub(make_epub(tmp_path, chapters={
        "cover.xhtml": xhtml('<img src="cover.jpg"/><p>Important introductory text.</p>'),
        "first.xhtml": xhtml("<p>Chapter prose.</p>"),
    }))
    assert len(book.chapters) == 2
    assert book.chapters[0].href == "OPS/cover.xhtml"
    assert "Important introductory text" in book.chapters[0].markdown
    assert book.metadata["skipped_chapters"] == []


def test_unrecognized_image_only_section_still_fails_explicitly(tmp_path):
    with pytest.raises(epub.EpubIngestError, match="empty/non-text"):
        epub.parse_epub(make_epub(tmp_path, chapters={
            "first.xhtml": xhtml("<p>Chapter prose.</p>"),
            "scanned-page.xhtml": xhtml('<img src="page.jpg"/>'),
        }))


@pytest.mark.parametrize("outside_prose", [False, True])
def test_manifest_navigation_in_spine_preserves_toc_and_outside_prose(tmp_path, outside_prose):
    nav_body = """<nav epub:type="toc"><ol>
    <li><a href="first.xhtml#one">One</a></li>
    <li><a href="second.xhtml#two">Two</a></li></ol></nav>"""
    if outside_prose:
        nav_body += '<p>Important introduction outside navigation. <a href="first.xhtml#one">Start</a></p>'
    opf = """<package version="3.0"><metadata/><manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="first" href="first.xhtml" media-type="application/xhtml+xml"/>
    <item id="second" href="second.xhtml" media-type="application/xhtml+xml"/>
    </manifest><spine><itemref idref="nav"/><itemref idref="first"/>
    <itemref idref="second"/></spine></package>"""
    book = epub.parse_epub(make_epub(tmp_path, opf=opf, chapters={
        "nav.xhtml": xhtml(nav_body, "Contents"),
        "first.xhtml": xhtml('<h1 id="one">One</h1><p><a href="second.xhtml#two">Next</a> <a href="nav.xhtml">Contents</a></p>'),
        "second.xhtml": xhtml('<h1 id="two">Two</h1><p><a href="first.xhtml#one">Back</a></p>'),
    }))
    offset = int(outside_prose)
    assert len(book.chapters) == 2 + offset
    files = book.metadata["chapter_files"]
    assert files["OPS/first.xhtml"] == f"{1 + offset:04d}.md"
    assert files["OPS/second.xhtml"] == f"{2 + offset:04d}.md"
    assert f"[Next](./{2 + offset:04d}.md#epub-74776f)" in book.chapters[offset].markdown
    assert f"[Back](./{1 + offset:04d}.md#epub-6f6e65)" in book.chapters[offset + 1].markdown
    assert book.metadata["toc"][0]["target"] == f"./{1 + offset:04d}.md#epub-6f6e65"
    assert book.metadata["toc"][1]["target"] == f"./{2 + offset:04d}.md#epub-74776f"
    if outside_prose:
        assert "Important introduction" in book.chapters[0].markdown
        assert "[Start](./0002.md#epub-6f6e65)" in book.chapters[0].markdown
        assert "[Contents](./0001.md)" in book.chapters[1].markdown
        assert book.metadata["skipped_chapters"] == []
    else:
        assert "OPS/nav.xhtml" not in files
        assert "[Contents](" not in book.chapters[0].markdown
        assert book.metadata["skipped_chapters"] == [
            {"href": "OPS/nav.xhtml", "reason": "navigation-only document"},
        ]
        assert any("navigation-only spine document excluded" in warning for warning in book.warnings)


def test_navigation_only_book_cannot_succeed_without_text(tmp_path):
    opf = """<package><metadata/><manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    </manifest><spine><itemref idref="nav"/></spine></package>"""
    with pytest.raises(epub.EpubIngestError, match="no linear textual"):
        epub.parse_epub(make_epub(tmp_path, opf=opf, chapters={
            "nav.xhtml": xhtml('<nav epub:type="toc"><ol><li><a href="#x">Contents</a></li></ol></nav>'),
        }))
