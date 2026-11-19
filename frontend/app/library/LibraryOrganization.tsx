"use client";

import { useState, type FormEvent } from "react";
import { api, type LibraryCollection, type LibraryPaper, type LibraryTag, type ReadingStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { LibraryDialog } from "./DocumentViewer";

type Group = "collections" | "tags";

export function OrganizeLibrary({ group, items, refresh, close }: {
  group: Group;
  items: (LibraryCollection | LibraryTag)[];
  refresh: () => void;
  close: () => void;
}) {
  const { pick } = useI18n();
  const [editing, setEditing] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [detail, setDetail] = useState("");
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const collection = group === "collections";

  function reset() {
    setEditing(null);
    setName("");
    setDetail("");
    setFailed(false);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || pending) return;
    setPending(true);
    setFailed(false);
    try {
      if (collection) {
        const body = { name: name.trim(), description: detail.trim() || null };
        if (editing === null) await api.createLibraryCollection(body);
        else await api.updateLibraryCollection(editing, body);
      } else {
        const body = { name: name.trim(), color: detail.trim() || null };
        if (editing === null) await api.createLibraryTag(body);
        else await api.updateLibraryTag(editing, body);
      }
      reset();
      refresh();
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  async function remove(id: number) {
    if (!window.confirm(pick("Remove this label from your library?", "আপনার লাইব্রেরি থেকে এই লেবেলটি সরাবেন?"))) return;
    setPending(true);
    setFailed(false);
    try {
      if (collection) await api.deleteLibraryCollection(id);
      else await api.deleteLibraryTag(id);
      if (editing === id) reset();
      refresh();
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <LibraryDialog title={collection ? pick("Manage collections", "সংগ্রহ পরিচালনা") : pick("Manage tags", "ট্যাগ পরিচালনা")} onClose={close}>
      <ul className="mb-5 grid gap-2">
        {items.map((item) => (
          <li className="session-card m-0 flex flex-wrap items-center justify-between gap-2" key={item.id}>
            <span className="min-w-0 break-words">{item.name}</span>
            <div className="flex flex-wrap gap-2">
              <button className="button secondary small" type="button" disabled={pending} onClick={() => {
                setEditing(item.id);
                setName(item.name);
                setDetail(("description" in item ? item.description : item.color) ?? "");
                setFailed(false);
              }}>{pick("Edit", "সম্পাদনা")}</button>
              <button className="button secondary small" type="button" disabled={pending} onClick={() => void remove(item.id)}>{pick("Delete", "মুছুন")}</button>
            </div>
          </li>
        ))}
      </ul>
      <form className="form-stack" onSubmit={save}>
        <label className="field">{collection ? pick("Collection name", "সংগ্রহের নাম") : pick("Tag name", "ট্যাগের নাম")}
          <input required maxLength={100} value={name} disabled={pending} onChange={(event) => setName(event.target.value)} />
        </label>
        {collection ? (
          <label className="field">{pick("Description (optional)", "বর্ণনা (ঐচ্ছিক)")}
            <textarea maxLength={2000} value={detail} disabled={pending} onChange={(event) => setDetail(event.target.value)} />
          </label>
        ) : (
          <label className="field">{pick("Color (optional)", "রং (ঐচ্ছিক)")}
            <input placeholder="#168049" pattern="#[0-9A-Fa-f]{6}" maxLength={7} value={detail} disabled={pending} onChange={(event) => setDetail(event.target.value)} />
          </label>
        )}
        <div className="flex flex-wrap gap-2">
          <button className="button primary" type="submit" disabled={pending}>{editing === null ? pick("Add", "যোগ করুন") : pick("Save changes", "পরিবর্তন সংরক্ষণ করুন")}</button>
          {editing !== null && <button className="button secondary" type="button" disabled={pending} onClick={reset}>{pick("Cancel edit", "সম্পাদনা বাতিল")}</button>}
        </div>
        {failed && <p className="notice error" role="alert">{pick("The change could not be saved.", "পরিবর্তন সংরক্ষণ করা যায়নি।")}</p>}
      </form>
    </LibraryDialog>
  );
}

export function PaperOrganization({ paper, collections, tags, refresh, close }: {
  paper: LibraryPaper;
  collections: LibraryCollection[];
  tags: LibraryTag[];
  refresh: () => void;
  close: () => void;
}) {
  const { pick } = useI18n();
  const [collectionIds, setCollectionIds] = useState(paper.collection_ids);
  const [tagIds, setTagIds] = useState(paper.tag_ids);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  async function toggle(group: Group, id: number, include: boolean) {
    setPending(true);
    setFailed(false);
    try {
      await api.setLibraryMembership(group, id, paper.id, include);
      const setIds = group === "collections" ? setCollectionIds : setTagIds;
      setIds((ids) => include ? [...ids, id] : ids.filter((value) => value !== id));
      refresh();
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <LibraryDialog title={pick("Organize paper", "গবেষণাপত্র সাজান")} onClose={close}>
      <div className="inline-fields">
        {([
          ["collections", pick("Collections", "সংগ্রহ"), collections, collectionIds],
          ["tags", pick("Tags", "ট্যাগ"), tags, tagIds],
        ] as const).map(([group, name, items, ids]) => (
          <fieldset className="min-w-0 grid gap-2 self-start" key={group}>
            <legend className="font-semibold mb-2">{name}</legend>
            {items.length === 0 && <p className="muted text-sm">{pick("Create one from the library sidebar.", "লাইব্রেরির পাশের তালিকা থেকে একটি তৈরি করুন।")}</p>}
            {items.map((item) => (
              <label className="flex items-start gap-2 text-sm" key={item.id}>
                <input className="mt-1" type="checkbox" checked={ids.includes(item.id)} disabled={pending}
                  onChange={(event) => void toggle(group, item.id, event.target.checked)} />
                <span className="min-w-0 break-words">{item.name}</span>
              </label>
            ))}
          </fieldset>
        ))}
      </div>
      {failed && <p className="notice error mt-4" role="alert">{pick("The change could not be saved.", "পরিবর্তন সংরক্ষণ করা যায়নি।")}</p>}
    </LibraryDialog>
  );
}

export function ReadingProgressForm({ paper, refresh }: { paper: LibraryPaper; refresh: () => void }) {
  const { pick } = useI18n();
  const [status, setStatus] = useState(paper.reading_status);
  const [percent, setPercent] = useState(String(paper.reading_progress_percent));
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setFailed(false);
    try {
      await api.setReadingProgress(paper.id, {
        reading_status: status,
        reading_progress_percent: Number(percent),
      });
      refresh();
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="library-progress" onSubmit={save}>
      <label className="field">{pick("Reading status", "পড়ার অবস্থা")}
        <select value={status} disabled={pending} onChange={(event) => {
          const value = event.target.value as ReadingStatus;
          setStatus(value);
          if (value === "completed") setPercent("100");
          else if (value === "unread" || percent === "100") setPercent("0");
        }}>
          <option value="unread">{pick("Unread", "পড়া হয়নি")}</option>
          <option value="reading">{pick("Reading", "পড়ছি")}</option>
          <option value="completed">{pick("Completed", "পড়া শেষ")}</option>
        </select>
      </label>
      <label className="field">{pick("Progress (%)", "অগ্রগতি (%)")}
        <input type="number" min={0} max={100} step="any" required value={percent} disabled={pending || status !== "reading"}
          onChange={(event) => {
            setPercent(event.target.value);
            if (event.target.value === "100") setStatus("completed");
          }} />
      </label>
      <button type="submit" className="button secondary small" disabled={pending || (status === paper.reading_status && Number(percent) === paper.reading_progress_percent)}>
        {pick("Save progress", "অগ্রগতি সংরক্ষণ")}
      </button>
      {failed && <p className="notice error col-span-full" role="alert">{pick("Progress could not be updated.", "অগ্রগতি আপডেট করা যায়নি।")}</p>}
    </form>
  );
}
