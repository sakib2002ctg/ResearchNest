"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import {
  api,
  ApiError,
  type DiscoveryPaper,
  type DiscoveryResponse,
  type DiscoverySearchRequest,
  type DiscoverySource,
  type DiscoverySort,
  type PublicationType,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

const sourceOptions: Array<{ value: DiscoverySource; label: string }> = [
  { value: "arxiv", label: "arXiv" },
  { value: "openalex", label: "OpenAlex" },
  { value: "crossref", label: "Crossref" },
  { value: "semantic_scholar", label: "Semantic Scholar" },
  { value: "pubmed", label: "PubMed" },
];

const publicationTypes: Array<{ value: PublicationType; en: string; bn: string }> = [
  { value: "article", en: "Article", bn: "প্রবন্ধ" },
  { value: "review", en: "Review", bn: "পর্যালোচনা" },
  { value: "preprint", en: "Preprint", bn: "প্রিপ্রিন্ট" },
  { value: "book", en: "Book", bn: "বই" },
  { value: "book_chapter", en: "Book chapter", bn: "বইয়ের অধ্যায়" },
  { value: "conference", en: "Conference paper", bn: "সম্মেলন প্রবন্ধ" },
  { value: "other", en: "Other", bn: "অন্যান্য" },
];

type SaveState = "saving" | "saved" | "error";
const minYear = 1800;
const maxYear = 2200;

function paperKey(paper: DiscoveryPaper): string {
  return paper.doi?.toLowerCase() || paper.url || `${paper.source}:${paper.external_id || paper.title}`;
}

function displaySource(source: string): string {
  return sourceOptions.find((option) => option.value === source)?.label ?? source;
}

