"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type Conversation, type LibraryCollection, type LibraryPaper, type ProjectDetail, type ProjectInput, type ProjectStatus, type ProjectTask, type ResearchNote, type ResearchProject, type TaskStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { LibraryDialog } from "../library/DocumentViewer";
import styles from "./workspace.module.css";

export const statusLabels: Record<ProjectStatus, [string, string]> = { planning: ["Planning", "পরিকল্পনাধীন"], active: ["Active", "চলমান"], review: ["In review", "পর্যালোচনায়"], completed: ["Completed", "সম্পন্ন"], archived: ["Archived", "আর্কাইভে"] };
export const taskLabels: Record<TaskStatus, [string, string]> = { todo: ["To do", "করণীয়"], in_progress: ["In progress", "চলছে"], done: ["Done", "সম্পন্ন"] };
function localDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
function isoDate(value: string): string | null { return value ? new Date(value).toISOString() : null; }
function useAlive() { const alive = useRef(true); useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []); return alive; }

export function ProjectForm({ project, onClose, onSaved }: { project: ResearchProject | null; onClose: () => void; onSaved: (item: ResearchProject) => void }) {
  const { pick } = useI18n();
  const [title, setTitle] = useState(project?.title || "");
  const [description, setDescription] = useState(project?.description || "");
  const [objectives, setObjectives] = useState(project?.objectives.join("\n") || "");
  const [status, setStatus] = useState<ProjectStatus>(project?.status || "planning");
  const [deadline, setDeadline] = useState(localDate(project?.target_deadline || null));
  const [collection, setCollection] = useState(project?.collection_id ? String(project.collection_id) : "");
  const [collections, setCollections] = useState<LibraryCollection[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const alive = useAlive();
  useEffect(() => {
    let current = true;
    api.getLibraryCollections().then((rows) => { if (current) setCollections(rows); }).catch(() => { if (current) setError("Unable to load collections / সংগ্রহ লোড হয়নি।"); });
    return () => { current = false; };
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); setPending(true); setError("");
    try {
      const body: ProjectInput = { title: title.trim(), description: description.trim() || null, objectives: objectives.split("\n").map((v) => v.trim()).filter(Boolean), status, target_deadline: isoDate(deadline), collection_id: collection ? Number(collection) : null };
      const result = project ? await api.updateProject(project.id, { ...body, expected_revision: project.revision }) : await api.createProject(body);
      if (alive.current) onSaved(result);
    } catch (cause) { if (alive.current) setError(cause instanceof ApiError && cause.status === 409 ? pick("Project changed in another window. Close and reopen to load the latest version.", "অন্য উইন্ডোতে প্রকল্প বদলেছে। বন্ধ করে আবার খুলুন।") : pick("Unable to save. Check the fields and retry.", "সংরক্ষণ হয়নি। তথ্য দেখে আবার চেষ্টা করুন।")); }
    finally { if (alive.current) setPending(false); }
  }
  return <LibraryDialog title={pick(project ? "Edit project" : "Create project", project ? "প্রকল্প সম্পাদনা" : "প্রকল্প তৈরি")} onClose={onClose}><form onSubmit={save} className={styles.form}>
    {error && <p className="notice error" role="alert">{error}</p>}
    <label className="field">{pick("Title", "শিরোনাম")}<input required maxLength={250} value={title} onChange={(e) => setTitle(e.target.value)} /></label>
    <label className="field">{pick("Description", "বিবরণ")}<textarea maxLength={10000} value={description} onChange={(e) => setDescription(e.target.value)} /></label>
    <label className="field">{pick("Objectives — one per line", "উদ্দেশ্য — প্রতি লাইনে একটি")}<textarea value={objectives} maxLength={20000} onChange={(e) => setObjectives(e.target.value)} /></label>
    <div className={styles.grid}><label className="field">{pick("Status", "অবস্থা")}<select value={status} onChange={(e) => setStatus(e.target.value as ProjectStatus)}>{Object.entries(statusLabels).map(([s, labels]) => <option key={s} value={s}>{pick(...labels)}</option>)}</select></label><label className="field">{pick("Target deadline", "সময়সীমা")}<input type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label></div>
    <label className="field">{pick("Linked collection (optional)", "সংযুক্ত সংগ্রহ (ঐচ্ছিক)")}<select value={collection} onChange={(e) => setCollection(e.target.value)}><option value="">{pick("No collection", "কোনো সংগ্রহ নয়")}</option>{collections.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <button className="button primary" disabled={pending}>{pick("Save project", "প্রকল্প সংরক্ষণ")}</button>
  </form></LibraryDialog>;
}

export function TaskForm({ projectId, task, onClose, onSaved }: { projectId: number; task: ProjectTask | null; onClose: () => void; onSaved: () => void }) {
  const { pick } = useI18n();
  const [title, setTitle] = useState(task?.title || "");
  const [description, setDescription] = useState(task?.description || "");
  const [milestone, setMilestone] = useState(task?.is_milestone || false);
  const [status, setStatus] = useState<TaskStatus>(task?.status || "todo");
  const [due, setDue] = useState(localDate(task?.due_date || null));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const alive = useAlive();
  async function save(e: FormEvent) {
    e.preventDefault(); setPending(true); setError("");
    try { const body = { title: title.trim(), description: description || null, is_milestone: milestone, status, due_date: isoDate(due) }; if (task) await api.updateProjectTask(projectId, task.id, body); else await api.createProjectTask(projectId, body); if (alive.current) onSaved(); }
    catch { if (alive.current) setError(pick("Unable to save task.", "কাজ সংরক্ষণ হয়নি।")); } finally { if (alive.current) setPending(false); }
  }
  return <LibraryDialog title={pick(task ? "Edit task" : "Add task", task ? "কাজ সম্পাদনা" : "কাজ যোগ করুন")} onClose={onClose}><form className={styles.form} onSubmit={save}>{error && <p className="notice error" role="alert">{error}</p>}<label className="field">{pick("Title", "শিরোনাম")}<input required maxLength={250} value={title} onChange={(e) => setTitle(e.target.value)} /></label><label className="field">{pick("Description", "বিবরণ")}<textarea maxLength={10000} value={description} onChange={(e) => setDescription(e.target.value)} /></label><label className="field">{pick("Status", "অবস্থা")}<select value={status} onChange={(e) => setStatus(e.target.value as TaskStatus)}>{Object.entries(taskLabels).map(([value, labels]) => <option key={value} value={value}>{pick(...labels)}</option>)}</select></label><label className="field">{pick("Due date", "নির্ধারিত সময়")}<input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} /></label><label className={styles.checkbox}><input type="checkbox" checked={milestone} onChange={(e) => setMilestone(e.target.checked)} />{pick("This is a milestone", "এটি একটি মাইলফলক")}</label><button className="button primary" disabled={pending}>{pick("Save task", "কাজ সংরক্ষণ")}</button></form></LibraryDialog>;
}

export function NoteForm({ project, note, onClose, onSaved }: { project: ProjectDetail; note: ResearchNote | null; onClose: () => void; onSaved: () => void }) {
  const { pick } = useI18n();
  const [title, setTitle] = useState(note?.title || "");
  const [content, setContent] = useState(note?.content || "");
  const [paper, setPaper] = useState(note?.user_paper_id ? String(note.user_paper_id) : "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const alive = useAlive();
  async function save(e: FormEvent) {
    e.preventDefault(); setPending(true); setError("");
    try { const body = { title: title.trim(), content, user_paper_id: paper ? Number(paper) : null }; if (note) await api.updateProjectNote(project.id, note.id, body); else await api.createProjectNote(project.id, body); if (alive.current) onSaved(); }
    catch { if (alive.current) setError(pick("Unable to save note.", "নোট সংরক্ষণ হয়নি।")); } finally { if (alive.current) setPending(false); }
  }
  return <LibraryDialog title={pick(note ? "Edit note" : "Add note", note ? "নোট সম্পাদনা" : "নোট যোগ করুন")} onClose={onClose}><form className={styles.form} onSubmit={save}>{error && <p className="notice error" role="alert">{error}</p>}<label className="field">{pick("Title", "শিরোনাম")}<input required maxLength={250} value={title} onChange={(e) => setTitle(e.target.value)} /></label><label className="field">{pick("Note", "নোট")}<textarea required rows={8} maxLength={100000} value={content} onChange={(e) => setContent(e.target.value)} /></label><label className="field">{pick("Related paper (optional)", "সম্পর্কিত গবেষণাপত্র (ঐচ্ছিক)")}<select value={paper} onChange={(e) => setPaper(e.target.value)}><option value="">{pick("Project note", "প্রকল্পের নোট")}</option>{project.papers.map((p) => <option key={p.id} value={p.user_paper_id}>{p.title}</option>)}</select></label><button className="button primary" disabled={pending}>{pick("Save note", "নোট সংরক্ষণ")}</button></form></LibraryDialog>;
}

export function PaperPicker({ project, onClose, onSaved }: { project: ProjectDetail; onClose: () => void; onSaved: () => void }) {
  const { pick } = useI18n();
  const [papers, setPapers] = useState<LibraryPaper[]>([]);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [role, setRole] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const alive = useAlive();
  useEffect(() => {
    let current = true;
    api.getLibrary({ page, size: 20, q: query || undefined }).then((result) => { if (current) { setPapers(result.items); setPages(result.pages); } }).catch(() => { if (current) setError("Unable to load library / লাইব্রেরি লোড হয়নি।"); });
    return () => { current = false; };
  }, [page, query]);
  async function link(paper: LibraryPaper) { setPending(true); setError(""); try { await api.addProjectPaper(project.id, paper.id, role || null); if (alive.current) onSaved(); } catch { if (alive.current) setError(pick("Unable to link paper.", "গবেষণাপত্র যুক্ত হয়নি।")); } finally { if (alive.current) setPending(false); } }
  return <LibraryDialog title={pick("Link a saved paper", "সংরক্ষিত গবেষণাপত্র যুক্ত করুন")} onClose={onClose}>{error && <p className="notice error" role="alert">{error}</p>}<div className={styles.form}><label className="field">{pick("Search my library", "আমার লাইব্রেরিতে খুঁজুন")}<input value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} /></label><label className="field">{pick("Paper role (optional)", "গবেষণাপত্রের ভূমিকা (ঐচ্ছিক)")}<select value={role} onChange={(e) => setRole(e.target.value)}><option value="">{pick("No role", "ভূমিকা নেই")}</option><option value="core_baseline">{pick("Core baseline", "মূল ভিত্তি")}</option><option value="methodology">{pick("Methodology", "পদ্ধতি")}</option><option value="related_work">{pick("Related work", "সম্পর্কিত কাজ")}</option><option value="dataset">{pick("Dataset", "ডেটাসেট")}</option></select></label></div><ul className={styles.list}>{papers.map((paper) => <li key={paper.id}><h3>{paper.title}</h3><button className="button secondary small" disabled={pending || project.papers.some((item) => item.user_paper_id === paper.id)} onClick={() => link(paper)}>{pick("Link paper", "যুক্ত করুন")}</button></li>)}</ul><div className={styles.pagination}><button className="button secondary small" disabled={page <= 1} onClick={() => setPage((v) => v - 1)}>{pick("Previous", "আগের")}</button><span>{page}/{Math.max(1, pages)}</span><button className="button secondary small" disabled={page >= pages} onClick={() => setPage((v) => v + 1)}>{pick("Next", "পরের")}</button></div></LibraryDialog>;
}

export function ChatPicker({ project, onClose, onSaved }: { project: ProjectDetail; onClose: () => void; onSaved: () => void }) {
  const { pick } = useI18n();
  const [chats, setChats] = useState<Conversation[]>([]);
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const alive = useAlive();
  useEffect(() => { let current = true; api.getConversations(30, offset).then((items) => { if (current) setChats(items); }).catch(() => { if (current) setError("Unable to load chats / আলোচনা লোড হয়নি।"); }); return () => { current = false; }; }, [offset]);
  async function link(id: number) { setPending(true); setError(""); try { await api.linkProjectConversation(project.id, id); if (alive.current) onSaved(); } catch { if (alive.current) setError(pick("Unable to link chat.", "আলোচনা যুক্ত হয়নি।")); } finally { if (alive.current) setPending(false); } }
  return <LibraryDialog title={pick("Link an existing AI chat", "আগের এআই আলোচনা যুক্ত করুন")} onClose={onClose}>{error && <p className="notice error" role="alert">{error}</p>}<p className={styles.small}>{pick("Linking a chat moves it from any previous project; its source scope stays the same.", "আলোচনা যুক্ত করলে আগের প্রকল্প থেকে সরবে; এর উৎসের সীমা একই থাকবে।")}</p><ul className={styles.list}>{chats.map((chat) => <li key={chat.id}><h3>{chat.title}</h3><button className="button secondary small" disabled={pending || project.conversations.some((item) => item.id === chat.id)} onClick={() => link(chat.id)}>{pick("Link chat", "আলোচনা যুক্ত করুন")}</button></li>)}</ul>{!chats.length && <p className="muted">{pick("No conversations on this page.", "এই পাতায় কোনো আলোচনা নেই।")}</p>}<div className={styles.pagination}><button className="button secondary small" disabled={!offset} onClick={() => setOffset((v) => Math.max(0, v - 30))}>{pick("Previous", "আগের")}</button><button className="button secondary small" disabled={chats.length < 30} onClick={() => setOffset((v) => v + 30)}>{pick("Next", "পরের")}</button></div></LibraryDialog>;
}
