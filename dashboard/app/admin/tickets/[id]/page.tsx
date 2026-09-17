"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { ArrowLeft, Send, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Ticket } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-wordlock-yellow/15 text-wordlock-yellow",
  in_progress: "bg-blurple/15 text-blurple",
  answered: "bg-wordlock-green/15 text-wordlock-green",
  closed: "bg-gray-500/15 text-gray-400",
};

interface TicketMessage {
  id: number;
  author_type: string;
  author_name: string | null;
  content: string;
  created_at: string;
}

export default function TicketDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t } = useI18n();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [messages, setMessages] = useState<TicketMessage[]>([]);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    api<{ ticket: Ticket; messages: TicketMessage[] }>(`/api/admin/tickets/${id}`)
      .then((res) => {
        setTicket(res.ticket);
        setMessages(res.messages);
      })
      .catch(() => {});
  }, [id]);

  const handleStatusChange = async (status: string) => {
    setUpdating(true);
    try {
      await api(`/api/admin/tickets/${id}`, { method: "PUT", body: JSON.stringify({ status }) });
      setTicket((prev) => (prev ? { ...prev, status } : prev));
    } catch {}
    setUpdating(false);
  };

  const handleAssign = async (assigned_to: string) => {
    setUpdating(true);
    try {
      await api(`/api/admin/tickets/${id}`, { method: "PUT", body: JSON.stringify({ assigned_to }) });
      setTicket((prev) => (prev ? { ...prev, assigned_to } : prev));
    } catch {}
    setUpdating(false);
  };

  const handleReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reply.trim()) return;
    setSending(true);
    try {
      await api(`/api/admin/tickets/${id}/reply`, { method: "POST", body: JSON.stringify({ reply }) });
      const res = await api<{ ticket: Ticket; messages: TicketMessage[] }>(`/api/admin/tickets/${id}`);
      setTicket(res.ticket);
      setMessages(res.messages);
      setReply("");
    } catch {}
    setSending(false);
  };

  const handleDelete = async () => {
    if (!confirm(t("adTicket.deleteConfirm"))) return;
    try {
      await api(`/api/admin/tickets/${id}`, { method: "DELETE" });
      window.location.href = "/admin/tickets";
    } catch {}
  };

  const formatDate = (d: string) => new Date(d).toLocaleString("de-DE");

  if (!ticket) {
    return <div className="py-20 text-center text-gray-500">{t("adTicket.loading")}</div>;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/admin/tickets" className="mb-6 inline-flex items-center gap-2 text-sm text-blurple hover:text-blurple/80">
        <ArrowLeft className="h-4 w-4" /> {t("adTicket.backToList")}
      </Link>

      <div className="card mb-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[ticket.status] || ""}`}>
                {ticket.status}
              </span>
              <span className="rounded-full bg-blurple/15 px-2.5 py-0.5 text-xs font-medium text-blurple">
                {ticket.type}
              </span>
            </div>
            <h1 className="mt-3 text-xl font-bold text-white">{ticket.subject}</h1>
            <p className="mt-1 text-xs text-gray-500">
              {ticket.sender_name} ({ticket.sender_email}) • {formatDate(ticket.created_at)}
            </p>
            {ticket.sender_id && <p className="text-xs text-gray-500">Discord ID: {ticket.sender_id}</p>}
            {ticket.guild_id && <p className="text-xs text-gray-500">Server: {ticket.guild_id}</p>}
          </div>
          <button onClick={handleDelete} className="rounded-lg p-2 text-gray-500 transition hover:bg-wordlock-red/10 hover:text-wordlock-red">
            <Trash2 className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-4 rounded-lg bg-discord-darker/50 p-4 text-sm text-gray-300 whitespace-pre-wrap">
          {ticket.message}
        </div>
      </div>

      <div className="card mb-6 space-y-4">
        <h2 className="text-sm font-semibold text-white">{t("adTicket.management")}</h2>

        <div className="flex gap-3">
          <div>
            <label className="mb-1 block text-xs text-gray-400">{t("adTicket.status")}</label>
            <select
              value={ticket.status}
              onChange={(e) => handleStatusChange(e.target.value)}
              disabled={updating}
              className="input text-sm"
            >
              <option value="open">{t("adTicket.statusOpen")}</option>
              <option value="in_progress">{t("adTicket.statusInProgress")}</option>
              <option value="answered">{t("adTicket.statusAnswered")}</option>
              <option value="closed">{t("adTicket.statusClosed")}</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="mb-1 block text-xs text-gray-400">{t("adTicket.assignTo")}</label>
            <input
              value={ticket.assigned_to || ""}
              onChange={(e) => handleAssign(e.target.value)}
              placeholder={t("adTicket.assignPlaceholder")}
              className="input text-sm"
            />
          </div>
        </div>
      </div>

      <div className="card mb-6 space-y-3">
        <h2 className="text-sm font-semibold text-white">{t("webticket.threadTitle")}</h2>
        <div
          className={`rounded-xl px-4 py-3 ${"rounded-tl-sm bg-discord-darker/60"}`}
        >
          <div className="mb-1 flex items-center gap-2 text-xs font-medium text-wordlock-green">
            {ticket.sender_name}
            <span className="font-normal text-gray-500">{formatDate(ticket.created_at)}</span>
          </div>
          <p className="text-sm text-gray-200 whitespace-pre-wrap">{ticket.message}</p>
        </div>
        {messages.map((m) => (
          <div key={m.id} className={`rounded-xl px-4 py-3 ${m.author_type === "admin" ? "bg-blurple/20 rounded-tl-sm" : "bg-discord-darker/60"}`}>
            <div className={`mb-1 flex items-center gap-2 text-xs font-medium ${m.author_type === "admin" ? "text-blurple" : "text-wordlock-green"}`}>
              {m.author_type === "admin" ? `${t("webticket.support")}${m.author_name ? `・${m.author_name}` : ""}` : m.author_name || ticket.sender_name}
              <span className="font-normal text-gray-500">{formatDate(m.created_at)}</span>
            </div>
            <p className="text-sm text-gray-200 whitespace-pre-wrap">{m.content}</p>
          </div>
        ))}
        {ticket.admin_reply && (
          <p className="pt-1 text-right text-[11px] text-gray-500">{t("adTicket.repliedAt")}: {formatDate(ticket.replied_at || ticket.updated_at)}</p>
        )}
      </div>

      <form onSubmit={handleReply} className="card">
        <h2 className="mb-3 text-sm font-semibold text-white">{t("adTicket.replyTitle")}</h2>
        <textarea
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          rows={4}
          className="input mb-3 resize-none"
          placeholder={t("adTicket.replyPlaceholder")}
        />
        <button type="submit" disabled={sending || !reply.trim()} className="btn-primary">
          {sending ? (
            <span className="flex items-center gap-2"><span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> {t("adTicket.sending")}</span>
          ) : (
            <span className="flex items-center gap-2"><Send className="h-4 w-4" /> {t("adTicket.replySend")}</span>
          )}
        </button>
      </form>
    </div>
  );
}
