"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  api, ApiError, type AIProvider, type AIUsageStats, type DocumentAsset, type DocumentAssetDetail,
  type DocumentAssets, type Language, type VisionAnswer,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { assetTablePreview, filterDocumentAssets, type AssetFilter } from "@/lib/multimodal";
import styles from "./multimodal.module.css";

const filters: Array<{ value: AssetFilter; labels: [string, string] }> = [
  { value: "all", labels: ["All", "সব"] },
  { value: "visual", labels: ["Figures & charts", "চিত্র ও লেখচিত্র"] },
  { value: "table", labels: ["Tables", "সারণি"] },
  { value: "equation", labels: ["Equations", "সমীকরণ"] },
];
const names: Record<DocumentAsset["asset_type"], [string, string]> = {
  figure: ["Figure", "চিত্র"], chart: ["Chart", "লেখচিত্র"], diagram: ["Diagram", "নকশা"],
  table: ["Table", "সারণি"], equation: ["Equation", "সমীকরণ"],
};

export function MultimodalAssetsPanel({ documentId, documentVersion, indexed = true }: {
  documentId: number; documentVersion: number; indexed?: boolean;
}) {
  const { user } = useAuth();
  return user ? <AssetsWorkspace key={`${user.id}-${documentId}-${documentVersion}`} documentId={documentId} indexed={indexed} /> : null;
}

