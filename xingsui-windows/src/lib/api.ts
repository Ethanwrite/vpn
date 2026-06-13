// 对 Tauri invoke 的薄封装：UI 层只调用这些函数，不直接接触 Rust。

import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type {
  NetMode,
  StatsPayload,
  StatusPayload,
  User,
  VpnNodeSummary,
} from "./types";

export const api = {
  login: (email: string, password: string) =>
    invoke<User>("login", { email, password }),

  register: (email: string, password: string, inviteCode?: string) =>
    invoke<User>("register", { email, password, inviteCode: inviteCode || null }),

  restoreSession: () => invoke<User | null>("restore_session"),

  getMe: () => invoke<User>("get_me"),

  logout: () => invoke<void>("logout"),

  listNodes: () => invoke<VpnNodeSummary[]>("list_nodes"),

  connect: (nodeId: string, mode: NetMode) =>
    invoke<void>("connect", { nodeId, mode }),

  disconnect: () => invoke<void>("disconnect"),

  switchMode: (mode: NetMode) => invoke<void>("switch_mode", { mode }),

  getStatus: () => invoke<StatusPayload>("get_status"),
};

// 事件订阅：连接状态与实时速率。
export function onStatus(cb: (s: StatusPayload) => void): Promise<UnlistenFn> {
  return listen<StatusPayload>("status", (e) => cb(e.payload));
}

export function onStats(cb: (s: StatsPayload) => void): Promise<UnlistenFn> {
  return listen<StatsPayload>("stats", (e) => cb(e.payload));
}

// 将 Rust 错误（字符串）规整为可展示文案。
export function errText(e: unknown): string {
  if (typeof e === "string") return e;
  if (e && typeof e === "object" && "message" in e) {
    return String((e as { message: unknown }).message);
  }
  return "操作失败，请稍后重试";
}
