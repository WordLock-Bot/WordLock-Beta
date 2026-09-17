"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MessageSquare, Filter, Search, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Ticket } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-wordlock-yellow/15 text-wordlock-yellow",
  in_progress: "bg-blurple/15 text-blurple",
  answered: "bg-wordlock-green/15 text-wordlock-green",
  closed: "bg-gray-500/15 text-gray-400",
};

const TYPE_COLORS: Record<string, string> = {
  contact: "bg-blurple/15 text-blurple",
  bug: "bg-wordlock-red/15 text-wordlock-red",
  feature: "bg-wordlock-green/15 text-wordlock-green",
  support: "bg-wordlock-yellow/15 text-wordlock-yellow",
};

export default function AdminTicketsPage() {
  const { t } = useI18n();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [search, setSearch] = useState("");

  const load = () => {
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    if (typeFilter) params.set("type", typeFilter);
    if (search) params.set("search", search);
    api<{ tickets: Ticket[] } | Ticket[]>(`/api/admin/tickets?${params}`)
      .then((r) => {
        const list = Array.isArray(r) ? r : (r.tickets ?? []);
        setTickets(Array.isArray(list) ? list : []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [statusFilter, typeFilter]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load();
  };

  const formatDate = (d: string) => {
    if (!d) return "—";
    return new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <MessageSquare className="h-6 w-6 text-blurple" />
        <div>
          <h1 className="text-2xl font-bold text-white">{t("adTicket.title")}</h1>
          <p className="text-sm text-gray-400">{t("adTicket.subtitle", { n: String(tickets.length) })}</p>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap gap-3">
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("adTicket.searchPlaceholder")}
            className="input w-64"
          />
          <button type="submit" className="btn-secondary">
            <Search className="h-4 w-4" />
          </button>
        </form>

        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input">
          <option value="">{t("adTicket.filterAllStatus")}</option>
          <option value="open">{t("adTicket.statusOpen")}</option>
          <option value="in_progress">{t("adTicket.statusInProgress")}</option>
          <option value="answered">{t("adTicket.statusAnswered")}</option>
          <option value="closed">{t("adTicket.statusClosed")}</option>
        </select>

        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="input">
          <option value="">{t("adTicket.filterAllType")}</option>
          <option value="contact">{t("adTicket.typeContact")}</option>
          <option value="bug">{t("adTicket.typeBug")}</option>
          <option value="feature">{t("adTicket.typeFeature")}</option>
          <option value="support">{t("adTicket.typeSupport")}</option>
        </select>
      </div>

      {loading ? (
        <div className="py-20 text-center text-gray-500">{t("adTicket.loading")}</div>
      ) : tickets.length === 0 ? (
        <div className="py-20 text-center text-gray-500">{t("adTicket.noTickets")}</div>
      ) : (
        <div className="space-y-2">
          {tickets.map((ticket) => (
            <Link
              key={ticket.id}
              href={`/admin/tickets/${ticket.id}`}
              className="card flex items-center justify-between gap-4 transition hover:border-blurple/40"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[ticket.status] || "bg-gray-500/15 text-gray-400"}`}>
                    {t(`adTicket.status${ticket.status.charAt(0).toUpperCase() + ticket.status.slice(1).replace("_", "")}`)}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[ticket.type] || "bg-gray-500/15 text-gray-400"}`}>
                    {t(`adTicket.type${ticket.type.charAt(0).toUpperCase() + ticket.type.slice(1)}`)}
                  </span>
                  {ticket.assigned_to && (
                    <span className="text-xs text-gray-500">{ticket.assigned_to}</span>
                  )}
                </div>
                <h3 className="mt-1 truncate text-sm font-medium text-white">{ticket.subject}</h3>
                <p className="mt-0.5 text-xs text-gray-500">
                  {ticket.sender_name} • {formatDate(ticket.created_at)}
                </p>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-gray-500" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
