"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { api, type AnalyticsOverview, type KnowledgeGraph as Graph, type ResearchProject, type ResearchTimeline } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { publicationBuckets } from "@/lib/knowledge-graph";
import { KnowledgeGraph } from "./KnowledgeGraph";
import styles from "./insights.module.css";

export default function InsightsPage() {
  return <Suspense fallback={<p role="status" className="loading-state">Loading insights… / অন্তর্দৃষ্টি লোড হচ্ছে…</p>}><InsightsPageContent /></Suspense>;
}

function InsightsPageContent() {
  const { user } = useAuth();
  const { pick } = useI18n();
  const params = useSearchParams();
  const value = params.get("project_id");
  const projectId = value && /^[1-9]\d*$/.test(value) ? value : "";
  return <AppShell title={pick("Research insights", "গবেষণার অন্তর্দৃষ্টি")} description={pick("Understand your library coverage, publication trends, and research connections.", "লাইব্রেরির পরিধি, প্রকাশনার প্রবণতা ও গবেষণার সম্পর্ক বুঝুন।")} showHeading>{user && <Insights key={`${user.id}:${projectId}`} initialProjectId={projectId} />}</AppShell>;
}

function Insights({ initialProjectId }: { initialProjectId: string }) {
  const { pick, locale } = useI18n();
  const [projects, setProjects] = useState<ResearchProject[]>([]);
  const [projectPage, setProjectPage] = useState(0);
  const [moreProjects, setMoreProjects] = useState(false);
  const [projectId, setProjectId] = useState(initialProjectId);
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [timeline, setTimeline] = useState<ResearchTimeline | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState("");
  const [filterError, setFilterError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api.getProjects(50, projectPage * 50, controller.signal).then((rows) => { if (!controller.signal.aborted) { setProjects((items) => projectPage ? [...items.filter((item) => !rows.some((row) => row.id === item.id)), ...rows] : rows); setMoreProjects(rows.length === 50); setFilterError(""); } }).catch(() => { if (!controller.signal.aborted) setFilterError("Unable to load project filters / প্রকল্প ফিল্টার লোড হয়নি।"); });
    return () => controller.abort();
  }, [projectPage, revision]);
  useEffect(() => {
    const controller = new AbortController();
    const id = projectId ? Number(projectId) : undefined;
    Promise.all([api.getAnalyticsOverview(id, controller.signal), api.getAnalyticsTimeline(id, controller.signal), api.getKnowledgeGraph(id, controller.signal)])
      .then(([summary, events, network]) => { if (!controller.signal.aborted) { setOverview(summary); setTimeline(events); setGraph(network); setError(""); } })
      .catch(() => { if (!controller.signal.aborted) setError("Unable to load research insights. Check access to the selected project and retry. / অন্তর্দৃষ্টি লোড হয়নি। প্রকল্পের অনুমতি দেখে আবার চেষ্টা করুন।"); });
    return () => controller.abort();
  }, [projectId, revision]);

  function changeProject(value: string) { setProjectId(value); setOverview(null); setTimeline(null); setGraph(null); }
  const nf = (value: number) => value.toLocaleString(locale, { maximumFractionDigits: 1 });
  return <>
    <div className={styles.toolbar}><label className="field">{pick("Research scope", "গবেষণার পরিধি")}<select value={projectId} onChange={(e) => changeProject(e.target.value)}><option value="">{pick("My entire library", "আমার পুরো লাইব্রেরি")}</option>{projectId && !projects.some((p) => String(p.id) === projectId) && <option value={projectId}>{pick(`Project ${projectId}`, `প্রকল্প ${projectId}`)}</option>}{projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></label>{moreProjects && <button className="button secondary small" onClick={() => setProjectPage((v) => v + 1)}>{pick("Load more projects", "আরও প্রকল্প লোড করুন")}</button>}<button className="button secondary" onClick={() => setRevision((v) => v + 1)}>{pick("Refresh insights", "অন্তর্দৃষ্টি রিফ্রেশ")}</button></div>
    {filterError && <p className="notice error" role="alert">{filterError}</p>}
    {error && <p className="notice error" role="alert">{error}</p>}
    {!overview && !error && <p className="loading-state" role="status">{pick("Computing your research insights…", "আপনার গবেষণার অন্তর্দৃষ্টি গণনা হচ্ছে…")}</p>}
    {overview && <>
      {overview.scope.truncated && <p className="notice" role="status">{pick(`Insights summarize ${overview.scope.included_papers} of ${overview.scope.total_papers} papers. Choose a project for a narrower scope.`, `অন্তর্দৃষ্টিতে ${overview.scope.total_papers}টির মধ্যে ${overview.scope.included_papers}টি গবেষণাপত্র রয়েছে। ছোট পরিধির জন্য প্রকল্প বাছুন।`)}</p>}
      {overview.project_scope?.truncated && <p className="notice" role="status">{pick(`Project metadata includes ${overview.project_scope.included_projects} of ${overview.project_scope.total_projects} projects. The project count shows the full total.`, `প্রকল্পের মেটাডেটায় ${overview.project_scope.total_projects}টির মধ্যে ${overview.project_scope.included_projects}টি প্রকল্প রয়েছে। প্রকল্পের সংখ্যা সম্পূর্ণ মোট দেখায়।`)}</p>}
      {overview.coverage.analysis_freshness?.truncated && <p className="notice" role="status">{pick(`Analysis counts are a confirmed lower bound. Current-source freshness was checked for ${overview.coverage.analysis_freshness.checked_papers} papers; ${overview.coverage.analysis_freshness.unchecked_papers} remain unchecked within this scope. Choose a smaller project for more complete verification.`, `বিশ্লেষণের সংখ্যা নিশ্চিত সর্বনিম্ন পরিমাণ। এই পরিধিতে ${overview.coverage.analysis_freshness.checked_papers}টি গবেষণাপত্রের বর্তমান উৎস যাচাই হয়েছে; ${overview.coverage.analysis_freshness.unchecked_papers}টি যাচাই বাকি। পূর্ণাঙ্গ যাচাইয়ের জন্য ছোট প্রকল্প বাছুন।`)}</p>}
      <div className={styles.metrics}>
        {[[pick("Saved papers", "সংরক্ষিত গবেষণাপত্র"), overview.coverage.saved, pick("In the selected scope", "নির্বাচিত পরিধিতে")], [pick("Indexed papers", "ইনডেক্স করা গবেষণাপত্র"), overview.coverage.indexed, `${nf(overview.coverage.indexed_percent)}% ${pick("of saved papers", "সংরক্ষিত গবেষণাপত্রের")}`], [pick("Analyzed papers", "বিশ্লেষিত গবেষণাপত্র"), overview.coverage.analysis_freshness?.truncated ? `≥ ${nf(overview.coverage.analyzed)}` : overview.coverage.analyzed, `${overview.coverage.analysis_freshness?.truncated ? "≥ " : ""}${nf(overview.coverage.analyzed_percent)}% ${pick("of saved papers", "সংরক্ষিত গবেষণাপত্রের")}`], [pick("Projects", "প্রকল্প"), overview.totals.projects, pick("Owned research workspaces", "আপনার গবেষণা কর্মপরিসর")]].map(([label, value, detail]) => <article key={String(label)} className={`card ${styles.metric}`}><p>{label}</p><strong>{typeof value === "number" ? nf(value) : value}</strong><p>{detail}</p></article>)}
      </div>
      <div className={styles.grid}>
        <section className="card"><h2>{pick("Publication trends", "প্রকাশনার প্রবণতা")}</h2><PublicationChart years={overview.publication_years} /><p className={styles.small}>{pick("Papers by recorded publication year. Saving a paper does not supply its publication date.", "নথিভুক্ত প্রকাশনার বছর অনুযায়ী গবেষণাপত্র। সংরক্ষণের তারিখ প্রকাশনার তারিখ নয়।")} {pick("Unknown year", "অজানা বছর")}: {nf(overview.unknown_publication_year_count)}</p></section>
        <section className="card"><h2>{pick("Reading & analysis coverage", "পড়া ও বিশ্লেষণের পরিধি")}</h2><ul className={styles.list}>{overview.reading_funnel.map((item) => <li key={item.status}><span>{item.status === "unread" ? pick("Unread", "পড়া হয়নি") : item.status === "reading" ? pick("Reading", "পড়ছি") : pick("Completed", "পড়া সম্পন্ন")}</span><strong>{nf(item.count)}</strong></li>)}<li><span>{pick("Not yet indexed", "এখনো ইনডেক্স হয়নি")}</span><strong>{nf(Math.max(0, overview.coverage.saved - overview.coverage.indexed))}</strong></li><li><span>{overview.coverage.analysis_freshness?.truncated ? pick("Analysis not confirmed current", "বর্তমান বিশ্লেষণ নিশ্চিত নয়") : pick("Not yet analyzed", "এখনো বিশ্লেষণ হয়নি")}</span><strong>{nf(Math.max(0, overview.coverage.saved - overview.coverage.analyzed))}</strong></li></ul><p className={styles.small}>{pick("Coverage measures processing of your saved library, not completeness of the wider literature.", "এটি আপনার সংরক্ষিত লাইব্রেরির প্রক্রিয়াকরণের পরিধি; সামগ্রিক সাহিত্যের সম্পূর্ণতা নয়।")}</p></section>
        <section className="card"><h2>{pick("Recurring authors & co-authorship", "পুনরাবৃত্ত লেখক ও সহলেখক")}</h2><CountList items={overview.authors} />{overview.coauthors.length > 0 && <><h3 className={styles.small}>{pick("Recorded co-authors", "নথিভুক্ত সহলেখক")}</h3><CountList items={overview.coauthors.slice(0, 8).map((item) => ({ name: `${item.source} ↔ ${item.target}`, count: item.count }))} /></>}</section>
        <section className="card"><h2>{pick("Venues & sources", "প্রকাশনাস্থল ও উৎস")}</h2><CountList items={overview.venues} /><h3 className={styles.small}>{pick("Provider sources", "প্রদানকারী উৎস")}</h3><CountList items={overview.sources} /></section>
        <section className="card"><h2>{pick("Topics & tags", "বিষয় ও ট্যাগ")}</h2><CountList items={overview.tags} /><ul className={styles.list}>{overview.topics.map((item) => <li key={item.name}><span>{item.name}<br /><small>{item.origin === "inferred_similarity" ? pick("Inferred topic", "অনুমিত বিষয়") : pick("Recorded metadata", "নথিভুক্ত মেটাডেটা")}</small></span><strong>{nf(item.count)}</strong></li>)}</ul>{!overview.tags.length && !overview.topics.length && <p className={styles.small}>{pick("No topics or tags yet.", "এখনো বিষয় বা ট্যাগ নেই।")}</p>}</section>
        <section className="card"><h2>{pick("Research timeline", "গবেষণার সময়রেখা")}</h2><ol className={styles.timeline}>{timeline?.items.map((item) => <li key={item.id}><time className={styles.small} dateTime={item.occurred_at}>{new Date(item.occurred_at).toLocaleString(locale)}</time><h3>{item.title}</h3><span className="tag">{timelineLabel(item.type, pick)}</span></li>)}</ol>{!timeline?.items.length && <p className={styles.small}>{pick("Your research activity will appear here.", "আপনার গবেষণার কার্যক্রম এখানে দেখা যাবে।")}</p>}{timeline?.truncated && <p className={styles.small}>{pick(`Showing the most recent ${timeline.limit} events.`, `সর্বশেষ ${timeline.limit}টি ঘটনা দেখানো হচ্ছে।`)}</p>}</section>
      </div>
    </>}
    {graph && <KnowledgeGraph key={projectId || "all"} graph={graph} />}
  </>;
}

