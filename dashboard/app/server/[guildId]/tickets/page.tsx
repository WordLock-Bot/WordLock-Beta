"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { Ticket, ArrowLeft, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import type { DiscordTicket } from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  open: "bg-wordlock-yellow/15 text-wordlock-yellow",
  claimed: "bg-blurple/15 text-blurple",
  closed: "bg-gray-500/15 text-gray-400",
};

export default function ServerTicketsPage({ params }: { params: Promise<{ guildId: string }> }) {
  const { guildId } = use(params);
  const router = useRouter();
  const [tickets, setTickets] = useState<DiscordTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<{ tickets: DiscordTicket[] }>(`/api/server/${guildId}/tickets`)
      .then((r) => setTickets(r.tickets))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [guildId]);

  const fmt = (d: string) =>
    new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

  if (loading) return <div className="py-20 text-center text-gray-500">Lade Tickets…</div>;
  if (error) return (
    <div className="py-20 text-center">
      <p className="text-gray-400">Kein Zugriff oder Server nicht gefunden.</p>
      <button onClick={() => router.push("/dashboard")} className="btn-primary mt-4">
        <ArrowLeft className="h-4 w-4" /> Zurück zum Dashboard
      </button>
    </div>
  );

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6">
        <button onClick={() => router.back()} className="mb-4 inline-flex items-center gap-2 text-sm text-blurple hover:text-blurple/80">
          <ArrowLeft className="h-4 w-4" /> Zurück
        </button>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Ticket className="h-6 w-6 text-blurple" />
            <div>
              <h1 className="text-2xl font-bold text-white">Tickets</h1>
              <p className="text-sm text-gray-400">{tickets.length} Tickets auf diesem Server</p>
            </div>
          </div>
          <Link href={`/dashboard/${guildId}/tickets`} className="inline-flex items-center gap-2 text-sm text-blurple hover:text-blurple/80">
            <ExternalLink className="h-4 w-4" /> Panel einrichten
          </Link>
        </div>
      </div>

      {tickets.length === 0 ? (
        <div className="card py-12 text-center text-gray-500">Noch keine Tickets erstellt.</div>
      ) : (
        <div className="space-y-2">
          {tickets.map((t) => (
            <div key={t.id} className="card flex items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">#{t.id}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[t.status] || ""}`}>
                    {t.status === "open" ? "Offen" : t.status === "claimed" ? "In Bearbeitung" : "Geschlossen"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-500">Erstellt: {fmt(t.created_at)}</p>
                <p className="text-xs text-gray-500">Ersteller: {t.creator_id}</p>
              </div>
              {t.transcript_id && (
                <a
                  href={`/server/${guildId}/tickets/transcripts/${t.transcript_id}`}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-blurple/10 px-3 py-1.5 text-xs font-medium text-blurple hover:bg-blurple/20"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Transkript
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
