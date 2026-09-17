"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CalendarClock, Trash2, Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ScheduledMessage, ServerChannel } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

type Mode = "interval" | "daily";

export default function GuildScheduled() {
  const params = useParams();
  const guildId = (params?.guildId as string) ?? "";
  const { t, locale } = useI18n();
  const [channels, setChannels] = useState<ServerChannel[]>([]);
  const [messages, setMessages] = useState<ScheduledMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [channelId, setChannelId] = useState("");
  const [content, setContent] = useState("");
  const [mode, setMode] = useState<Mode>("interval");
  const [intervalMin, setIntervalMin] = useState(60);
  const [dailyTime, setDailyTime] = useState("09:00");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(false);
    try {
      const [ch, msgs] = await Promise.all([
        api<{ channels: ServerChannel[] }>(`/api/guilds/${guildId}/channels`),
        api<ScheduledMessage[] | { messages: ScheduledMessage[] }>(`/api/guilds/${guildId}/scheduled`),
      ]);
      setChannels(ch.channels ?? []);
      setMessages(Array.isArray(msgs) ? msgs : (msgs?.messages ?? []));
    } catch (e) {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guildId]);

  const create = async () => {
    setFormError(null);
    if (!channelId || !content.trim()) {
      setFormError(t("common.error"));
      return;
    }
    setCreating(true);
    try {
      await api<{ ok: boolean; id: number }>(`/api/guilds/${guildId}/scheduled`, {
        method: "POST",
        body: JSON.stringify({
          channel_id: Number(channelId),
          content: content.trim(),
          interval_minutes: mode === "interval" ? intervalMin : null,
          daily_hhmm: mode === "daily" ? dailyTime : null,
        }),
      });
      await load();
      setChannelId("");
      setContent("");
      setIntervalMin(60);
      setDailyTime("09:00");
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : t("common.unknownError"));
    } finally {
      setCreating(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await api(`/api/guilds/${guildId}/scheduled/${id}`, { method: "DELETE" });
      setMessages((msgs) => msgs.filter((m) => m.id !== id));
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  const channelName = (id: string | number) =>
    channels.find((c) => c.id === String(id))?.name ?? String(id);

  if (loading) return <p className="text-gray-400">{t("common.loading")}</p>;
  if (error) return <p className="text-gray-400">{t("common.unknownError")}</p>;

  return (
    <div className="max-w-5xl space-y-8">
      <header>
        <h1 className="flex items-center gap-2 text-3xl font-bold text-white">
          <CalendarClock className="h-7 w-7 text-blurple" /> {t("scheduled.title")}
        </h1>
        <p className="mt-1 text-sm text-gray-400">{t("scheduled.subtitle")}</p>
      </header>

      {formError && (
        <div className="rounded-lg bg-wordlock-red/10 px-4 py-3 text-sm text-wordlock-red">
          {formError}
        </div>
      )}

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">{t("scheduled.newTitle")}</h2>
        <div className="space-y-4">
          <div>
            <label className="label">{t("scheduled.channel")}</label>
            <select
              className="input"
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
            >
              <option value="">—</option>
              {channels.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.type === 5 ? "📢 " : "# "}
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">{t("scheduled.content")}</label>
            <textarea
              className="input resize-none"
              rows={3}
              maxLength={1000}
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </div>
          <div>
            <label className="label">{t("scheduled.mode")}</label>
            <div className="flex gap-2">
              <button
                onClick={() => setMode("interval")}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                  mode === "interval"
                    ? "bg-blurple/20 text-blurple"
                    : "bg-white/5 text-gray-300 hover:bg-white/10"
                }`}
              >
                {t("scheduled.modeInterval")}
              </button>
              <button
                onClick={() => setMode("daily")}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                  mode === "daily"
                    ? "bg-blurple/20 text-blurple"
                    : "bg-white/5 text-gray-300 hover:bg-white/10"
                }`}
              >
                {t("scheduled.modeDaily")}
              </button>
            </div>
            {mode === "interval" ? (
              <input
                className="input mt-3"
                type="number"
                min={1}
                max={10080}
                value={intervalMin}
                onChange={(e) => setIntervalMin(Number(e.target.value))}
              />
            ) : (
              <input
                className="input mt-3"
                type="time"
                value={dailyTime}
                onChange={(e) => setDailyTime(e.target.value)}
              />
            )}
          </div>
          <div className="flex justify-end">
            <button onClick={create} disabled={creating} className="btn-primary">
              <Plus className="h-4 w-4" />
              {creating ? t("common.saving") : t("scheduled.create")}
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">
          {t("scheduled.title")} ({messages.length})
        </h2>
        {messages.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-500">{t("scheduled.empty")}</p>
        ) : (
          <ul className="space-y-3">
            {messages.map((m) => (
              <li
                key={m.id}
                className="flex items-start gap-3 rounded-lg bg-white/5 px-4 py-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-sm text-gray-200">{m.content}</p>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                    <span>
                      <span className="text-gray-400">#</span>
                      {channelName(m.channel_id)}
                    </span>
                    <span>
                      {m.interval_minutes != null
                        ? t("scheduled.everyMin", { n: m.interval_minutes })
                        : m.daily_hhmm
                          ? t("scheduled.dailyAt", { time: m.daily_hhmm })
                          : "—"}
                    </span>
                    <span>{t("scheduled.createdAt", { date: new Date(m.created_at).toLocaleString(locale) })}</span>
                  </div>
                </div>
                <button
                  onClick={() => remove(m.id)}
                  className="rounded-lg p-2 text-gray-500 transition hover:bg-wordlock-red/10 hover:text-wordlock-red"
                  aria-label={t("scheduled.delete")}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
