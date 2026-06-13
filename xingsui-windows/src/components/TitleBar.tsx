// 无边框窗口自定义标题栏：拖拽 + 最小化/关闭。

import { getCurrentWindow } from "@tauri-apps/api/window";

export default function TitleBar() {
  const win = getCurrentWindow();
  return (
    <div
      data-tauri-drag-region
      className="flex h-10 shrink-0 items-center justify-between px-4 select-none"
    >
      <div
        data-tauri-drag-region
        className="flex items-center gap-2 text-sm font-semibold tracking-wide text-white/90"
      >
        <span className="inline-block h-2.5 w-2.5 rounded-full bg-brand-gradient shadow-glow" />
        星隧 VPN
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => win.minimize()}
          className="grid h-7 w-7 place-items-center rounded-lg text-white/60 transition hover:bg-white/10 hover:text-white"
          aria-label="最小化"
        >
          –
        </button>
        <button
          onClick={() => win.close()}
          className="grid h-7 w-7 place-items-center rounded-lg text-white/60 transition hover:bg-rose-500/70 hover:text-white"
          aria-label="关闭"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