function CountList({ items }: { items: { name: string; count: number }[] }) {
  const { pick, locale } = useI18n();
  return items.length ? <ul className={styles.list}>{items.slice(0, 12).map((item, index) => <li key={`${item.name}:${index}`}><span>{item.name}</span><strong>{item.count.toLocaleString(locale)}</strong></li>)}</ul> : <p className={styles.small}>{pick("No recorded metadata in this scope.", "এই পরিধিতে নথিভুক্ত মেটাডেটা নেই।")}</p>;
}

function PublicationChart({ years: records }: { years: AnalyticsOverview["publication_years"] }) {
  const { pick, locale } = useI18n();
  const years = publicationBuckets(records);
  if (!years.length) return <p className="empty-state">{pick("No recorded publication years yet.", "এখনো প্রকাশনার বছর নথিভুক্ত নেই।")}</p>;
  const width = Math.max(480, years.length * 48 + 70);
  const max = Math.max(1, ...years.map((item) => item.count));
  return <div className={styles.chart}><svg style={{ minWidth: width }} viewBox={`0 0 ${width} 270`} role="img" aria-label={pick("Publication year distribution, starting at zero", "শূন্য থেকে প্রকাশনার বছরের বণ্টন")}><title>{pick("Papers by publication year", "প্রকাশনার বছর অনুযায়ী গবেষণাপত্র")}</title>
    {[0, 0.5, 1].map((fraction) => <g key={fraction}><line x1={40} y1={220 - fraction * 180} x2={width - 15} y2={220 - fraction * 180} /><text x={32} y={224 - fraction * 180} textAnchor="end">{(max * fraction).toLocaleString(locale, { maximumFractionDigits: 1 })}</text></g>)}
    {years.map((item, index) => { const x = 50 + index * (width - 70) / years.length; const barWidth = Math.min(40, (width - 70) / years.length - 12); const height = item.count / max * 180; return <g key={item.year}><rect x={x} y={220 - height} width={barWidth} height={height} rx={3}><title>{item.year}: {item.count}</title></rect><text x={x + barWidth / 2} y={210 - height} textAnchor="middle">{item.count.toLocaleString(locale)}</text><text x={x + barWidth / 2} y={242} textAnchor="middle">{item.year}</text></g>; })}
  </svg></div>;
}

function timelineLabel(type: string, pick: (en: string, bn: string) => string) {
  const labels: Record<string, [string, string]> = { paper_saved: ["Paper saved", "গবেষণাপত্র সংরক্ষিত"], paper_indexed: ["Document indexed", "নথি ইনডেক্স সম্পন্ন"], paper_analyzed: ["Paper analyzed", "গবেষণাপত্র বিশ্লেষিত"], project_created: ["Project created", "প্রকল্প তৈরি"], task_created: ["Task created", "কাজ তৈরি"], task_completed: ["Task completed", "কাজ সম্পন্ন"], note_created: ["Research note", "গবেষণার নোট"] };
  return pick(...(labels[type] || [type.replaceAll("_", " "), type.replaceAll("_", " ")]));
}
