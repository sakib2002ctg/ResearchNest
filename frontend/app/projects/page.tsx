"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api, type ProjectDetail, type ProjectTask, type ResearchNote, type ResearchProject, type TaskStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadPrivateFile } from "@/lib/download";
import { useI18n } from "@/lib/i18n";
import { projectConversationInput } from "@/lib/projects";
import { LibraryDialog } from "../library/DocumentViewer";
import { ChatPicker, NoteForm, PaperPicker, ProjectForm, statusLabels, TaskForm, taskLabels } from "./ProjectForms";
import styles from "./workspace.module.css";

const tabs = [["overview", "Overview & objectives", "সারসংক্ষেপ ও উদ্দেশ্য"], ["papers", "Project papers", "প্রকল্পের গবেষণাপত্র"], ["tasks", "Tasks & milestones", "কাজ ও মাইলফলক"], ["notes", "Research notes", "গবেষণার নোট"], ["chats", "Linked AI chats", "সংযুক্ত এআই আলোচনা"]] as const;
type Tab = typeof tabs[number][0];

export default function ProjectsPage() {
  const { user } = useAuth();
  const { pick } = useI18n();
  return <AppShell title={pick("My projects", "আমার প্রকল্প")} description={pick("Bring papers, tasks, notes, and conversations into a research workspace.", "গবেষণাপত্র, কাজ, নোট ও আলোচনা এক কর্মপরিসরে সাজান।")} showHeading>{user && <Projects key={user.id} />}</AppShell>;
}

function Projects() {
  const { pick, locale } = useI18n();
  const [items, setItems] = useState<ResearchProject[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [editing, setEditing] = useState<ResearchProject | "new" | null>(null);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    api.getProjects(30, offset, controller.signal).then((rows) => { if (!controller.signal.aborted) { setItems(rows); setLoading(false); setError(""); } })
      .catch(() => { if (!controller.signal.aborted) { setLoading(false); setError("Unable to load projects / প্রকল্প লোড হয়নি।"); } });
    return () => controller.abort();
  }, [offset, revision]);
  return <>
    {error && <p className="notice error" role="alert">{error}<button className="button ghost small" onClick={() => setRevision((v) => v + 1)}>{pick("Retry", "আবার চেষ্টা")}</button></p>}
    {selected === null ? <>
      <div className={styles.toolbar}><button className="button primary" onClick={() => setEditing("new")}>{pick("Create project", "প্রকল্প তৈরি করুন")}</button><Link className="button secondary" href="/insights">{pick("Research insights", "গবেষণার অন্তর্দৃষ্টি")}</Link></div>
      {loading ? <p role="status" className="loading-state">{pick("Loading projects…", "প্রকল্প লোড হচ্ছে…")}</p> : <div className={styles.cards}>
        {items.map((item) => <article key={item.id} className={`card ${styles.project}`}>
          <span className="tag">{pick(...statusLabels[item.status])}</span><h2>{item.title}</h2><p>{item.description}</p>
          <label className={styles.small}>{pick("Progress", "অগ্রগতি")} · {item.progress_percent.toLocaleString(locale, { maximumFractionDigits: 1 })}%<progress className={styles.progress} max={100} value={item.progress_percent} /></label>
          <p>{item.completed_task_count}/{item.task_count} {pick("tasks complete", "কাজ সম্পন্ন")} · {item.paper_count} {pick("papers", "গবেষণাপত্র")}</p>
          <p>{pick("Deadline", "সময়সীমা")}: {item.target_deadline ? new Date(item.target_deadline).toLocaleDateString(locale) : pick("Not set", "নির্ধারিত নয়")}</p>
          <div className={styles.actions}><button className="button secondary" onClick={() => setSelected(item.id)}>{pick("Open workspace", "কর্মপরিসর খুলুন")}</button></div>
        </article>)}
      </div>}
      {!loading && !error && items.length === 0 && <div className="card empty-state"><h3>{pick("Start a research project", "একটি গবেষণা প্রকল্প শুরু করুন")}</h3><p>{pick("Set objectives and connect your saved papers to the work ahead.", "উদ্দেশ্য নির্ধারণ করুন এবং সংরক্ষিত গবেষণাপত্র যুক্ত করুন।")}</p></div>}
      <div className={styles.pagination}><button className="button secondary small" disabled={offset === 0} onClick={() => { setLoading(true); setOffset((v) => Math.max(0, v - 30)); }}>{pick("Previous", "আগের")}</button><span className={styles.small}>{Math.floor(offset / 30) + 1}</span><button className="button secondary small" disabled={items.length < 30} onClick={() => { setLoading(true); setOffset((v) => v + 30); }}>{pick("Next", "পরের")}</button></div>
    </> : <ProjectWorkspace key={selected} id={selected} onBack={() => setSelected(null)} onEdit={setEditing} onChange={() => setRevision((v) => v + 1)} revision={revision} />}
    {editing && <ProjectForm project={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={(item) => { setEditing(null); setSelected(item.id); setRevision((v) => v + 1); }} />}
  </>;
}