function AssetsWorkspace({ documentId, indexed }: { documentId: number; indexed: boolean }) {
  const { pick, language: uiLanguage, locale } = useI18n();
  const [result, setResult] = useState<DocumentAssets | null>(null);
  const [filter, setFilter] = useState<AssetFilter>("all");
  const [page, setPage] = useState("");
  const [revision, setRevision] = useState(0);
  const [pending, setPending] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [actionError, setActionError] = useState(0);
  const [detail, setDetail] = useState<DocumentAssetDetail | null>(null);
  const [detailPending, setDetailPending] = useState(false);
  const [language, setLanguage] = useState<Language>(uiLanguage);
  const [provider, setProvider] = useState<AIProvider>("auto");
  const [consent, setConsent] = useState(false);
  const [usage, setUsage] = useState<AIUsageStats | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<VisionAnswer | null>(null);
  const alive = useRef(true);
  const detailTicket = useRef(0);
  const retry = useRef<{ fingerprint: string; id: string } | null>(null);
  const extracting = result?.extraction?.status === "queued" || result?.extraction?.status === "running";
  const stale = Boolean(result?.is_stale);

  useEffect(() => {
    alive.current = true;
    let active = true;
    const refresh = () => {
      Promise.all([api.getPreferences(), api.getAIUsage()]).then(([preferences, stats]) => {
        if (active) { setConsent(preferences.allow_external_ai); setUsage(stats); }
      }).catch(() => {});
    };
    refresh();
    window.addEventListener("focus", refresh);
    return () => { active = false; alive.current = false; window.removeEventListener("focus", refresh); };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let active = true;
    async function load() {
      try {
        const data = await api.getDocumentAssets(documentId, { page_number: page ? Number(page) : undefined }, controller.signal);
        if (!active) return;
        setResult(data); setLoadError(false);
        if (data.extraction?.status === "queued" || data.extraction?.status === "running") timer = setTimeout(load, 2000);
      } catch {
        if (active && !controller.signal.aborted) setLoadError(true);
      }
    }
    void load();
    return () => { active = false; controller.abort(); if (timer) clearTimeout(timer); };
  }, [documentId, page, revision]);

  async function extract() {
    setPending(true); setActionError(0);
    try {
      const extraction = await api.extractDocumentAssets(documentId);
      if (!alive.current) return;
      ++detailTicket.current; setDetailPending(false); setDetail(null); setAnswer(null); setQuestion("");
      setResult((old) => ({ items: old?.items || [], extraction, is_stale: old?.is_stale || false }));
      setRevision((old) => old + 1);
    } catch (cause) { if (alive.current) setActionError(cause instanceof ApiError ? cause.status || -1 : -1); }
    finally { if (alive.current) setPending(false); }
  }

  async function openAsset(id: number) {
    const ticket = ++detailTicket.current;
    setDetailPending(true); setActionError(0); setDetail(null); setAnswer(null); setQuestion("");
    retry.current = null;
    try {
      const data = await api.getDocumentAsset(id);
      if (alive.current && ticket === detailTicket.current) setDetail(data);
    } catch (cause) { if (alive.current && ticket === detailTicket.current) setActionError(cause instanceof ApiError ? cause.status || -1 : -1); }
    finally { if (alive.current && ticket === detailTicket.current) setDetailPending(false); }
  }

  async function generate(vqa: boolean) {
    if (!detail || stale || extracting) return;
    const fingerprint = JSON.stringify([detail.id, language, provider, vqa ? question.trim() : null]);
    const request_id = retry.current?.fingerprint === fingerprint ? retry.current.id : crypto.randomUUID();
    retry.current = { fingerprint, id: request_id };
    setPending(true); setActionError(0);
    try {
      const options = { language, provider, request_id };
      const data = vqa ? await api.questionDocumentAsset(detail.id, { ...options, question: question.trim() }) : await api.explainDocumentAsset(detail.id, options);
      if (!alive.current) return;
      setAnswer(data); retry.current = null;
      const stats = await api.getAIUsage(); if (alive.current) setUsage(stats);
    } catch (cause) {
      if (alive.current) {
        const status = cause instanceof ApiError ? cause.status || -1 : -1;
        setActionError(status);
        if (status === 409) { retry.current = null; setRevision((old) => old + 1); }
      }
    } finally { if (alive.current) setPending(false); }
  }

  const items = filterDocumentAssets(result?.items || [], filter);
  const status = result?.extraction?.status;
  return <section className={styles.panel} aria-label={pick("Multimodal assets: figures, tables and equations", "বহুমাধ্যমের উপাদান: চিত্র, সারণি ও সমীকরণ")}>
    <header className={styles.heading}><div><h3>{pick("Figures, tables & equations", "চিত্র, সারণি ও সমীকরণ")}</h3><p className="muted text-xs">{pick("Extract source visuals and ask questions with evidence.", "উৎসের দৃশ্যমান উপাদান বের করুন এবং প্রমাণভিত্তিক প্রশ্ন করুন।")}</p></div>
      <button type="button" className="button secondary small" disabled={!indexed || pending || extracting} onClick={extract}>{extracting ? pick("Extracting…", "নিষ্কাশন চলছে…") : result?.extraction ? pick("Refresh assets", "উপাদান আবার বের করুন") : pick("Extract assets", "উপাদান বের করুন")}</button>
    </header>
    {!indexed && <p className="notice">{pick("Finish indexing the PDF before extracting assets.", "উপাদান নিষ্কাশনের আগে পিডিএফ ইনডেক্স সম্পন্ন করুন।")}</p>}
    <p className={styles.integrity}>{pick("Extracted facts and AI visual interpretation are shown separately. Unlabeled chart values and unverified equations must not be treated as facts.", "নিষ্কাশিত তথ্য ও এআইয়ের দৃশ্য ব্যাখ্যা আলাদা দেখানো হয়। লেখচিত্রের অনুল্লিখিত মান বা যাচাই না করা সমীকরণকে সত্য বলে ধরবেন না।")}</p>
    {stale && <p role="status" className="notice">{pick("These assets belong to an older document version. Refresh extraction before asking questions.", "এই উপাদানগুলো নথির পুরোনো সংস্করণের। প্রশ্ন করার আগে আবার নিষ্কাশন করুন।")}</p>}
    {status && <p role="status" className="muted text-sm">{pick("Extraction", "নিষ্কাশন")}: {status === "queued" ? pick("Queued", "সারিতে আছে") : status === "running" ? pick("Processing", "প্রক্রিয়াধীন") : status === "failed" ? pick("Failed — refresh to retry", "ব্যর্থ — আবার নিষ্কাশন করুন") : pick("Completed", "সম্পন্ন")}</p>}
    {loadError && <p role="alert" className="notice error">{pick("Assets could not be loaded.", "উপাদান লোড করা যায়নি।")} <button type="button" disabled={pending} onClick={() => setRevision((old) => old + 1)}>{pick("Retry", "আবার চেষ্টা করুন")}</button></p>}
    {actionError !== 0 && <p role="alert" className="notice error">{actionError === 403 ? pick("Enable external AI consent in Settings to use cloud vision.", "ক্লাউড দৃশ্য বিশ্লেষণের জন্য সেটিংসে বাহ্যিক এআই অনুমতি দিন।") : actionError === 429 ? pick("AI fair-use quota reached. Wait and retry.", "এআই ব্যবহারের সীমা পূর্ণ হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।") : actionError === 409 ? pick("The document or asset changed. Refresh and try again.", "নথি বা উপাদান বদলেছে। রিফ্রেশ করে আবার চেষ্টা করুন।") : pick("The request could not be completed. Please retry.", "অনুরোধ সম্পন্ন হয়নি। আবার চেষ্টা করুন।")}</p>}
    <div className={styles.filters} role="group" aria-label={pick("Asset type", "উপাদানের ধরন")}>{filters.map((item) => <button key={item.value} type="button" aria-pressed={filter === item.value} disabled={pending} onClick={() => setFilter(item.value)}>{pick(...item.labels)}</button>)}</div>
    <label className={styles.pageFilter}>{pick("Page number (empty for all)", "পৃষ্ঠা নম্বর (সব পৃষ্ঠার জন্য ফাঁকা)")}<input type="number" min={1} max={1000} value={page} disabled={pending} onChange={(event) => { const value = event.target.value; if (value === "" || (Number.isInteger(Number(value)) && Number(value) >= 1 && Number(value) <= 1000)) { setPage(value); ++detailTicket.current; setDetailPending(false); setDetail(null); setAnswer(null); } }} /></label>
    {!result && !loadError ? <p role="status">{pick("Loading assets…", "উপাদান লোড হচ্ছে…")}</p> : items.length === 0 && !loadError ? <p className="muted text-sm">{pick("No extracted assets match this filter.", "এই বাছাইয়ে কোনো নিষ্কাশিত উপাদান নেই।")}</p> : null}
    <div className={styles.assetGrid}>{items.map((asset) => <article key={asset.id} className={styles.assetCard}><div className={styles.heading}><strong>{asset.asset_label || pick(...names[asset.asset_type])}</strong><span className="tag">{pick("p.", "পৃষ্ঠা")} {asset.page_number.toLocaleString(locale)}</span></div>
      {asset.caption && <p>{asset.caption}</p>}<AssetContent asset={asset} />
      <button type="button" className="button secondary small" disabled={pending || stale || extracting} aria-pressed={detail?.id === asset.id} onClick={() => openAsset(asset.id)}>{pick("Open asset & visual Q&A", "উপাদান খুলুন ও দৃশ্যভিত্তিক প্রশ্ন করুন")}</button>
    </article>)}</div>
    {detailPending && <p role="status">{pick("Loading source details…", "উৎসের বিবরণ লোড হচ্ছে…")}</p>}
    {detail && <section className={styles.details} aria-label={pick("Selected asset", "নির্বাচিত উপাদান")}>
      <div className={styles.heading}><h4>{detail.asset_label || pick(...names[detail.asset_type])} · {pick("Page", "পৃষ্ঠা")} {detail.page_number.toLocaleString(locale)}</h4><button type="button" className="button secondary small" disabled={pending} onClick={() => { ++detailTicket.current; setDetail(null); setAnswer(null); }}>{pick("Close asset", "উপাদান বন্ধ করুন")}</button></div>
      {detail.has_image && <PrivateAssetImage key={detail.id} asset={detail} />}
      {detail.caption && <p>{detail.caption}</p>}<AssetContent asset={detail} />
      {detail.linked_chunks.length > 0 && <details className={styles.linked}><summary>{pick("Linked text passages", "যুক্ত পাঠ্যাংশ")} ({detail.linked_chunks.length})</summary>{detail.linked_chunks.map((chunk) => <article key={chunk.id} id={`multimodal-${documentId}-chunk-${chunk.id}`}><strong>{pick("Page", "পৃষ্ঠা")} {chunk.page_number} {chunk.section_heading && `· ${chunk.section_heading}`}</strong><p className={styles.pre}>{chunk.content}</p></article>)}</details>}
      {detail.ai_explanation && !answer && <details><summary>{pick("Saved explanation — review required", "সংরক্ষিত ব্যাখ্যা — যাচাই প্রয়োজন")}</summary><p className={styles.pre}>{detail.ai_explanation}</p></details>}
      {!consent && <p className="muted text-xs">{pick("Cloud vision is disabled. Local/offline analysis remains available.", "ক্লাউড দৃশ্য বিশ্লেষণ বন্ধ। স্থানীয়/অফলাইন বিশ্লেষণ করা যাবে।")} <Link href="/settings">{pick("Privacy settings", "গোপনীয়তা সেটিংস")}</Link></p>}
      {usage && <p className="muted text-xs">{pick("Remaining this hour", "এই ঘণ্টায় অবশিষ্ট")}: {usage.hourly.remaining_requests.toLocaleString(locale)} {pick("requests", "অনুরোধ")} · {usage.hourly.remaining_tokens.toLocaleString(locale)} {pick("tokens", "টোকেন")}</p>}
      <div className={styles.controls}><label>{pick("Response language", "উত্তরের ভাষা")}<select value={language} disabled={pending} onChange={(event) => setLanguage(event.target.value as Language)}><option value="en">English</option><option value="bn">বাংলা</option></select></label>
        <label>{pick("Vision provider", "দৃশ্য বিশ্লেষণের ব্যবস্থা")}<select value={provider} disabled={pending} onChange={(event) => setProvider(event.target.value as AIProvider)}><option value="auto">{pick("Default", "ডিফল্ট")}</option><option value="offline">{pick("Offline extracted facts", "অফলাইন নিষ্কাশিত তথ্য")}</option><option value="local">{pick("Local vision model", "স্থানীয় দৃশ্য বিশ্লেষণের মডেল")}</option><option value="cloud" disabled={!consent}>{pick("Cloud vision (consent required)", "ক্লাউড বিশ্লেষণ (অনুমতি প্রয়োজন)")}</option></select></label>
        <button type="button" className="button secondary small" disabled={pending || stale || extracting} onClick={() => generate(false)}>{pick("Explain asset", "উপাদান ব্যাখ্যা করুন")}</button>
      </div>
      <form className={styles.question} onSubmit={(event) => { event.preventDefault(); void generate(true); }}><label>{pick("Visual question", "দৃশ্যভিত্তিক প্রশ্ন")}<textarea minLength={2} maxLength={1000} rows={2} required value={question} disabled={pending} onChange={(event) => setQuestion(event.target.value)} placeholder={pick("What does this figure or table explicitly show?", "এই চিত্র বা সারণিতে স্পষ্টভাবে কী দেখানো হয়েছে?")} /></label><button className="button primary small" disabled={pending || stale || extracting || question.trim().length < 2}>{pending ? pick("Preparing answer…", "উত্তর তৈরি হচ্ছে…") : pick("Ask with evidence", "প্রমাণভিত্তিক প্রশ্ন করুন")}</button></form>
      {answer && <VisionResult answer={answer} documentId={documentId} detail={detail} />}
    </section>}
  </section>;
}

