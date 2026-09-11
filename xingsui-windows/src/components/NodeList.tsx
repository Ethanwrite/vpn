// 节点选择弹层：仅展示线路名称、地区、状态与操作。

import type { VpnNodeSummary } from "../lib/types";
import { formatNodeDetail } from "../lib/format";

interface Props {
  open: boolean;
  nodes: VpnNodeSummary[];
  selectedId: string | null;
  onPick: (node: VpnNodeSummary) => void;
  onClose: () => void;
}

export default function NodeList({ open, nodes, selectedId, onPick, onClose }: Props) {
  if (!open) return null;
  return (
    <div
      className="absolute inset-0 z-40 flex items-end bg-ink-900/35 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="max-h-[70%] w-full animate-fade-in overflow-y-auto border-t border-ink-900/15 bg-paper-raised p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-extrabold text-ink-900">选择线路</h3>
            <p className="mt-1 text-xs text-ink-500">选择适合你的网络线路</p>
          </div>
          <button className="text-ink-300 transition hover:text-ink-900" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="space-y-2">
          {nodes.length === 0 && (
            <p className="py-8 text-center text-sm text-ink-300">暂无可用线路</p>
          )}
          {nodes.map((n) => {
            const online = n.status === "online";
            const selected = n.id === selectedId;
            return (
              <button
                key={n.id}
                disabled={n.locked}
                onClick={() => onPick(n)}
                className={`flex w-full items-center gap-3 rounded-brand border px-4 py-3.5 text-left transition ${
                  selected
                    ? "border-ink-900 bg-ink-900 text-paper-raised"
                    : "border-ink-900/15 bg-paper hover:shadow-block"
                } ${n.locked ? "opacity-45" : ""}`}
              >
                <span
                  className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                    online ? "bg-gold" : "bg-ink-300"
                  }`}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-bold">{n.name}</span>
                    {n.vip_only && (
                      <span className="rounded-[2px] bg-gold-light px-1.5 py-0.5 text-[10px] font-bold text-ink-900">
                        VIP
                      </span>
                    )}
                    {n.locked && <span className="text-xs">🔒</span>}
                  </div>
                  <div className={`mt-1 flex items-center gap-2 text-xs ${selected ? "text-paper-raised/70" : "text-ink-500"}`}>
                    <span>{formatNodeDetail(n)}</span>
                    <span>·</span>
                    <span>{online ? "可用" : "维护中"}</span>
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <span className={`font-mono text-[11px] ${selected ? "text-paper-raised/60" : "text-ink-300"}`}>
                    {online ? "在线" : "离线"}
                  </span>
                  <span className={`rounded-[2px] px-2.5 py-1 text-[11px] font-bold ${
                    selected
                      ? "bg-gold-light text-ink-900"
                      : "border border-ink-900/20 text-ink-500"
                  }`}>
                    {selected ? "已选择" : n.locked ? "暂不可用" : "选择"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
