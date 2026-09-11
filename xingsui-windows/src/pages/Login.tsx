// 登录 / 注册页：奶油白纸面卡片 + 黑金标志。

import { useState } from "react";
import BrandMark from "../components/BrandMark";
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
        <BrandMark className="mx-auto mb-4 h-16 w-16" />
        <p className="kicker">MARX VPN</p>
        <h1 className="mt-2 text-2xl font-extrabold tracking-tight">星火 VPN</h1>
        <p className="mt-1.5 text-xs text-ink-500">连接世界 · 消除网络边界</p>
      </div>

      <div className="card w-full p-5 shadow-block">
        <div className="mb-4 flex border-b border-ink-900/12 text-sm">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 border-b-2 py-2.5 font-bold transition ${
                mode === m
                  ? "border-gold text-ink-900"
                  : "border-transparent text-ink-300"
              }`}
            >
              {m === "login" ? "登录" : "注册"}
            </button>
          ))}
        </div>

        <div className="space-y-3">
          <input
            className="field"
            placeholder="邮箱"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            className="field"
            placeholder="密码"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          {mode === "register" && (
            <input
              className="field"
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
