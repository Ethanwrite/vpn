// 应用根：会话恢复、全局事件订阅、页面路由（登录 / 主页 / 我的）。

import { useEffect, useState } from "react";
import TitleBar from "./components/TitleBar";
import ToastHost from "./components/Toast";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Profile from "./pages/Profile";
import { api, onStats, onStatus } from "./lib/api";
import { useStore } from "./store/useStore";

type Tab = "home" | "profile";

export default function App() {
  const user = useStore((s) => s.user);
  const setUser = useStore((s) => s.setUser);
  const setConn = useStore((s) => s.setConn);
  const setStats = useStore((s) => s.setStats);
  const resetStats = useStore((s) => s.resetStats);
  const pushToast = useStore((s) => s.pushToast);
  const [booted, setBooted] = useState(false);
  const [tab, setTab] = useState<Tab>("home");

  // 启动：恢复登录态 + 订阅状态/速率事件。
  useEffect(() => {
    let unStatus: (() => void) | undefined;
    let unStats: (() => void) | undefined;
    (async () => {
      try {
        const restored = await api.restoreSession();
        if (restored) setUser(restored);
      } catch {
        /* 忽略恢复失败，落到登录页 */
      }
      unStatus = await onStatus((s) => {
        setConn(s.state, s.node_name);
        if (s.state === "disconnected") resetStats();
        if (s.message) pushToast(s.state === "connected" ? "success" : "info", s.message);
      });
      unStats = await onStats((s) => setStats(s));
      setBooted(true);
    })();
    return () => {
      unStatus?.();
      unStats?.();
    };
  }, [setUser, setConn, setStats, resetStats, pushToast]);

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-ink-900 bg-brand-radial text-white">
      <TitleBar />
      <ToastHost />
      <main className="flex-1 overflow-hidden">
        {!booted ? (
          <Splash />
        ) : !user ? (
          <Login />
        ) : tab === "home" ? (
          <Home onProfile={() => setTab("profile")} />
        ) : (
          <Profile onBack={() => setTab("home")} />
        )}
      </main>
    </div>
  );
}

function Splash() {
  return (
    <div className="grid h-full place-items-center">
      <div className="h-10 w-10 animate-spin-slow rounded-full border-2 border-white/20 border-t-brand-glow" />
    </div>
  );
}
