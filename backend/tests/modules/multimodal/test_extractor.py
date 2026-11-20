import fitz
import pytest

from app.modules.multimodal import extractor


def sample_asset_pdf():
    document = fitz.open()
    page = document.new_page(width=600, height=800)
    page.insert_text((50, 40), "Table 1: Accuracy measurements", fontsize=11)
    for x in (50, 200, 350):
        page.draw_line((x, 55), (x, 145))
    for y in (55, 85, 115, 145):
        page.draw_line((50, y), (350, y))
    for x, y, text in [
        (60, 75, "Model"),
        (210, 75, "Accuracy"),
        (60, 105, "Alpha"),
        (210, 105, "92.5"),
        (60, 135, "Beta"),
        (210, 135, "88.2"),
    ]:
        page.insert_text((x, y), text, fontsize=10)
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 80))
    pixmap.clear_with(240)
    page.insert_image(fitz.Rect(50, 190, 250, 350), stream=pixmap.tobytes("png"))
    page.insert_text((50, 370), "Figure 1: Experimental apparatus", fontsize=11)
    page.insert_text(
        (50, 400), "Figure 1 shows the apparatus used in the study.", fontsize=10
    )
    page.insert_text((50, 440), "The energy relation is described below.", fontsize=10)
    page.insert_text((120, 470), "E = m c^2                    (3)", fontsize=12)
    # A vector bar chart, with geometry independent of the raster figure.
    page.draw_line((330, 650), (550, 650))
    page.draw_line((330, 510), (330, 650))
    page.draw_rect(fitz.Rect(360, 580, 400, 650), fill=(0.2, 0.4, 0.7))
    page.draw_rect(fitz.Rect(440, 550, 480, 650), fill=(0.3, 0.6, 0.5))
    page.insert_text((335, 675), "Chart 2: Relative performance", fontsize=10)
    page.insert_text(
        (50, 720),
        "Table 1 and Equation 3 are referenced in this paragraph.",
        fontsize=10,
    )
    payload = document.tobytes()
    document.close()
    return payload


def test_real_table_graphic_caption_vector_chart_and_equation_extraction():
    assets = extractor.extract_assets(sample_asset_pdf())
    table = next(asset for asset in assets if asset["asset_type"] == "table")
    assert table["asset_label"] == "Table 1"
    assert table["caption"] == "Table 1: Accuracy measurements"
    assert table["structured_data"]["headers"] == ["Model", "Accuracy"]
    assert table["structured_data"]["rows"] == [["Alpha", "92.5"], ["Beta", "88.2"]]
    assert "| Alpha | 92.5 |" in table["extracted_text_or_latex"]
    figure = next(asset for asset in assets if asset["asset_type"] == "figure")
    assert figure["asset_label"] == "Figure 1"
    assert figure["caption"] == "Figure 1: Experimental apparatus"
    chart = next(asset for asset in assets if asset["asset_type"] == "chart")
    assert chart["asset_label"] == "Chart 2"
    assert chart["structured_data"]["values_status"] == "not_digitized"
    assert "series" not in chart["structured_data"]
    equation = next(asset for asset in assets if asset["asset_type"] == "equation")
    assert equation["asset_label"] == "Eq. (3)"
    assert "E = m c^2" in equation["extracted_text_or_latex"]
    assert equation["structured_data"]["equation_format"] == "normalized_source_text"
    assert equation["structured_data"]["equation_verified"] is False
    assert "energy relation" in equation["structured_data"]["context"]
    for asset in assets:
        assert asset["page_number"] == 1
        assert len(asset["structured_data"]["bbox"]) == 4
        assert asset["image_bytes"].startswith(b"\x89PNG\r\n\x1a\n")
        image = fitz.Pixmap(asset["image_bytes"])
        assert image.width * image.height <= extractor.MAX_CROP_PIXELS


def test_extraction_is_repeatable_and_does_not_duplicate_table_grid_as_figure():
    payload = sample_asset_pdf()
    first = extractor.extract_assets(payload)
    second = extractor.extract_assets(payload)
    assert first == second
    assert len(first) == 4
    assert {a["structured_data"]["extraction_method"] for a in first} == {
        "pymupdf.find_tables",
        "rendered_embedded_image",
        "rendered_vector_cluster",
        "pdf_text_math_heuristic",
    }


def test_blank_pdf_has_no_assets_and_does_not_call_any_model():
    with fitz.open() as pdf:
        pdf.new_page()
        assert extractor.extract_assets(pdf.tobytes()) == []


@pytest.mark.parametrize("payload", [b"", b"not PDF", b"%PDF-broken"])
def test_invalid_documents_fail_closed(payload):
    with pytest.raises(ValueError):
        extractor.extract_assets(payload)


@pytest.mark.parametrize(
    "limit,value",
    [
        ("MAX_ASSETS", 1),
        ("MAX_TOTAL_TEXT", 10),
        ("MAX_PNG_BYTES", 1),
        ("MAX_TOTAL_IMAGE_BYTES", 1),
        ("MAX_TABLE_CELLS", 1),
        ("MAX_DRAWINGS_PER_PAGE", 1),
        ("MAX_DOCUMENT_BYTES", 10),
        ("MAX_PAGE_CHARACTERS", 1),
    ],
)
def test_extraction_resource_limits_reject_instead_of_silently_truncating(
    monkeypatch, limit, value
):
    monkeypatch.setattr(extractor, limit, value)
    with pytest.raises(ValueError):
        extractor.extract_assets(sample_asset_pdf())


