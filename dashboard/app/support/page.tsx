"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Shield, Send, CheckCircle, AlertCircle, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const TURNSTILE_SITE_KEY = "0x4AAAAAAEdA6qihu5DI9s0e";

declare global {
  interface Window {
    turnstile?: {
      render: (container: string | HTMLElement, options: Record<string, unknown>) => string;
      reset: (widgetId: string) => void;
      getResponse: (widgetId: string) => string | null;
    };
  }
}

export default function SupportPage() {
  const { t } = useI18n();
  const [formData, setFormData] = useState({
    type: "contact",
    subject: "",
    message: "",
    sender_name: "",
    sender_email: "",
    sender_id: "",
    guild_id: "",
  });
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turnstileWidget, setTurnstileWidget] = useState<string | null>(null);

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.onload = () => {
      if (window.turnstile) {
        const widget = window.turnstile.render("#turnstile-container", {
          sitekey: TURNSTILE_SITE_KEY,
          theme: "dark",
          size: "invisible",
        });
        setTurnstileWidget(widget);
      }
    };
    document.head.appendChild(script);
    return () => {
      document.head.removeChild(script);
    };
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.subject.trim() || !formData.message.trim() || !formData.sender_name.trim() || !formData.sender_email.trim()) {
      setError(t("support.errorRequired"));
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.sender_email)) {
      setError(t("support.errorEmail"));
      return;
    }

    setSending(true);
    try {
      let turnstileToken = "";
      if (window.turnstile && turnstileWidget) {
        turnstileToken = window.turnstile.getResponse(turnstileWidget) || "";
      }
      await api("/api/tickets", {
        method: "POST",
        body: JSON.stringify({
          ...formData,
          sender_id: formData.sender_id || undefined,
          guild_id: formData.guild_id || undefined,
          turnstile_token: turnstileToken,
        }),
      });
      setSent(true);
    } catch (e) {
      setError((e as Error).message || t("support.errorGeneric"));
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-discord-darker via-discord to-blurple/20">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center gap-2 text-xl font-bold text-white">
          <Shield className="h-7 w-7 text-blurple" />
          WordLock
        </Link>
        <Link href="/" className="text-sm text-blurple transition-colors hover:text-blurple/80">
          ← {t("support.back")}
        </Link>
      </nav>

      <section className="mx-auto max-w-2xl px-6 pb-24 pt-8">
        <div className="mb-8 text-center">
          <MessageSquare className="mx-auto h-10 w-10 text-blurple" />
          <h1 className="mt-4 text-3xl font-bold text-white">{t("support.title")}</h1>
          <p className="mt-2 text-sm text-gray-400">{t("support.subtitle")}</p>
        </div>

        {sent ? (
          <div className="card text-center">
            <CheckCircle className="mx-auto h-12 w-12 text-wordlock-green" />
            <h2 className="mt-4 text-xl font-semibold text-white">{t("support.successTitle")}</h2>
            <p className="mt-2 text-sm text-gray-400">{t("support.successText")}</p>
            <Link href="/" className="btn-primary mt-6 inline-flex">
              {t("support.backHome")}
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="card space-y-5">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("support.type")}</label>
              <select name="type" value={formData.type} onChange={handleChange} className="input">
                <option value="contact">{t("support.typeContact")}</option>
                <option value="bug">{t("support.typeBug")}</option>
                <option value="feature">{t("support.typeFeature")}</option>
                <option value="support">{t("support.typeSupport")}</option>
              </select>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("support.name")} *</label>
                <input name="sender_name" value={formData.sender_name} onChange={handleChange} className="input" placeholder={t("support.namePlaceholder")} />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("support.email")} *</label>
                <input name="sender_email" type="email" value={formData.sender_email} onChange={handleChange} className="input" placeholder={t("support.emailPlaceholder")} />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("support.discordId")}</label>
                <input name="sender_id" value={formData.sender_id} onChange={handleChange} className="input" placeholder={t("support.discordIdPlaceholder")} />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("support.serverId")}</label>
                <input name="guild_id" value={formData.guild_id} onChange={handleChange} className="input" placeholder={t("support.serverIdPlaceholder")} />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("support.subject")} *</label>
              <input name="subject" value={formData.subject} onChange={handleChange} className="input" placeholder={t("support.subjectPlaceholder")} />
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("support.message")} *</label>
              <textarea name="message" value={formData.message} onChange={handleChange} rows={6} className="input resize-none" placeholder={t("support.messagePlaceholder")} />
            </div>

            <div id="turnstile-container" className="hidden" />

            {error && (
              <div className="flex items-center gap-2 rounded-lg bg-wordlock-red/10 px-4 py-3 text-sm text-wordlock-red">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}

            <button type="submit" disabled={sending} className="btn-primary w-full justify-center">
              {sending ? (
                <span className="flex items-center gap-2"><span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> {t("support.sending")}</span>
              ) : (
                <span className="flex items-center gap-2"><Send className="h-4 w-4" /> {t("support.submit")}</span>
              )}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