export default function DiscoverPage() {
  const { isAuthenticated } = useAuth();
  const { pick, locale } = useI18n();
  const router = useRouter();
  const [queryInput, setQueryInput] = useState("");
  const [doiInput, setDoiInput] = useState("");
  const [selectedSources, setSelectedSources] = useState<DiscoverySource[]>(
    sourceOptions.map((source) => source.value),
  );
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [publicationType, setPublicationType] = useState<PublicationType | "">("");
  const [sort, setSort] = useState<DiscoverySort>("relevance");
  const [limit, setLimit] = useState(10);
  const [result, setResult] = useState<DiscoveryResponse | null>(null);
  const [doiPaper, setDoiPaper] = useState<DiscoveryPaper | null>(null);
  const [loading, setLoading] = useState(false);
  const [doiLoading, setDoiLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [doiError, setDoiError] = useState<string | null>(null);
  const [saveStates, setSaveStates] = useState<Record<string, SaveState>>({});
  const requestId = useRef(0);
  const lastSearch = useRef<Omit<DiscoverySearchRequest, "offset"> | null>(null);

  function messageFor(cause: unknown, isDoiLookup = false): string {
    const status = cause instanceof ApiError ? cause.status : undefined;
    if (status === 404 && isDoiLookup) {
      return pick("No paper was found for that DOI.", "ওই DOI দিয়ে কোনো গবেষণাপত্র পাওয়া যায়নি।");
    }
    if (status === 422 && isDoiLookup) {
      return pick("Check the DOI and try again.", "DOI দেখে আবার চেষ্টা করুন।");
    }
    if (status === 429) {
      return pick("Too many requests. Wait a moment and try again.", "অনেক অনুরোধ পাঠানো হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।");
    }
    return pick("The search could not be completed. Please try again.", "অনুসন্ধান সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।");
  }

  async function runSearch(parameters: Omit<DiscoverySearchRequest, "offset">, offset = 0) {
    const request = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const response = await api.searchDiscovery({ ...parameters, offset });
      if (request === requestId.current) setResult(response);
    } catch (cause: unknown) {
      if (request === requestId.current) setError(messageFor(cause));
    } finally {
      if (request === requestId.current) setLoading(false);
    }
  }

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = queryInput.trim();
    if (q.length < 2) {
      setError(pick("Enter at least two characters to search.", "অনুসন্ধানের জন্য অন্তত দুইটি অক্ষর লিখুন।"));
      return;
    }
    if (selectedSources.length === 0) {
      setError(pick("Choose at least one source.", "অন্তত একটি উৎস বেছে নিন।"));
      return;
    }
    const from = yearFrom.trim() ? Number(yearFrom) : undefined;
    const to = yearTo.trim() ? Number(yearTo) : undefined;
    if ((from !== undefined && (!Number.isInteger(from) || from < minYear || from > maxYear)) ||
      (to !== undefined && (!Number.isInteger(to) || to < minYear || to > maxYear)) ||
      (from !== undefined && to !== undefined && from > to)) {
      setError(pick("Enter a valid year range from 1800 to 2200.", "১৮০০ থেকে ২২০০ সালের মধ্যে সঠিক বছরসীমা লিখুন।"));
      return;
    }
    const parameters: Omit<DiscoverySearchRequest, "offset"> = {
      q,
      sources: selectedSources,
      ...(from === undefined ? {} : { year_from: from }),
      ...(to === undefined ? {} : { year_to: to }),
      ...(publicationType ? { publication_type: publicationType } : {}),
      sort,
      limit,
    };
    lastSearch.current = parameters;
    void runSearch(parameters);
  }

  async function lookupDOI(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const doi = doiInput.trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, "");
    if (!doi) {
      setDoiError(pick("Enter a DOI to look up.", "খুঁজতে একটি DOI লিখুন।"));
      return;
    }
    setDoiLoading(true);
    setDoiError(null);
    try {
      setDoiPaper(await api.getDiscoveryDOI(doi));
    } catch (cause: unknown) {
      setDoiPaper(null);
      setDoiError(messageFor(cause, true));
    } finally {
      setDoiLoading(false);
    }
  }

  async function savePaper(paper: DiscoveryPaper) {
    const key = paperKey(paper);
    if (!isAuthenticated) {
      router.push("/login?next=%2Fdiscover");
      return;
    }
    if (saveStates[key] === "saving" || saveStates[key] === "saved") return;
    setSaveStates((current) => ({ ...current, [key]: "saving" }));
    try {
      const saved = await api.saveDiscoveryPaper(paper);
      setSaveStates((current) => ({ ...current, [key]: saved.saved || saved.already_saved ? "saved" : "error" }));
    } catch {
      setSaveStates((current) => ({ ...current, [key]: "error" }));
    }
  }

  function toggleSource(source: DiscoverySource) {
    setSelectedSources((selected) =>
      selected.includes(source) ? selected.filter((value) => value !== source) : [...selected, source],
    );
  }

  function changeLimit(value: number) {
    setLimit(value);
    if (lastSearch.current) {
      const next = { ...lastSearch.current, limit: value };
      lastSearch.current = next;
      void runSearch(next);
    }
  }

  function changePage(offset: number) {
    if (lastSearch.current) void runSearch(lastSearch.current, offset);
  }

  function paperCard(paper: DiscoveryPaper, key: string) {
    const saveState = saveStates[paperKey(paper)];
    const canSave = Boolean(paper.external_id || paper.doi);
    const badges = paper.sources?.length ? paper.sources : [paper.source];
    const paperType = publicationTypes.find(({ value }) => value === paper.paper_type);
    const published = paper.publication_date
      ? new Date(paper.publication_date).toLocaleDateString(locale, {
        year: "numeric",
        month: "short",
        day: "numeric",
        timeZone: "UTC",
      })
      : null;
    return (
      <article className="paper-card" key={key}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {badges.map((source) => <span className="tag" key={source}>{displaySource(source)}</span>)}
          {paperType && <span className="tag">{pick(paperType.en, paperType.bn)}</span>}
          {published && <time className="tag" dateTime={paper.publication_date ?? undefined}>{published}</time>}
        </div>
        <h3>{paper.title}</h3>
        {paper.authors.length > 0 && <p className="muted">{paper.authors.join(", ")}</p>}
        {paper.abstract && <p>{paper.abstract}</p>}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 16px", marginTop: 8 }}>
          {paper.citation_count !== null && paper.citation_count !== undefined && (
            <span className="muted">
              {pick("Citations", "উদ্ধৃতি")}: {paper.citation_count.toLocaleString(locale)}
            </span>
          )}
          {paper.doi && <span className="muted">DOI: {paper.doi}</span>}
        </div>
        {paper.citation_links.length > 0 && (
          <details style={{ marginTop: 10 }}>
            <summary style={{ cursor: "pointer" }}>{pick("Related citation links", "সম্পর্কিত উদ্ধৃতি লিংক")} ({paper.citation_links.length})</summary>
            <ul style={{ paddingLeft: 20 }}>
              {paper.citation_links.slice(0, 8).map((citation, index) => (
                <li key={`${citation.doi || citation.url || citation.title}-${index}`}>
                  {citation.url ? <a href={citation.url} target="_blank" rel="noreferrer">{citation.title || citation.doi || citation.url}</a> : (citation.title || citation.doi)}
                  <span className="muted"> · {displaySource(citation.source)}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
        <div className="paper-actions">
          {paper.url && (
            <a className="button secondary small" href={paper.url} target="_blank" rel="noreferrer">
              <Icon name="external-link" size={15} /> {pick("View source", "উৎস দেখুন")}
            </a>
          )}
          {canSave && <button className="button primary small" type="button" onClick={() => void savePaper(paper)}
            disabled={saveState === "saving" || saveState === "saved"}>
            <Icon name={saveState === "saved" ? "check" : "plus"} size={15} />
            {saveState === "saving" ? pick("Saving…", "সংরক্ষণ হচ্ছে…")
              : saveState === "saved" ? pick("Saved to library", "লাইব্রেরিতে সংরক্ষিত")
                : pick("Save to My Library", "আমার লাইব্রেরিতে সংরক্ষণ")}
          </button>}
          {saveState === "error" && <span className="muted" role="status">{pick("Save failed. Try again.", "সংরক্ষণ হয়নি। আবার চেষ্টা করুন।")}</span>}
        </div>
      </article>
    );
  }

  return (
    <AppShell title={pick("Discover papers", "গবেষণাপত্র খুঁজুন")} description={pick(
      "Search academic sources and save useful papers to your library.",
      "একাডেমিক উৎসে খুঁজুন এবং দরকারি প্রবন্ধ আপনার লাইব্রেরিতে সংরক্ষণ করুন।",
    )} showHeading>
      <section className="card" aria-labelledby="discovery-search-title">
        <h2 id="discovery-search-title" style={{ marginTop: 0 }}>{pick("Search academic sources", "একাডেমিক উৎসে অনুসন্ধান")}</h2>
        <form onSubmit={search}>
          <label className="field" htmlFor="discovery-query">{pick("Topic, title, author, or keyword", "বিষয়, শিরোনাম, লেখক বা কীওয়ার্ড")}</label>
          <div className="search-form" style={{ marginTop: 8 }}>
            <input id="discovery-query" type="search" value={queryInput} onChange={(event) => setQueryInput(event.target.value)}
              placeholder={pick("e.g. climate adaptation", "যেমন: জলবায়ু অভিযোজন")} minLength={2} maxLength={300} required />
            <button className="button primary" type="submit" disabled={loading}>
              <Icon name="search" size={17} /> {loading ? pick("Searching…", "খোঁজা হচ্ছে…") : pick("Search", "অনুসন্ধান")}
            </button>
          </div>
          <fieldset style={{ border: 0, padding: 0, margin: "18px 0 0" }}>
            <legend className="field" style={{ marginBottom: 8 }}>{pick("Sources", "উৎস")}</legend>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 18px" }}>
              {sourceOptions.map((source) => (
                <label key={source.value} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 13 }}>
                  <input type="checkbox" checked={selectedSources.includes(source.value)} onChange={() => toggleSource(source.value)} />
                  {source.label}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="inline-fields" style={{ marginTop: 16 }}>
            <label className="field">{pick("From year", "শুরুর বছর")}
              <input type="number" min={minYear} max={maxYear} value={yearFrom} onChange={(event) => setYearFrom(event.target.value)} />
            </label>
            <label className="field">{pick("To year", "শেষের বছর")}
              <input type="number" min={minYear} max={maxYear} value={yearTo} onChange={(event) => setYearTo(event.target.value)} />
            </label>
            <label className="field">{pick("Publication type", "প্রকাশনার ধরন")}
              <select value={publicationType} onChange={(event) => setPublicationType(event.target.value as PublicationType | "")}>
                <option value="">{pick("Any type", "যেকোনো ধরন")}</option>
                {publicationTypes.map((type) => <option key={type.value} value={type.value}>{pick(type.en, type.bn)}</option>)}
              </select>
            </label>
            <label className="field">{pick("Sort by", "সাজান")}
              <select value={sort} onChange={(event) => setSort(event.target.value as DiscoverySort)}>
                <option value="relevance">{pick("Relevance", "প্রাসঙ্গিকতা")}</option>
                <option value="date">{pick("Newest first", "নতুন আগে")}</option>
              </select>
            </label>
          </div>
        </form>
      </section>

      <section className="card" style={{ marginTop: 18 }} aria-labelledby="doi-lookup-title">
        <h2 id="doi-lookup-title" style={{ marginTop: 0 }}>{pick("Look up a DOI", "DOI দিয়ে খুঁজুন")}</h2>
        <form className="search-form" onSubmit={(event) => void lookupDOI(event)}>
          <input aria-label={pick("DOI", "DOI")} value={doiInput} onChange={(event) => setDoiInput(event.target.value)}
            placeholder="10.1038/s41586-020-2649-2" maxLength={300} />
          <button className="button secondary" type="submit" disabled={doiLoading}>
            {doiLoading ? pick("Looking up…", "খোঁজা হচ্ছে…") : pick("Look up", "খুঁজুন")}
          </button>
        </form>
        {doiError && <p className="notice error" role="alert" style={{ marginTop: 12 }}>{doiError}</p>}
        {doiPaper && <div style={{ marginTop: 8 }}>{paperCard(doiPaper, `doi-${paperKey(doiPaper)}`)}</div>}
      </section>

      {error && <p className="notice error" role="alert" style={{ marginTop: 18 }}>{error}</p>}
      {loading && <p className="loading-state" role="status" style={{ marginTop: 18 }}>{pick("Searching academic sources…", "একাডেমিক উৎসে খোঁজা হচ্ছে…")}</p>}
      {!loading && !error && result && (
        <section className="card" style={{ marginTop: 18 }} aria-live="polite">
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>{pick("Search results", "অনুসন্ধানের ফলাফল")} · {result.total.toLocaleString(locale)}</h2>
            <label className="field" style={{ flexDirection: "row", alignItems: "center" }}>
              {pick("Per page", "প্রতি পাতায়")}
              <select value={limit} onChange={(event) => changeLimit(Number(event.target.value))} style={{ minHeight: 36 }}>
                {[10, 20, 50].map((count) => <option key={count} value={count}>{count.toLocaleString(locale)}</option>)}
              </select>
            </label>
          </div>
          {result.warnings.length > 0 && <p className="notice" style={{ marginTop: 12 }}>
            {pick("Sources unavailable for this search", "এই অনুসন্ধানে অনুপলব্ধ উৎস")}: {result.warnings.map(displaySource).join(", ")}
          </p>}
          {result.items.length === 0 ? (
            <div className="empty-state"><Icon name="search" size={26} /><p>{pick("No papers found. Try another search or source.", "কোনো প্রবন্ধ পাওয়া যায়নি। অন্য অনুসন্ধান বা উৎস চেষ্টা করুন।")}</p></div>
          ) : (
            <div className="paper-list">{result.items.map((paper, index) => paperCard(paper, `${paperKey(paper)}-${index}`))}</div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center", marginTop: 14 }}>
            <span className="muted">
              {result.items.length === 0
                ? (0).toLocaleString(locale)
                : `${(result.offset + 1).toLocaleString(locale)}–${(result.offset + result.items.length).toLocaleString(locale)}`} {pick("of", "এর মধ্যে")} {result.total.toLocaleString(locale)}
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="button secondary small" type="button" disabled={loading || result.offset <= 0}
                onClick={() => changePage(Math.max(0, result.offset - result.limit))}>{pick("Previous", "আগের")}</button>
              <button className="button secondary small" type="button" disabled={loading || result.offset + result.limit >= result.total}
                onClick={() => changePage(result.offset + result.limit)}>{pick("Next", "পরের")}</button>
            </div>
          </div>
        </section>
      )}
    </AppShell>
  );
}
