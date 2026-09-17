"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import type { SeriesPoint } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const grid = "#ffffff10";

export function ViolationsChart({ data }: { data: SeriesPoint[] }) {
  const { t } = useI18n();
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="violations" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5865F2" stopOpacity={0.6} />
              <stop offset="100%" stopColor="#5865F2" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={grid} strokeDasharray="3 3" />
          <XAxis dataKey="day" tick={{ fill: "#9ca3af", fontSize: 11 }} />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: "#2b2d31",
              border: "1px solid #ffffff20",
              borderRadius: 8,
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            name={t("charts.violations")}
            stroke="#5865F2"
            strokeWidth={2}
            fill="url(#violations)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function GrowthChart({ data }: { data: SeriesPoint[] }) {
  const { t } = useI18n();
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid stroke={grid} strokeDasharray="3 3" />
          <XAxis dataKey="day" tick={{ fill: "#9ca3af", fontSize: 11 }} />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: "#2b2d31",
              border: "1px solid #ffffff20",
              borderRadius: 8,
            }}
          />
          <Bar dataKey="value" name={t("charts.servers")} fill="#57F287" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TopWordsList({ data }: { data: { matched_word: string; count: number }[] }) {
  const { t } = useI18n();
  if (!data.length) {
    return <p className="py-8 text-center text-sm text-gray-500">{t("charts.noData")}</p>;
  }
  const max = Math.max(...data.map((d) => d.count));
  return (
    <ul className="space-y-3">
      {data.map((d) => (
        <li key={d.matched_word}>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="font-mono text-gray-200">{d.matched_word}</span>
            <span className="text-gray-400">{d.count}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blurple to-wordlock-pink"
              style={{ width: `${(d.count / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
