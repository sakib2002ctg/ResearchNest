"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type CollaboratorRole, type LibraryCollection, type TeamDetail, type TeamNote, type TeamWorkspace } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { LibraryDialog } from "../library/DocumentViewer";
import styles from "@/components/ModuleWorkspace.module.css";

function useRequest() {
  const controller = useRef<AbortController | null>(null);
  useEffect(() => { const active = new AbortController(); controller.current = active; return () => active.abort(); }, []);
  return controller;
}

function accessError(cause: unknown) { return cause instanceof ApiError && [403, 404].includes(cause.status); }

export function TeamForm({ team, onClose, onSaved }: { team: TeamWorkspace | null; onClose: () => void; onSaved: (team: TeamWorkspace) => void }) {
  const { pick } = useI18n();
  const [name, setName] = useState(team?.name || "");
  const [description, setDescription] = useState(team?.description || "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const request = useRequest();
  async function save(event: FormEvent) {
    event.preventDefault(); setPending(true); setError("");
    const signal = request.current?.signal;
    try {
      const body = { name: name.trim(), description: description.trim() || null };
      const result = team ? await api.updateTeam(team.id, body, signal) : await api.createTeam(body, signal);
      if (!signal?.aborted) onSaved(result);
    } catch (cause) {
      if (!signal?.aborted) setError(accessError(cause) ? pick("Your access may have changed. Close and refresh this workspace.", "আপনার অনুমতি বদলে যেতে পারে। বন্ধ করে কর্মপরিসর রিফ্রেশ করুন।") : pick("Unable to save the team. Check the fields and retry.", "দল সংরক্ষণ হয়নি। তথ্য দেখে আবার চেষ্টা করুন।"));
    } finally { if (!signal?.aborted) setPending(false); }
  }
  return <LibraryDialog title={team ? pick("Edit team workspace", "দলীয় কর্মপরিসর সম্পাদনা") : pick("Create team workspace", "দলীয় কর্মপরিসর তৈরি")} onClose={onClose}>
    <form className={styles.form} onSubmit={save}>{error && <p className="notice error" role="alert">{error}</p>}
      <label className="field">{pick("Team name", "দলের নাম")}<input required maxLength={160} value={name} onChange={(e) => setName(e.target.value)} /></label>
      <label className="field">{pick("Description", "বিবরণ")}<textarea rows={4} maxLength={10000} value={description} onChange={(e) => setDescription(e.target.value)} /></label>
      {!team && <p className={styles.small}>{pick("You become the owner. You can add existing ResearchNest accounts as editors or viewers after creating the team.", "আপনি মালিক হবেন। দল তৈরি করে রিসার্চনেস্টের বিদ্যমান অ্যাকাউন্ট সম্পাদক বা দর্শক হিসেবে যুক্ত করতে পারবেন।")}</p>}
      <button className="button primary" disabled={pending}>{pending ? pick("Saving…", "সংরক্ষণ হচ্ছে…") : pick("Save workspace", "কর্মপরিসর সংরক্ষণ")}</button>
    </form>
  </LibraryDialog>;
}

export function MemberForm({ workspaceId, onClose, onSaved }: { workspaceId: number; onClose: () => void; onSaved: () => void }) {
  const { pick } = useI18n();
  const [identifier, setIdentifier] = useState("");
  const [role, setRole] = useState<CollaboratorRole>("viewer");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const request = useRequest();
  async function add(event: FormEvent) {
    event.preventDefault(); setPending(true); setError("");
    const signal = request.current?.signal;
    try { await api.addTeamMember(workspaceId, identifier.trim(), role, signal); if (!signal?.aborted) onSaved(); }
    catch (cause) { if (!signal?.aborted) setError(cause instanceof ApiError && cause.status === 409 ? pick("This account is already a member. Change its role in the member list.", "অ্যাকাউন্টটি আগে থেকেই সদস্য। সদস্য তালিকায় ভূমিকা বদলান।") : pick("Unable to add this account. Check the identifier and your owner access.", "অ্যাকাউন্টটি যুক্ত হয়নি। পরিচয় ও আপনার মালিকানার অনুমতি দেখুন।")); }
    finally { if (!signal?.aborted) setPending(false); }
  }
  return <LibraryDialog title={pick("Add a collaborator", "সহযোগী যুক্ত করুন")} onClose={onClose}>
    <form className={styles.form} onSubmit={add}>
      <p className={styles.small}>{pick("Add an existing ResearchNest account by email or username. It gains team access immediately; no invitation email is sent.", "ইমেইল বা ব্যবহারকারীর নামে রিসার্চনেস্টের বিদ্যমান অ্যাকাউন্ট যুক্ত করুন। সঙ্গে সঙ্গে দলের অনুমতি পাবে; আমন্ত্রণের ইমেইল যাবে না।")}</p>
      {error && <p className="notice error" role="alert">{error}</p>}
      <label className="field">{pick("Email or username", "ইমেইল বা ব্যবহারকারীর নাম")}<input required maxLength={254} autoComplete="off" value={identifier} onChange={(e) => setIdentifier(e.target.value)} /></label>
      <label className="field">{pick("Team role", "দলের ভূমিকা")}<select value={role} onChange={(e) => setRole(e.target.value as CollaboratorRole)}><option value="viewer">{pick("Viewer — read only", "দর্শক — শুধু পড়া")}</option><option value="editor">{pick("Editor — share and edit notes", "সম্পাদক — ভাগ করা ও নোট সম্পাদনা")}</option></select></label>
      <button className="button primary" disabled={pending}>{pick("Add collaborator", "সহযোগী যুক্ত করুন")}</button>
    </form>
  </LibraryDialog>;
}

export function CollectionPicker({ team, onClose, onSaved }: { team: TeamDetail; onClose: () => void; onSaved: () => void }) {
  const { pick } = useI18n();
  const [collections, setCollections] = useState<LibraryCollection[] | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const request = useRequest();
  useEffect(() => {
    const active = new AbortController();
    api.getLibraryCollections(active.signal).then((items) => { if (!active.signal.aborted) setCollections(items); })
      .catch(() => { if (!active.signal.aborted) setError("Unable to load your own collections / আপনার নিজের সংগ্রহ লোড হয়নি।"); });
    return () => active.abort();
  }, []);
  async function share(id: number) {
    setPending(true); setError(""); const signal = request.current?.signal;
    try { await api.shareTeamCollection(team.id, id, signal); if (!signal?.aborted) onSaved(); }
    catch { if (!signal?.aborted) setError(pick("Unable to share. Verify that you still own the collection and have an editor or owner role.", "ভাগ করা যায়নি। সংগ্রহটি এখনো আপনার এবং আপনার সম্পাদক বা মালিকের ভূমিকা আছে কি না দেখুন।")); }
    finally { if (!signal?.aborted) setPending(false); }
  }
  return <LibraryDialog title={pick("Share my collection", "আমার সংগ্রহ ভাগ করুন")} onClose={onClose}>
    <p className={styles.small}>{pick("All current members will see the collection description and its current paper metadata, including future additions. Private PDFs, library notes, and annotations remain private. You can stop sharing later.", "বর্তমান সব সদস্য সংগ্রহের বিবরণ ও বর্তমান গবেষণাপত্রের মেটাডেটা দেখবেন, পরে যোগ করাও। ব্যক্তিগত পিডিএফ, লাইব্রেরির নোট ও টীকা ব্যক্তিগতই থাকবে। পরে ভাগ করা বন্ধ করতে পারবেন।")}</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    {!collections && !error && <p role="status">{pick("Loading your collections…", "আপনার সংগ্রহ লোড হচ্ছে…")}</p>}
    <ul className={styles.list}>{collections?.map((collection) => <li key={collection.id}><h3>{collection.name}</h3><p className={styles.small}>{collection.description}</p><button className="button secondary small" disabled={pending || team.collections.some((item) => item.collection_id === collection.id)} onClick={() => { void share(collection.id); }}>{team.collections.some((item) => item.collection_id === collection.id) ? pick("Already shared", "আগেই ভাগ করা আছে") : pick("Share with team", "দলের সঙ্গে ভাগ করুন")}</button></li>)}</ul>
    {collections?.length === 0 && <p className="empty-state">{pick("Create a personal collection in My Library first.", "আগে আমার লাইব্রেরিতে নিজের সংগ্রহ তৈরি করুন।")}</p>}
  </LibraryDialog>;
}

export function TeamNoteForm({ workspaceId, note, onClose, onSaved }: { workspaceId: number; note: TeamNote | null; onClose: () => void; onSaved: () => void }) {
  const { pick } = useI18n();
  const [title, setTitle] = useState(note?.title || "");
  const [content, setContent] = useState(note?.content || "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const request = useRequest();
  async function save(event: FormEvent) {
    event.preventDefault(); setPending(true); setError(""); const signal = request.current?.signal;
    try {
      const body = { title: title.trim(), content };
      if (note) await api.updateTeamNote(workspaceId, note.id, body, signal); else await api.createTeamNote(workspaceId, body, signal);
      if (!signal?.aborted) onSaved();
    } catch { if (!signal?.aborted) setError(pick("Unable to save this note. Your team access or role may have changed.", "নোট সংরক্ষণ হয়নি। দলের অনুমতি বা ভূমিকা বদলে যেতে পারে।")); }
    finally { if (!signal?.aborted) setPending(false); }
  }
  return <LibraryDialog title={note ? pick("Edit team note", "দলীয় নোট সম্পাদনা") : pick("Write team note", "দলীয় নোট লিখুন")} onClose={onClose}>
    <form className={styles.form} onSubmit={save}>
      <p className={styles.small}>{pick("This note is shared with current team members. Write only content you intend to share. It stays in the workspace if a collaborator leaves.", "এই নোট দলের বর্তমান সদস্যদের সঙ্গে ভাগ হবে। শুধু ভাগ করতে চান এমন বিষয় লিখুন। কোনো সহযোগী চলে গেলেও নোট কর্মপরিসরে থাকবে।")}</p>
      {error && <p className="notice error" role="alert">{error}</p>}
      <label className="field">{pick("Title", "শিরোনাম")}<input required maxLength={250} value={title} onChange={(e) => setTitle(e.target.value)} /></label>
      <label className="field">{pick("Team note", "দলীয় নোট")}<textarea required rows={8} maxLength={100000} value={content} onChange={(e) => setContent(e.target.value)} /></label>
      <button className="button primary" disabled={pending}>{pick("Save team note", "দলীয় নোট সংরক্ষণ")}</button>
    </form>
  </LibraryDialog>;
}
