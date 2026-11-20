"use client";

import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api, ApiError, type CollaboratorRole, type TeamDetail, type TeamMember, type TeamNote, type TeamWorkspace } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { safePublicLink, teamPermissions } from "@/lib/learning-teams";
import { LibraryDialog } from "../library/DocumentViewer";
import { CollectionPicker, MemberForm, TeamForm, TeamNoteForm } from "./TeamForms";
import styles from "@/components/ModuleWorkspace.module.css";

export default function TeamsPage() {
  const { user } = useAuth();
  const { pick } = useI18n();
  return <AppShell title={pick("Team Workspaces", "দলীয় কর্মপরিসর")} description={pick("Collaborate through explicit team access while keeping your personal library private.", "দলের নির্দিষ্ট অনুমতিতে একসঙ্গে কাজ করুন, ব্যক্তিগত লাইব্রেরি ব্যক্তিগত রাখুন।")} showHeading>{user && <Teams key={user.id} userId={user.id} />}</AppShell>;
}

function Teams({ userId }: { userId: number }) {
  const { pick, locale } = useI18n();
  const [teams, setTeams] = useState<TeamWorkspace[]>([]);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api.getTeams(30, page * 30, controller.signal).then((items) => {
      if (!controller.signal.aborted) { setTeams(items); setLoaded(true); setError(""); }
    }).catch(() => { if (!controller.signal.aborted) setError("Unable to load your teams / আপনার দলগুলো লোড হয়নি।"); });
    return () => controller.abort();
  }, [page, revision]);
  if (selected) return <TeamWorkspaceView key={selected} id={selected} userId={userId} onBack={() => setSelected(null)} onChange={() => setRevision((v) => v + 1)} />;
  return <>
    <div className={styles.toolbar}><button className="button primary" onClick={() => setCreating(true)}>{pick("Create research team", "গবেষণা দল তৈরি করুন")}</button><button className="button secondary" onClick={() => setRevision((v) => v + 1)}>{pick("Refresh teams", "দল রিফ্রেশ")}</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {!loaded && !error && <p className="loading-state" role="status">{pick("Loading team workspaces…", "দলীয় কর্মপরিসর লোড হচ্ছে…")}</p>}
    {loaded && !teams.length && <p className="empty-state">{pick("You have no teams on this page. Create a workspace or ask a team owner to add your account.", "এই পাতায় আপনার কোনো দল নেই। কর্মপরিসর তৈরি করুন বা দলের মালিককে আপনার অ্যাকাউন্ট যুক্ত করতে বলুন।")}</p>}
    <div className={styles.cards}>{teams.map((team) => <article className={`card ${styles.card}`} key={team.id}>
      <span className="tag">{roleLabel(team.my_role, pick)}</span><h2>{team.name}</h2><p>{team.description || pick("A shared research workspace", "একটি যৌথ গবেষণা কর্মপরিসর")}</p>
      <p className={styles.small}>{team.member_count.toLocaleString(locale)} {pick("members", "সদস্য")} · {team.shared_collection_count.toLocaleString(locale)} {pick("shared collections", "ভাগ করা সংগ্রহ")} · {team.note_count.toLocaleString(locale)} {pick("notes", "নোট")}</p>
      <div className={styles.actions}><button className="button secondary" onClick={() => setSelected(team.id)}>{pick("Open workspace", "কর্মপরিসর খুলুন")}</button></div>
    </article>)}</div>
    <div className={styles.pagination}><button className="button secondary small" disabled={!page} onClick={() => setPage((v) => v - 1)}>{pick("Previous", "আগের")}</button><span>{(page + 1).toLocaleString(locale)}</span><button className="button secondary small" disabled={teams.length < 30} onClick={() => setPage((v) => v + 1)}>{pick("Next", "পরের")}</button></div>
    {creating && <TeamForm team={null} onClose={() => setCreating(false)} onSaved={(team) => { setCreating(false); setRevision((v) => v + 1); setSelected(team.id); }} />}
  </>;
}

