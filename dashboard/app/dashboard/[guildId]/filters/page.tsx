"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Plus, Trash2, Power, PowerOff, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import type { ServerConfig, Word } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const CATEGORIES = ["insult", "profanity", "slur", "sexual", "threat", "spam", "custom"];
const ACTIONS = ["delete", "warn", "timeout", "log"];

interface ListInfo {
  language: string;
  name: string;
  version: string;
  words: number;
}

interface StandardWord {
  word: string;
  category: string;
  severity: number;
  language: string;
  enabled: boolean;
  action: string | null;
}

export default function GuildFilters() {
  const params = useParams();
  const guildId = (params?.guildId as string) ?? "";
  const { t } = useI18n();
  const [words, setWords] = useState<Word[]>([]);
  const [stdWords, setStdWords] = useState<StandardWord[]>([]);
  const [lists, setLists] = useState<ListInfo[]>([]);
  const [defaultLists, setDefaultLists] = useState<Record<string, boolean>>({});
  const [form, setForm] = useState({ word: "", category: "custom", severity: 3, action: "delete" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [stdAction, setStdAction] = useState("delete");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api<Word[]>(`/api/guilds/${guildId}/words?enabled_only=false`),
      api<StandardWord[]>(`/api/guilds/${guildId}/standard-words`),
      api<{ available: ListInfo[] }>(`/api/guilds/${guildId}/lists`),
      api<ServerConfig>(`/api/guilds/${guildId}`),
    ])
      .then(([w, sw, l, cfg]) => {
        setWords(w);
        setStdWords(sw);
        setLists(l.available);
        setDefaultLists(cfg.default_lists ?? {});
        setStdAction(cfg.std_word_action || "delete");
      })
      .finally(() => setLoading(false));
  }, [guildId]);

  const filteredStd = stdWords.filter(
    (w) =>
      w.word.toLowerCase().includes(search.toLowerCase()) ||
      w.category.toLowerCase().includes(search.toLowerCase())
  );

  const saveStdAction = async (val: string) => {
    setStdAction(val);
    await api(`/api/guilds/${guildId}`, {
      method: "PUT",
      body: JSON.stringify({ std_word_action: val }),
    });
  };

  const addWord = async () => {
    setMsg(null);
    try {
      await api(`/api/guilds/${guildId}/words`, {
        method: "POST",
        body: JSON.stringify(form),
      });
      setMsg({ ok: true, text: t("filters.added", { word: form.word }) });
      setForm({ ...form, word: "" });
      window.location.reload();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  };

  const removeWord = async (word: string) => {
    await api(`/api/guilds/${guildId}/words/${word}`, { method: "DELETE" });
    window.location.reload();
  };

  const toggleWord = async (word: Word) => {
    await api(`/api/guilds/${guildId}/words/${word.word}/enabled`, {
      method: "PATCH",
      body: JSON.stringify({ enabled: !word.enabled }),
    });
    window.location.reload();
  };

  const toggleList = async (lang: string, enabled: boolean) => {
    const next = { ...defaultLists, [lang]: enabled };
    setDefaultLists(next);
    await api(`/api/guilds/${guildId}`, {
      method: "PUT",
      body: JSON.stringify({ default_lists: next }),
    });
  };

  const saveStandardWord = async (sw: StandardWord, patch: Partial<StandardWord>) => {
    setMsg(null);
    try {
      const next = { ...sw, ...patch };
      await api(`/api/guilds/${guildId}/standard-words/${encodeURIComponent(sw.word)}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: next.enabled, action: next.action }),
      });
      setStdWords((prev) => prev.map((w) => (w.word === sw.word ? next : w)));
      setMsg({ ok: true, text: t("filters.stdWordsSaved", { word: sw.word }) });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  };

  const resetStandardWord = async (sw: StandardWord) => {
    await api(`/api/guilds/${guildId}/standard-words/${encodeURIComponent(sw.word)}`, {
      method: "DELETE",
    });
    setStdWords((prev) =>
      prev.map((w) => (w.word === sw.word ? { ...w, enabled: true, action: null } : w))
    );
  };

  const resetAllStandardWords = async () => {
    await Promise.all(
      stdWords.filter((w) => w.action !== null || !w.enabled).map((w) => resetStandardWord(w))
    );
  };

  const severityColor = (s: number) =>
    s >= 5 ? "text-red-400" : s >= 4 ? "text-orange-400" : s >= 3 ? "text-yellow-300" : "text-green-400";

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-white">{t("filters.title")}</h1>
        <p className="mt-1 text-sm text-gray-400">{t("filters.subtitle")}</p>
      </header>

      {msg && (
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            msg.ok
              ? "bg-wordlock-green/10 text-wordlock-green"
              : "bg-wordlock-red/10 text-wordlock-red"
          }`}
        >
          {msg.text}
        </div>
      )}

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">{t("filters.addWord")}</h2>
        <div className="grid gap-3 sm:grid-cols-5">
          <div className="sm:col-span-1">
            <label className="label">{t("common.word")}</label>
            <input
              className="input"
              value={form.word}
              onChange={(e) => setForm({ ...form, word: e.target.value })}
              placeholder={t("filters.wordPlaceholder")}
            />
          </div>
          <div>
            <label className="label">{t("common.category")}</label>
            <select
              className="input"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">{t("common.severity")}</label>
            <select
              className="input"
              value={form.severity}
              onChange={(e) => setForm({ ...form, severity: Number(e.target.value) })}
            >
              {[1, 2, 3, 4, 5].map((s) => (
                <option key={s} value={s}>
                  {s} {s >= 4 ? t("filters.severityHigh") : ""}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">{t("common.action")}</label>
            <select
              className="input"
              value={form.action}
              onChange={(e) => setForm({ ...form, action: e.target.value })}
            >
              {ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={addWord} className="btn-primary w-full">
              <Plus className="h-4 w-4" /> {t("common.add")}
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">
          {t("filters.yourWords", { count: words.length })}
        </h2>
        {loading ? (
          <p className="text-sm text-gray-500">{t("common.loading")}</p>
        ) : words.length === 0 ? (
          <p className="py-6 text-center text-sm text-gray-500">{t("filters.noWords")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-gray-400">
                  <th className="pb-2">{t("common.word")}</th>
                  <th className="pb-2">{t("common.category")}</th>
                  <th className="pb-2">{t("common.severity")}</th>
                  <th className="pb-2">{t("common.action")}</th>
                  <th className="pb-2 text-right">{t("filters.th.statusActions")}</th>
                </tr>
              </thead>
              <tbody>
                {words.map((w) => (
                  <tr key={w.id} className="border-b border-white/5 last:border-0">
                    <td className="py-3 font-mono text-gray-100">{w.word}</td>
                    <td className="py-3 capitalize text-gray-300">{w.category}</td>
                    <td className={`py-3 font-semibold ${severityColor(w.severity)}`}>
                      {w.severity}/5
                    </td>
                    <td className="py-3 capitalize text-gray-300">{w.action}</td>
                    <td className="py-3">
                      <div className="flex items-center justify-end gap-2">
                        <span className={`badge ${w.enabled ? "bg-wordlock-green/10 text-wordlock-green" : "bg-white/5 text-gray-400"}`}>
                          {w.enabled ? t("common.active") : t("common.off")}
                        </span>
                        <button
                          onClick={() => toggleWord(w)}
                          className="btn-secondary px-2 py-1"
                          title={w.enabled ? t("common.disable") : t("common.enable")}
                        >
                          {w.enabled ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                        </button>
                        <button
                          onClick={() => removeWord(w.word)}
                          className="btn-danger px-2 py-1"
                          title={t("common.delete")}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">
              {t("filters.stdWords", { count: stdWords.length })}
            </h2>
            <p className="mt-1 text-sm text-gray-400">{t("filters.stdWordsSubtitle")}</p>
          </div>
          <button
            onClick={resetAllStandardWords}
            className="btn-secondary px-3 py-1.5 text-xs"
            title={t("filters.stdWordsResetAll")}
          >
            <RotateCcw className="h-3.5 w-3.5" /> {t("filters.stdWordsResetAll")}
          </button>
        </div>
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="label">{t("filters.search")}</label>
            <input
              className="input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("filters.searchPlaceholder")}
            />
          </div>
          <div>
            <label className="label">{t("filters.stdWordDefaultAction")}</label>
            <select
              className="input"
              value={stdAction}
              onChange={(e) => saveStdAction(e.target.value)}
            >
              {ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
        </div>
        {loading ? (
          <p className="text-sm text-gray-500">{t("common.loading")}</p>
        ) : stdWords.length === 0 ? (
          <p className="py-6 text-center text-sm text-gray-500">{t("filters.noWords")}</p>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-[#17181f]">
                <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-gray-400">
                  <th className="pb-2">{t("common.word")}</th>
                  <th className="pb-2">{t("common.category")}</th>
                  <th className="pb-2">{t("common.severity")}</th>
                  <th className="pb-2">{t("common.action")}</th>
                  <th className="pb-2 text-right">{t("filters.th.statusActions")}</th>
                </tr>
              </thead>
              <tbody>
                {filteredStd.map((w) => (
                  <tr key={`${w.language}-${w.word}`} className="border-b border-white/5 last:border-0">
                    <td className="py-2 font-mono text-gray-100">
                      {w.word}
                      <span className="ml-2 rounded bg-white/5 px-1.5 py-0.5 text-[10px] uppercase text-gray-500">
                        {w.language}
                      </span>
                    </td>
                    <td className="py-2 capitalize text-gray-300">{w.category}</td>
                    <td className={`py-2 font-semibold ${severityColor(w.severity)}`}>
                      {w.severity}/5
                    </td>
                    <td className="py-2">
                      <select
                        className="input px-2 py-1 text-xs"
                        value={w.action ?? ""}
                        onChange={(e) =>
                          saveStandardWord(w, { action: e.target.value || null })
                        }
                      >
                        <option value="">{t("filters.stdWordsActionNone")}</option>
                        {ACTIONS.map((a) => (
                          <option key={a} value={a}>
                            {a}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-2">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => saveStandardWord(w, { enabled: !w.enabled })}
                          className="btn-secondary px-2 py-1"
                          title={w.enabled ? t("common.disable") : t("common.enable")}
                        >
                          {w.enabled ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                        </button>
                        <button
                          onClick={() => resetStandardWord(w)}
                          className="btn-secondary px-2 py-1"
                          title={t("filters.stdWordsReset")}
                        >
                          <RotateCcw className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-4 text-xs text-gray-500">{t("filters.stdWordsNote")}</p>
      </div>

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">{t("filters.stdLists")}</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {lists.map((l) => (
            <div key={l.language} className="flex items-center justify-between rounded-lg bg-white/5 px-4 py-3">
              <div>
                <div className="font-semibold text-white">{l.name}</div>
                <div className="text-xs text-gray-400">
                  v{l.version} • {t("common.wordsCount", { n: l.words })}
                </div>
              </div>
              <button
                onClick={() => toggleList(l.language, !defaultLists[l.language])}
                className={`badge cursor-pointer px-3 py-1 ${
                  defaultLists[l.language]
                    ? "bg-wordlock-green/15 text-wordlock-green"
                    : "bg-white/5 text-gray-400"
                }`}
              >
                {defaultLists[l.language] ? t("filters.stdListActive") : t("filters.stdListInactive")}
              </button>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-gray-500">{t("filters.stdListsNote")}</p>
      </div>
    </div>
  );
}
