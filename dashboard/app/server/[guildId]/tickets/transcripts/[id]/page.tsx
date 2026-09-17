"use client";

import { useEffect, useState, use } from "react";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import type { TicketTranscript } from "@/lib/types";

export default function TranscriptViewer({ params }: { params: Promise<{ guildId: string; id: string }> }) {
  const { guildId, id } = use(params);
  const [data, setData] = useState<TicketTranscript | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<TicketTranscript>(`/api/server/${guildId}/tickets/transcripts/${id}`)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [guildId, id]);

  if (loading) return <div className="py-20 text-center text-gray-500">Lade Transkript…</div>;
  if (error || !data) return (
    <div className="py-20 text-center">
      <p className="text-gray-400">Transkript nicht gefunden oder kein Zugriff.</p>
      <a href={`/server/${guildId}/tickets`} className="btn-primary mt-4 inline-flex">
        <ArrowLeft className="h-4 w-4" /> Zurück zu Tickets
      </a>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#1e1f22]">
      <div className="mx-auto max-w-3xl px-4 pt-6">
        <a href={`/server/${guildId}/tickets`} className="inline-flex items-center gap-2 text-sm text-blurple hover:text-blurple/80">
          <ArrowLeft className="h-4 w-4" /> Zurück zu Tickets
        </a>
        <h1 className="mt-4 text-xl font-bold text-white">Ticket-Transkript</h1>
        <p className="mt-1 text-xs text-gray-500">
          Ticket #{data.ticket_id ?? "?"} • Erstellt am {new Date(data.created_at).toLocaleString("de-DE")}
        </p>
      </div>
      <div className="mx-auto max-w-3xl px-4 py-6">
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-discord shadow-2xl" dangerouslySetInnerHTML={{ __html: data.html }} />
      </div>
    </div>
  );
}
