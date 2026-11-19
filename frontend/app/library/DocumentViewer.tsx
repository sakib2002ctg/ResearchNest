"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from "pdfjs-dist";

import { Icon } from "@/components/Icon";
import { api, type LibraryAnnotation, type LibraryAnnotationInput, type LibraryPaper } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export function LibraryDialog({ title, onClose, children, wide = false }: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const { pick } = useI18n();
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);

  return (
    <dialog
      ref={dialog}
      className={wide ? "library-dialog library-dialog-wide" : "library-dialog"}
      aria-label={title}
      onCancel={(event) => { event.preventDefault(); onClose(); }}
    >
      <div className="library-dialog-heading">
        <h2>{title}</h2>
        <button type="button" className="icon-button" aria-label={pick("Close", "বন্ধ করুন")} onClick={onClose}>
          <Icon name="x" />
        </button>
      </div>
      {children}
    </dialog>
  );
}

const emptyAnnotation: LibraryAnnotationInput = {
  type: "note", content: "", page_number: null, color: null,
};
const colors = ["#fde68a", "#bbf7d0", "#bfdbfe", "#fbcfe8"];

export function DocumentViewer({ paper, onClose }: { paper: LibraryPaper; onClose: () => void }) {
  const { pick, locale } = useI18n();
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [pdfError, setPdfError] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [annotations, setAnnotations] = useState<LibraryAnnotation[] | null>(null);
  const [annotationError, setAnnotationError] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<LibraryAnnotationInput>(emptyAnnotation);
  const [pending, setPending] = useState(false);
  const [savingError, setSavingError] = useState(false);
  const document = paper.document;

  useEffect(() => {
    if (!document) return;
    const controller = new AbortController();
    let objectUrl = "";
    let loadingTask: PDFDocumentLoadingTask | null = null;
    api.getLibraryPDF(paper.id, controller.signal).then(async (blob) => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setDownloadUrl(objectUrl);
      const bytes = new Uint8Array(await blob.arrayBuffer());
      if (controller.signal.aborted) return;
      const pdfjs = await import("pdfjs-dist/webpack.mjs");
      if (controller.signal.aborted) return;
      const task = pdfjs.getDocument({
        data: bytes,
        useWorkerFetch: false,
        useWasm: false,
        enableXfa: false,
        disableWorkerRendering: true,
      });
      loadingTask = task;
      const documentProxy = await task.promise;
      if (controller.signal.aborted) return;
      setPdf(documentProxy);
      setPageCount(documentProxy.numPages);
    }).catch(() => {
      if (!controller.signal.aborted) setPdfError(true);
    });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      if (loadingTask) void loadingTask.destroy().catch(() => {});
    };
  }, [document, paper.id]);

  const canvas = useRef<HTMLCanvasElement>(null);
  const pageFrame = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!pdf || !canvas.current || !pageFrame.current) return;
    const pageCanvas = canvas.current;
    const container = pageFrame.current;
    let cancelled = false;
    let renderTask: RenderTask | null = null;
    pdf.getPage(page).then((pdfPage) => {
      if (cancelled) return;
      const base = pdfPage.getViewport({ scale: 1 });
      if (!Number.isFinite(base.width) || !Number.isFinite(base.height) || base.width <= 0 || base.height <= 0) {
        throw new Error("Invalid PDF page size.");
      }
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      const scale = Math.min(
        ratio * Math.min(2, Math.max(1, container.clientWidth - 2) / base.width),
        4096 / Math.max(base.width, base.height),
        Math.sqrt(8_000_000) / Math.sqrt(base.width) / Math.sqrt(base.height),
      );
      const viewport = pdfPage.getViewport({ scale });
      pageCanvas.width = Math.max(1, Math.floor(viewport.width));
      pageCanvas.height = Math.max(1, Math.floor(viewport.height));
      pageCanvas.style.width = `${viewport.width / ratio}px`;
      const context = pageCanvas.getContext("2d");
      if (!context) throw new Error("PDF canvas unavailable.");
      renderTask = pdfPage.render({
        canvas: pageCanvas,
        canvasContext: context,
        viewport,
        background: "rgb(255,255,255)",
        annotationMode: 0,
      });
      void renderTask.promise.catch(() => {
        if (!cancelled) setPdfError(true);
      });
    }).catch(() => {
      if (!cancelled) setPdfError(true);
    });
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [pdf, page]);

  useEffect(() => {
    const controller = new AbortController();
    api.getLibraryAnnotations(paper.id, controller.signal).then((items) => {
      if (!controller.signal.aborted) setAnnotations(items);
    }).catch(() => {
      if (!controller.signal.aborted) setAnnotationError(true);
    });
    return () => controller.abort();
  }, [paper.id]);

  function reset() {
    setEditing(null);
    setDraft(emptyAnnotation);
    setSavingError(false);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.content.trim() || pending) return;
    setSavingError(false);
    setPending(true);
    const input = { ...draft, content: draft.content.trim() };
    try {
      const annotation = editing === null
        ? await api.createLibraryAnnotation(paper.id, input)
        : await api.updateLibraryAnnotation(paper.id, editing, input);
      setAnnotations((items) => editing === null
        ? [annotation, ...(items ?? [])]
        : (items ?? []).map((item) => item.id === editing ? annotation : item));
      reset();
    } catch {
      setSavingError(true);
    } finally {
      setPending(false);
    }
  }

  async function remove(id: number) {
    setPending(true);
    setSavingError(false);
    try {
      await api.deleteLibraryAnnotation(paper.id, id);
      setAnnotations((items) => (items ?? []).filter((item) => item.id !== id));
      if (editing === id) reset();
    } catch {
      setSavingError(true);
    } finally {
      setPending(false);
    }
  }

  const annotationName = (type: LibraryAnnotation["type"]) =>
    type === "highlight" ? pick("Highlight", "হাইলাইট") : pick("Note", "নোট");

  return (
    <LibraryDialog title={paper.title} onClose={onClose} wide={Boolean(document)}>
      <div className={document ? "library-viewer-grid" : undefined}>
        {document && (
          <div className="min-w-0">
            <div className="paper-actions mt-0 mb-3 items-center">
              <span className="muted text-sm break-all">{document.original_filename}</span>
              {downloadUrl && (
                <a className="button secondary small" href={downloadUrl} download={document.original_filename}>
                  <Icon name="download" size={16} /> {pick("Download PDF", "PDF ডাউনলোড")}
                </a>
              )}
            </div>
            {pdfError ? (
              <p className="notice error" role="alert">{downloadUrl
                ? pick("Preview unavailable. The PDF is ready to download.", "প্রিভিউ পাওয়া যাচ্ছে না। PDF ডাউনলোডের জন্য প্রস্তুত।")
                : pick("The PDF could not be loaded.", "PDF লোড করা যায়নি।")}</p>
            ) : pdf ? (
              <>
                <div ref={pageFrame} className="library-pdf-page">
                  <canvas ref={canvas} aria-label={`${pick("PDF page", "PDF পৃষ্ঠা")} ${page}`} />
                </div>
                <div className="library-pdf-navigation">
                  <button type="button" className="button secondary small" disabled={page <= 1}
                    onClick={() => setPage((value) => value - 1)}>{pick("Previous", "আগের")}</button>
                  <span className="muted text-sm">{pick("Page", "পৃষ্ঠা")} {page.toLocaleString(locale)} / {pageCount.toLocaleString(locale)}</span>
                  <button type="button" className="button secondary small" disabled={page >= pageCount}
                    onClick={() => setPage((value) => value + 1)}>{pick("Next", "পরের")}</button>
                </div>
              </>
            ) : <p role="status" className="muted">{pick("Loading PDF…", "PDF লোড হচ্ছে…")}</p>}
          </div>
        )}
        <section aria-label={pick("Annotations", "টীকা")}>
          <h3 className="font-semibold mb-3">{pick("Notes and highlights", "নোট ও হাইলাইট")}</h3>
          {annotationError ? (
            <p className="notice error" role="alert">{pick("Annotations could not be loaded.", "টীকা লোড করা যায়নি।")}</p>
          ) : annotations === null ? (
            <p role="status" className="muted">{pick("Loading annotations…", "টীকা লোড হচ্ছে…")}</p>
          ) : (
            <>
              <form className="form-stack" onSubmit={save}>
                <div className="inline-fields">
                  <label className="field">{pick("Type", "ধরন")}
                    <select value={draft.type} disabled={pending} onChange={(event) => setDraft({ ...draft, type: event.target.value as LibraryAnnotationInput["type"] })}>
                      <option value="note">{annotationName("note")}</option>
                      <option value="highlight">{annotationName("highlight")}</option>
                    </select>
                  </label>
                  {document && <label className="field">{pick("Page (optional)", "পৃষ্ঠা (ঐচ্ছিক)")}
                    <input type="number" min={1} max={document.page_count} value={draft.page_number ?? ""} disabled={pending}
                      onChange={(event) => setDraft({ ...draft, page_number: event.target.value ? Number(event.target.value) : null })} />
                  </label>}
                </div>
                <label className="field">{editing === null ? pick("New annotation", "নতুন টীকা") : pick("Edit annotation", "টীকা সম্পাদনা")}
                  <textarea required maxLength={10000} value={draft.content} disabled={pending}
                    onChange={(event) => setDraft({ ...draft, content: event.target.value })} />
                </label>
                {draft.type === "highlight" && (
                  <label className="field">{pick("Color", "রং")}
                    <select value={draft.color ?? ""} disabled={pending} onChange={(event) => setDraft({ ...draft, color: event.target.value || null })}>
                      <option value="">{pick("Default", "ডিফল্ট")}</option>
                      {colors.map((color, index) => <option key={color} value={color}>{[
                        pick("Yellow", "হলুদ"), pick("Green", "সবুজ"), pick("Blue", "নীল"), pick("Pink", "গোলাপি"),
                      ][index]}</option>)}
                    </select>
                  </label>
                )}
                <div className="flex flex-wrap gap-2">
                  <button className="button primary small" type="submit" disabled={pending}>{pick("Save annotation", "টীকা সংরক্ষণ")}</button>
                  {editing !== null && <button className="button secondary small" type="button" disabled={pending} onClick={reset}>{pick("Cancel", "বাতিল")}</button>}
                </div>
              </form>
              {savingError && <p role="alert" className="notice error mt-3">{pick("The annotation change could not be saved.", "টীকার পরিবর্তন সংরক্ষণ করা যায়নি।")}</p>}
              <ul className="mt-4 grid gap-3">
                {annotations.map((item) => (
                  <li key={item.id} className="session-card m-0 min-w-0">
                    <p className="muted text-xs">{annotationName(item.type)}{item.page_number && <> · {pick("Page", "পৃষ্ঠা")} {item.page_number.toLocaleString(locale)}</>}</p>
                    <p className="mt-2 whitespace-pre-wrap break-words">{item.content}</p>
                    <div className="paper-actions">
                      <button type="button" className="button secondary small" disabled={pending}
                        onClick={() => { setEditing(item.id); setDraft({ type: item.type, content: item.content, page_number: item.page_number, color: item.color }); setSavingError(false); }}>
                        {pick("Edit", "সম্পাদনা")}
                      </button>
                      <button type="button" className="button secondary small" disabled={pending}
                        onClick={() => { if (window.confirm(pick("Delete this annotation?", "এই টীকাটি মুছবেন?"))) void remove(item.id); }}>
                        {pick("Delete", "মুছুন")}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </LibraryDialog>
  );
}