def test_encrypted_pdf_and_page_limit_fail_closed(monkeypatch):
    with fitz.open() as pdf:
        pdf.new_page()
        encrypted = pdf.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="password")
        with pytest.raises(ValueError):
            extractor.extract_assets(encrypted)
        pdf.new_page()
        monkeypatch.setattr(extractor, "MAX_DOCUMENT_PAGES", 1)
        with pytest.raises(ValueError):
            extractor.extract_assets(pdf.tobytes())


def test_table_markdown_escapes_separators_without_changing_raw_values():
    result = extractor._markdown(["A|B", "C"], [[r"x\y", None]])
    assert r"A\|B" in result
    assert r"x\\y" in result


def test_uncaptioned_image_remains_unclassified_figure_and_caption_types_are_explicit():
    with fitz.open() as pdf:
        page = pdf.new_page()
        image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80))
        image.clear_with(180)
        page.insert_image(fitz.Rect(50, 100, 150, 200), stream=image.tobytes("png"))
        assets = extractor.extract_assets(pdf.tobytes())
    assert len(assets) == 1
    assert assets[0]["asset_label"] is None
    assert assets[0]["asset_type"] == "figure"
    assert assets[0]["structured_data"]["classification_basis"] == "unclassified_figure"


def test_diagram_classification_uses_caption_without_inventing_structure():
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.draw_rect(fitz.Rect(50, 100, 150, 160))
        page.insert_text((50, 185), "Diagram 1: Proposed architecture")
        result = extractor.extract_assets(pdf.tobytes())
    assert len(result) == 1
    assert result[0]["asset_type"] == "diagram"
    assert result[0]["asset_label"] == "Diagram 1"
    assert result[0]["structured_data"]["classification_basis"] == "caption"


def test_process_wrapper_runs_valid_extraction_and_rejects_invalid_pdf():
    assert any(
        a["asset_type"] == "table"
        for a in extractor.extract_assets_bounded(sample_asset_pdf())
    )
    with pytest.raises(ValueError):
        extractor.extract_assets_bounded(b"invalid")


def test_rotated_page_keeps_source_coordinates_and_captions():
    payload = sample_asset_pdf()
    with fitz.open(stream=payload, filetype="pdf") as pdf:
        pdf[0].set_rotation(90)
        rotated = pdf.tobytes()
    assets = extractor.extract_assets(rotated)
    assert len(assets) == 4
    table = next(a for a in assets if a["asset_type"] == "table")
    assert table["asset_label"] == "Table 1"
    assert table["structured_data"]["bbox"] == [50.0, 55.0, 350.0, 145.0]
    with fitz.open(stream=rotated, filetype="pdf") as original:
        assert original[0].rotation == 90


def test_distant_caption_does_not_assign_an_unrelated_asset_label():
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.draw_rect(fitz.Rect(50, 50, 170, 120))
        page.insert_text((50, 600), "Diagram 9: A different section")
        assets = extractor.extract_assets(pdf.tobytes())
    assert len(assets) == 1
    assert assets[0]["asset_type"] == "figure"
    assert assets[0]["asset_label"] is None


@pytest.mark.parametrize("mode", ["timeout", "eof", "failed"])
def test_process_wrapper_terminates_native_worker_on_timeout_or_failure(
    monkeypatch, mode
):
    class Connection:
        closed = False

        def close(self):
            self.closed = True

        def poll(self, timeout):
            assert timeout == extractor.EXTRACTION_TIMEOUT_SECONDS + 5
            return mode != "timeout"

        def recv(self):
            if mode == "eof":
                raise EOFError()
            return None

    class Worker:
        pid = 1
        terminated = False

        def start(self):
            pass

        def join(self, timeout):
            assert timeout <= 2

        def is_alive(self):
            return True

        def terminate(self):
            self.terminated = True

    receiver, sender, worker = Connection(), Connection(), Worker()

    class Context:
        def Pipe(self, duplex):
            assert duplex is False
            return receiver, sender

        def Process(self, **kwargs):
            assert kwargs["daemon"] is True
            return worker

    monkeypatch.setattr(extractor.multiprocessing, "get_context", lambda _: Context())
    with pytest.raises(TimeoutError if mode == "timeout" else ValueError):
        extractor.extract_assets_bounded(b"%PDF-mock")
    assert worker.terminated and receiver.closed and sender.closed


def test_native_table_failure_is_safe_and_not_silently_ignored(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Native parser error with document contents")

    monkeypatch.setattr(fitz.Page, "find_tables", fail)
    with pytest.raises(ValueError, match="PDF table detection failed") as error:
        extractor.extract_assets(sample_asset_pdf())
    assert "document contents" not in str(error.value)


def test_asset_budget_is_checked_incrementally_before_later_visuals(monkeypatch):
    monkeypatch.setattr(extractor, "MAX_ASSETS", 1)
    calls = []
    original = extractor._render

    def observe(page, box):
        calls.append(1)
        return original(page, box)

    monkeypatch.setattr(extractor, "_render", observe)
    with pytest.raises(ValueError, match="extraction limit"):
        extractor.extract_assets(sample_asset_pdf())
    # Stop after the first offending asset, not after materializing the page.
    assert len(calls) == 2
