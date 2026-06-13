// 浮动 Toast 通知（成功/错误/信息），自动消失。

import { useEffect } from "react";
import { useStore } from "../store/useStore";
import type { ToastItem } from "../lib/types";

const STYLES: Record<ToastItem["kind"], string> = {
  success: "border-emerald-400/40 bg-emerald-500/15 text-emerald-100",
  error: "border-rose-400/40 bg-rose-500/15 text-rose-100",
  info: "border-indigo-400/40 bg-indigo-500/15 text-indigo-100",
};

function ToastRow({ item }: { item: ToastItem }) {
  const dismiss = useStore((s) => s.dismissToast);
  useEffect(() => {
    const t = setTimeout(() => dismiss(item.id), 3000);
    return () => clearTimeout(t);
  }, [item.id, dismiss]);
  return (
    <div
      onClick={() => dismiss(item.id)}
      className={`pointer-events-auto animate-fade-in cursor-pointer rounded-xl border px-4 py-2.5
        text-sm shadow-glass backdrop-blur-glass ${STYLES[item.kind]}`}
    >
      {item.text}
    </div>
  );
}

export default function ToastHost() {
  const toasts = useStore((s) => s.toasts);
  return (
    <div className="pointer-events-none fixed inset-x-0 top-10 z-50 flex flex-col items-center gap-2 px-4">
      {toasts.map((t) => (
        <ToastRow key={t.id} item={t} />
      ))}
    </div>
  );
}
