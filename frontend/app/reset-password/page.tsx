"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import AuthPanel from "@/components/AuthPanel";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function ResetPasswordPage() {
  const { pick } = useI18n();
  const { clearSession } = useAuth();
  const [step, setStep] = useState<"request" | "confirm">("request");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);

  async function request(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setMessage("");
    setError("");
    try {
      await api.requestPasswordReset(email.trim());
      setMessage(pick("If the account exists, password reset instructions will be sent. Check your email and use the latest token.", "অ্যাকাউন্টটি থাকলে পাসওয়ার্ড পুনরুদ্ধারের নির্দেশনা পাঠানো হবে। ইমেইলে সর্বশেষ টোকেন দেখুন।"));
      setStep("confirm");
    } catch {
      setError(pick("We could not submit this request. Check your connection and try again.", "অনুরোধ পাঠানো যায়নি। সংযোগ পরীক্ষা করে আবার চেষ্টা করুন।"));
    } finally {
      setPending(false);
    }
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (password !== confirmation) {
      setError(pick("Your passwords do not match.", "পাসওয়ার্ড দুটি এক নয়।"));
      return;
    }
    setPending(true);
    try {
      await api.confirmPasswordReset(token.trim(), password);
      clearSession();
      setToken("");
      setPassword("");
      setConfirmation("");
      setComplete(true);
      setMessage(pick("Your password has been reset and existing sessions have been signed out. Log in with your new password.", "পাসওয়ার্ড বদলেছে এবং পুরোনো সেশনগুলো বন্ধ হয়েছে। নতুন পাসওয়ার্ড দিয়ে লগইন করুন।"));
    } catch {
      setError(pick("This token is invalid, expired, or already used. Request a fresh token and try again.", "এই টোকেন সঠিক নয়, মেয়াদ শেষ বা আগেই ব্যবহৃত। নতুন টোকেন নিয়ে আবার চেষ্টা করুন।"));
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthPanel title={pick("Let's get you back in.", "ফিরে আসুন আপনার কর্মক্ষেত্রে।")} description={pick("A secure reset for a fresh start. Your research stays right where you left it.", "নিরাপদভাবে নতুন পাসওয়ার্ড দিন। আপনার গবেষণা আগের জায়গাতেই থাকবে।")}>
      {!complete && <div className="mb-6 grid grid-cols-2 rounded-lg bg-stone-100 p-1" role="group" aria-label={pick("Password reset step", "পাসওয়ার্ড পুনরুদ্ধারের ধাপ")}>
        <button type="button" className={`rounded-md px-2 py-2 text-xs font-medium ${step === "request" ? "bg-white shadow-sm" : "text-stone-500"}`} aria-pressed={step === "request"} onClick={() => { setStep("request"); setError(""); }} disabled={pending}>{pick("1. Request email", "১. ইমেইল অনুরোধ")}</button>
        <button type="button" className={`rounded-md px-2 py-2 text-xs font-medium ${step === "confirm" ? "bg-white shadow-sm" : "text-stone-500"}`} aria-pressed={step === "confirm"} onClick={() => { setStep("confirm"); setError(""); }} disabled={pending}>{pick("2. Set new password", "২. নতুন পাসওয়ার্ড")}</button>
      </div>}
      {!complete && step === "request" && <form className="form-stack" onSubmit={request}><div className="field"><label htmlFor="reset-email">{pick("Account email address", "অ্যাকাউন্টের ইমেইল ঠিকানা")}</label><input id="reset-email" name="email" type="email" required maxLength={255} autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@university.edu" /></div><button className="button primary w-full" type="submit" disabled={pending}>{pending ? pick("Requesting…", "অনুরোধ করা হচ্ছে…") : pick("Request password reset", "পাসওয়ার্ড পুনরুদ্ধার অনুরোধ")}</button></form>}
      {!complete && step === "confirm" && <form className="form-stack" onSubmit={confirm}>
        <div className="field"><label htmlFor="reset-token">{pick("Reset token", "পুনরুদ্ধার টোকেন")}</label><input id="reset-token" name="token" required minLength={32} maxLength={128} autoComplete="off" spellCheck={false} value={token} onChange={(event) => setToken(event.target.value)} placeholder={pick("Paste the latest token from your email", "ইমেইলের সর্বশেষ টোকেন দিন")} /><p className="text-xs text-stone-400">{pick("Tokens expire after 20 minutes and work only once.", "টোকেনের মেয়াদ ২০ মিনিট এবং এটি একবারই কাজ করে।")}</p></div>
        <div className="field"><label htmlFor="reset-password">{pick("New password", "নতুন পাসওয়ার্ড")}</label><input id="reset-password" name="new-password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} aria-describedby="reset-hint" /><p id="reset-hint" className="text-xs text-stone-400">{pick("Use 8–128 characters.", "৮–১২৮ অক্ষর ব্যবহার করুন।")}</p></div>
        <div className="field"><label htmlFor="reset-confirm">{pick("Confirm new password", "নতুন পাসওয়ার্ড আবার লিখুন")}</label><input id="reset-confirm" name="confirm-password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></div>
        <button className="button primary w-full" type="submit" disabled={pending}>{pending ? pick("Resetting password…", "পাসওয়ার্ড বদলানো হচ্ছে…") : pick("Reset my password", "আমার পাসওয়ার্ড বদলান")}</button>
      </form>}
      {message && <p className="notice success mt-5" role="status">{message}</p>}
      {error && <p className="notice error mt-5" role="alert">{error}</p>}
      <Link className={complete ? "button primary mt-6 w-full" : "mt-6 block text-center text-sm font-medium text-emerald-800"} href="/login">{pick("Back to log in", "লগইনে ফিরে যান")}{complete && <span aria-hidden="true">→</span>}</Link>
    </AuthPanel>
  );
}
