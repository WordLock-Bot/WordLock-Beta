"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Save,
  ArrowLeft,
  ShieldBan,
  ShieldOff,
  Plus,
  Trash2,
  RefreshCw,
  Send,
  AlertTriangle,
  CheckCircle2,
  ShieldCheck,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import {
  ViolationsChart,
  TopWordsList,
} from "@/components/Charts";
import type {
  AdminServerDetail,
  ServerChannel,
  Word,
  Incident,
} from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const asArray = (v: unknown): string[] =>
  Array.isArray(v) ? v.map(String).filter((s) => s.length > 0 && !Number.isNaN(Number(s))) : [];

export default function AdminServerDetailPage() {
  const params = useParams();
  const guildId = (params?.guildId as string) ?? "";
  const { t, locale } = useI18n();
  const [cfg, setCfg] = useState<AdminServerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [channels, setChannels] = useState<ServerChannel[]>([]);
  const [newWord, setNewWord] = useState("");
  const [newWordSeverity, setNewWordSeverity] = useState(3);
  const [newWordAction, setNewWordAction] = useState("delete");
  const [broadcastMsg, setBroadcastMsg] = useState("");
  const [broadcastChannel, setBroadcastChannel] = useState("");
  const [broadcastBusy, setBroadcastBusy] = useState(false);

  const reload = async () => {
    setLoading(true);
    setToast(null);
    try {
      const data = await api<AdminServerDetail>(`/api/admin/servers/${guildId}`);
      setCfg(data);
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    api<{ channels: ServerChannel[] }>(`/api/admin/servers/${guildId}/channels`)
      .then((r) => {
        setChannels(r.channels ?? []);
        setBroadcastChannel((prev) => prev || r.channels?.[0]?.id || "");
      })
      .catch(() => setChannels([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guildId]);

  const save = async () => {
    if (!cfg) return;
    setSaved(false);
    try {
      await api(`/api/admin/servers/${guildId}`, {
        method: "PATCH",
        body: JSON.stringify({
          language: cfg.language,
          mod_level: cfg.mod_level,
          log_channel_id: cfg.log_channel_id,
          timeout_minutes: cfg.timeout_minutes,
          action_delete: cfg.action_delete,
          action_warn: cfg.action_warn,
          action_timeout: cfg.action_timeout,
          action_log: cfg.action_log,
          bypass_roles: asArray(cfg.bypass_roles),
          bypass_users: asArray(cfg.bypass_users),
          bypass_privileged: cfg.bypass_privileged,
          std_word_action: cfg.std_word_action,
          anti_spam_enabled: cfg.anti_spam_enabled,
          anti_nuke_enabled: cfg.anti_nuke_enabled,
          anti_spam_config: cfg.anti_spam_config,
          anti_nuke_config: cfg.anti_nuke_config,
        }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  const setStatus = async (status: string) => {
    try {
      await api(`/api/admin/servers/${guildId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      reload();
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  const addWord = async () => {
    const word = newWord.trim().toLowerCase();
    if (!word) return;
    try {
      await api(`/api/admin/servers/${guildId}/words`, {
        method: "POST",
        body: JSON.stringify({ word, severity: newWordSeverity, action: newWordAction }),
      });
      setNewWord("");
      reload();
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  const toggleWord = async (w: Word) => {
    try {
      await api(`/api/admin/servers/${guildId}/words/${w.word}/enabled`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !w.enabled }),
      });
      reload();
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  const deleteWord = async (w: Word) => {
    if (!window.confirm(`${t("adServDetail.delWordConfirm")} "${w.word}"?`)) return;
    try {
      await api(`/api/admin/servers/${guildId}/words/${w.word}`, { method: "DELETE" });
      reload();
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  const sendBroadcast = async () => {
    if (!broadcastMsg.trim()) return;
    setBroadcastBusy(true);
    try {
      await api(`/api/admin/servers/${guildId}/announce`, {
        method: "POST",
        body: JSON.stringify({ message: broadcastMsg, channel_id: broadcastChannel }),
      });
      setBroadcastMsg("");
      setToast(t("adServDetail.broadcastSent"));
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    } finally {
      setBroadcastBusy(false);
    }
  };

  if (loading) return <p className="text-gray-400">{t("common.loading")}</p>;

  if (!cfg) {
    return (
      <div className="space-y-4">
        <Link href="/admin/servers" className="inline-flex items-center gap-2 text-sm text-blurple hover:text-white">
          <ArrowLeft className="h-4 w-4" /> {t("adServ.backToServers")}
        </Link>
        <div className="card p-8 text-center text-gray-400">
          <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-wordlock-yellow" />
          {toast || t("common.unknownError")}
        </div>
      </div>
    );
  }

  const actions: { key: keyof AdminServerDetail; label: string; desc: string }[] = [
    { key: "action_delete", label: t("settings.actionDelete"), desc: t("settings.actionDeleteDesc") },
    { key: "action_warn", label: t("settings.actionWarn"), desc: t("settings.actionWarnDesc") },
    { key: "action_timeout", label: t("settings.actionTimeout"), desc: t("settings.actionTimeoutDesc") },
    { key: "action_log", label: t("settings.actionLog"), desc: t("settings.actionLogDesc") },
  ];

  const toggle = (key: keyof AdminServerDetail) =>
    setCfg({ ...cfg, [key]: !cfg[key] });

  return (
    <div className="max-w-6xl space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href="/admin/servers" className="rounded-lg p-2 text-gray-400 hover:bg-white/5 hover:text-white" aria-label={t("adServ.backToServers")}>
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-3xl font-bold text-white">{cfg.name || "—"}</h1>
            <p className="mt-1 text-sm text-gray-400">
              {t("adServDetail.serverId")} <span className="font-mono">{cfg.guild_id}</span>
              {" · "}
              {t("adServ.thMembers")}: {cfg.member_count?.toLocaleString(locale)}
              {" · "}
              {cfg.bot_version ? `v${cfg.bot_version}` : "?"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {cfg.status === "active" ? (
            <button onClick={() => setStatus("disabled")} className="btn-secondary">
              <ShieldBan className="h-4 w-4" /> {t("adServ.deactivate")}
            </button>
          ) : (
            <button onClick={() => setStatus("active")} className="btn-secondary">
              <ShieldCheck className="h-4 w-4" /> {t("adServ.activate")}
            </button>
          )}
          <button onClick={() => setStatus(cfg.status === "maintenance" ? "active" : "maintenance")} className="btn-secondary">
            {cfg.status === "maintenance" ? t("adServDetail.clearMaintenance") : t("adServ.maintenance")}
          </button>
          <button onClick={reload} className="btn-secondary">
            <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
          </button>
        </div>
      </div>

      {toast && (
        <div className="rounded-xl border border-wordlock-green/40 bg-wordlock-green/10 p-4 text-sm text-wordlock-green">
          {toast}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("settings.general")}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">{t("common.language")}</label>
              <select className="input" value={cfg.language} onChange={(e) => setCfg({ ...cfg, language: e.target.value })}>
                <option value="en">English</option>
                <option value="de">Deutsch</option>
              </select>
            </div>
            <div>
              <label className="label">{t("settings.modLevel")}</label>
              <select className="input" value={cfg.mod_level} onChange={(e) => setCfg({ ...cfg, mod_level: Number(e.target.value) })}>
                {[1, 2, 3, 4, 5].map((s) => (
                  <option key={s} value={s}>
                    {t("settings.levelOption", {
                      s: String(s),
                      desc: s === 1 ? t("settings.levelStrict") : s === 5 ? t("settings.levelHeavy") : t("settings.levelBalanced"),
                    })}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">{t("settings.logChannelId")}</label>
              <select
                className="input"
                value={cfg.log_channel_id ?? ""}
                onChange={(e) => setCfg({ ...cfg, log_channel_id: e.target.value ? e.target.value : null })}
              >
                <option value="">{t("settings.logChannelNone")}</option>
                {channels.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.type === 5 ? "📢 " : "# "}
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">{t("settings.timeout")}</label>
              <input
                className="input"
                type="number"
                min={1}
                max={10080}
                value={cfg.timeout_minutes}
                onChange={(e) => setCfg({ ...cfg, timeout_minutes: Number(e.target.value) })}
              />
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("settings.actions")}</h2>
          <div className="space-y-3">
            {actions.map((a) => (
              <div key={a.key} className="flex items-center justify-between rounded-lg bg-white/5 px-4 py-3">
                <div>
                  <div className="font-medium text-white">{a.label}</div>
                  <div className="text-xs text-gray-400">{a.desc}</div>
                </div>
                <button
                  onClick={() => toggle(a.key)}
                  className={`relative h-6 w-11 rounded-full transition ${cfg[a.key] ? "bg-wordlock-green" : "bg-white/10"}`}
                  aria-label={a.label}
                >
                  <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${cfg[a.key] ? "left-[22px]" : "left-0.5"}`} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-white">{t("settings.antiSpamTitle")}</h2>
            <p className="mt-1 text-sm text-gray-400">{t("settings.antiSpamDesc")}</p>
          </div>
          <button
            onClick={() => setCfg({ ...cfg, anti_spam_enabled: !cfg.anti_spam_enabled })}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold ${cfg.anti_spam_enabled ? "bg-wordlock-green/20 text-wordlock-green" : "bg-white/10 text-gray-300"}`}
          >
            <ShieldBan className="h-4 w-4" />
            {cfg.anti_spam_enabled ? t("common.disable") : t("common.enable")}
          </button>
        </div>
        {cfg.anti_spam_enabled ? (
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="label">{t("settings.antiSpamAction")}</label>
              <select
                className="input"
                value={cfg.anti_spam_config.action}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    anti_spam_config: {
                      ...cfg.anti_spam_config,
                      action: e.target.value as typeof cfg.anti_spam_config.action,
                    },
                  })
                }
              >
                <option value="delete">{t("settings.antiSpamActionDelete")}</option>
                <option value="warn">{t("settings.antiSpamActionWarn")}</option>
                <option value="timeout">{t("settings.antiSpamActionTimeout")}</option>
                <option value="kick">{t("settings.antiSpamActionKick")}</option>
                <option value="ban">{t("settings.antiSpamActionBan")}</option>
              </select>
            </div>
            <div>
              <label className="label">{t("settings.antiSpamRateLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_spam_config.rate_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_spam_config: { ...cfg.anti_spam_config, rate_limit: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiSpamRateWindow")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_spam_config.rate_window}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_spam_config: { ...cfg.anti_spam_config, rate_window: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiSpamMentionLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_spam_config.mention_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_spam_config: { ...cfg.anti_spam_config, mention_limit: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiSpamLinkLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_spam_config.link_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_spam_config: { ...cfg.anti_spam_config, link_limit: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiSpamEmojiLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_spam_config.emoji_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_spam_config: { ...cfg.anti_spam_config, emoji_limit: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiSpamWebhookLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_spam_config.webhook_rate_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_spam_config: { ...cfg.anti_spam_config, webhook_rate_limit: Number(e.target.value) } })
                }
              />
            </div>
          </div>
        ) : (
          <p className="py-4 text-center text-sm text-gray-500">{t("settings.antiSpamOffHint")}</p>
        )}
      </div>

      <div className="card">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-white">{t("settings.antiNukeTitle")}</h2>
            <p className="mt-1 text-sm text-gray-400">{t("settings.antiNukeDesc")}</p>
          </div>
          <button
            onClick={() => setCfg({ ...cfg, anti_nuke_enabled: !cfg.anti_nuke_enabled })}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold ${cfg.anti_nuke_enabled ? "bg-wordlock-red/20 text-wordlock-red" : "bg-white/10 text-gray-300"}`}
          >
            <ShieldOff className="h-4 w-4" />
            {cfg.anti_nuke_enabled ? t("common.disable") : t("common.enable")}
          </button>
        </div>
        {cfg.anti_nuke_enabled ? (
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="label">{t("settings.antiNukeAction")}</label>
              <select
                className="input"
                value={cfg.anti_nuke_config.action}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    anti_nuke_config: {
                      ...cfg.anti_nuke_config,
                      action: e.target.value as typeof cfg.anti_nuke_config.action,
                    },
                  })
                }
              >
                <option value="timeout">{t("settings.antiNukeActionTimeout")}</option>
                <option value="kick">{t("settings.antiNukeActionKick")}</option>
                <option value="ban">{t("settings.antiNukeActionBan")}</option>
              </select>
            </div>
            <div>
              <label className="label">{t("settings.antiNukeChannelLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_nuke_config.channel_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_nuke_config: { ...cfg.anti_nuke_config, channel_limit: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiNukeWindow")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_nuke_config.channel_window}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_nuke_config: { ...cfg.anti_nuke_config, channel_window: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiNukeRoleLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_nuke_config.role_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_nuke_config: { ...cfg.anti_nuke_config, role_limit: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiNukeBanLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_nuke_config.ban_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_nuke_config: { ...cfg.anti_nuke_config, ban_limit: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiNukeKickLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_nuke_config.kick_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_nuke_config: { ...cfg.anti_nuke_config, kick_limit: Number(e.target.value) } })
                }
              />
            </div>
            <div>
              <label className="label">{t("settings.antiNukeWebhookLimit")}</label>
              <input
                className="input"
                type="number"
                min={1}
                value={cfg.anti_nuke_config.webhook_limit}
                onChange={(e) =>
                  setCfg({ ...cfg, anti_nuke_config: { ...cfg.anti_nuke_config, webhook_limit: Number(e.target.value) } })
                }
              />
            </div>
          </div>
        ) : (
          <p className="py-4 text-center text-sm text-gray-500">{t("settings.antiNukeOffHint")}</p>
        )}
      </div>

      <div className="flex justify-end">
        <button onClick={save} className="btn-primary">
          <Save className="h-4 w-4" />
          {saved ? t("common.saved") : t("common.save")}
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adStats.violations30d")}</h2>
          <ViolationsChart data={cfg.violations} />
        </div>
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adStats.topWords")}</h2>
          <TopWordsList data={cfg.top_words} />
        </div>
      </div>

      <div className="card">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">{t("adServDetail.customWords")}</h2>
          <span className="badge bg-blurple/15 text-blurple">{t("adServDetail.totalViolations", { n: String(cfg.violations_total) })}</span>
        </div>
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="flex-1">
            <label className="label">{t("adServDetail.newWord")}</label>
            <input
              className="input"
              placeholder={t("adServDetail.wordPlaceholder")}
              value={newWord}
              onChange={(e) => setNewWord(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addWord()}
            />
          </div>
          <div>
            <label className="label">{t("adServDetail.severity")}</label>
            <select className="input" value={newWordSeverity} onChange={(e) => setNewWordSeverity(Number(e.target.value))}>
              {[1, 2, 3, 4, 5].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">{t("adServDetail.action")}</label>
            <select className="input" value={newWordAction} onChange={(e) => setNewWordAction(e.target.value)}>
              <option value="delete">{t("settings.antiSpamActionDelete")}</option>
              <option value="warn">{t("settings.antiSpamActionWarn")}</option>
              <option value="timeout">{t("settings.antiSpamActionTimeout")}</option>
              <option value="log">{t("settings.antiSpamActionLog")}</option>
            </select>
          </div>
          <button onClick={addWord} className="btn-primary">
            <Plus className="h-4 w-4" /> {t("common.add")}
          </button>
        </div>
        {cfg.words.length ? (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {cfg.words.map((w) => (
              <div
                key={w.id}
                className={`flex items-center justify-between gap-2 rounded-lg bg-white/5 px-3 py-2 ${w.enabled ? "" : "opacity-50"}`}
              >
                <div className="min-w-0">
                  <div className="truncate font-mono text-sm text-white">{w.word}</div>
                  <div className="text-xs text-gray-400">
                    {w.category} · {w.severity} · {w.action}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    onClick={() => toggleWord(w)}
                    className={`rounded-md px-2 py-1 text-xs ${w.enabled ? "bg-wordlock-green/20 text-wordlock-green" : "bg-white/10 text-gray-400"}`}
                  >
                    {w.enabled ? t("common.enabled") : t("common.disabled")}
                  </button>
                  <button onClick={() => deleteWord(w)} className="rounded-md p-1 text-gray-400 hover:text-wordlock-red" aria-label={t("common.delete")}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="py-4 text-center text-sm text-gray-500">{t("adServDetail.noWords")}</p>
        )}
      </div>

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">{t("adServDetail.broadcast")}</h2>
        <p className="mb-4 text-sm text-gray-400">{t("adServDetail.broadcastDesc")}</p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[200px] flex-1">
            <label className="label">{t("settings.logChannelId")}</label>
            <select className="input" value={broadcastChannel} onChange={(e) => setBroadcastChannel(e.target.value)}>
              {channels.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.type === 5 ? "📢 " : "# "}
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[240px] flex-1">
            <label className="label">{t("adServDetail.message")}</label>
            <textarea
              className="input"
              rows={2}
              maxLength={2000}
              value={broadcastMsg}
              onChange={(e) => setBroadcastMsg(e.target.value)}
              placeholder={t("adServDetail.messagePlaceholder")}
            />
          </div>
          <button onClick={sendBroadcast} disabled={broadcastBusy} className="btn-primary">
            <Send className="h-4 w-4" />
            {t("adServDetail.send")}
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adServDetail.openIncidents")}</h2>
          {cfg.incidents.length ? (
            <ul className="space-y-2">
              {cfg.incidents.map((inc) => (
                <li key={inc.id} className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm text-white">{t(`security.kind.${inc.kind}`)}</div>
                    <div className="text-xs text-gray-400">{new Date(inc.created_at).toLocaleString(locale)}</div>
                  </div>
                  <span
                    className={`badge shrink-0 ${
                      inc.status === "open" ? "bg-wordlock-red/15 text-wordlock-red" : "bg-wordlock-green/15 text-wordlock-green"
                    }`}
                  >
                    {inc.status === "open" ? t("security.open") : t("security.resolved")}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="flex items-center gap-2 py-4 text-center text-sm text-gray-500">
              <CheckCircle2 className="h-4 w-4 text-wordlock-green" /> {t("adServDetail.noIncidents")}
            </p>
          )}
        </div>

        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adServDetail.recentLogs")}</h2>
          {cfg.logs.length ? (
            <ul className="space-y-2">
              {cfg.logs.map((l) => (
                <li key={l.id} className="rounded-lg bg-white/5 px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-blurple">{l.type}</span>
                    <span className="text-xs text-gray-500">{new Date(l.created_at).toLocaleString(locale)}</span>
                  </div>
                  <div className="mt-0.5 truncate text-sm text-gray-200">{l.message}</div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-4 text-center text-sm text-gray-500">{t("adServDetail.noLogs")}</p>
          )}
        </div>
      </div>
    </div>
  );
}
