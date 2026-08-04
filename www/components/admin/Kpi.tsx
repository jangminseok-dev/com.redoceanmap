import type { LucideIcon } from "lucide-react";

export default function Kpi({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon?: LucideIcon;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-2xl bg-surface border border-border p-4 sm:p-5">
      {Icon && (
        <span className="grid place-items-center w-10 h-10 rounded-xl bg-brand/10 text-brand">
          <Icon size={17} strokeWidth={1.9} />
        </span>
      )}
      <p className={`${Icon ? "mt-3" : ""} text-2xl font-bold tracking-tight`}>{value}</p>
      <div className="mt-0.5 flex items-center gap-1.5 text-xs">
        <span className="text-foreground-muted">{label}</span>
        {sub && <span className="ml-auto text-foreground-muted tabular-nums">{sub}</span>}
      </div>
    </div>
  );
}