function TeamWorkspaceView({ id, userId, onBack, onChange }: { id: number; userId: number; onBack: () => void; onChange: () => void }) {
  const { pick, locale } = useI18n();
  const [team, setTeam] = useState<TeamDetail | null>(null);
  const [tab, setTab] = useState<"collections" | "notes" | "members">("collections");
  const [modal, setModal] = useState<"edit" | "member" | "share" | "note" | "delete" | null>(null);
  const [note, setNote] = useState<TeamNote | null>(null);
  const [remove, setRemove] = useState<TeamMember | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    const lifetime = new AbortController(); controller.current = lifetime;
    return () => lifetime.abort();
  }, []);
  useEffect(() => {
    const refresh = () => setRevision((value) => value + 1);
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, []);
  useEffect(() => {
    const active = new AbortController();
    api.getTeam(id, active.signal).then((value) => { if (!active.signal.aborted) { setTeam(value); setError(""); } })
      .catch(() => { if (!active.signal.aborted) { setTeam(null); setModal(null); setError("This workspace is unavailable. Your membership may have changed. / কর্মপরিসরটি পাওয়া যাচ্ছে না। সদস্যপদ বদলে যেতে পারে।"); } });
    return () => active.abort();
  }, [id, revision]);
  function changed() { setModal(null); setRemove(null); setRevision((v) => v + 1); onChange(); }
  async function action(work: (signal?: AbortSignal) => Promise<void>) {
    const signal = controller.current?.signal;
    setPending(true); setError("");
    try { await work(signal); }
    catch (cause) {
      if (!signal?.aborted) {
        const accessLost = cause instanceof ApiError && [403, 404].includes(cause.status);
        if (accessLost) { setTeam(null); setModal(null); setRemove(null); }
        setError(accessLost ? pick("Your access or role may have changed. Refresh to check membership.", "আপনার অনুমতি বা ভূমিকা বদলে যেতে পারে। সদস্যপদ দেখতে রিফ্রেশ করুন।") : pick("The change could not be saved. Refresh and retry.", "পরিবর্তন সংরক্ষণ হয়নি। রিফ্রেশ করে আবার চেষ্টা করুন।"));
      }
    } finally { if (!signal?.aborted) setPending(false); }
  }
  const permissions = team ? teamPermissions(team.my_role) : null;
  return <>
    <div className={styles.toolbar}><button className="button secondary" onClick={onBack}>{pick("← All teams", "← সব দল")}</button><button className="button secondary" disabled={pending} onClick={() => setRevision((v) => v + 1)}>{pick("Refresh workspace", "কর্মপরিসর রিফ্রেশ")}</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {!team ? !error && <p role="status">{pick("Opening team workspace…", "দলীয় কর্মপরিসর খুলছে…")}</p> : <>
      <section className={`card ${styles.section}`}><div className={styles.heading}><div><span className="tag">{roleLabel(team.my_role, pick)}</span><h2>{team.name}</h2></div>{permissions?.canWrite && <button className="button secondary small" disabled={pending} onClick={() => setModal("edit")}>{pick("Edit workspace", "কর্মপরিসর সম্পাদনা")}</button>}</div><p className={styles.prose}>{team.description}</p>
        <p className={styles.small}>{pick("Only team members can access this workspace. Shared collections expose paper metadata; private PDFs, annotations, document text, and AI history stay in their owner's library.", "শুধু দলের সদস্যরা এই কর্মপরিসর দেখতে পারেন। ভাগ করা সংগ্রহে গবেষণাপত্রের মেটাডেটা দেখা যায়; ব্যক্তিগত পিডিএফ, টীকা, নথির পাঠ্য ও এআই ইতিহাস মালিকের লাইব্রেরিতেই থাকে।")}</p>
        {team.my_role === "viewer" && <p className="notice">{pick("You have read-only access. Ask the owner if you need editing permissions.", "আপনি শুধু পড়তে পারবেন। সম্পাদনার অনুমতি দরকার হলে মালিককে বলুন।")}</p>}
        {permissions?.canDelete && <div><button className={`button ghost small ${styles.danger}`} onClick={() => setModal("delete")}>{pick("Delete workspace", "কর্মপরিসর মুছুন")}</button></div>}
      </section>
      <div className={styles.tabs} role="group" aria-label={pick("Team workspace sections", "দলীয় কর্মপরিসরের বিভাগ")}>{([['collections', 'Shared collections', 'ভাগ করা সংগ্রহ'], ['notes', 'Team notes', 'দলীয় নোট'], ['members', 'Members & roles', 'সদস্য ও ভূমিকা']] as const).map(([value, en, bn]) => <button key={value} aria-pressed={tab === value} onClick={() => setTab(value)}>{pick(en, bn)}</button>)}</div>
      <section className={`card ${styles.section}`} aria-busy={pending}>
        {tab === "collections" && <><div className={styles.heading}><h2>{pick("Shared collections", "ভাগ করা সংগ্রহ")}</h2>{permissions?.canWrite && <button className="button primary small" onClick={() => setModal("share")}>{pick("Share my collection", "আমার সংগ্রহ ভাগ করুন")}</button>}</div>
          {team.collections_truncated && <p className="notice">{pick(`Showing the first ${team.collections.length} of ${team.shared_collection_count} shared collections.`, `${team.shared_collection_count}টি ভাগ করা সংগ্রহের প্রথম ${team.collections.length}টি দেখানো হচ্ছে।`)}</p>}
          <ul className={styles.list}>{team.collections.map((collection) => <li key={collection.id}>
            <div className={styles.heading}><h3>{collection.name}</h3>{permissions?.canWrite && (team.my_role === "owner" || collection.shared_by_id === userId) && <button className="button ghost small" disabled={pending} onClick={() => { void action(async (signal) => { await api.unshareTeamCollection(id, collection.collection_id, signal); if (!signal?.aborted) changed(); }); }}>{pick("Stop sharing", "ভাগ করা বন্ধ করুন")}</button>}</div>
            <p>{collection.description}</p><p className={styles.small}>{pick("Shared", "ভাগ করা হয়েছে")}: {new Date(collection.shared_at).toLocaleString(locale)}</p>
            <ul className={styles.list}>{collection.papers.map((paper) => <li key={paper.user_paper_id}><h3>{paper.title}</h3><p>{paper.authors}</p><p className={styles.small}>{paper.source}{paper.doi && ` · DOI: ${paper.doi}`}</p>{safePublicLink(paper.url) && <a href={safePublicLink(paper.url)!} target="_blank" rel="noopener noreferrer nofollow">{pick("Public paper link ↗", "গবেষণাপত্রের প্রকাশ্য লিংক ↗")}</a>}</li>)}</ul>
            {!collection.papers.length && <p className={styles.small}>{pick("No papers currently shared in this collection.", "এই সংগ্রহে এখন কোনো গবেষণাপত্র ভাগ করা নেই।")}</p>}
            {collection.papers_truncated && <p className="notice">{pick(`Showing ${collection.papers.length} of ${collection.total_papers} papers in this collection.`, `এই সংগ্রহের ${collection.total_papers}টির মধ্যে ${collection.papers.length}টি গবেষণাপত্র দেখানো হচ্ছে।`)}</p>}
          </li>)}</ul>{!team.collections.length && <p className="empty-state">{pick("Share one of your own collections to make its paper metadata available to the team.", "দলের কাছে গবেষণাপত্রের মেটাডেটা দিতে নিজের সংগ্রহ ভাগ করুন।")}</p>}
        </>}
        {tab === "notes" && <><div className={styles.heading}><h2>{pick("Collaborative notes", "যৌথ নোট")}</h2>{permissions?.canWrite && <button className="button primary small" onClick={() => { setNote(null); setModal("note"); }}>{pick("Write team note", "দলীয় নোট লিখুন")}</button>}</div>
          <ul className={styles.list}>{team.notes.map((item) => <li key={item.id}><h3>{item.title}</h3><p className={styles.small}>{item.author_username} · {new Date(item.updated_at).toLocaleString(locale)}</p><p>{item.content}</p>{item.user_paper_id && <p className={styles.small}>{pick("Linked shared paper", "সংযুক্ত ভাগ করা গবেষণাপত্র")}: {team.collections.flatMap((c) => c.papers).find((p) => p.user_paper_id === item.user_paper_id)?.title || pick("Reference unavailable", "রেফারেন্স পাওয়া যায়নি")}</p>}{permissions?.canWrite && <div className={styles.actions}><button className="button secondary small" disabled={pending} onClick={() => { setNote(item); setModal("note"); }}>{pick("Edit note", "নোট সম্পাদনা")}</button><button className="button ghost small" disabled={pending} onClick={() => { void action(async (signal) => { await api.deleteTeamNote(id, item.id, signal); if (!signal?.aborted) changed(); }); }}>{pick("Delete note", "নোট মুছুন")}</button></div>}</li>)}</ul>{!team.notes.length && <p className="empty-state">{pick("No team notes yet. Notes written here are visible to all current team members.", "এখনো দলীয় নোট নেই। এখানে লেখা নোট দলের বর্তমান সবাই দেখতে পারবেন।")}</p>}
        </>}
        {tab === "notes" && team.notes_truncated && <div className={styles.actions}><span className={styles.small}>{pick(`Showing ${team.notes.length} of ${team.note_count} notes.`, `${team.note_count}টি নোটের মধ্যে ${team.notes.length}টি দেখানো হচ্ছে।`)}</span><button className="button secondary small" disabled={pending} onClick={() => { void action(async (signal) => {
          const rows = await api.getTeamNotes(id, 100, team.notes.length, signal);
          if (!signal?.aborted) setTeam((current) => current ? { ...current, notes: [...current.notes, ...rows.filter((row) => !current.notes.some((item) => item.id === row.id))], notes_truncated: rows.length === 100 && current.notes.length + rows.length < current.note_count } : current);
        }); }}>{pick("Load more notes", "আরও নোট দেখুন")}</button></div>}
        {tab === "members" && <><div className={styles.heading}><h2>{pick("Members & roles", "সদস্য ও ভূমিকা")}</h2>{permissions?.canManageMembers && <button className="button primary small" onClick={() => setModal("member")}>{pick("Add collaborator", "সহযোগী যুক্ত করুন")}</button>}</div>
          <p className={styles.small}>{pick("Owners manage membership. Editors can share their own collections and edit team notes. Viewers can read shared metadata and notes.", "মালিক সদস্যপদ পরিচালনা করেন। সম্পাদক নিজের সংগ্রহ ভাগ করতে ও দলীয় নোট সম্পাদনা করতে পারেন। দর্শক ভাগ করা মেটাডেটা ও নোট পড়তে পারেন।")}</p>
          {team.members_truncated && <p className="notice">{pick(`Showing the first ${team.members.length} of ${team.member_count} members.`, `${team.member_count}জনের মধ্যে প্রথম ${team.members.length}জন সদস্য দেখানো হচ্ছে।`)}</p>}
          <ul className={styles.list}>{team.members.map((member) => <li key={member.user_id}><div className={styles.heading}><div><h3>{member.username}{member.user_id === userId ? pick(" (you)", " (আপনি)") : ""}</h3><p className={styles.small}>{pick("Joined", "যোগ দিয়েছেন")}: {new Date(member.joined_at).toLocaleDateString(locale)}</p></div>
            {permissions?.canManageMembers && member.role !== "owner" ? <div className={styles.actions}><label className="field">{pick("Role", "ভূমিকা")}<select disabled={pending} value={member.role} onChange={(e) => { const role = e.target.value as CollaboratorRole; void action(async (signal) => { await api.updateTeamMember(id, member.user_id, role, signal); if (!signal?.aborted) changed(); }); }}><option value="editor">{pick("Editor", "সম্পাদক")}</option><option value="viewer">{pick("Viewer", "দর্শক")}</option></select></label><button className="button ghost small" disabled={pending} onClick={() => setRemove(member)}>{pick("Remove member", "সদস্য সরান")}</button></div> : <span className="tag">{roleLabel(member.role, pick)}</span>}
          </div></li>)}</ul>
        </>}
      </section>
      {modal === "edit" && permissions?.canWrite && <TeamForm team={team} onClose={() => setModal(null)} onSaved={changed} />}
      {modal === "member" && permissions?.canManageMembers && <MemberForm workspaceId={id} onClose={() => setModal(null)} onSaved={changed} />}
      {modal === "share" && permissions?.canWrite && <CollectionPicker team={team} onClose={() => setModal(null)} onSaved={changed} />}
      {modal === "note" && permissions?.canWrite && <TeamNoteForm workspaceId={id} note={note} onClose={() => setModal(null)} onSaved={changed} />}
      {modal === "delete" && permissions?.canDelete && <LibraryDialog title={pick("Delete team workspace?", "দলীয় কর্মপরিসর মুছবেন?")} onClose={() => setModal(null)}><p>{pick("This removes membership, sharing links, and team notes. Original personal collections and papers remain in their owners' libraries.", "সদস্যপদ, ভাগ করার সংযোগ ও দলীয় নোট মুছে যাবে। মূল ব্যক্তিগত সংগ্রহ ও গবেষণাপত্র মালিকের লাইব্রেরিতেই থাকবে।")}</p><button className="button danger" disabled={pending} onClick={() => { void action(async (signal) => { await api.deleteTeam(id, signal); if (!signal?.aborted) { onChange(); onBack(); } }); }}>{pick("Delete workspace", "কর্মপরিসর মুছুন")}</button></LibraryDialog>}
      {remove && permissions?.canManageMembers && <LibraryDialog title={pick("Remove collaborator?", "সহযোগীকে সরাবেন?")} onClose={() => setRemove(null)}><p>{pick(`Remove ${remove.username} from this team? Their shared collection links will also be removed.`, `${remove.username}-কে দল থেকে সরাবেন? তাঁর ভাগ করা সংগ্রহের সংযোগও সরবে।`)}</p><button className="button danger" disabled={pending} onClick={() => { void action(async (signal) => { await api.removeTeamMember(id, remove.user_id, signal); if (!signal?.aborted) changed(); }); }}>{pick("Remove member", "সদস্য সরান")}</button></LibraryDialog>}
    </>}
  </>;
}

function roleLabel(role: string, pick: (en: string, bn: string) => string) {
  return role === "owner" ? pick("Owner", "মালিক") : role === "editor" ? pick("Editor", "সম্পাদক") : pick("Viewer", "দর্শক");
}
