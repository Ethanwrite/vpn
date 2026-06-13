// 主连接按钮：圆形大按钮 + 状态指示灯 + 脉冲动画。

import type { ConnState } from "../lib/types";

interface Props {
  conn: ConnState;
  onClick: () => void;
}

const LABEL: Record<ConnState, string> = {
  disconnected: "点击连接",
  connecting: "连接中…",
  connected: "已连接",
};

export default function ConnectButton({ conn, onClick }: Props) {
  const active = conn === "connected";
  const connecting = conn === "connecting";
  return (
    <button
      onClick={onClick}
      disabled={connecting}
      className="relative grid h-44 w-44 place-items-center rounded-full outline-none"
      aria-label={LABEL[conn]}
    >
      {/* 外圈脉冲（已连接时） */}
      {active && (
        <span className="absolute inset-0 rounded-full bg-brand-glow/30 animate-pulse-ring" />
      )}
      <span
        className={`absolute inset-0 rounded-full border transition-colors duration-500 ${
          active
            ? "border-brand-glow/60 shadow-glow"
            : "border-white/10"
        }`}
      />
      <span
        className={`grid h-32 w-32 place-items-center rounded-full transition-all duration-500 ${
          active
            ? "bg-brand-gradient shadow-glow"
            : connecting
            ? "bg-white/10"
            : "bg-white/5 hover:bg-white/10"
        }`}
      >
        <div className="text-center">
          <div
            className={`mx-auto mb-1 h-3 w-3 rounded-full ${
              active
                ? "bg-emerald-300"
                : connecting
                ? "animate-pulse bg-amber-300"
                : "bg-white/40"
            }`}
          />
          <span className="text-sm font-semibold tracking-wide">
            {LABEL[conn]}
          </span>
        </div>
      </span>
    </button>
  );
}
