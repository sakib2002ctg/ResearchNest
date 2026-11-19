"use client";

import { useEffect, useState, type FormEvent } from "react";

import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { api, ApiError, type LibraryCollection, type LibraryPage as LibraryResult, type LibraryPaper, type LibraryTag } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

import { DocumentViewer, LibraryDialog } from "./DocumentViewer";
import { OrganizeLibrary, PaperOrganization, ReadingProgressForm } from "./LibraryOrganization";

const blankPaper = { title: "", authors: "", abstract: "", source: "", url: "" };
type Modal = "manual" | "upload" | "collections" | "tags" | null;

function sourceUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

export default function LibraryPage() {
  const { user } = useAuth();
  const { pick } = useI18n();
  return (
    <AppShell title={pick("My library", "আমার লাইব্রেরি")} description={pick("Papers you have saved for your research.", "গবেষণার জন্য আপনার সংরক্ষিত গবেষণাপত্র।")} showHeading>
      {user && <LibraryWorkspace key={user.id} />}
    </AppShell>
  );
}

function LibraryWorkspace() {
  const { pick, locale } = useI18n();
  const [result, setResult] = useState<LibraryResult | null>(null);
  const [collections, setCollections] = useState<LibraryCollection[]>([]);
  const [tags, setTags] = useState<LibraryTag[]>([]);
  const [filterError, setFilterError] = useState(false);
  const [query, setQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [collectionId, setCollectionId] = useState<number>();
  const [tagId, setTagId] = useState<number>();
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [organizationRevision, setOrganizationRevision] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const [modal, setModal] = useState<Modal>(null);
  const [draft, setDraft] = useState(blankPaper);
  const [attachment, setAttachment] = useState<LibraryPaper | null>(null);
  const [viewer, setViewer] = useState<LibraryPaper | null>(null);
  const [organizing, setOrganizing] = useState<LibraryPaper | null>(null);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null);
  const loading = result === null && !loadError;

  useEffect(() => {
    let current = true;
    Promise.all([api.getLibraryCollections(), api.getLibraryTags()]).then(([newCollections, newTags]) => {
      if (!current) return;
      setCollections(newCollections);
      setTags(newTags);
      setFilterError(false);
      if (
        (collectionId !== undefined && !newCollections.some((item) => item.id === collectionId)) ||
        (tagId !== undefined && !newTags.some((item) => item.id === tagId))
      ) {
        setCollectionId(undefined);
        setTagId(undefined);
        setPage(1);
      }
    }).catch(() => {
      if (current) setFilterError(true);
    });
    return () => { current = false; };
  }, [collectionId, tagId, organizationRevision]);

  useEffect(() => {
    let current = true;
    api.getLibrary({ q: query || undefined, collection_id: collectionId, tag_id: tagId, page, size: 10 })
      .then((data) => {
        if (!current) return;
        if (page > Math.max(data.pages, 1)) {
          setPage(Math.max(data.pages, 1));
          return;
        }
        setResult(data);
        setLoadError(false);
      }).catch(() => { if (current) setLoadError(true); });
    return () => { current = false; };
  }, [query, collectionId, tagId, page, revision]);

  useEffect(() => {
    const processing = result?.items.some((paper) =>
      paper.document?.status === "pending" || paper.document?.status === "processing",
    );
    if (!processing) return;
    const timer = window.setTimeout(() => setRevision((value) => value + 1), 3000);
    return () => window.clearTimeout(timer);
  }, [result]);

  function refresh(wait = false) {
    if (wait) setResult(null);
    setLoadError(false);
    setRevision((value) => value + 1);
  }

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery(searchInput.trim());
    setPage(1);
    refresh(true);
  }

  function selectFilter(group: "collection" | "tag", value: string) {
    const selected = value ? Number(value) : undefined;
    if (group === "collection") setCollectionId(selected);
    else setTagId(selected);
    setPage(1);
    refresh(true);
  }

  function showModal(value: Modal, paper: LibraryPaper | null = null) {
    setNotice(null);
    setAttachment(paper);
    setModal(value);
  }

  function resetFilters() {
    setQuery("");
    setSearchInput("");
    setCollectionId(undefined);
    setTagId(undefined);
    setPage(1);
    refresh(true);
  }

  async function addManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.title.trim() || pending) return;
    setPending(true);
    setNotice(null);
    try {
      await api.createPaper({
        title: draft.title.trim(),
        authors: draft.authors.trim() || null,
        source: draft.source.trim() || null,
        abstract: draft.abstract.trim() || null,
        url: draft.url.trim() || null,
      });
      setDraft(blankPaper);
      setModal(null);
      resetFilters();
      setNotice({ text: pick("Paper added to your library.", "গবেষণাপত্রটি আপনার লাইব্রেরিতে যোগ হয়েছে।") });
    } catch {
      setNotice({ error: true, text: pick("The paper could not be saved.", "গবেষণাপত্রটি সংরক্ষণ করা যায়নি।") });
    } finally {
      setPending(false);
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    const title = String(form.get("title") ?? "").trim();
    if (!(file instanceof File) || !file.size) return;
    setPending(true);
    setNotice(null);
    try {
      await api.uploadLibraryPDF(file, title || undefined, attachment?.id);
      setModal(null);
      if (attachment) refresh();
      else resetFilters();
      setNotice({ text: pick("PDF added to your library.", "PDF আপনার লাইব্রেরিতে যোগ হয়েছে।") });
    } catch (cause) {
      const status = cause instanceof ApiError ? cause.status : 0;
      const text = status === 413
        ? pick("This PDF is too large to upload.", "এই PDF আপলোড করার জন্য খুব বড়।")
        : status === 415 || status === 422
          ? pick("Choose a valid, unencrypted PDF.", "একটি বৈধ, পাসওয়ার্ডবিহীন PDF বেছে নিন।")
          : pick("The PDF could not be uploaded.", "PDF আপলোড করা যায়নি।");
      setNotice({ error: true, text });
    } finally {
      setPending(false);
    }
  }

  async function remove(paper: LibraryPaper, pdfOnly: boolean) {
    const confirmed = window.confirm(pdfOnly
      ? pick("Remove the PDF attachment?", "সংযুক্ত PDF সরাবেন?")
      : pick("Remove this paper from your library?", "লাইব্রেরি থেকে এই গবেষণাপত্র সরাবেন?"));
    if (!confirmed || pending) return;
    setPending(true);
    setNotice(null);
    try {
      if (pdfOnly) await api.deleteLibraryPDF(paper.id);
      else if (paper.legacy_paper_id !== null) await api.deletePaper(paper.legacy_paper_id);
      setNotice({ text: pdfOnly ? pick("PDF removed.", "PDF সরানো হয়েছে।") : pick("Paper removed.", "গবেষণাপত্র সরানো হয়েছে।") });
      refresh();
    } catch {
      setNotice({ error: true, text: pick("The item could not be removed.", "আইটেমটি সরানো যায়নি।") });
    } finally {
      setPending(false);
    }
  }

  async function retryIndexing(paper: LibraryPaper) {
    if (!paper.document || pending) return;
    setPending(true);
    setNotice(null);
    try {
      const status = await api.retryDocument(paper.document.id);
      setResult((current) => current && ({
        ...current,
        items: current.items.map((item) => item.id === paper.id && item.document
          ? { ...item, document: { ...item.document, status: status.status, version: status.version } }
          : item),
      }));
      setNotice({ text: pick("Document indexing was queued again.", "ডকুমেন্ট ইনডেক্স আবার কিউ করা হয়েছে।") });
    } catch {
      setNotice({ error: true, text: pick("Document indexing could not be retried.", "ডকুমেন্ট ইনডেক্স আবার শুরু করা যায়নি।") });
    } finally {
      setPending(false);
    }
  }

  const number = (value: number) => value.toLocaleString(locale);
  const field = (key: keyof typeof blankPaper, value: string) => setDraft((current) => ({ ...current, [key]: value }));
  const closeModal = () => { if (!pending) showModal(null); };
  const alert = notice && <p className={"notice " + (notice.error ? "error" : "success")} role={notice.error ? "alert" : "status"}>{notice.text}</p>;
  const filtersActive = query || collectionId !== undefined || tagId !== undefined;

  return (
    <>
      <div className="mb-5 flex flex-wrap gap-2">
        <button type="button" className="button primary" onClick={() => showModal("upload")} disabled={pending}>
          <Icon name="file-text" size={17} />{pick("Upload PDF", "PDF আপলোড")}
        </button>
        <button type="button" className="button secondary" onClick={() => showModal("manual")} disabled={pending}>
          <Icon name="plus" size={17} />{pick("Add paper manually", "নিজে গবেষণাপত্র যোগ করুন")}
        </button>
      </div>
      {!modal && notice && <div className="mb-4">{alert}</div>}

      <div className="library-layout">
        <aside aria-label={pick("Library filters", "লাইব্রেরি ফিল্টার")} className="card form-stack">
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-1">
              <h2 className="font-semibold">{pick("Collections", "সংগ্রহ")}</h2>
              <button className="button secondary small" type="button" onClick={() => showModal("collections")}>{pick("Manage", "পরিচালনা")}</button>
            </div>
            <label className="field">
              <span className="sr-only">{pick("Filter by collection", "সংগ্রহ দিয়ে ফিল্টার করুন")}</span>
              <select value={collectionId ?? ""} onChange={(event) => selectFilter("collection", event.target.value)}>
                <option value="">{pick("All collections", "সব সংগ্রহ")}</option>
                {collections.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
              </select>
            </label>
          </div>
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-1">
              <h2 className="font-semibold">{pick("Tags", "ট্যাগ")}</h2>
              <button className="button secondary small" type="button" onClick={() => showModal("tags")}>{pick("Manage", "পরিচালনা")}</button>
            </div>
            <label className="field">
              <span className="sr-only">{pick("Filter by tag", "ট্যাগ দিয়ে ফিল্টার করুন")}</span>
              <select value={tagId ?? ""} onChange={(event) => selectFilter("tag", event.target.value)}>
                <option value="">{pick("All tags", "সব ট্যাগ")}</option>
                {tags.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
              </select>
            </label>
          </div>
          {filterError && (
            <div className="notice error" role="alert">
              <p>{pick("Filters could not be loaded.", "ফিল্টার লোড করা যায়নি।")}</p>
              <button type="button" className="button secondary small mt-2" onClick={() => setOrganizationRevision((value) => value + 1)}>{pick("Try again", "আবার চেষ্টা করুন")}</button>
            </div>
          )}
        </aside>
        <div className="min-w-0">
          <section className="card mb-4" aria-label={pick("Search library", "লাইব্রেরিতে খুঁজুন")}>
            <form className="search-form flex-wrap" onSubmit={search}>
              <input type="search" className="min-w-[12rem]" maxLength={300} value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                aria-label={pick("Search titles, authors, and abstracts", "শিরোনাম, লেখক ও সারসংক্ষেপ খুঁজুন")}
                placeholder={pick("Titles, authors, or abstracts", "শিরোনাম, লেখক বা সারসংক্ষেপ")} />
              <button className="button secondary" type="submit" disabled={loading}>
                <Icon name="search" size={17} />{pick("Search", "খুঁজুন")}
              </button>
              {filtersActive && <button className="button ghost" type="button" onClick={resetFilters}>{pick("Clear filters", "ফিল্টার মুছুন")}</button>}
            </form>
          </section>

          {loading && <p className="loading-state" role="status">{pick("Opening your library…", "আপনার লাইব্রেরি খোলা হচ্ছে…")}</p>}
          {loadError && <div className="notice error" role="alert">
            <p>{pick("Your library could not be loaded.", "আপনার লাইব্রেরি লোড করা যায়নি।")}</p>
            <button type="button" className="button secondary small mt-2" onClick={() => refresh(true)}>{pick("Try again", "আবার চেষ্টা করুন")}</button>
          </div>}
          {result && (
            <>
              <div className="section-heading mb-4">
                <h2>{filtersActive ? pick("Matching papers", "মিলে যাওয়া গবেষণাপত্র") : pick("Saved papers", "সংরক্ষিত গবেষণাপত্র")}</h2>
                <span className="muted text-sm">{number(result.total)} {pick("papers", "টি গবেষণাপত্র")}</span>
              </div>
              {result.items.length === 0 && <section className="card empty-state">
                <Icon name="library" size={30} />
                <p>{filtersActive ? pick("No papers match these filters.", "এই ফিল্টারের সাথে কোনো গবেষণাপত্র মেলেনি।") : pick("Your library is empty.", "আপনার লাইব্রেরি খালি।")}</p>
              </section>}
              <div className="grid gap-3">
                {result.items.map((paper) => {
                  const url = sourceUrl(paper.url);
                  const selectedLabels = [
                    ...collections.filter((item) => paper.collection_ids.includes(item.id)).map((item) => ({ ...item, key: "collection-" + item.id })),
                    ...tags.filter((item) => paper.tag_ids.includes(item.id)).map((item) => ({ ...item, key: "tag-" + item.id })),
                  ];
                  return (
                    <article className="card min-w-0" key={paper.id}>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {paper.source && <span className="tag">{paper.source}</span>}
                        {paper.document && (
                          <>
                            <span className="tag" aria-label={pick("Document indexing status", "ডকুমেন্ট ইনডেক্সের অবস্থা")}>
                              {({
                                pending: pick("Pending indexing", "ইনডেক্সের অপেক্ষায়"),
                                processing: pick("Indexing", "ইনডেক্স করা হচ্ছে"),
                                completed: pick("Indexed", "ইনডেক্স সম্পন্ন"),
                                failed: pick("Indexing failed", "ইনডেক্স ব্যর্থ"),
                              })[paper.document.status]}
                            </span>
                            <span className="muted text-xs">
                              {paper.document.page_count.toLocaleString(locale)} {pick("pages", "পৃষ্ঠা")}
                            </span>
                          </>
                        )}
                        {selectedLabels.map((item) => <span className="tag break-all" key={item.key}>{item.name}</span>)}
                      </div>
                      <h3 className="text-lg font-semibold break-words">{paper.title}</h3>
                      {paper.authors && <p className="muted mt-1 text-sm">{paper.authors}</p>}
                      {paper.abstract && <p className="muted mt-3 line-clamp-3 text-sm leading-7">{paper.abstract}</p>}
                      <ReadingProgressForm
                        key={[paper.reading_status, paper.reading_progress_percent].join("-")}
                        paper={paper} refresh={refresh}
                      />
                      <div className="paper-actions">
                        <button type="button" className="button primary small" onClick={() => setViewer(paper)}>
                          <Icon name={paper.document ? "file-text" : "pen"} size={16} />
                          {paper.document ? pick("Read PDF", "PDF পড়ুন") : pick("Notes and highlights", "নোট ও হাইলাইট")}
                        </button>
                        <button type="button" className="button secondary small" onClick={() => setOrganizing(paper)}>{pick("Organize", "সাজান")}</button>
                        {!paper.document && <button type="button" className="button secondary small" disabled={pending} onClick={() => showModal("upload", paper)}>{pick("Attach PDF", "PDF সংযুক্ত করুন")}</button>}
                        {paper.document && <button type="button" className="button secondary small" disabled={pending} onClick={() => void remove(paper, true)}>{pick("Remove PDF", "PDF সরান")}</button>}
                        {paper.document?.status === "failed" && <button type="button" className="button secondary small" disabled={pending} onClick={() => void retryIndexing(paper)}>{pick("Retry indexing", "ইনডেক্স আবার করুন")}</button>}
                        {url && <a className="button secondary small" href={url} target="_blank" rel="noopener noreferrer">{pick("Read original", "মূল প্রকাশনা পড়ুন")}<Icon name="external-link" size={14} /></a>}
                        {paper.legacy_paper_id !== null && <button type="button" className="button ghost small" disabled={pending} onClick={() => void remove(paper, false)}>{pick("Remove paper", "গবেষণাপত্র সরান")}</button>}
                      </div>
                    </article>
                  );
                })}
              </div>
              {result.pages > 1 && <nav className="mt-6 flex flex-wrap items-center justify-between gap-2" aria-label={pick("Library pages", "লাইব্রেরির পৃষ্ঠা")}>
                <button type="button" className="button secondary small" disabled={page <= 1} onClick={() => { setPage(page - 1); refresh(true); }}>{pick("Previous", "আগের")}</button>
                <span className="muted text-sm">{pick("Page", "পৃষ্ঠা")} {number(page)} / {number(result.pages)}</span>
                <button type="button" className="button secondary small" disabled={page >= result.pages} onClick={() => { setPage(page + 1); refresh(true); }}>{pick("Next", "পরের")}</button>
              </nav>}
            </>
          )}
        </div>
      </div>

      {modal === "manual" && (
        <LibraryDialog title={pick("Add a paper manually", "নিজে গবেষণাপত্র যোগ করুন")} onClose={closeModal}>
          <form className="form-stack" onSubmit={addManual}>
            <label className="field">{pick("Paper title", "গবেষণাপত্রের শিরোনাম")}
              <input required maxLength={255} value={draft.title} onChange={(event) => field("title", event.target.value)} />
            </label>
            <div className="inline-fields">
              <label className="field">{pick("Authors", "লেখকবৃন্দ")}
                <input maxLength={255} value={draft.authors} onChange={(event) => field("authors", event.target.value)} />
              </label>
              <label className="field">{pick("Publication or source", "প্রকাশনা বা উৎস")}
                <input maxLength={100} value={draft.source} onChange={(event) => field("source", event.target.value)} />
              </label>
            </div>
            <label className="field">{pick("Original paper URL", "মূল গবেষণাপত্রের লিংক")}
              <input maxLength={500} type="url" value={draft.url} onChange={(event) => field("url", event.target.value)} />
            </label>
            <label className="field">{pick("Abstract", "সারসংক্ষেপ")}
              <textarea maxLength={5000} value={draft.abstract} onChange={(event) => field("abstract", event.target.value)} />
            </label>
            {alert}
            <button className="button primary self-start" type="submit" disabled={pending}>{pending ? pick("Saving…", "সংরক্ষণ হচ্ছে…") : pick("Save to library", "লাইব্রেরিতে সংরক্ষণ করুন")}</button>
          </form>
        </LibraryDialog>
      )}
      {modal === "upload" && (
        <LibraryDialog title={attachment ? pick("Attach PDF", "PDF সংযুক্ত করুন") : pick("Upload PDF", "PDF আপলোড")} onClose={closeModal}>
          <form className="form-stack" onSubmit={upload}>
            {attachment ? <p className="muted break-words">{attachment.title}</p> : (
              <label className="field">{pick("Paper title (optional)", "গবেষণাপত্রের শিরোনাম (ঐচ্ছিক)")}
                <input name="title" maxLength={255} disabled={pending} />
              </label>
            )}
            <label className="field">{pick("Choose a PDF", "একটি PDF বেছে নিন")}
              <input name="file" type="file" accept="application/pdf,.pdf" required disabled={pending} />
            </label>
            {alert}
            <button className="button primary self-start" type="submit" disabled={pending}>
              {pending ? pick("Uploading…", "আপলোড হচ্ছে…") : pick("Upload", "আপলোড করুন")}
            </button>
          </form>
        </LibraryDialog>
      )}
      {(modal === "collections" || modal === "tags") && (
        <OrganizeLibrary group={modal} items={modal === "collections" ? collections : tags}
          refresh={() => { setOrganizationRevision((value) => value + 1); refresh(); }} close={closeModal} />
      )}
      {viewer && <DocumentViewer paper={viewer} onClose={() => { setViewer(null); refresh(); }} />}
      {organizing && <PaperOrganization paper={organizing} collections={collections} tags={tags}
        refresh={refresh} close={() => setOrganizing(null)} />}
    </>
  );
}
