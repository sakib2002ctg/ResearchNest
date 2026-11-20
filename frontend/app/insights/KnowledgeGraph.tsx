"use client";

import { useMemo, useState } from "react";
import type { GraphNode, KnowledgeGraph as Graph } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { graphWindow, layoutGraph } from "@/lib/knowledge-graph";
import styles from "./insights.module.css";

const nodeColors: Record<GraphNode["type"], string> = { paper: "#2e7859", author: "#477fb2", project: "#8b5fa8", topic: "#b47926", tag: "#b34e77" };
const typeNames: Record<GraphNode["type"], [string, string]> = { paper: ["Paper", "গবেষণাপত্র"], author: ["Author", "লেখক"], project: ["Project", "প্রকল্প"], topic: ["Topic", "বিষয়"], tag: ["Tag", "ট্যাগ"] };
const edgeNames: Record<string, [string, string]> = { authored_by: ["Authored by", "লেখক"], tagged_with: ["Tagged with", "ট্যাগযুক্ত"], project_contains: ["Project contains", "প্রকল্পে আছে"], cites_or_related: ["Recorded citation / relation", "নথিভুক্ত উদ্ধৃতি / সম্পর্ক"], shared_topic_inferred: ["Inferred shared topic", "অনুমিত মিলযুক্ত বিষয়"] };

