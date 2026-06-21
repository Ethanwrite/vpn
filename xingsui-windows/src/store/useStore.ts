// 全局前端状态（zustand）：用户、节点、连接状态、速率、Toast。

import { create } from "zustand";
import type {
  ConnState,
  NetMode,
  StatsPayload,
  ToastItem,
  ToastKind,
  User,
  VpnNodeSummary,
} from "../lib/types";

interface AppStore {
  user: User | null;
  nodes: VpnNodeSummary[];
  selectedNodeId: string | null;
  conn: ConnState;
  connNodeName: string | null;
  mode: NetMode;
  stats: StatsPayload;
  toasts: ToastItem[];

  setUser: (u: User | null) => void;
  setNodes: (n: VpnNodeSummary[]) => void;
  selectNode: (id: string | null) => void;
  setConn: (c: ConnState, name?: string | null) => void;
  setMode: (m: NetMode) => void;
  setStats: (s: StatsPayload) => void;
  resetStats: () => void;
  pushToast: (kind: ToastKind, text: string) => void;
  dismissToast: (id: number) => void;
}

const emptyStats: StatsPayload = {
  up_bps: 0,
  down_bps: 0,
  up_total: 0,
  down_total: 0,
};

let toastSeq = 1;

export const useStore = create<AppStore>((set) => ({
  user: null,
  nodes: [],
  selectedNodeId: null,
  conn: "disconnected",
  connNodeName: null,
  mode: "systemproxy",
  stats: emptyStats,
  toasts: [],

  setUser: (u) => set({ user: u }),
  setNodes: (n) => set({ nodes: n }),
  selectNode: (id) => set({ selectedNodeId: id }),
  setConn: (c, name) =>
    set((s) => ({ conn: c, connNodeName: name !== undefined ? name : s.connNodeName })),
  setMode: (m) => set({ mode: m }),
  setStats: (s) => set({ stats: s }),
  resetStats: () => set({ stats: emptyStats }),
  pushToast: (kind, text) =>
    set((s) => ({ toasts: [...s.toasts, { id: toastSeq++, kind, text }] })),
  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