function AssetContent({ asset }: { asset: DocumentAsset }) {
  const { pick } = useI18n();
  const table = assetTablePreview(asset);
  if (table) return <div className={styles.tableWrap}><table><caption>{asset.asset_label || pick("Extracted table", "নিষ্কাশিত সারণি")}</caption>{table.headers.length > 0 && <thead><tr>{table.headers.map((value, i) => <th scope="col" key={i}>{value || pick("Unlabeled", "শিরোনাম নেই")}</th>)}</tr></thead>}<tbody>{table.rows.map((row, i) => <tr key={i}>{row.map((value, j) => <td key={j}>{value}</td>)}</tr>)}</tbody></table>{table.total > table.rows.length && <p className="muted text-xs">{pick("Preview shows the first 10 rows. Full extracted text is available below.", "প্রিভিউতে প্রথম ১০টি সারি দেখানো হয়। সম্পূর্ণ নিষ্কাশিত লেখা নিচে আছে।")}</p>}{asset.extracted_text_or_latex && <details><summary>{pick("Full extracted table text", "সারণির সম্পূর্ণ নিষ্কাশিত লেখা")}</summary><pre className={styles.pre}>{asset.extracted_text_or_latex}</pre></details>}</div>;
  if (!asset.extracted_text_or_latex) return null;
  return <div><p className="muted text-xs">{asset.asset_type === "equation" ? pick("Extracted expression — notation is not independently verified", "নিষ্কাশিত রাশি — সংকেত স্বতন্ত্রভাবে যাচাই করা হয়নি") : pick("Extracted source labels", "উৎস থেকে নিষ্কাশিত লেবেল")}</p><pre className={styles.pre}>{asset.extracted_text_or_latex}</pre></div>;
}