export function KnowledgeGraph({ graph }: { graph: Graph }) {
  const { pick } = useI18n();
  const [query, setQuery] = useState("");
  const [type, setType] = useState("all");
  const [inferred, setInferred] = useState(true);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const window = useMemo(() => graphWindow(graph, { query, type, inferred, page, size: 120 }), [graph, query, type, inferred, page]);
  const layout = useMemo(() => layoutGraph(window.nodes), [window.nodes]);
  const positions = new Map(layout.nodes.map((node) => [node.id, node]));
  const node = graph.nodes.find((item) => item.id === selected);
  const neighbors = selected ? graph.edges.filter((edge) => (edge.source === selected || edge.target === selected) && (inferred || edge.origin === "verified_metadata")) : [];
  return <section className="card">
    <h2>{pick("Knowledge graph explorer", "জ্ঞান গ্রাফ অনুসন্ধান")}</h2>
    <p className={styles.small}>{pick("Explore relationships in your own library. Solid edges represent stored metadata or explicit user records; dashed edges are inferred similarities, not verified citations.", "আপনার লাইব্রেরির সম্পর্ক দেখুন। একটানা রেখা সংরক্ষিত মেটাডেটা বা ব্যবহারকারীর নথি; ড্যাশযুক্ত রেখা অনুমিত মিল, যাচাইকৃত উদ্ধৃতি নয়।")}</p>
    <div className={styles.legend}><span><i />{pick("Verified metadata / recorded relation", "যাচাইকৃত মেটাডেটা / নথিভুক্ত সম্পর্ক")}</span><span><i className={styles.inferred} />{pick("Inferred relationship", "অনুমিত সম্পর্ক")}</span></div>
    <div className={styles.toolbar}>
      <label className="field">{pick("Find a node", "নোড খুঁজুন")}<input value={query} onChange={(e) => { setQuery(e.target.value); setPage(0); setSelected(null); }} /></label>
      <label className="field">{pick("Node type", "নোডের ধরন")}<select value={type} onChange={(e) => { setType(e.target.value); setPage(0); setSelected(null); }}><option value="all">{pick("All types", "সব ধরন")}</option>{Object.entries(typeNames).map(([value, labels]) => <option value={value} key={value}>{pick(...labels)}</option>)}</select></label>
      <label className={styles.checkbox}><input type="checkbox" checked={inferred} onChange={(e) => { setInferred(e.target.checked); setPage(0); setSelected(null); }} />{pick("Show inferred", "অনুমিত সম্পর্ক দেখান")}</label>
      <button className="button secondary small" disabled={zoom >= 2.5} onClick={() => setZoom((v) => Math.min(2.5, v + 0.25))} aria-label={pick("Zoom in", "বড় করুন")}>+</button><button className="button secondary small" disabled={zoom <= 0.75} onClick={() => setZoom((v) => Math.max(0.75, v - 0.25))} aria-label={pick("Zoom out", "ছোট করুন")}>−</button><button className="button ghost small" onClick={() => setZoom(1)}>{pick("Reset zoom", "স্বাভাবিক আকার")}</button>
    </div>
    <div className={styles.legend}>{Object.entries(nodeColors).map(([key, color]) => <span key={key}><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill={color} /></svg>{pick(...typeNames[key as GraphNode["type"]])}</span>)}</div>
    <p className={styles.small}>{pick(`Showing ${window.nodes.length} of ${window.total} matching nodes and ${window.edges.length} connecting edges. Up to 120 nodes per view; filter or change page for other nodes.`, `${window.total}টি মিলের মধ্যে ${window.nodes.length}টি নোড ও ${window.edges.length}টি সংযোগ দেখানো হচ্ছে। প্রতি দৃশ্যে সর্বোচ্চ ১২০টি নোড; অন্য নোড দেখতে ফিল্টার বা পাতা বদলান।`)}</p>
    {graph.truncated && <p className="notice" role="status">{pick(`The server graph is bounded to ${graph.limits.papers} papers, ${graph.limits.nodes} nodes and ${graph.limits.edges} edges. Choose a project for a narrower graph.`, `সার্ভার গ্রাফের সীমা ${graph.limits.papers}টি গবেষণাপত্র, ${graph.limits.nodes}টি নোড ও ${graph.limits.edges}টি সংযোগ। ছোট গ্রাফের জন্য প্রকল্প বাছুন।`)}</p>}
    {graph.project_scope?.truncated && <p className="notice" role="status">{pick(`Project metadata includes ${graph.project_scope.included_projects} of ${graph.project_scope.total_projects} projects.`, `প্রকল্পের মেটাডেটায় ${graph.project_scope.total_projects}টির মধ্যে ${graph.project_scope.included_projects}টি প্রকল্প রয়েছে।`)}</p>}
    {layout.nodes.length ? <div className={styles.graphFrame}><svg className={styles.graph} style={{ width: `${zoom * 100}%` }} viewBox={`0 0 ${layout.width} ${layout.height}`} aria-label={pick("Interactive knowledge graph. Select a node for its recorded and inferred connections.", "ইন্টার‌্যাক্টিভ জ্ঞান গ্রাফ। নথিভুক্ত ও অনুমিত সম্পর্ক দেখতে নোড বাছুন।")}>
      {window.edges.map((edge) => { const source = positions.get(edge.source); const target = positions.get(edge.target); return source && target ? <line key={edge.id} x1={source.x} y1={source.y} x2={target.x} y2={target.y} data-origin={edge.origin}><title>{pick(...(edgeNames[edge.type] || [edge.type, edge.type]))} · {edge.origin}</title></line> : null; })}
      {layout.nodes.map((item) => <g key={item.id} transform={`translate(${item.x} ${item.y})`} role="button" tabIndex={0} aria-label={`${pick(...typeNames[item.type])}: ${item.label}`} aria-pressed={selected === item.id} onClick={() => setSelected(item.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(item.id); } }}><title>{item.label}</title><circle r={item.type === "paper" ? 9 : 7} fill={nodeColors[item.type]} /><text x={13} y={4}>{item.label.length > 23 ? `${item.label.slice(0, 22)}…` : item.label}</text></g>)}
    </svg></div> : <p className="muted">{pick("No nodes match these filters.", "এই ফিল্টারে কোনো নোড নেই।")}</p>}
    <div className={styles.pagination}><button className="button secondary small" disabled={window.page <= 0} onClick={() => { setPage((v) => v - 1); setSelected(null); }}>{pick("Previous nodes", "আগের নোড")}</button><span>{window.page + 1}/{window.pageCount}</span><button className="button secondary small" disabled={window.page >= window.pageCount - 1} onClick={() => { setPage((v) => v + 1); setSelected(null); }}>{pick("Next nodes", "পরের নোড")}</button></div>
    {node && <div className={styles.detail} aria-live="polite"><h3>{node.label}</h3><p className={styles.small}>{pick(...typeNames[node.type])} · {node.origin === "verified_metadata" ? pick("Stored metadata or user record", "সংরক্ষিত মেটাডেটা বা ব্যবহারকারীর নথি") : pick("Inferred topic", "অনুমিত বিষয়")} · {node.provenance}</p><ul className={styles.list}>{neighbors.slice(0, 100).map((edge) => { const other = graph.nodes.find((n) => n.id === (edge.source === selected ? edge.target : edge.source)); return <li key={edge.id}><span>{other?.label || pick("Unknown node", "অজানা নোড")}<br /><small>{pick(...(edgeNames[edge.type] || [edge.type, edge.type]))}</small></span><span>{edge.origin === "verified_metadata" ? pick("Recorded", "নথিভুক্ত") : pick("Inferred", "অনুমিত")}</span></li>; })}</ul>{!neighbors.length && <p className={styles.small}>{pick("No connections in the current origin filter.", "বর্তমান ফিল্টারে কোনো সংযোগ নেই।")}</p>}{neighbors.length > 100 && <p className={styles.small}>{pick("First 100 connections shown.", "প্রথম ১০০টি সংযোগ দেখানো হচ্ছে।")}</p>}</div>}
  </section>;
}
