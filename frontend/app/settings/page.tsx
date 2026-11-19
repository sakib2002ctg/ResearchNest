"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { api, type Preferences, type Profile, type SessionInfo } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

type Operation = "profile" | "preferences" | "password" | "sessions" | "export" | "delete";
type Notice = { operation: Operation | "language"; success: boolean } | null;

export default function SettingsPage() {
  const { user, isAuthenticated, clearSession, currentSessionId } = useAuth();
  const { language, setLanguage, pick, locale } = useI18n();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<Operation | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [passwords, setPasswords] = useState({ current: "", next: "", confirmation: "" });
  const [passwordMismatch, setPasswordMismatch] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [revokeId, setRevokeId] = useState<string | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);
  const [confirmLogoutAll, setConfirmLogoutAll] = useState(false);

  const load = useCallback(async (showLoading = true) => {
    if (!isAuthenticated) return;
    if (showLoading) setLoading(true);
    setFailed(false);
    try {
      const [profileData, preferenceData, sessionData] = await Promise.all([
        api.getProfile(), api.getPreferences(), api.getSessions(),
      ]);
      setProfile(profileData);
      setPreferences(preferenceData);
      setSessions(sessionData);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(false), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  function updateProfileField(key: keyof Pick<Profile, "full_name" | "bio" | "institution" | "academic_role" | "avatar_url">, value: string) {
    setProfile((current) => current ? { ...current, [key]: value } : current);
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile || busy) return;
    setBusy("profile");
    setNotice(null);
    try {
      setProfile(await api.updateProfile({
        full_name: profile.full_name?.trim() || null, bio: profile.bio?.trim() || null,
        institution: profile.institution?.trim() || null, academic_role: profile.academic_role?.trim() || null,
        avatar_url: profile.avatar_url?.trim() || null,
      }));
      setNotice({ operation: "profile", success: true });
    } catch {
      setNotice({ operation: "profile", success: false });
    } finally { setBusy(null); }
  }

  async function savePreferences(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preferences || busy) return;
    setBusy("preferences");
    setNotice(null);
    try {
      const saved = await api.updatePreferences({
        theme: preferences.theme, privacy_default: preferences.privacy_default,
        allow_external_ai: preferences.allow_external_ai,
      });
      setPreferences(saved);
      window.dispatchEvent(new CustomEvent("researchnest:theme", { detail: saved.theme }));
      setNotice({ operation: "preferences", success: true });
    } catch {
      setNotice({ operation: "preferences", success: false });
    } finally { setBusy(null); }
  }

  async function changeLanguage(value: "en" | "bn") {
    setNotice(null);
    try {
      await setLanguage(value);
      setNotice({ operation: "language", success: true });
    } catch { setNotice({ operation: "language", success: false }); }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setPasswordMismatch(passwords.next !== passwords.confirmation);
    if (passwords.next !== passwords.confirmation) return;
    setBusy("password");
    setNotice(null);
    try {
      await api.changePassword(passwords.current, passwords.next);
      setPasswords({ current: "", next: "", confirmation: "" });
      setSessions(await api.getSessions());
      setNotice({ operation: "password", success: true });
    } catch {
      setNotice({ operation: "password", success: false });
    } finally { setBusy(null); }
  }

  async function revokeSession(id: string) {
    if (busy) return;
    setBusy("sessions");
    setRevokeId(id);
    setNotice(null);
    try {
      await api.revokeSession(id);
      if (id === currentSessionId) {
        clearSession();
        return;
      }
      setSessions(await api.getSessions());
      setConfirmRevoke(null);
      setNotice({ operation: "sessions", success: true });
    } catch {
      setNotice({ operation: "sessions", success: false });
    } finally { setBusy(null); setRevokeId(null); }
  }

  async function logoutAll() {
    if (busy) return;
    setBusy("sessions");
    setNotice(null);
    try {
      await api.logoutAll();
      clearSession();
    } catch {
      setNotice({ operation: "sessions", success: false });
    } finally { setBusy(null); }
  }

  async function exportAccount() {
    if (busy) return;
    setBusy("export");
    setNotice(null);
    try {
      const data = await api.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `researchnest-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
      setNotice({ operation: "export", success: true });
    } catch { setNotice({ operation: "export", success: false }); }
    finally { setBusy(null); }
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || deleteConfirmation !== "DELETE") return;
    setBusy("delete");
    setNotice(null);
    try {
      await api.deleteAccount();
      clearSession();
    } catch {
      setNotice({ operation: "delete", success: false });
    } finally { setBusy(null); }
  }

  const date = (value: string) => new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
  function noticeText() {
    if (!notice) return "";
    if (!notice.success) return notice.operation === "password"
      ? pick("The password could not be changed. Check your current password and try again.", "পাসওয়ার্ড পরিবর্তন করা যায়নি। বর্তমান পাসওয়ার্ড যাচাই করে আবার চেষ্টা করুন।")
      : pick("The change could not be completed. Please try again.", "পরিবর্তনটি সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।");
    const messages: Record<NonNullable<Notice>["operation"], readonly [string, string]> = {
      profile: ["Your profile has been updated.", "আপনার প্রোফাইল হালনাগাদ হয়েছে।"],
      preferences: ["Your preferences have been saved.", "আপনার পছন্দসমূহ সংরক্ষিত হয়েছে।"],
      language: ["Language preference saved.", "ভাষার পছন্দ সংরক্ষিত হয়েছে।"],
      password: ["Password changed. Your other sessions have been signed out.", "পাসওয়ার্ড পরিবর্তন হয়েছে। অন্য সেশনগুলো থেকে সাইন আউট করা হয়েছে।"],
      sessions: ["The device session has been revoked.", "ডিভাইসের সেশন বাতিল করা হয়েছে।"],
      export: ["Your JSON export download has started.", "আপনার JSON তথ্য রপ্তানির ডাউনলোড শুরু হয়েছে।"],
      delete: ["Your account has been deleted.", "আপনার অ্যাকাউন্ট মুছে ফেলা হয়েছে।"],
    };
    return pick(...messages[notice.operation]);
  }

  return <AppShell title={pick("Settings", "সেটিংস")} description={pick("Your research, your preferences, your control.", "আপনার গবেষণা, আপনার পছন্দ, আপনার নিয়ন্ত্রণ।")}>
    <div className="page-heading"><div><p className="eyebrow">{pick("MAKE YOURSELF AT HOME", "নিজের মতো করে সাজান")}</p><h1>{pick("Account & preferences", "অ্যাকাউন্ট ও পছন্দসমূহ")}</h1><p className="muted">{pick("A workspace that respects how you think and work.", "আপনার ভাবনা ও কাজের ধরনকে সম্মান করে এমন কর্মপরিসর।")}</p></div></div>
    <div aria-live="polite">{notice && <div className={`notice ${notice.success ? "success" : "error"}`} role={notice.success ? "status" : "alert"}>{noticeText()}</div>}</div>
    {loading && <div className="loading-state" role="status">{pick("Loading your account settings…", "অ্যাকাউন্ট সেটিংস লোড হচ্ছে…")}</div>}
    {failed && <div className="notice error" role="alert"><p>{pick("Your settings could not be loaded.", "আপনার সেটিংস লোড করা যায়নি।")}</p><button className="button secondary small" type="button" onClick={() => void load()}>{pick("Try again", "আবার চেষ্টা করুন")}</button></div>}

    {!loading && !failed && profile && preferences && <div className="settings-grid">
      <div className="flex min-w-0 flex-col gap-6">
        <section className="card settings-section" id="profile"><div className="section-heading"><div><h2>{pick("Researcher profile", "গবেষকের প্রোফাইল")}</h2><p className="muted text-sm">{pick("Tell us a little about the person behind the questions.", "প্রশ্নের পেছনের মানুষটি সম্পর্কে একটু জানান।")}</p></div><Icon name="user" size={22} /></div><form className="form-stack" onSubmit={saveProfile}>
          <div className="inline-fields"><label className="field" htmlFor="full-name"><span>{pick("Full name", "পূর্ণ নাম")}</span><input id="full-name" autoComplete="name" maxLength={255} value={profile.full_name ?? ""} onChange={(event) => updateProfileField("full_name", event.target.value)} /></label><label className="field" htmlFor="account-email"><span>{pick("Email address", "ইমেইল ঠিকানা")}</span><input id="account-email" type="email" value={user?.email ?? ""} readOnly aria-readonly="true" className="opacity-70" /></label></div>
          <div className="inline-fields"><label className="field" htmlFor="institution"><span>{pick("Institution", "প্রতিষ্ঠান")}</span><input id="institution" autoComplete="organization" maxLength={255} value={profile.institution ?? ""} onChange={(event) => updateProfileField("institution", event.target.value)} /></label><label className="field" htmlFor="academic-role"><span>{pick("Academic role", "একাডেমিক ভূমিকা")}</span><input id="academic-role" maxLength={100} value={profile.academic_role ?? ""} onChange={(event) => updateProfileField("academic_role", event.target.value)} placeholder={pick("Student, researcher, educator…", "শিক্ষার্থী, গবেষক, শিক্ষক…")} /></label></div>
          <label className="field" htmlFor="profile-bio"><span>{pick("Short bio", "সংক্ষিপ্ত পরিচয়")}</span><textarea id="profile-bio" maxLength={5000} rows={3} value={profile.bio ?? ""} onChange={(event) => updateProfileField("bio", event.target.value)} /></label>
          <label className="field" htmlFor="avatar-url"><span>{pick("Avatar URL", "প্রোফাইল ছবির লিংক")}</span><input id="avatar-url" type="url" maxLength={2048} value={profile.avatar_url ?? ""} onChange={(event) => updateProfileField("avatar_url", event.target.value)} placeholder="https://" /></label>
          <div className="flex flex-wrap items-center justify-between gap-3"><button className="button primary" type="submit" disabled={busy !== null}>{busy === "profile" ? pick("Saving…", "সংরক্ষণ হচ্ছে…") : pick("Save profile", "প্রোফাইল সংরক্ষণ করুন")}</button><Link href="/verify-email" className="text-sm">{user?.is_verified ? pick("Email verified", "ইমেইল যাচাইকৃত") : pick("Verify your email", "ইমেইল যাচাই করুন")}</Link></div>
        </form></section>

        <section className="card settings-section" id="preferences"><div className="section-heading"><div><h2>{pick("Language & privacy", "ভাষা ও গোপনীয়তা")}</h2><p className="muted text-sm">{pick("Personal settings for a more comfortable workspace.", "আরও স্বাচ্ছন্দ্যের জন্য আপনার নিজস্ব সেটিংস।")}</p></div><Icon name="sliders" size={22} /></div>
          <label className="field mb-5" htmlFor="preference-language"><span>{pick("Language · saved instantly", "ভাষা · সাথে সাথে সংরক্ষিত")}</span><select id="preference-language" value={language} onChange={(event) => void changeLanguage(event.target.value as "en" | "bn")}><option value="en">English</option><option value="bn">বাংলা</option></select></label>
          <form className="form-stack" onSubmit={savePreferences}><div className="inline-fields"><label className="field" htmlFor="preference-theme"><span>{pick("Appearance", "দেখানোর ধরন")}</span><select id="preference-theme" value={preferences.theme} onChange={(event) => setPreferences({ ...preferences, theme: event.target.value as Preferences["theme"] })}><option value="system">{pick("Use device setting", "ডিভাইসের সেটিংস")}</option><option value="light">{pick("Light", "হালকা")}</option><option value="dark">{pick("Dark", "গাঢ়")}</option></select></label><label className="field" htmlFor="preference-privacy"><span>{pick("Default privacy preference", "গোপনীয়তার পূর্বনির্ধারিত পছন্দ")}</span><select id="preference-privacy" value={preferences.privacy_default} onChange={(event) => setPreferences({ ...preferences, privacy_default: event.target.value as Preferences["privacy_default"] })}><option value="private">{pick("Private", "ব্যক্তিগত")}</option><option value="public">{pick("Public", "সর্বজনীন")}</option></select></label></div>
            <p className="muted text-xs">{pick("This saves a default preference; it does not publish your existing papers or make your library public.", "এটি শুধু পূর্বনির্ধারিত পছন্দ সংরক্ষণ করে; পুরোনো গবেষণাপত্র বা লাইব্রেরি সর্বজনীন করে না।")}</p>
            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-[var(--border)] p-4" htmlFor="external-ai"><input id="external-ai" type="checkbox" className="mt-1 h-4 w-4 shrink-0 accent-[var(--accent)]" checked={preferences.allow_external_ai} onChange={(event) => setPreferences({ ...preferences, allow_external_ai: event.target.checked })} /><span><strong className="text-sm">{pick("Allow external AI processing", "বহিরাগত এআই প্রক্রিয়াকরণে অনুমতি দিন")}</strong><span className="muted mt-1 block text-sm">{pick("I explicitly consent to eligible private research content being sent to an external AI provider when I use a supported AI feature. This is off by default; AI tools are planned for later phases.", "সমর্থিত এআই সুবিধা ব্যবহারের সময় উপযুক্ত ব্যক্তিগত গবেষণার তথ্য বহিরাগত এআই সেবায় পাঠানোর জন্য আমি স্পষ্ট সম্মতি দিচ্ছি। এটি শুরুতে বন্ধ থাকে; এআই সুবিধাগুলো পরবর্তী পর্যায়ে আসবে।")}</span></span></label>
            <div><button type="submit" className="button primary" disabled={busy !== null}>{busy === "preferences" ? pick("Saving…", "সংরক্ষণ হচ্ছে…") : pick("Save preferences", "পছন্দসমূহ সংরক্ষণ করুন")}</button></div>
          </form>
        </section>

        <section className="card settings-section" id="password"><div className="section-heading"><div><h2>{pick("Password & security", "পাসওয়ার্ড ও নিরাপত্তা")}</h2><p className="muted text-sm">{pick("Changing your password signs out your other active sessions.", "পাসওয়ার্ড পরিবর্তন করলে অন্য সক্রিয় সেশনগুলো থেকে সাইন আউট হবে।")}</p></div><Icon name="lock" size={22} /></div><form className="form-stack" onSubmit={changePassword}>
          <label className="field" htmlFor="current-password"><span>{pick("Current password", "বর্তমান পাসওয়ার্ড")}</span><input id="current-password" type="password" autoComplete="current-password" minLength={8} maxLength={128} required value={passwords.current} onChange={(event) => setPasswords({ ...passwords, current: event.target.value })} /></label>
          <div className="inline-fields"><label className="field" htmlFor="new-password"><span>{pick("New password", "নতুন পাসওয়ার্ড")}</span><input id="new-password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={passwords.next} onChange={(event) => setPasswords({ ...passwords, next: event.target.value })} aria-describedby="password-help" /></label><label className="field" htmlFor="confirm-password"><span>{pick("Confirm new password", "নতুন পাসওয়ার্ড নিশ্চিত করুন")}</span><input id="confirm-password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={passwords.confirmation} onChange={(event) => setPasswords({ ...passwords, confirmation: event.target.value })} aria-invalid={passwordMismatch} aria-describedby={passwordMismatch ? "password-mismatch" : undefined} /></label></div>
          <p className="muted text-xs" id="password-help">{pick("Use 8–128 characters and a unique password.", "৮–১২৮ অক্ষরের একটি অনন্য পাসওয়ার্ড ব্যবহার করুন।")}</p>{passwordMismatch && <p className="text-sm text-red-700" id="password-mismatch" role="alert">{pick("The new passwords do not match.", "নতুন পাসওয়ার্ড দুটি মেলেনি।")}</p>}
          <div><button className="button primary" type="submit" disabled={busy !== null}>{busy === "password" ? pick("Updating…", "হালনাগাদ হচ্ছে…") : pick("Update password", "পাসওয়ার্ড হালনাগাদ করুন")}</button></div>
        </form></section>
      </div>

      <aside className="flex min-w-0 flex-col gap-6">
        <section className="card settings-section" id="sessions"><div className="section-heading"><div><h2>{pick("Active devices", "সক্রিয় ডিভাইস")}</h2><p className="muted text-sm">{pick("Review where your account is signed in.", "কোন ডিভাইসে সাইন ইন করা আছে দেখুন।")}</p></div><Icon name="monitor" size={22} /></div>
          {sessions.length === 0 ? <p className="muted text-sm">{pick("No active sessions to display.", "দেখানোর মতো সক্রিয় সেশন নেই।")}</p> : <ul className="space-y-3">{sessions.map((session) => <li key={session.id} className="session-card"><div className="flex items-start gap-3"><Icon name="monitor" size={18} /><div className="min-w-0 flex-1"><p className="break-words text-sm font-medium">{session.user_agent || pick("Unknown device", "অজানা ডিভাইস")}</p>{session.id === currentSessionId && <span className="tag mt-2">{pick("This session", "বর্তমান সেশন")}</span>}<p className="muted mt-2 text-xs">{pick("IP", "আইপি")}: {session.ip_address || pick("Not recorded", "তথ্য নেই")}</p><p className="muted mt-1 text-xs">{pick("Signed in", "সাইন ইন")}: {date(session.created_at)}</p><p className="muted mt-1 text-xs">{pick("Expires", "মেয়াদ শেষ")}: {date(session.expires_at)}</p></div></div>
            {confirmRevoke === session.id ? <div className="mt-3"><p className="mb-2 text-xs">{session.id === currentSessionId ? pick("This will sign you out of this session.", "এতে বর্তমান সেশন থেকে সাইন আউট হবে।") : pick("Sign this device out?", "এই ডিভাইস থেকে সাইন আউট করবেন?")}</p><div className="flex flex-wrap gap-2"><button type="button" className="button danger small" disabled={busy !== null} onClick={() => void revokeSession(session.id)}>{revokeId === session.id ? pick("Revoking…", "বাতিল হচ্ছে…") : pick("Revoke session", "সেশন বাতিল করুন")}</button><button className="button ghost small" type="button" onClick={() => setConfirmRevoke(null)} disabled={busy !== null}>{pick("Cancel", "বাতিল")}</button></div></div> : <button className="button ghost small mt-3" type="button" disabled={busy !== null} onClick={() => setConfirmRevoke(session.id)}>{pick("Revoke session", "সেশন বাতিল করুন")}</button>}
          </li>)}</ul>}
          {confirmLogoutAll ? <div className="mt-5 border-t border-[var(--border)] pt-4"><p className="mb-3 text-sm">{pick("You will be signed out on every device, including this one.", "বর্তমান ডিভাইসসহ সব ডিভাইস থেকে সাইন আউট হবে।")}</p><div className="flex flex-wrap gap-2"><button className="button danger small" type="button" disabled={busy !== null} onClick={() => void logoutAll()}>{busy === "sessions" ? pick("Signing out…", "সাইন আউট হচ্ছে…") : pick("Confirm sign out all", "সব সেশন থেকে সাইন আউট করুন")}</button><button className="button ghost small" type="button" onClick={() => setConfirmLogoutAll(false)} disabled={busy !== null}>{pick("Cancel", "বাতিল")}</button></div></div> : <button className="button secondary mt-5 w-full" type="button" disabled={busy !== null} onClick={() => setConfirmLogoutAll(true)}>{pick("Sign out all devices", "সব ডিভাইস থেকে সাইন আউট")}</button>}
        </section>

        <section className="card settings-section"><Icon name="download" size={23} /><h2 className="mt-3">{pick("Your data belongs to you", "আপনার তথ্য আপনারই")}</h2><p className="muted mt-2 text-sm">{pick("Download your profile, preferences, saved papers, active session metadata, and account activity as JSON. Passwords and tokens are excluded.", "প্রোফাইল, পছন্দসমূহ, সংরক্ষিত গবেষণাপত্র, সক্রিয় সেশনের তথ্য ও অ্যাকাউন্টের কার্যক্রম JSON ফাইলে নামান। পাসওয়ার্ড ও টোকেন এতে থাকে না।")}</p><button className="button secondary mt-4 w-full" type="button" disabled={busy !== null} onClick={() => void exportAccount()}>{busy === "export" ? pick("Preparing download…", "ডাউনলোড প্রস্তুত হচ্ছে…") : pick("Export my data", "আমার তথ্য রপ্তানি করুন")}</button></section>

        <section className="card settings-section border-red-200" id="delete-account"><Icon name="shield" size={23} /><h2 className="mt-3">{pick("Delete account", "অ্যাকাউন্ট মুছুন")}</h2><p className="muted mt-2 text-sm">{pick("This permanently removes your account and private library data. Limited security audit records are retained without an account link.", "এতে আপনার অ্যাকাউন্ট ও ব্যক্তিগত লাইব্রেরির তথ্য স্থায়ীভাবে মুছে যাবে। সীমিত নিরাপত্তা রেকর্ড অ্যাকাউন্টের সংযোগ ছাড়া রাখা হয়।")}</p>
          {deleteOpen ? <form className="form-stack mt-4" onSubmit={deleteAccount}><label className="field" htmlFor="delete-confirm"><span>{pick("Type DELETE to confirm permanent deletion", "স্থায়ীভাবে মুছে ফেলা নিশ্চিত করতে DELETE লিখুন")}</span><input id="delete-confirm" type="text" autoComplete="off" spellCheck={false} value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} required pattern="DELETE" /></label><button className="button danger" type="submit" disabled={busy !== null || deleteConfirmation !== "DELETE"}>{busy === "delete" ? pick("Deleting…", "মুছে ফেলা হচ্ছে…") : pick("Permanently delete my account", "আমার অ্যাকাউন্ট স্থায়ীভাবে মুছুন")}</button><button type="button" className="button ghost" disabled={busy !== null} onClick={() => { setDeleteOpen(false); setDeleteConfirmation(""); }}>{pick("Keep my account", "আমার অ্যাকাউন্ট রাখুন")}</button></form> : <button className="button danger mt-4 w-full" type="button" disabled={busy !== null} onClick={() => setDeleteOpen(true)}>{pick("Delete my account", "আমার অ্যাকাউন্ট মুছুন")}</button>}
        </section>
      </aside>
    </div>}
  </AppShell>;
}
