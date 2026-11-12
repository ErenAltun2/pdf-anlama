import hashlib
import html
import json
import re
import tempfile
import uuid
from pathlib import Path
import base64
from PIL import Image

import pymupdf
import streamlit as st

from exporting.export import html_to_rows
from extraction.extract_table import parse_markdown_table, readable_rows, rows_to_csv

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "outputs" / "results"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
LOGO_PATH = ROOT / "assets" / "logo.png"
def favicon_image() -> Image.Image:
    logo = Image.open(LOGO_PATH).convert("RGBA")
    size = max(logo.size) + 40
    canvas = Image.new("RGBA", (size, size), "white")
    canvas.alpha_composite(
        logo, ((size - logo.width) // 2, (size - logo.height) // 2)
    )
    return canvas


def logo_base64() -> str:
    return base64.b64encode(LOGO_PATH.read_bytes()).decode()


def safe_stem(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")[:80].strip("._-")
    return cleaned or "makale"


def make_processing_pdf(pdf_bytes: bytes, paper_id: str, selected_pages: list[int] | None):
    temp_dir = tempfile.TemporaryDirectory(prefix="pdf_anlama_")
    source_path = Path(temp_dir.name) / f"{paper_id}_source.pdf"
    source_path.write_bytes(pdf_bytes)
    if selected_pages is None:
        return temp_dir, source_path, None

    with pymupdf.open(source_path) as source, pymupdf.open() as selected:
        for page_number in selected_pages:
            selected.insert_pdf(source, from_page=page_number - 1, to_page=page_number - 1)
        processing_path = Path(temp_dir.name) / f"{paper_id}.pdf"
        selected.save(processing_path)
    return temp_dir, processing_path, selected_pages


def page_preview(pdf_bytes: bytes, page_number: int) -> bytes:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        page = document[page_number - 1]
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(0.7, 0.7), alpha=False)
        return pixmap.tobytes("png")


def pending_page_work(
    page_selection: list[int],
    selected_types: set[str],
    completed: dict[int, set[str]],
) -> list[tuple[int, set[str]]]:
    return [
        (page, remaining)
        for page in page_selection
        if (remaining := selected_types - completed.get(page, set()))
    ]


def group_page_work(
    page_work: list[tuple[int, set[str]]],
) -> list[tuple[list[int], set[str]]]:
    grouped: dict[frozenset[str], list[int]] = {}
    for page, types in page_work:
        grouped.setdefault(frozenset(types), []).append(page)
    return [(pages, set(types)) for types, pages in grouped.items()]


def copy_button(label: str, text: str) -> None:
    payload = html.escape(json.dumps(text, ensure_ascii=True), quote=True)
    button_id = f"copy-{uuid.uuid4().hex}"
    status_id = f"status-{uuid.uuid4().hex}"
    st.html(
        f"""
        <div class="copy-control">
          <button class="copy-button" id="{button_id}" data-payload="{payload}">{html.escape(label)}</button>
          <span class="copy-status" id="{status_id}" aria-live="polite"></span>
        </div>
        <style>
        .copy-control {{ display: flex; align-items: center; gap: 0.5rem; margin-top: 0.5rem; }}
        .copy-button {{
          min-height: 2.5rem; padding: 0.25rem 0.75rem; border: 1px solid rgba(49, 51, 63, 0.2);
          border-radius: 0.5rem; background: #fff; color: #31333f; font: inherit;
          font-size: 0.875rem; cursor: pointer;
        }}
        .copy-button:hover {{ border-color: #ff4b4b; color: #ff4b4b; }}
        .copy-status {{ font-size: 0.875rem; }}
        </style>
        <script>
        const button = document.getElementById("{button_id}");
        const status = document.getElementById("{status_id}");
        button.addEventListener("click", () => {{
          const value = JSON.parse(button.dataset.payload);
          status.textContent = "";
          let clipboardWrite;
          try {{
            if (navigator.clipboard?.writeText) {{
              clipboardWrite = navigator.clipboard.writeText(value);
            }}
          }} catch (error) {{
            clipboardWrite = null;
          }}

          const field = document.createElement("textarea");
          field.value = value;
          field.setAttribute("readonly", "");
          field.style.position = "fixed";
          field.style.opacity = "0";
          document.body.appendChild(field);
          field.select();
          field.setSelectionRange(0, field.value.length);
          let fallbackCopied = false;
          try {{
            fallbackCopied = document.execCommand("copy");
          }} catch (error) {{
            fallbackCopied = false;
          }}
          field.remove();

          status.textContent = fallbackCopied ? "Kopyalandı" : "Kopyalanamadı";
          if (clipboardWrite) {{
            clipboardWrite.then(() => {{
              status.textContent = "Kopyalandı";
            }}).catch(() => {{
              if (!fallbackCopied) {{
                status.textContent = "Kopyalanamadı";
              }}
            }});
          }}
        }});
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def render_result(paper_id: str) -> None:
    result_path = RESULTS_DIR / paper_id / "result.json"
    if not result_path.is_file():
        st.error(f"Sonuç dosyası bulunamadı: {result_path}")
        return

    from models.schemas import PaperResult

    result = PaperResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    items = result.tables + result.equations + result.figures
    items_by_id = {item.id: item for item in items}

    st.subheader("İşlem özeti")
    if result.docling_device:
        st.info(f"Docling hızlandırıcısı / kaynak: {result.docling_device}")
    counts = {
        status: sum(item.status == status for item in items)
        for status in ("ok", "failed", "skipped")
    }
    columns = st.columns(4)
    columns[0].metric("Başarılı", counts["ok"])
    columns[1].metric("Hatalı", counts["failed"])
    columns[2].metric("Atlanan", counts["skipped"])
    columns[3].metric("Süre", f"{result.sure_sn} sn")

    for message in result.messages:
        st.warning(message)

    if items:
        for item_id in result.okuma_sirasi:
            item = items_by_id.get(item_id)
            if item is None:
                continue
            with st.container(border=True):
                heading = item.caption if hasattr(item, "caption") and item.caption else item.id
                st.markdown(
                    f"### {item.sira}. {heading} · sayfa {item.page} · {item.status}"
                )
                if item.warning:
                    st.caption(f"Uyarı: {item.warning}")
                if item.error:
                    st.error(item.error)

                image_column, output_column = st.columns([1, 1.25])
                with image_column:
                    crop = ROOT / "outputs" / "crops" / paper_id / f"p{item.page}_{item.id}.png"
                    if crop.is_file():
                        st.image(
                            str(crop),
                            caption=f"PDF kırpıntısı · sayfa {item.page}",
                            width="stretch",
                        )
                    else:
                        st.info("Bu öğenin PDF kırpıntısı bulunamadı.")

                with output_column:
                    if hasattr(item, "markdown"):
                        raw = item.markdown
                        rows = (
                            html_to_rows(raw)
                            if "<table" in raw.lower()
                            else parse_markdown_table(raw)
                        )
                        if rows:
                            rows = readable_rows(rows)
                            headers = [
                                header or f"Sütun {index + 1}"
                                for index, header in enumerate(rows[0])
                            ]
                            seen_headers = {}
                            for index, header in enumerate(headers):
                                seen_headers[header] = seen_headers.get(header, 0) + 1
                                if seen_headers[header] > 1:
                                    headers[index] = f"{header} ({seen_headers[header]})"
                            records = [
                                dict(zip(headers, row))
                                for row in rows[1:]
                            ]
                            st.dataframe(records, width="stretch", hide_index=True)
                            st.download_button(
                                "Bu tabloyu CSV indir",
                                data=rows_to_csv(rows, delimiter=";").encode("utf-8-sig"),
                                file_name=f"{item.id}.csv",
                                mime="text/csv",
                                key=f"download-{paper_id}-{item.id}",
                            )
                        else:
                            st.code(
                                raw or "Tablo çıktısı yok.",
                                language="html" if "<table" in raw.lower() else "markdown",
                            )
                    elif hasattr(item, "latex"):
                        st.markdown("**Formül kodu (LaTeX)**")
                        st.code(item.latex or "Formül çıktısı yok.", language="latex")
                        if item.latex:
                            st.caption(
                                "Bu LaTeX kodu Word'de de kullanılabilir: Alt+= ile denklem alanı açıp kodu yapıştır."
                            )
                    elif hasattr(item, "description"):
                        st.markdown("**Figür açıklaması**")
                        st.write(item.description or "Açıklama üretilemedi.")
                        if item.description:
                            copy_button("Açıklamayı kopyala", item.description)
    else:
        st.info("Seçilen PDF için işlenecek öğe bulunamadı.")

def main() -> None:
    st.set_page_config(
        page_title="Kırpıt",
        page_icon=favicon_image(),
        layout="wide",
    )
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.5rem;">
          <div style="
            height:3.5rem; width:2.94rem;
            background-color: currentColor;
            -webkit-mask: url(data:image/png;base64,{logo_base64()}) center / contain no-repeat;
            mask: url(data:image/png;base64,{logo_base64()}) center / contain no-repeat;
          "></div>
          <h1 style="margin:0; padding:0;">Kırpıt</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("PDF'inden tablo, formül ve figürleri çıkar; görüntüyü ve sonucu yan yana incele, kopyala.")

    uploaded = st.file_uploader("PDF dosyası", type=["pdf"])
    pdf_bytes = uploaded.getvalue() if uploaded is not None else None
    page_count = None
    if pdf_bytes:
        try:
            with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
                page_count = document.page_count
        except Exception as exc:
            st.error(f"PDF önizlemesi açılamadı: {type(exc).__name__}: {exc}")

    page_mode = "Tüm PDF"
    selected_pages = None
    if page_count:
        page_mode = st.radio(
            "İşlenecek sayfalar",
            ["Tüm PDF", "Belirli sayfalar"],
            horizontal=True,
        )
        if page_mode == "Belirli sayfalar":
            selected_pages = st.multiselect(
                "İşlenecek sayfaları seç",
                options=list(range(1, page_count + 1)),
                format_func=lambda page: f"Sayfa {page}",
                help="Yalnızca seçtiğiniz sayfalar Docling ve VLM ile işlenir.",
            )
            if selected_pages:
                st.caption(f"Seçilen {len(selected_pages)} sayfa işlenecek: {', '.join(map(str, selected_pages))}")
                with st.expander("Seçilen sayfaların önizlemesi"):
                    for start in range(0, min(len(selected_pages), 6), 3):
                        columns = st.columns(3)
                        for column, page_number in zip(columns, selected_pages[start:start + 3]):
                            column.image(
                                page_preview(pdf_bytes, page_number),
                                caption=f"Sayfa {page_number}",
                                width="stretch",
                            )
                    if len(selected_pages) > 6:
                        st.caption("Önizlemede ilk 6 sayfa gösteriliyor; seçilen tüm sayfalar işlenecek.")

    left, right = st.columns(2)
    with left:
        st.markdown("**Neleri çıkaralım?**")
        extract_tables = st.checkbox("Tablolar", value=True)
        extract_equations = st.checkbox("Formüller", value=True)
        extract_figures = st.checkbox("Figürler", value=True)
    with right:
        st.info("Tabloları kopyalayabilir veya CSV indirebilirsin. Formül ve açıklamalar kopyalanabilir.")

    if uploaded is not None and uploaded.size > MAX_UPLOAD_BYTES:
        st.error("PDF en fazla 100 MB olabilir.")
        return

    selected = set()
    if extract_tables:
        selected.add("table")
    if extract_equations:
        selected.add("equation")
    if extract_figures:
        selected.add("figure")

    if st.button("PDF'i işle", type="primary", disabled=uploaded is None):
        if not selected:
            st.error("Lütfen en az bir öğe türü seç.")
        elif page_mode == "Belirli sayfalar" and not selected_pages:
            st.error("Lütfen işlenecek en az bir sayfa seç.")
        elif uploaded is not None:
            page_selection = selected_pages if page_mode == "Belirli sayfalar" else None
            if page_selection is None:
                paper_id = f"{safe_stem(uploaded.name)}-{uuid.uuid4().hex[:8]}"
            else:
                source_hash = hashlib.sha256(pdf_bytes).hexdigest()[:12]
                paper_id = f"{safe_stem(uploaded.name)}-{source_hash}"
            temp_dirs = []
            try:
                if page_selection is None:
                    temp_dir, processing_path, page_numbers = make_processing_pdf(
                        pdf_bytes, paper_id, None
                    )
                    temp_dirs.append(temp_dir)
                    pages_to_run = [(processing_path, page_numbers, selected)]
                else:
                    from run import processed_page_types

                    completed = processed_page_types(paper_id)
                    pages_to_run = []
                    page_work = pending_page_work(page_selection, selected, completed)
                    for page_numbers, remaining_types in group_page_work(page_work):
                        temp_dir, processing_path, page_numbers = make_processing_pdf(
                            pdf_bytes, paper_id, page_numbers
                        )
                        temp_dirs.append(temp_dir)
                        pages_to_run.append(
                            (processing_path, page_numbers, remaining_types)
                        )

                if not pages_to_run:
                    st.info("Seçtiğin sayfalar ve öğe türleri daha önce işlendi; yeni işlem gerekmedi.")
                    st.session_state["processed_paper_id"] = paper_id
                else:
                    progress = st.progress(0, text="İşlem başlatılıyor...")
                    docling_status = st.empty()

                    def show_docling_status(message: str) -> None:
                        docling_status.info(f"Docling: {message}")

                    from run import run_paper

                    result = None
                    try:
                        with st.spinner("Yeni seçilen sayfalar işleniyor..."):
                            for index, (processing_path, page_numbers, page_types) in enumerate(
                                pages_to_run, 1
                            ):
                                result = run_paper(
                                    processing_path,
                                    page_types,
                                    {"csv", "md"},
                                    page_numbers=page_numbers,
                                    on_docling_status=show_docling_status,
                                )
                                progress.progress(
                                    index / len(pages_to_run),
                                    text=f"{index}/{len(pages_to_run)} sayfa grubu işlendi",
                                )
                    finally:
                        progress.empty()
                        docling_status.empty()
                    if result is not None:
                        st.session_state["processed_paper_id"] = result.paper_id
                        st.success("Yeni sayfalar işlendi; önceki sonuçlar korundu.")
            except Exception as exc:
                st.error(f"PDF işlenemedi: {type(exc).__name__}: {exc}")
            finally:
                for temp_dir in temp_dirs:
                    temp_dir.cleanup()

    paper_id = st.session_state.get("processed_paper_id")
    if paper_id:
        render_result(paper_id)


if __name__ == "__main__":
    main()
