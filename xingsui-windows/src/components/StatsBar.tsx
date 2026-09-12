// 实时上传/下载速率展示。

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useStore } from "../store/useStore";
import { formatSpeed } from "../lib/format";

export default function StatsBar() {
  const stats = useStore((s) => s.stats);
  const conn = useStore(s => s.conn);
  const node = useStore(s => s.connNodeName);
  const mode = useStore(s => s.mode);
  const [latency, setLatency] = useState<number | null>(null);
  useEffect(() => {
    setLatency(null);
    if (conn !== "connected") return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const sample = async () => {
      const value = await api.getLatency().catch(() => null);
      if (active) { setLatency(value); timer = setTimeout(sample, 15000); }
    };
    sample();
    return () => { active = false; clearTimeout(timer); };
  }, [conn, node, mode]);
  return (
    <div className="grid grid-cols-3 gap-2">
      <Metric label="延迟" value={conn === "connected" && latency !== null ? `${latency} ms` : "—"} arrow="↔" tint="text-ink-500" />
      <Metric label="下载" value={conn === "connected" ? formatSpeed(stats.down_bps) : "—"} arrow="↓" tint="text-gold" />
      <Metric label="上传" value={conn === "connected" ? formatSpeed(stats.up_bps) : "—"} arrow="↑" tint="text-ink-500" />
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
    <div className="card px-3 py-2.5">
      <div className="flex items-center gap-1 text-[11px] tracking-[0.12em] text-ink-500">
        <span className={tint}>{arrow}</span>
        {label}
      </div>
      <div className="mt-0.5 font-mono text-sm font-bold text-ink-900">{value}</div>
    </div>
  );
}
