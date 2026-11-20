import type { CSSProperties } from "react";

const paths: Record<string, string> = {
  dashboard: "M3 3h7v7H3z M14 3h7v4h-7z M14 11h7v10h-7z M3 14h7v7H3z",
  search: "m21 21-5-5 M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15",
  discover: "m21 21-5-5 M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15",
  library: "M4 4h4v16H4z M10 4h4v16h-4z m6 1 4-1 4 15-4 1z",
  book: "M3 4h6a4 4 0 0 1 3 2 4 4 0 0 1 3-2h6v15h-6a4 4 0 0 0-3 2 4 4 0 0 0-3-2H3z M12 6v15",
  "book-open": "M3 4h6a4 4 0 0 1 3 2 4 4 0 0 1 3-2h6v15h-6a4 4 0 0 0-3 2 4 4 0 0 0-3-2H3z M12 6v15",
  "file-text": "M6 3h9l4 4v14H6z M14 3v5h5 M9 12h6 M9 16h5",
  assistant: "M7 5h10v3h3v12H4V8h3z M9 12v2 M15 12v2 M9 17h6 M12 2v3",
  sparkles: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z",
  analysis: "M6 3h9l4 4v14H6z M14 3v5h5 M9 12h7 M9 16h5",
  writing: "m4 16 12-12 4 4-12 12-5 1z M14 6l4 4",
  pen: "m4 16 12-12 4 4-12 12-5 1z M14 6l4 4",
  citations: "M4 6h6v6H5c0 4 2 5 4 5 M14 6h6v6h-5c0 4 2 5 4 5",
  projects: "M3 6h7l2 3h9v11H3z M3 6V4h7l2 2",
  folder: "M3 6h7l2 3h9v11H3z M3 6V4h7l2 2",
  insights: "M4 20V4 M4 20h17 M8 16l4-6 4 3 5-8",
  learn: "m2 9 10-5 10 5-10 5z M6 11v6c4 3 8 3 12 0v-6 M22 9v8",
  teams: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M2 21v-2a7 7 0 0 1 14 0v2 M17 4a4 4 0 0 1 0 8 M20 21v-2a7 7 0 0 0-2-5",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  close: "m6 6 12 12 M6 18 18 6",
  x: "m6 6 12 12 M6 18 18 6",
  arrow: "M4 12h16 M14 6l6 6-6 6",
  arrowRight: "M4 12h16 M14 6l6 6-6 6",
  "arrow-right": "M4 12h16 M14 6l6 6-6 6",
  check: "m5 12 4 4L19 6",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z m-4 9 3 3 5-6",
  lock: "M5 10h14v11H5z M8 10V7a4 4 0 0 1 8 0v3",
  globe: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M3 12h18 M12 3c-5 5-5 13 0 18 5-5 5-13 0-18",
  plus: "M12 5v14 M5 12h14",
  trash: "M4 6h16 M9 6V3h6v3 M6 6l1 15h10l1-15 M10 10v7 M14 10v7",
  download: "M12 3v12 m-5-5 5 5 5-5 M4 16v5h16v-5",
  logout: "M9 4H4v16h5 M9 12h12 m-5-5 5 5-5 5",
  mail: "M3 5h18v14H3z m0 1 9 7 9-7",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M4 21v-2a8 8 0 0 1 16 0v2",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 7v6l4 2",
  external: "M14 3h7v7 M21 3l-10 10 M10 4H4v16h16v-6",
  "external-link": "M14 3h7v7 M21 3l-10 10 M10 4H4v16h16v-6",
  activity: "M3 12h4l2-7 4 14 2-7h6",
  sliders: "M4 6h16 M4 12h16 M4 18h16 M8 4v4 M16 10v4 M10 16v4",
  monitor: "M3 4h18v12H3z M12 16v5 M8 21h8",
  leaf: "M20 3C7 2 2 8 5 15s15 4 15-12z M5 20l10-11"
};

export function Icon({ name, size = 20, className, style }: {
  name: string; size?: number; className?: string; style?: CSSProperties;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
      focusable="false" className={className} style={style}>
      <path d={paths[name] ?? paths.book} />
    </svg>
  );
}
