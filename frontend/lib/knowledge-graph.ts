import type { GraphNode, KnowledgeGraph } from "./api";

const typeOrder: GraphNode["type"][] = ["project", "paper", "author", "tag", "topic"];

export function publicationBuckets(records: { year: number; count: number }[]) {
  const years = new Map<number, number>();
  records.forEach((record) => years.set(record.year, (years.get(record.year) || 0) + record.count));
  return [...years].sort(([a], [b]) => a - b).map(([year, count]) => ({ year, count }));
}

/** A bounded, deterministic view. Filters never create new relationships. */
export function graphWindow(graph: KnowledgeGraph, options: { query: string; type: string; inferred: boolean; page: number; size: number }) {
  const query = options.query.trim().toLocaleLowerCase();
  const filtered = graph.nodes.filter((node) =>
    (!query || node.label.toLocaleLowerCase().includes(query)) &&
    (options.type === "all" || node.type === options.type) &&
    (options.inferred || node.origin === "verified_metadata"),
  ).sort((a, b) => typeOrder.indexOf(a.type) - typeOrder.indexOf(b.type) || a.id.localeCompare(b.id));
  const pageCount = Math.max(1, Math.ceil(filtered.length / options.size));
  const page = Math.min(Math.max(0, options.page), pageCount - 1);
  const nodes = filtered.slice(page * options.size, (page + 1) * options.size);
  const ids = new Set(nodes.map((node) => node.id));
  const edges = graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target) && (options.inferred || edge.origin === "verified_metadata"));
  return { nodes, edges, total: filtered.length, pageCount, page };
}

export function layoutGraph(nodes: GraphNode[]) {
  const groups = typeOrder.map((type) => nodes.filter((node) => node.type === type));
  const height = Math.max(420, Math.max(0, ...groups.map((group) => group.length)) * 42 + 80);
  return {
    width: 1200, height,
    nodes: groups.flatMap((group, column) => group.map((node, index) => ({ ...node, x: 80 + column * 225, y: 65 + index * 42 }))),
  };
}
