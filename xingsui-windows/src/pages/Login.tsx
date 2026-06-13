// 登录 / 注册页：毛玻璃卡片 + 品牌渐变。

import { useState } from "react";
import { api, errText } from "../lib/api";
import { useStore } from "../store/useStore";

export default function Login() {
  const setUser = useStore((s) => s.setUser);
  const pushToast = useStore((s) => s.pushToast);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email || !password) {
      pushToast("error", "请填写邮箱与密码");
      return;
    }
    setBusy(true);
    try {
      const user =
        mode === "login"
          ? await api.login(email, password)
          : await api.register(email, password, invite);
      setUser(user);
      pushToast("success", mode === "login" ? "登录成功" : "注册成功");
    } catch (e) {
      pushToast("error", errText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col items-center justify-center px-7">
      <div className="mb-7 text-center">
        <div className="mx-auto mb-3 grid h-16 w-16 place-items-center rounded-2xl bg-brand-gradient shadow-glow">
          <span className="text-2xl font-black">星</span>
        </div>
        <h1 className="text-xl font-bold tracking-wide">星隧 VPN</h1>
        <p className="mt-1 text-xs text-white/50">极速 · 安全 · 抗封锁</p>
      </div>

      <div className="glass w-full rounded-2xl p-5">
        <div className="mb-4 flex rounded-xl bg-white/5 p-1 text-sm">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 rounded-lg py-2 transition ${
                mode === m ? "bg-brand-gradient font-semibold" : "text-white/60"
              }`}
            >
              {m === "login" ? "登录" : "注册"}
            </button>
          ))}
        </div>

        <div className="space-y-3">
          <input
            className="glass-input"
            placeholder="邮箱"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            className="glass-input"
            placeholder="密码"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          {mode === "register" && (
            <input
              className="glass-input"
              placeholder="邀请码（选填）"
              value={invite}
              onChange={(e) => setInvite(e.target.value)}
            />
          )}
          <button className="btn-primary w-full" disabled={busy} onClick={submit}>
            {busy ? "处理中…" : mode === "login" ? "登 录" : "注 册"}
          </button>
        </div>
      </div>
    </div>
  );
}
