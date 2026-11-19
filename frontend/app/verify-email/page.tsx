"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import AuthPanel from "@/components/AuthPanel";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function VerifyEmailPage() {
  const { pick } = useI18n();
  const { isAuthenticated, user, refreshUser } = useAuth();
  const [token, setToken] = useState("");
  const [debugToken, setDebugToken] = useState("");
  const [pending, setPending] = useState<"request" | "confirm" | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  async function requestToken() {
    setPending("request");
    setMessage("");
    setError("");
    setDebugToken("");
    try {
      const result = await api.requestEmailVerification();
      setMessage(pick("Verification requested. Check your email. If you have made several requests, wait a few minutes before trying again.", "যাচাইয়ের অনুরোধ করা হয়েছে। ইমেইল দেখুন। একাধিকবার অনুরোধ করলে কয়েক মিনিট পর আবার চেষ্টা করুন।"));
      if (result.debug_token) setDebugToken(result.debug_token);
    } catch {
      setError(pick("We could not request verification. Please sign in and try again.", "যাচাইয়ের অনুরোধ করা যায়নি। লগইন করে আবার চেষ্টা করুন।"));
    } finally {
      setPending(null);
    }
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending("confirm");
    setMessage("");
    setError("");
    try {
      await api.confirmEmailVerification(token.trim());
      if (isAuthenticated) await refreshUser().catch(() => undefined);
      setToken("");
      setDebugToken("");
      setConfirmed(true);
      setMessage(pick("Your email is verified. You're ready to continue.", "আপনার ইমেইল যাচাই হয়েছে। এবার এগিয়ে যেতে পারেন।"));
    } catch {
      setError(pick("This token is invalid, expired, or already used. Request a new one and try again.", "এই টোকেন সঠিক নয়, মেয়াদ শেষ বা আগেই ব্যবহৃত। নতুন টোকেন নিয়ে আবার চেষ্টা করুন।"));
    } finally {
      setPending(null);
    }
  }

  return (
    <AuthPanel title={pick("A small step. A safer account.", "ছোট একটি ধাপ। আরও নিরাপদ অ্যাকাউন্ট।")} description={pick("Verify the email address connected to your research workspace.", "আপনার গবেষণার কর্মক্ষেত্রের ইমেইল ঠিকানা যাচাই করুন।")}>
      {isAuthenticated && !confirmed && <div className="mb-7 rounded-xl bg-stone-50 p-4"><p className="mb-3 text-sm leading-relaxed text-stone-500">{pick("Send a verification token to", "যাচাই টোকেন পাঠান")} <span className="font-medium text-stone-700">{user?.email}</span></p><button type="button" className="button secondary w-full" onClick={() => void requestToken()} disabled={pending !== null}>{pending === "request" ? pick("Requesting…", "অনুরোধ করা হচ্ছে…") : pick("Send verification email", "যাচাইয়ের ইমেইল পাঠান")}</button></div>}
      {!isAuthenticated && !confirmed && <p className="notice mb-6">{pick("To request an email, first", "ইমেইল পেতে আগে")} <Link className="font-medium underline" href="/login">{pick("log in", "লগইন করুন")}</Link>{pick(". You can confirm an existing token below.", "। আপনার কাছে থাকা টোকেন নিচে যাচাই করতে পারেন।")}</p>}
      {!confirmed && <form className="form-stack" onSubmit={confirm}><div className="field"><label htmlFor="verification-token">{pick("Verification token", "যাচাই টোকেন")}</label><input id="verification-token" name="token" required minLength={32} maxLength={128} autoComplete="off" spellCheck={false} value={token} onChange={(event) => setToken(event.target.value)} placeholder={pick("Paste the token from your email", "ইমেইল থেকে টোকেনটি দিন")} /><p className="text-xs leading-relaxed text-stone-400">{pick("Tokens expire after 24 hours and work only once.", "টোকেনের মেয়াদ ২৪ ঘণ্টা এবং এটি একবারই ব্যবহার করা যায়।")}</p></div><button className="button primary w-full" type="submit" disabled={pending !== null}>{pending === "confirm" ? pick("Verifying…", "যাচাই হচ্ছে…") : pick("Verify my email", "আমার ইমেইল যাচাই করুন")}</button></form>}
      {message && <p className="notice success mt-5" role="status">{message}</p>}
      {error && <p className="notice error mt-5" role="alert">{error}</p>}
      {debugToken && <div className="notice mt-5"><p className="text-xs font-semibold uppercase tracking-wide">{pick("Development token · local/test only", "ডেভেলপমেন্ট টোকেন · শুধু লোকাল/টেস্ট")}</p><code className="mt-2 block break-all text-xs">{debugToken}</code><button type="button" className="mt-3 text-xs font-medium underline" onClick={() => setToken(debugToken)}>{pick("Use this token", "এই টোকেন ব্যবহার করুন")}</button></div>}
      {confirmed && <Link className="button primary mt-6 w-full" href={isAuthenticated ? "/dashboard" : "/login"}>{isAuthenticated ? pick("Go to my dashboard", "ড্যাশবোর্ডে যান") : pick("Log in to continue", "এগিয়ে যেতে লগইন করুন")} <span aria-hidden="true">→</span></Link>}
    </AuthPanel>
  );
}
