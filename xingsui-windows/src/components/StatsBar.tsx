// 实时上传/下载速率展示。

import { useStore } from "../store/useStore";
import { formatSpeed } from "../lib/format";

export default function StatsBar() {
  const stats = useStore((s) => s.stats);
  return (
    <div className="grid grid-cols-2 gap-3">
      <Metric label="下载" value={formatSpeed(stats.down_bps)} arrow="↓" tint="text-emerald-300" />
      <Metric label="上传" value={formatSpeed(stats.up_bps)} arrow="↑" tint="text-indigo-300" />
    </div>
  );
}

function Metric({
  label,
  value,
  arrow,
  tint,
}: {
  label: string;
  value: string;
  arrow: string;
  tint: string;
}) {
  return (
    <div className="glass rounded-xl px-3 py-2.5">
      <div className="flex items-center gap-1 text-[11px] text-white/50">
        <span className={tint}>{arrow}</span>
        {label}
      </div>
      <div className="mt-0.5 font-mono text-sm font-semibold">{value}</div>
    </div>
  );
}