function PrivateAssetImage({ asset }: { asset: DocumentAsset }) {
  const { pick } = useI18n();
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = "";
    let active = true;
    api.getDocumentAssetImage(asset.id, controller.signal).then((blob) => {
      if (!active) return;
      objectUrl = URL.createObjectURL(blob); setUrl(objectUrl);
    }).catch(() => { if (active && !controller.signal.aborted) setFailed(true); });
    return () => { active = false; controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [asset.id]);
  if (failed) return <p role="alert">{pick("The private image is unavailable. Refresh the asset list.", "ব্যক্তিগত ছবিটি পাওয়া যাচ্ছে না। উপাদানের তালিকা রিফ্রেশ করুন।")}</p>;
  if (!url) return <p role="status">{pick("Loading private image…", "ব্যক্তিগত ছবি লোড হচ্ছে…")}</p>;
  // Private image bytes require the bearer client; a public URL/Next image proxy would bypass it.
  // eslint-disable-next-line @next/next/no-img-element
  return <img className={styles.image} src={url} alt={asset.caption || asset.asset_label || pick("Extracted source figure", "উৎস থেকে নিষ্কাশিত চিত্র")} />;
}

function VisionResult({ answer, documentId, detail }: { answer: VisionAnswer; documentId: number; detail: DocumentAssetDetail }) {
  const { pick } = useI18n();
  return <section className={styles.answer} aria-label={pick("Grounded visual answer", "প্রমাণভিত্তিক দৃশ্যের উত্তর")} aria-live="polite">
    <p className="tag">{answer.evidence_status === "supported" ? pick("Extracted evidence", "নিষ্কাশিত প্রমাণ") : answer.evidence_status === "partial_interpretation" ? pick("AI interpretation", "এআই ব্যাখ্যা") : pick("Insufficient evidence", "অপর্যাপ্ত প্রমাণ")}</p>
    {answer.extracted_facts.length > 0 && <section><h5>{pick("Extracted facts", "নিষ্কাশিত তথ্য")}</h5><ul>{answer.extracted_facts.map((fact, i) => <li key={i} className={styles.pre}>{fact}</li>)}</ul></section>}
    {answer.visual_interpretation && <section><h5>{pick("AI visual interpretation — review required", "এআইয়ের দৃশ্য ব্যাখ্যা — যাচাই প্রয়োজন")}</h5><p className={styles.pre}>{answer.visual_interpretation}</p></section>}
    {answer.missing_information && <section><h5>{pick("Missing or unverified information", "অনুপস্থিত বা যাচাই না করা তথ্য")}</h5><p className={styles.pre}>{answer.missing_information}</p></section>}
    <p className="muted text-xs">{pick("Source", "উৎস")}: {answer.evidence.asset_label || detail.asset_label || pick("Asset", "উপাদান")} · {pick("page", "পৃষ্ঠা")} {answer.evidence.page_number}</p>
    <div className={styles.links}>{answer.evidence.linked_chunk_ids.filter((id) => detail.linked_chunks.some((chunk) => chunk.id === id)).map((id) => <a href={`#multimodal-${documentId}-chunk-${id}`} key={id}>{pick("Text passage", "পাঠ্যাংশ")} #{id}</a>)}</div>
    <p className="muted text-xs">{answer.provider_used} · {answer.model_used} · {answer.language === "bn" ? "বাংলা" : "English"}</p>
  </section>;
}
