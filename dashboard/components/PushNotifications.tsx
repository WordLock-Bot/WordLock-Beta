"use client";

import { BellRing, BellOff, Loader2, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { urlSafeBase64ToUint8Array, useI18n } from "@/lib/i18n";

const PUSH_KEY = "wordlock_push";

export function PushNotifications() {
  const { t } = useI18n();
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    try {
      setEnabled(Boolean(window.localStorage.getItem(PUSH_KEY)));
    } catch {
      /* ignore */
    }
  }, []);

  const getSubscription = async (): Promise<PushSubscription | null> => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return null;
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg) return null;
    return reg.pushManager.getSubscription();
  };

  const enable = async () => {
    setBusy(true);
    setMsg(null);
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        setMsg(t("push.unsupported"));
        return;
      }
      if (typeof Notification !== "undefined") {
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
          setMsg(t("push.denied"));
          return;
        }
      }
      const reg = await navigator.serviceWorker.register("/sw.js");
      const { public_key } = await api<{ public_key: string }>("/api/push/vapid-key");
      if (!public_key) {
        setMsg(t("push.error"));
        return;
      }
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlSafeBase64ToUint8Array(public_key),
        });
      }
      const json = sub.toJSON();
      await api("/api/push/subscribe", {
        method: "POST",
        body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys }),
      });
      try {
        window.localStorage.setItem(PUSH_KEY, "1");
      } catch {
        /* ignore */
      }
      setEnabled(true);
      setMsg(t("push.enabled"));
    } catch (e) {
      setMsg(t("push.error"));
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const sub = await getSubscription();
      if (sub) {
        try {
          await api("/api/push/unsubscribe", {
            method: "POST",
            body: JSON.stringify({ endpoint: sub.endpoint }),
          });
        } catch {
          /* ignore server errors */
        }
        await sub.unsubscribe();
      }
      try {
        window.localStorage.removeItem(PUSH_KEY);
      } catch {
        /* ignore */
      }
      setEnabled(false);
      setMsg(t("push.unsubscribed"));
    } catch (e) {
      setMsg(t("push.error"));
    } finally {
      setBusy(false);
    }
  };

  const sendTest = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api("/api/push/test", { method: "POST" });
      setMsg(t("push.testSent"));
    } catch (e) {
      setMsg(t("push.testError"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-1 px-3 pb-1">
      <button
        onClick={enabled ? disable : enable}
        disabled={busy}
        className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
          enabled
            ? "text-wordlock-green hover:bg-white/5"
            : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
        }`}
      >
        {busy ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : enabled ? (
          <BellOff className="h-4 w-4" />
        ) : (
          <BellRing className="h-4 w-4" />
        )}
        {enabled ? t("push.disable") : t("push.enable")}
      </button>
      {enabled && (
        <button
          onClick={sendTest}
          disabled={busy}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-400 transition hover:bg-white/5 hover:text-gray-200"
        >
          <Send className="h-4 w-4" />
          {t("push.test")}
        </button>
      )}
      {msg && (
        <div
          className={`mx-3 mb-1 rounded-lg px-3 py-2 text-xs ${
            msg === t("push.enabled") || msg === t("push.unsubscribed") || msg === t("push.testSent")
              ? "bg-wordlock-green/10 text-wordlock-green"
              : "bg-wordlock-red/10 text-wordlock-red"
          }`}
        >
          {msg}
        </div>
      )}
    </div>
  );
}
