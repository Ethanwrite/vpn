// 我的：用户名、VIP 状态、到期时间、流量额度、退出登录。

import { useEffect } from "react";
import { api, errText } from "../lib/api";
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

  // 进入页面刷新一次用户信息。
  useEffect(() => {
    (async () => {
      try {
        const me = await api.getMe();
        setUser(me);
      } catch {
        /* 忽略刷新失败 */
      }
    })();
  }, [setUser]);

  if (!user) return null;

  const vip = vipView(user.vip_status);
  const left = daysLeft(user.vip_expired_at);
  const usedPct = user.free_traffic_quota_bytes
    ? Math.min(
        100,
        Math.round(
          (user.free_traffic_used_bytes / user.free_traffic_quota_bytes) * 100
        )
      )
    : 0;

  const logout = async () => {
    try {
      await api.logout();
      setConn("disconnected", null);
      setUser(null);
      pushToast("info", "已退出登录");
    } catch (e) {
      pushToast("error", errText(e));
    }
  };

  return (
    <div className="flex h-full flex-col px-6 pb-6">
      <div className="flex items-center gap-3 py-2">
        <button
          onClick={onBack}
          className="grid h-8 w-8 place-items-center rounded-lg text-white/60 transition hover:bg-white/10 hover:text-white"
          aria-label="返回"
        >
          ‹
        </button>
        <h2 className="text-base font-semibold">我的</h2>
      </div>

      {/* 用户卡片 */}
      <div className="glass mt-2 flex items-center gap-4 rounded-2xl p-5">
        <span className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-gradient text-xl font-bold shadow-glow">
          {(user.nickname || user.email).slice(0, 1).toUpperCase()}
        </span>
        <div className="min-w-0">
          <div className="truncate text-base font-semibold">
            {user.nickname || user.email}
          </div>
          <div className="truncate text-xs text-white/45">{user.email}</div>
          <span
            className={`mt-1 inline-block rounded px-2 py-0.5 text-[11px] font-semibold ${
              vip.isVip
                ? "bg-amber-400/20 text-amber-300"
                : "bg-white/10 text-white/60"
            }`}
          >
            {vip.label}
          </span>
        </div>
      </div>

      {/* 信息行 */}
      <div className="mt-4 space-y-2">
        <InfoRow label="VIP 到期" value={formatDate(user.vip_expired_at)} />
        <InfoRow
          label="剩余天数"
          value={left === null ? "—" : `${left} 天`}
        />
        <InfoRow label="邀请码" value={user.invite_code} />
        <InfoRow
          label="余额"
          value={`¥${(user.cash_balance_cents / 100).toFixed(2)}`}
        />
      </div>

      {/* 免费流量进度 */}
      <div className="glass mt-4 rounded-2xl p-4">
        <div className="mb-2 flex items-center justify-between text-xs text-white/55">
          <span>免费流量</span>
          <span>
            {formatBytes(user.free_traffic_used_bytes)} /{" "}
            {formatBytes(user.free_traffic_quota_bytes)}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-brand-gradient transition-all"
            style={{ width: `${usedPct}%` }}
          />
        </div>
      </div>

      <div className="flex-1" />

      <button
        onClick={logout}
        className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/20"
      >
        退出登录
      </button>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass flex items-center justify-between rounded-xl px-4 py-3">
      <span className="text-sm text-white/55">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}
