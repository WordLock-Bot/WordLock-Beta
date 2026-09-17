"use client";

import { useEffect, useState } from "react";
import { FileText, Trash2, Plus, Save } from "lucide-react";
import { api } from "@/lib/api";
import type { WordListInfo } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

interface WordItem {
  word: string;
  category: string;
  severity: number;
  description?: string;
}

interface ListDoc {
  meta: { language: string; name: string; version: string };
  words: WordItem[];
}

const CATEGORIES = ["insult", "profanity", "slur", "sexual", "threat", "spam", "custom"];

export default function AdminLists() {
  const { t } = useI18n();
  const [lists, setLists] = useState<WordListInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [doc, setDoc] = useState<ListDoc | null>(null);
  const [newWord, setNewWord] = useState<WordItem>({
    word: "",
    category: "profanity",
    severity: 3,
  });
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api<WordListInfo[]>("/api/admin/lists").then(setLists);
  }, []);

  const openList = async (lang: string) => {
    setSelected(lang);
    setDoc(await api<ListDoc>(`/api/admin/lists/${lang}`));
  };

  const save = async () => {
    if (!doc) return;
    setMsg(null);
    const res = await api<any>(`/api/admin/lists/${selected}`, {
      method: "PUT",
      body: JSON.stringify(doc),
    });
    setMsg(t("adLists.saved", { count: String(res.word_count), version: res.version }));
    api<WordListInfo[]>("/api/admin/lists").then(setLists);
  };

  const addWord = () => {
    if (!doc || !newWord.word.trim()) return;
    setDoc({
      ...doc,
      words: [
        ...doc.words,
        { ...newWord, word: newWord.word.trim().toLowerCase(), description: "" },
      ],
    });
    setNewWord({ word: "", category: "profanity", severity: 3 });
  };

  const updateWord = (idx: number, patch: Partial<WordItem>) => {
    if (!doc) return;
    const words = [...doc.words];
    words[idx] = { ...words[idx], ...patch };
    setDoc({ ...doc, words });
  };

  const removeWord = (idx: number) => {
    if (!doc) return;
    setDoc({ ...doc, words: doc.words.filter((_, i) => i !== idx) });
  };

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-white">{t("adLists.title")}</h1>
        <p className="mt-1 text-sm text-gray-400">{t("adLists.subtitle")}</p>
      </header>

      {msg && <div className="rounded-lg bg-wordlock-green/10 px-4 py-3 text-sm text-wordlock-green">{msg}</div>}

      <div className="grid gap-6 lg:grid-cols-4">
        <div className="space-y-3 lg:col-span-1">
          {lists.map((l) => (
            <button
              key={l.language}
              onClick={() => openList(l.language)}
              className={`card w-full text-left transition hover:border-blurple/50 ${
                selected === l.language ? "border-blurple/60 bg-blurple/5" : ""
              }`}
            >
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-blurple" />
                <div>
                  <div className="font-semibold text-white">{l.name}</div>
                  <div className="text-xs text-gray-400">
                    v{l.version} • {t("common.wordsCount", { n: String(l.word_count) })}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>

        <div className="card lg:col-span-3">
          {!doc ? (
            <p className="py-12 text-center text-gray-500">
              {t("adLists.choose")}
            </p>
          ) : (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    {doc.meta.name} ({doc.words.length} {t("common.wordsCount", { n: String(doc.words.length) })})
                  </h2>
                  <p className="text-xs text-gray-400">v{doc.meta.version}</p>
                </div>
                <button onClick={save} className="btn-primary">
                  <Save className="h-4 w-4" /> {t("common.save")}
                </button>
              </div>

              <div className="flex flex-wrap gap-2 rounded-lg bg-white/5 p-3">
                <input
                  className="input max-w-[220px]"
                  placeholder={t("adLists.newWord")}
                  value={newWord.word}
                  onChange={(e) => setNewWord({ ...newWord, word: e.target.value })}
                />
                <select
                  className="input max-w-[140px]"
                  value={newWord.category}
                  onChange={(e) => setNewWord({ ...newWord, category: e.target.value })}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <select
                  className="input max-w-[130px]"
                  value={newWord.severity}
                  onChange={(e) =>
                    setNewWord({ ...newWord, severity: Number(e.target.value) })
                  }
                >
                  {[1, 2, 3, 4, 5].map((s) => (
                    <option key={s} value={s}>
                      {t("adLists.severity", { s: String(s) })}
                    </option>
                  ))}
                </select>
                <button onClick={addWord} className="btn-primary">
                  <Plus className="h-4 w-4" /> {t("common.add")}
                </button>
              </div>

              <div className="max-h-[520px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-discord">
                    <tr className="text-left text-xs uppercase tracking-wider text-gray-400">
                      <th className="pb-2">{t("common.word")}</th>
                      <th className="pb-2">{t("common.category")}</th>
                      <th className="pb-2">{t("common.severity")}</th>
                      <th className="pb-2 text-right">{t("common.action")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {doc.words.map((w, i) => (
                      <tr key={`${w.word}-${i}`} className="border-t border-white/5">
                        <td className="py-2 font-mono text-gray-100">{w.word}</td>
                        <td className="py-2">
                          <select
                            className="input max-w-[140px]"
                            value={w.category}
                            onChange={(e) => updateWord(i, { category: e.target.value })}
                          >
                            {CATEGORIES.map((c) => (
                              <option key={c} value={c}>
                                {c}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-2">
                          <select
                            className="input max-w-[120px]"
                            value={w.severity}
                            onChange={(e) =>
                              updateWord(i, { severity: Number(e.target.value) })
                            }
                          >
                            {[1, 2, 3, 4, 5].map((s) => (
                              <option key={s} value={s}>
                                {s}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-2 text-right">
                          <button
                            onClick={() => removeWord(i)}
                            className="btn-danger px-2 py-1"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
