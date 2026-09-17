"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Users, UserPlus, Trash2, ShieldCheck, Eye, Copy, Check } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface PanelMember {
  discord_id: string;
  username: string | null;
  role: "moderator" | "viewer";
  invited_by: string;
  created_at: string;
  pending: boolean;
}

interface PanelResponse {
  members: PanelMember[];
  inviter_id: string | null;
}

export default function GuildPanel() {
  const params = useParams();
  const guildId = (params?.guildId as string) ?? "";
  const { t } = useI18n();
  const [data, setData] = useState<PanelResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [meId, setMeId] = useState<string | null>(null);

  const [discordId, setDiscordId] = useState("");
  const [role, setRole] = useState<"moderator" | "viewer">("moderator");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [msgErr, setMsgErr] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(false);
    api<PanelResponse>(`/api/guilds/${guildId}/panel-members`)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    api<{ id: string }>("/api/auth/me").then((me) => setMeId(me.id)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guildId]);

  const submit = async () => {
    if (!discordId.trim()) return;
    setBusy(true);
    setMsg(null);
    setMsgErr(null);
    try {
      await api(`/api/guilds/${guildId}/panel-members`, {
        method: "POST",
        body: JSON.stringify({ discord_id: discordId.trim(), role }),
      });
      setMsg(t("panel.inviteSuccess"));
      setDiscordId("");
      load();
    } catch (e) {
      setMsgErr(e instanceof ApiError ? e.message : t("common.unknownError"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm(t("panel.removeConfirm"))) return;
    try {
      await api(`/api/guilds/${guildId}/panel-members/${id}`, { method: "DELETE" });
      load();
    } catch {
      /* keep state */
    }
  };

  const copyId = (id: string) => {
    navigator.clipboard?.writeText(id).catch(() => {});
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const isInviter = meId != null && data?.inviter_id === meId;

  if (loading) return <p className="text-gray-400">{t("common.loading")}</p>;
  if (error || !data)
    return <p className="text-gray-400">{t("common.unknownError")}</p>;

  const fmt = (d: string) =>
    new Date(d).toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });

  return (
    <div className="max-w-5xl space-y-8">
      <header>
        <h1 className="flex items-center gap-2 text-3xl font-bold text-white">
          <Users className="h-7 w-7 text-blurple" /> {t("panel.title")}
        </h1>
        <p className="mt-1 text-sm text-gray-400">{t("panel.subtitle")}</p>
      </header>

      {msg && (
        <div className="rounded-lg bg-wordlock-green/10 px-4 py-3 text-sm text-wordlock-green">
          {msg}
        </div>
      )}
      {msgErr && (
        <div className="rounded-lg bg-wordlock-red/10 px-4 py-3 text-sm text-wordlock-red">
          {msgErr}
        </div>
      )}

      {isInviter ? (
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">
            <UserPlus className="mr-2 inline h-5 w-5 text-blurple" />
            {t("panel.inviteTitle")}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">{t("panel.discordId")}</label>
              <input
                className="input"
                placeholder={t("panel.discordIdPlaceholder")}
                value={discordId}
                onChange={(e) => setDiscordId(e.target.value)}
              />
            </div>
            <div>
              <label className="label">{t("panel.role")}</label>
              <select
                className="input"
                value={role}
                onChange={(e) => setRole(e.target.value as "moderator" | "viewer")}
              >
                <option value="moderator">{t("panel.role.moderator")}</option>
                <option value="viewer">{t("panel.role.viewer")}</option>
              </select>
              <p className="mt-1 text-xs text-gray-500">
                {role === "moderator" ? t("panel.roleModHelp") : t("panel.roleViewHelp")}
              </p>
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <button onClick={submit} disabled={busy || !discordId.trim()} className="btn-primary">
              <UserPlus className="h-4 w-4" />
              {t("panel.inviteBtn")}
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-lg bg-white/5 px-4 py-3 text-sm text-gray-400">
          {t("panel.onlyManaged")}
        </div>
      )}

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">
          {data.members.length}
        </h2>
        {data.members.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-500">{t("panel.empty")}</p>
        ) : (
          <ul className="space-y-2">
            <li className="flex items-center gap-3 rounded-lg bg-white/5 px-4 py-3">
              <ShieldCheck className="h-5 w-5 text-wordlock-yellow" />
              <span className="text-sm font-medium text-white">
                {t("panel.owner")} {meId === data.inviter_id && `(${t("panel.yourself")})`}
              </span>
              <span className="ml-auto rounded-full bg-wordlock-yellow/15 px-2 py-0.5 text-xs font-medium text-wordlock-yellow">
                {t("panel.owner")}
              </span>
            </li>
            {data.members.map((m) => {
              const isMe = meId === m.discord_id;
              return (
                <li
                  key={m.discord_id}
                  className="flex items-center gap-3 rounded-lg bg-white/5 px-4 py-3"
                >
                  <button
                    onClick={() => copyId(m.discord_id)}
                    className="text-gray-400 transition hover:text-blurple"
                    title={t("panel.copied")}
                  >
                    {copiedId === m.discord_id ? (
                      <Check className="h-5 w-5 text-wordlock-green" />
                    ) : (
                      <Copy className="h-5 w-5" />
                    )}
                  </button>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-white">
                      {m.username || t("panel.unknownUser")}
                      {isMe && <span className="text-gray-400"> ({t("panel.yourself")})</span>}
                    </div>
                    <div className="font-mono text-xs text-gray-500">
                      {m.discord_id} · {fmt(m.created_at)}
                    </div>
                  </div>
                  <div className="ml-auto flex items-center gap-3">
                    {m.pending && (
                      <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-gray-300">
                        {t("panel.pendingBadge")}
                      </span>
                    )}
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                        m.role === "moderator"
                          ? "bg-blurple/15 text-blurple"
                          : "bg-white/10 text-gray-300"
                      }`}
                    >
                      {m.role === "moderator" ? (
                        <ShieldCheck className="h-3 w-3" />
                      ) : (
                        <Eye className="h-3 w-3" />
                      )}
                      {m.role === "moderator"
                        ? t("panel.role.moderator")
                        : t("panel.role.viewer")}
                    </span>
                    {isInviter && !isMe && (
                      <button
                        onClick={() => remove(m.discord_id)}
                        className="rounded-lg p-1.5 text-gray-400 transition hover:bg-wordlock-red/15 hover:text-wordlock-red"
                        title={t("panel.remove")}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
