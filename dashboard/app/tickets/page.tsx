"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Shield,
  ArrowLeft,
  Ticket,
  Plus,
  Send,
  AlertCircle,
  CheckCircle,
  LogIn,
} from "lucide-react";
import { api, loginUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-wordlock-yellow/15 text-wordlock-yellow",
  in_progress: "bg-blurple/15 text-blurple",
  answered: "bg-wordlock-green/15 text-wordlock-green",
  closed: "bg-gray-500/15 text-gray-400",
};

interface Ticket {
  id: number;
  type: string;
  subject: string;
  message: string;
  status: string;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
}

interface TicketMessage {
  id: number;
  author_type: string;
  author_name: string | null;
  content: string;
  created_at: string;
}

const STATUS_LABELS: Record<string, string> = {
  open: "webticket.statusOpen",
  in_progress: "webticket.statusInProgress",
  answered: "webticket.statusAnswered",
  closed: "webticket.statusClosed",
};

const TYPE_LABELS: Record<string, string> = {
  contact: "webticket.typeContact",
  bug: "webticket.typeBug",
  feature: "webticket.typeFeature",
  support: "webticket.typeSupport",
};

export default function TicketsPage() {
  const { t } = useI18n();
  const [user, setUser] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState("");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [messages, setMessages] = useState<TicketMessage[]>([]);
  const [creating, setCreating] = useState(false);
  const [sendingReply, setSendingReply] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ type: "support", subject: "", message: "" });
  const [newReply, setNewReply] = useState("");

  const loadTickets = async () => {
    try {
      const res = await api<{ tickets: Ticket[] }>("/api/me/tickets");
      setTickets(res.tickets);
    } catch (e) {
      setError((e as Error).message || t("webticket.errorGeneric"));
    }
  };

  useEffect(() => {
    (async () => {
      loginUrl().then(setUrl).catch(() => setUrl(""));
      try {
        const me = await api<any>("/api/auth/me");
        setUser(me);
        await loadTickets();
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const loadThread = async (ticket: Ticket) => {
    setSelected(ticket);
    setMessages([]);
    setNewReply("");
    setError(null);
    try {
      const res = await api<{ ticket: Ticket; messages: TicketMessage[] }>(
        `/api/me/tickets/${ticket.id}`,
      );
      setSelected(res.ticket);
      setMessages(res.messages);
    } catch (e) {
      setError((e as Error).message || t("webticket.errorGeneric"));
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.subject.trim() || !form.message.trim()) {
      setError(t("webticket.errorRequired"));
      return;
    }
    setCreating(true);
    try {
      await api(`/api/me/tickets`, {
        method: "POST",
        body: JSON.stringify({ type: form.type, subject: form.subject, message: form.message }),
      });
      setShowCreate(false);
      setForm({ type: "support", subject: "", message: "" });
      await loadTickets();
    } catch (e) {
      setError((e as Error).message || t("webticket.errorGeneric"));
    } finally {
      setCreating(false);
    }
  };

  const handleReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !newReply.trim()) return;
    setSendingReply(true);
    setError(null);
    try {
      await api(`/api/me/tickets/${selected.id}/reply`, {
        method: "POST",
        body: JSON.stringify({ content: newReply }),
      });
      await loadThread(selected);
    } catch (e) {
      setError((e as Error).message || t("webticket.errorGeneric"));
    } finally {
      setSendingReply(false);
    }
  };

  const handleClose = async () => {
    if (!selected || !confirm(t("webticket.closeConfirm"))) return;
    setClosing(true);
    try {
      await api(`/api/me/tickets/${selected.id}/close`, { method: "POST" });
      await loadThread(selected);
      await loadTickets();
    } catch {
      /* ignore */
    }
    setClosing(false);
  };

  const formatDate = (d: string) => new Date(d).toLocaleString();

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-discord-darker via-discord to-blurple/20">
        <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
          <Link href="/" className="flex items-center gap-2 text-xl font-bold text-white">
            <Shield className="h-7 w-7 text-blurple" /> WordLock
          </Link>
        </nav>
        <div className="flex justify-center py-24 text-gray-500">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-blurple border-t-transparent" />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-discord-darker via-discord to-blurple/20">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center gap-2 text-xl font-bold text-white">
          <Shield className="h-7 w-7 text-blurple" /> WordLock
        </Link>
        <Link href="/" className="text-sm text-blurple transition-colors hover:text-blurple/80">
          ← Zurück
        </Link>
      </nav>

      <section className="mx-auto max-w-3xl px-6 pb-24 pt-8">
        <div className="mb-8 text-center">
          <Ticket className="mx-auto h-10 w-10 text-blurple" />
          <h1 className="mt-4 text-3xl font-bold text-white">{t("webticket.title")}</h1>
          <p className="mt-2 text-sm text-gray-400">{t("webticket.subtitle")}</p>
        </div>

        {!user ? (
          <div className="card py-16 text-center">
            <LogIn className="mx-auto h-10 w-10 text-blurple" />
            <p className="mt-4 text-sm text-gray-400">{t("webticket.loginRequired")}</p>
            {url ? (
              <a href={url} className="btn-primary mt-6 inline-flex">
                {t("webticket.login")}
              </a>
            ) : (
              <p className="mt-6 text-xs text-gray-500">…</p>
            )}
          </div>
        ) : selected ? (
          <>
            <button
              onClick={() => setSelected(null)}
              className="mb-6 inline-flex items-center gap-2 text-sm text-blurple hover:text-blurple/80"
            >
              <ArrowLeft className="h-4 w-4" /> {t("webticket.back")}
            </button>

            <div className="card mb-6">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[selected.status] || ""}`}>
                      {t(STATUS_LABELS[selected.status] || "webticket.statusOpen")}
                    </span>
                    <span className="rounded-full bg-blurple/15 px-2.5 py-0.5 text-xs font-medium text-blurple">
                      {t(TYPE_LABELS[selected.type] || "webticket.typeSupport")}
                    </span>
                  </div>
                  <h2 className="mt-3 text-xl font-bold text-white">{selected.subject}</h2>
                  <p className="mt-1 text-xs text-gray-500">
                    {t("webticket.created")}: {formatDate(selected.created_at)}
                  </p>
                </div>
                {selected.status !== "closed" && (
                  <button
                    onClick={handleClose}
                    disabled={closing}
                    className="rounded-lg bg-wordlock-red/10 px-3 py-1.5 text-xs font-medium text-wordlock-red transition hover:bg-wordlock-red/20"
                  >
                    {t("webticket.closeTicket")}
                  </button>
                )}
              </div>
            </div>

            <div className="card mb-6 space-y-4">
              <h2 className="text-sm font-semibold text-white">{t("webticket.threadTitle")}</h2>
              <div className="space-y-3">
                <MessageBubble
                  byTeam={false}
                  author={`${t("webticket.you")}・${t(TYPE_LABELS[selected.type] || "")}`}
                  content={selected.message}
                  time={formatDate(selected.created_at)}
                />
                {messages.map((m) => (
                  <MessageBubble
                    key={m.id}
                    byTeam={m.author_type === "admin"}
                    author={
                      m.author_type === "admin"
                        ? `${t("webticket.support")}${m.author_name ? `・${m.author_name}` : ""}`
                        : t("webticket.you")
                    }
                    content={m.content}
                    time={formatDate(m.created_at)}
                  />
                ))}
              </div>
            </div>

            {selected.status !== "closed" && (
              <form onSubmit={handleReply} className="card">
                <h2 className="mb-3 text-sm font-semibold text-white">{t("webticket.threadTitle")}</h2>
                <textarea
                  value={newReply}
                  onChange={(e) => setNewReply(e.target.value)}
                  rows={3}
                  className="input mb-3 resize-none"
                  placeholder={t("webticket.replyPlaceholder")}
                />
                <button type="submit" disabled={sendingReply || !newReply.trim()} className="btn-primary">
                  {sendingReply ? (
                    <span className="flex items-center gap-2">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      {t("adTicket.sending")}
                    </span>
                  ) : (
                    <span className="flex items-center gap-2"><Send className="h-4 w-4" /> {t("webticket.sendReply")}</span>
                  )}
                </button>
              </form>
            )}
          </>
        ) : (
          <>
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">{t("webticket.listTitle")}</h2>
              <button
                onClick={() => setShowCreate((v) => !v)}
                className="btn-primary inline-flex items-center gap-2"
              >
                <Plus className="h-4 w-4" /> {t("webticket.createNew")}
              </button>
            </div>

            {showCreate && (
              <form onSubmit={handleCreate} className="card mb-6 space-y-4">
                <h2 className="text-sm font-semibold text-white">{t("webticket.newTitle")}</h2>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("webticket.type")}</label>
                  <select
                    value={form.type}
                    onChange={(e) => setForm((p) => ({ ...p, type: e.target.value }))}
                    className="input"
                  >
                    <option value="support">{t("webticket.typeSupport")}</option>
                    <option value="contact">{t("webticket.typeContact")}</option>
                    <option value="bug">{t("webticket.typeBug")}</option>
                    <option value="feature">{t("webticket.typeFeature")}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("webticket.subject")} *</label>
                  <input
                    value={form.subject}
                    onChange={(e) => setForm((p) => ({ ...p, subject: e.target.value }))}
                    className="input"
                    placeholder={t("webticket.subjectPlaceholder")}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-300">{t("webticket.message")} *</label>
                  <textarea
                    value={form.message}
                    onChange={(e) => setForm((p) => ({ ...p, message: e.target.value }))}
                    rows={4}
                    className="input resize-none"
                    placeholder={t("webticket.messagePlaceholder")}
                  />
                </div>
                {error && (
                  <div className="flex items-center gap-2 rounded-lg bg-wordlock-red/10 px-4 py-3 text-sm text-wordlock-red">
                    <AlertCircle className="h-4 w-4 shrink-0" /> {error}
                  </div>
                )}
                <button type="submit" disabled={creating} className="btn-primary">
                  {creating ? (
                    <span className="flex items-center gap-2">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      {t("adTicket.sending")}
                    </span>
                  ) : (
                    <span className="flex items-center gap-2"><CheckCircle className="h-4 w-4" /> {t("webticket.create")}</span>
                  )}
                </button>
              </form>
            )}

            {error && !selected && (
              <div className="mb-4 flex items-center gap-2 rounded-lg bg-wordlock-red/10 px-4 py-3 text-sm text-wordlock-red">
                <AlertCircle className="h-4 w-4 shrink-0" /> {error}
              </div>
            )}

            {tickets.length === 0 ? (
              <div className="card py-12 text-center text-sm text-gray-500">{t("webticket.noTickets")}</div>
            ) : (
              <div className="space-y-3">
                {tickets.map((ticket) => (
                  <button
                    key={ticket.id}
                    onClick={() => loadThread(ticket)}
                    className="card w-full text-left transition hover:border-blurple/40"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="truncate font-medium text-white">#{ticket.id} · {ticket.subject}</span>
                        </div>
                        <p className="mt-1 text-xs text-gray-500">
                          {t(TYPE_LABELS[ticket.type] || "")} · {formatDate(ticket.created_at)}
                        </p>
                      </div>
                      <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[ticket.status] || ""}`}>
                        {t(STATUS_LABELS[ticket.status] || "webticket.statusOpen")}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function MessageBubble({
  byTeam,
  author,
  content,
  time,
}: {
  byTeam: boolean;
  author: string;
  content: string;
  time: string;
}) {
  return (
    <div className={`flex ${byTeam ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[85%] rounded-xl px-4 py-3 ${
          byTeam ? "rounded-tl-sm bg-discord-darker/60" : "rounded-tr-sm bg-blurple/20"
        }`}
      >
        <div className={`mb-1 flex items-center gap-2 text-xs font-medium ${byTeam ? "text-blurple" : "text-wordlock-green"}`}>
          {author}
          <span className="font-normal text-gray-500">{time}</span>
        </div>
        <p className="text-sm text-gray-200 whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  );
}
