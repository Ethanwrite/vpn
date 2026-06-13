// 与 Rust 后端模型严格对齐的前端类型。

export interface User {
  id: string;
  email: string;
  nickname: string;
  invite_code: string;
  vip_status: string;
  vip_expired_at: string | null;
  cash_balance_cents: number;
  free_traffic_quota_bytes: number;
  free_traffic_used_bytes: number;
  free_traffic_remaining_bytes: number;
}

export interface VpnNodeSummary {
  id: string;
  name: string;
  region: string;
  vip_only: boolean;
  status: string;
  load_percent: number;
  locked: boolean;
}

export type NetMode = "tun" | "systemproxy";

export type ConnState = "disconnected" | "connecting" | "connected";

export interface StatusPayload {
  state: ConnState;
  node_id: string | null;
  node_name: string | null;
  mode: NetMode;
  message: string | null;
}

export interface StatsPayload {
  up_bps: number;
  down_bps: number;
  up_total: number;
  down_total: number;
}

export type ToastKind = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  kind: ToastKind;
  text: string;
}
