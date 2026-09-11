// 无边框窗口自定义标题栏：拖拽 + 最小化/关闭。

import { getCurrentWindow } from "@tauri-apps/api/window";
import BrandMark from "./BrandMark";

export default function TitleBar() {
  const win = getCurrentWindow();
  return (
    <div
      data-tauri-drag-region
      className="flex h-10 shrink-0 items-center justify-between border-b border-ink-900/10 px-4 select-none"
    >
      <div
        data-tauri-drag-region
        className="flex items-center gap-2.5 text-[13px] font-extrabold tracking-[0.18em] text-ink-900"
      >
        <BrandMark className="h-5 w-5" />
        MARX VPN
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => win.minimize()}
          className="grid h-7 w-7 place-items-center rounded-brand text-ink-500 transition hover:bg-ink-900/8 hover:text-ink-900"
          aria-label="最小化"
        >
          –
        </button>
        <button
          onClick={() => win.close()}
          className="grid h-7 w-7 place-items-center rounded-brand text-ink-500 transition hover:bg-signal hover:text-paper-raised"
          aria-label="关闭"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