function ProjectWorkspace({ id, revision, onBack, onEdit, onChange }: { id: number; revision: number; onBack: () => void; onEdit: (item: ResearchProject) => void; onChange: () => void }) {
  const { pick, locale, language } = useI18n();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [refresh, setRefresh] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<"paper" | "task" | "note" | "chat" | "delete" | null>(null);
  const [task, setTask] = useState<ProjectTask | null>(null);
  const [note, setNote] = useState<ResearchNote | null>(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    api.getProject(id, controller.signal).then((row) => { if (!controller.signal.aborted) { setProject(row); setError(""); } }).catch(() => { if (!controller.signal.aborted) setError("Unable to load project / প্রকল্প লোড হয়নি।"); });
    return () => controller.abort();
  }, [id, refresh, revision]);
  function changed() { if (alive.current) { setModal(null); setRefresh((v) => v + 1); onChange(); } }
  async function action(work: () => Promise<void>) {
    setPending(true); setError("");
    try { await work(); } catch { if (alive.current) setError(pick("The request failed. Reload the project and try again.", "অনুরোধ ব্যর্থ হয়েছে। প্রকল্প আবার লোড করে চেষ্টা করুন।")); }
    finally { if (alive.current) setPending(false); }
  }
  async function exportBundle(format: "json" | "markdown") { await action(async () => { const blob = await api.exportProject(id, format); if (alive.current) downloadPrivateFile(blob, `project-${id}.${format === "json" ? "json" : "md"}`); }); }
  return <>
    <div className={styles.toolbar}><button className="button secondary" onClick={onBack}>{pick("← All projects", "← সব প্রকল্প")}</button><button className="button ghost" disabled={pending} onClick={() => setRefresh((v) => v + 1)}>{pick("Refresh", "রিফ্রেশ")}</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {!project ? <p className="loading-state" role="status">{pick("Loading workspace…", "কর্মপরিসর লোড হচ্ছে…")}</p> : <>
      <section className="card"><div className={styles.heading}><div><span className="tag">{pick(...statusLabels[project.status])}</span><h2>{project.title}</h2></div><div className={styles.actions}><button className="button secondary small" disabled={pending} onClick={() => onEdit(project)}>{pick("Edit project", "সম্পাদনা")}</button><button className="button secondary small" disabled={pending} onClick={() => exportBundle("json")}>{pick("Export JSON", "JSON রপ্তানি")}</button><button className="button secondary small" disabled={pending} onClick={() => exportBundle("markdown")}>{pick("Export Markdown", "Markdown রপ্তানি")}</button></div></div>
        <label className={styles.small}>{pick("Progress from completed tasks and milestones", "সম্পন্ন কাজ ও মাইলফলক থেকে অগ্রগতি")}: {project.progress_percent.toLocaleString(locale, { maximumFractionDigits: 1 })}%<progress className={styles.progress} value={project.progress_percent} max={100} /></label><p className={styles.small}>{pick("Deadline", "সময়সীমা")}: {project.target_deadline ? new Date(project.target_deadline).toLocaleString(locale) : pick("Not set", "নির্ধারিত নয়")}</p>
      </section>
      <div role="tablist" aria-label={pick("Project workspace", "প্রকল্প কর্মপরিসর")} className={styles.tabs}>{tabs.map(([key, en, bn]) => <button key={key} id={`tab-${key}`} role="tab" aria-controls={`panel-${key}`} aria-selected={tab === key} tabIndex={tab === key ? 0 : -1} onKeyDown={(event) => { const index = tabs.findIndex(([value]) => value === key); const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null; if (next !== null) { event.preventDefault(); setTab(tabs[next][0]); document.getElementById(`tab-${tabs[next][0]}`)?.focus(); } }} onClick={() => setTab(key)}>{pick(en, bn)}</button>)}</div>
      <section className={`card ${styles.section}`} role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "overview" && <><h2>{pick("Overview & objectives", "সারসংক্ষেপ ও উদ্দেশ্য")}</h2><p className={styles.note}>{project.description || pick("No description yet.", "এখনো বিবরণ নেই।")}</p><ol className={styles.objectives}>{project.objectives.map((text, i) => <li key={i}>{text}</li>)}</ol>{!project.objectives.length && <p className="muted">{pick("Edit the project to add objectives.", "উদ্দেশ্য যোগ করতে প্রকল্প সম্পাদনা করুন।")}</p>}<Link className="button secondary" href={`/insights?project_id=${id}`}>{pick("View project insights", "প্রকল্পের অন্তর্দৃষ্টি দেখুন")}</Link><button className={`button ghost ${styles.danger}`} onClick={() => setModal("delete")}>{pick("Delete project", "প্রকল্প মুছুন")}</button></>}
        {tab === "papers" && <><div className={styles.heading}><h2>{pick("Project papers", "প্রকল্পের গবেষণাপত্র")}</h2><button className="button primary" onClick={() => setModal("paper")}>{pick("Link library paper", "লাইব্রেরির গবেষণাপত্র যুক্ত করুন")}</button></div><ul className={styles.list}>{project.papers.map((paper) => <li key={paper.id}><h3>{paper.title}</h3><p className="muted">{paper.authors}</p><span className="tag">{paper.role_in_project || pick("No role", "ভূমিকা নেই")}</span><div className={styles.actions}><Link className="button ghost small" href="/library">{pick("Open library", "লাইব্রেরি খুলুন")}</Link><button disabled={pending} className="button secondary small" onClick={() => action(async () => { await api.removeProjectPaper(id, paper.user_paper_id); changed(); })}>{pick("Unlink", "সংযোগ সরান")}</button></div></li>)}</ul>{!project.papers.length && <p className="muted">{pick("Link saved papers to build the project knowledge base.", "প্রকল্পের জ্ঞানভিত্তি গড়তে সংরক্ষিত গবেষণাপত্র যুক্ত করুন।")}</p>}</>}
        {tab === "tasks" && <><div className={styles.heading}><h2>{pick("Tasks & milestones", "কাজ ও মাইলফলক")}</h2><button className="button primary" onClick={() => { setTask(null); setModal("task"); }}>{pick("Add task", "কাজ যোগ করুন")}</button></div><ul className={styles.list}>{project.tasks.map((item) => <li key={item.id}><h3>{item.title} {item.is_milestone && <span className="tag">{pick("Milestone", "মাইলফলক")}</span>}</h3><p>{item.description}</p><p className={styles.small}>{pick("Due", "নির্ধারিত সময়")}: {item.due_date ? new Date(item.due_date).toLocaleString(locale) : pick("Not set", "নির্ধারিত নয়")}</p><div className={styles.actions}><label className="field">{pick("Status", "অবস্থা")}<select aria-label={`${pick("Status", "অবস্থা")}: ${item.title}`} disabled={pending} value={item.status} onChange={(e) => action(async () => { await api.updateProjectTask(id, item.id, { status: e.target.value as TaskStatus }); changed(); })}>{Object.entries(taskLabels).map(([value, labels]) => <option key={value} value={value}>{pick(...labels)}</option>)}</select></label><button className="button secondary small" disabled={pending} onClick={() => { setTask(item); setModal("task"); }}>{pick("Edit", "সম্পাদনা")}</button><button className="button ghost small" disabled={pending} onClick={() => action(async () => { await api.deleteProjectTask(id, item.id); changed(); })}>{pick("Delete task", "কাজ মুছুন")}</button></div></li>)}</ul>{!project.tasks.length && <p className="muted">{pick("Add tasks and milestones to track progress.", "অগ্রগতি দেখতে কাজ ও মাইলফলক যোগ করুন।")}</p>}</>}
        {tab === "notes" && <><div className={styles.heading}><h2>{pick("Research notes", "গবেষণার নোট")}</h2><button className="button primary" onClick={() => { setNote(null); setModal("note"); }}>{pick("Add note", "নোট যোগ করুন")}</button></div><ul className={styles.list}>{project.notes.map((item) => <li key={item.id}><h3>{item.title}</h3><p>{item.content}</p>{item.user_paper_id && <span className="tag">{project.papers.find((paper) => paper.user_paper_id === item.user_paper_id)?.title || pick("Linked paper", "সংযুক্ত গবেষণাপত্র")}</span>}<div className={styles.actions}><button className="button secondary small" disabled={pending} onClick={() => { setNote(item); setModal("note"); }}>{pick("Edit", "সম্পাদনা")}</button><button className="button ghost small" disabled={pending} onClick={() => action(async () => { await api.deleteProjectNote(id, item.id); changed(); })}>{pick("Delete note", "নোট মুছুন")}</button></div></li>)}</ul>{!project.notes.length && <p className="muted">{pick("Capture your own observations and research decisions.", "নিজের পর্যবেক্ষণ ও গবেষণার সিদ্ধান্ত লিখে রাখুন।")}</p>}</>}
        {tab === "chats" && <><div className={styles.heading}><h2>{pick("Linked AI chats", "সংযুক্ত এআই আলোচনা")}</h2><button className="button primary" onClick={() => setModal("chat")}>{pick("Link existing chat", "আগের আলোচনা যুক্ত করুন")}</button><button className="button secondary" disabled={pending || !project.papers.length} onClick={() => action(async () => { await api.createConversation(projectConversationInput(project, language)); changed(); })}>{pick("Create project chat", "প্রকল্পের আলোচনা তৈরি")}</button></div><p className={styles.small}>{pick("New chats use up to the first 50 linked papers as their source scope. AI calls begin only when you send a question in the assistant.", "নতুন আলোচনার উৎস হবে প্রথম সর্বোচ্চ ৫০টি সংযুক্ত গবেষণাপত্র। সহকারীকে প্রশ্ন পাঠালেই শুধু এআই চালু হবে।")}</p><ul className={styles.list}>{project.conversations.map((chat) => <li key={chat.id}><h3>{chat.title}</h3><p className={styles.small}>{new Date(chat.updated_at).toLocaleString(locale)}</p><Link className="button secondary small" href={`/assistant?conversation_id=${chat.id}`}>{pick("Open conversation", "আলোচনা খুলুন")}</Link></li>)}</ul></>}
      </section>
      {modal === "task" && <TaskForm projectId={id} task={task} onClose={() => setModal(null)} onSaved={changed} />}
      {modal === "note" && <NoteForm project={project} note={note} onClose={() => setModal(null)} onSaved={changed} />}
      {modal === "paper" && <PaperPicker project={project} onClose={() => setModal(null)} onSaved={changed} />}
      {modal === "chat" && <ChatPicker project={project} onClose={() => setModal(null)} onSaved={changed} />}
      {modal === "delete" && <LibraryDialog title={pick("Delete this project?", "এই প্রকল্প মুছবেন?")} onClose={() => setModal(null)}><p>{pick("The project, tasks, and notes will be removed. Your library papers and AI conversations remain.", "প্রকল্প, কাজ ও নোট মুছে যাবে। লাইব্রেরির গবেষণাপত্র এবং এআই আলোচনা থাকবে।")}</p><button className="button danger" disabled={pending} onClick={() => action(async () => { await api.deleteProject(id); if (alive.current) { onChange(); onBack(); } })}>{pick("Delete project", "প্রকল্প মুছুন")}</button></LibraryDialog>}
    </>}
  </>;
}
