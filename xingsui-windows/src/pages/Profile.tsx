import { useEffect, useState } from "react";
import { getVersion } from "@tauri-apps/api/app";
import { open } from "@tauri-apps/plugin-shell";
import { api, CONNECTION_SYNC_ERROR, errText } from "../lib/api";
import { useStore } from "../store/useStore";
import { daysLeft, formatBytes, formatDate, vipView } from "../lib/format";

interface Props {
  onBack: () => void;
}

export default function Profile({ onBack }: Props) {
  const user = useStore((s) => s.user);
  const setUser = useStore((s) => s.setUser);
  const setConn = useStore((s) => s.setConn);
  const pushToast = useStore((s) => s.pushToast);
  const [version, setVersion] = useState("");

  useEffect(() => {
    getVersion().then(setVersion).catch(() => undefined);
    (async () => {
      try {
        setUser(await api.getMe());
      } catch {
        pushToast("error", CONNECTION_SYNC_ERROR);
      }
    })();
  }, [setUser, pushToast]);

  if (!user) return null;

  const vip = vipView(user.vip_status);
  const left = daysLeft(user.vip_expired_at);

  const logout = async () => {
    try {
      await api.logout();
      setConn("disconnected", null);
      setUser(null);
      pushToast("info", "已退出登录");
    } catch (error) {
      pushToast("error", errText(error));
    }
  };

  const openWebsite = async (url: string) => {
    try {
      await open(url);
    } catch (error) {
      pushToast("error", errText(error));
    }
  };

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(user.invite_code);
      pushToast("success", "邀请码已复制");
    } catch {
      pushToast("error", "复制失败，请稍后重试");
    }
  };

  const checkUpdate = async () => {
    await openWebsite("https://xingsui.org/download");
    pushToast("info", "已打开官方下载页");
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto px-6 pb-6">
      <div className="flex items-center gap-3 py-2">
        <button onClick={onBack} className="grid h-9 w-9 place-items-center rounded-xl border border-white/10 bg-white/5 text-white/65 transition hover:bg-white/10 hover:text-white" aria-label="返回连接页面">‹</button>
        <div><h2 className="text-base font-semibold">我的</h2><p className="text-[11px] text-white/40">账户与服务</p></div>
      </div>
      <section className="glass mt-3 rounded-3xl border border-white/10 p-5 shadow-glass">
        <div className="flex items-center gap-4">
          <span className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-brand-gradient text-2xl font-bold shadow-glow">{(user.nickname || user.email).slice(0, 1).toUpperCase()}</span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-base font-semibold">{user.nickname || user.email}</div>
            <div className="mt-1 truncate text-xs text-white/45">{user.email}</div>
            <span className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${vip.isVip ? "bg-amber-400/15 text-amber-300" : "bg-white/8 text-white/55"}`}><span>{vip.isVip ? "♛" : "●"}</span>{vip.label}</span>
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-2">
          <SummaryCard label="会员有效期" value={vip.isVip ? formatDate(user.vip_expired_at) : "未开通"} hint={vip.isVip && left !== null ? `剩余 ${left} 天` : "开通后解锁全部线路"} />
          <SummaryCard label="体验流量" value={formatBytes(user.free_traffic_remaining_bytes)} hint="当前剩余" />
        </div>
      </section>
      <section className="mt-4 space-y-2">
        <ActionRow icon="⌂" label="官网" detail="访问星隧官网" onClick={() => openWebsite("https://xingsui.org")} />
        <ActionRow icon="✦" label="我的邀请码" detail={user.invite_code} onClick={copyInvite} />
        <ActionRow icon="↻" label="检查更新" detail={version ? `当前版本 ${version}` : "获取最新版本"} onClick={checkUpdate} />
      </section>
      <div className="flex-1" />
      <button onClick={logout} className="mt-5 rounded-2xl border border-rose-400/25 bg-rose-500/8 px-4 py-3 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/15">退出登录</button>
    </div>
  );
}

function SummaryCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return <div className="rounded-2xl border border-white/8 bg-white/5 p-3.5"><div className="text-[11px] text-white/40">{label}</div><div className="mt-1.5 truncate text-sm font-semibold text-white/90">{value}</div><div className="mt-1 truncate text-[10px] text-white/35">{hint}</div></div>;
}

function ActionRow({ icon, label, detail, onClick }: { icon: string; label: string; detail: string; onClick: () => void }) {
  return <button onClick={onClick} className="glass flex w-full items-center gap-3 rounded-2xl border border-white/8 px-4 py-3.5 text-left transition hover:border-brand-glow/30 hover:bg-white/10"><span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-glow/15 text-base text-violet-200">{icon}</span><span className="min-w-0 flex-1"><span className="block text-sm font-medium text-white/90">{label}</span><span className="mt-0.5 block truncate text-[11px] text-white/40">{detail}</span></span><span className="text-lg text-white/25">›</span></button>;
}
