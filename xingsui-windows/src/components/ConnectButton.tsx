// 主连接控件：黑金锤镰标志。沿 45° 轴对称分离 → 向中心扣合 → 脉冲 → 暗红圆环闭合转金。
// 轮廓数据与官网 SITE_HTML、Android 的 XingsuiEmblemView 同源（200×200 设计坐标）。

import { useMemo } from "react";
import type { ConnState } from "../lib/types";

interface Props {
  conn: ConnState;
  onClick: () => void;
}

const LABEL: Record<ConnState, string> = {
  disconnected: "开始连接",
  connecting: "连接中",
  connected: "断开连接",
};

const STATE_LINE: Record<ConnState, string> = {
  disconnected: "NETWORK IDLE",
  connecting: "ESTABLISHING…",
  connected: "NETWORK CONNECTED",
};

/** 镰刀：刃 + 握柄；锤子：柄 + 头 + 尾钉。两组分别滑入、在中心扣合。 */
const SICKLE = [
  "M126 38A57.29 57.29 0 0 1 136 150A80.78 80.78 0 0 0 126 38Z",
  "M68.72 159.97L130.54 155.48A7.5 7.5 0 0 0 130.06 140.5L68.08 140A10 10 0 1 0 68.72 159.97Z",
];
const HAMMER = [
  "M75.51 88.82L135.2 145.09A7 7 0 0 0 144.92 135.03L86.63 77.31L75.51 88.82Z",
  "M94.27 53.64L102.77 68.36A2 2 0 0 1 102.03 71.09L60.47 95.09A2 2 0 0 1 57.73 94.36L49.23 79.64A2 2 0 0 1 49.97 76.91L91.53 52.91A2 2 0 0 1 94.27 53.64Z",
  "M47.5 86A4.5 4.5 0 1 0 56.5 86A4.5 4.5 0 1 0 47.5 86Z",
];

/** 连接完成后背后浮出的一层很淡的放射纹。 */
function useRays() {
  return useMemo(
    () =>
      Array.from({ length: 36 }, (_, i) => {
        const angle = (i * 10 * Math.PI) / 180;
        const inner = 92;
        const outer = i % 3 === 0 ? 116 : 104;
        return {
          x1: 100 + Math.cos(angle) * inner,
          y1: 100 + Math.sin(angle) * inner,
          x2: 100 + Math.cos(angle) * outer,
          y2: 100 + Math.sin(angle) * outer,
        };
      }),
    []
  );
}

/** 一个部件的三层辉光 + 一层实线，全部用同一组轮廓。 */
function Part({ id, paths }: { id: string; paths: string[] }) {
  return (
    <g className={`em-part ${id}`}>
      {[
        { cls: "em-glow em-glow1", width: 16.4 },
        { cls: "em-glow em-glow2", width: 12.4 },
        { cls: "em-glow em-glow3", width: 8.8 },
        // 未连接时看见的是 em-ghost：轮廓始终画满、但很淡；扣合开始后它淡出，
        // 把画面交给正在逐段勾勒的 em-stroke。
        { cls: "em-ghost", width: 5.4 },
        { cls: "em-stroke", width: 5.4 },
      ].map((layer) => (
        <g key={layer.cls} className={layer.cls} strokeWidth={layer.width}>
          {paths.map((d, i) => (
            <path key={i} d={d} />
          ))}
        </g>
      ))}
    </g>
  );
}

export default function ConnectButton({ conn, onClick }: Props) {
  const rays = useRays();
  const phase =
    conn === "connected" ? "is-on" : conn === "connecting" ? "is-busy" : "";

  return (
    <div className="flex flex-col items-center gap-5">
      <button
        onClick={onClick}
        className={`em relative h-56 w-56 outline-none transition active:translate-y-px ${phase}`}
        aria-label={LABEL[conn]}
      >
        <svg viewBox="0 0 200 200" aria-hidden="true">
          {/* 常驻的淡圆环与构成主义参考线 */}
          <circle className="em-guide" cx="100" cy="100" r="96" />
          <circle className="em-guide" cx="100" cy="100" r="68" strokeDasharray="1 5" />
          <line className="em-guide" x1="6" y1="100" x2="194" y2="100" />
          <line className="em-guide" x1="100" y1="6" x2="100" y2="194" />

          <g className="em-rays">
            {rays.map((r, i) => (
              <line key={i} x1={r.x1} y1={r.y1} x2={r.x2} y2={r.y2} />
            ))}
          </g>

          <circle className="em-disc" cx="100" cy="100" r="84" />
          <circle className="em-track" cx="100" cy="100" r="90" />
          <circle className="em-progress" cx="100" cy="100" r="90" />
          <circle className="em-pulse" cx="100" cy="100" r="76" />

          <Part id="em-sickle" paths={SICKLE} />
          <Part id="em-hammer" paths={HAMMER} />
        </svg>
      </button>

      <div className="text-center">
        <div
          className={`font-mono text-[11px] font-bold tracking-[0.24em] ${
            conn === "connected" ? "text-gold-deep" : "text-ink-300"
          }`}
        >
          {STATE_LINE[conn]}
        </div>
        <button
          onClick={onClick}
          className="btn-primary mt-3 w-44"
          aria-label={LABEL[conn]}
        >
          {LABEL[conn]}
        </button>
      </div>
    </div>
  );
}
