import type { DocumentAsset } from "./api";

export type AssetFilter = "all" | "visual" | "table" | "equation";

export function filterDocumentAssets(items: DocumentAsset[], filter: AssetFilter): DocumentAsset[] {
  if (filter === "all") return items;
  if (filter === "visual") return items.filter((item) => ["figure", "chart", "diagram"].includes(item.asset_type));
  return items.filter((item) => item.asset_type === filter);
}

export function assetTablePreview(asset: DocumentAsset): { headers: string[]; rows: string[][]; total: number } | null {
  if (asset.asset_type !== "table" || !asset.structured_data) return null;
  const data = asset.structured_data;
  if (!Array.isArray(data.rows)) return null;
  // Source cells are plain strings. Never interpret HTML or execute formulas.
  const cell = (value: unknown) => value == null ? "" : typeof value === "string" || typeof value === "number" ? String(value) : "";
  const headers = Array.isArray(data.headers) ? data.headers.slice(0, 20).map(cell) : [];
  const rows = data.rows.filter(Array.isArray).slice(0, 10).map((row) => row.slice(0, 20).map(cell));
  return { headers, rows, total: data.rows.length };
}
