export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "default" | "green" | "red" | "yellow";
}) {
  const tones: Record<string, string> = {
    default: "text-blurple bg-blurple/10",
    green: "text-wordlock-green bg-wordlock-green/10",
    red: "text-wordlock-red bg-wordlock-red/10",
    yellow: "text-wordlock-yellow bg-wordlock-yellow/10",
  };
  return (
    <div className="card flex items-center gap-4">
      <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${tones[tone]}`}>
        <Icon className="h-6 w-6" />
      </div>
      <div>
        <div className="text-2xl font-bold text-white">{value}</div>
        <div className="text-xs font-medium uppercase tracking-wider text-gray-400">
          {label}
        </div>
      </div>
    </div>
  );
}
