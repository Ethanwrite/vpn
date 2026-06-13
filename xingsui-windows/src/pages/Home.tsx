// 主页：节点选择 + 连接按钮 + 实时统计 + 模式切换。

import { useEffect, useMemo, useState } from "react";
import ConnectButton from "../components/ConnectButton";
import StatsBar from "../components/StatsBar";
import NodeList from "../components/NodeList";
import { api, errText } from "../lib/api";
import { useStore } from "../store/useStore";
import type { NetMode, VpnNodeSummary } from "../lib/types";

interface Props {
  onProfile: () => void;
}

export default function Home({ onProfile }: Props) {
  const user = useStore((s) => s.user);
  const nodes = useStore((s) => s.nodes);
  const setNodes = useStore((s) => s.setNodes);
  const selectedNodeId = useStore((s) => s.selectedNodeId);
  const selectNode = useStore((s) => s.selectNode);
  const conn = useStore((s) => s.conn);
  const connNodeName = useStore((s) => s.connNodeName);
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  const pushToast = useStore((s) => s.pushToast);
  const [pickerOpen, setPickerOpen] = useState(false);

  // 首次进入拉取节点列表。
  useEffect(() => {
    (async () => {
      try {
        const list = await api.listNodes();
        setNodes(list);
        if (!selectedNodeId) {
          const first = list.find((n) => !n.locked && n.status === "online");
          if (first) selectNode(first.id);
        }
      } catch (e) {
        pushToast("error", errText(e));
      }
    })();
  }, [setNodes, selectNode, selectedNodeId, pushToast]);

  const selected: VpnNodeSummary | undefined = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId),
    [nodes, selectedNodeId]
  );

  const onConnectToggle = async () => {
    if (conn === "connected") {
      try {
        await api.disconnect();
      } catch (e) {
        pushToast("error", errText(e));
      }
      return;
    }
    if (!selectedNodeId) {
      pushToast("error", "请先选择线路");
      setPickerOpen(true);
      return;
    }
    try {
      await api.connect(selectedNodeId, mode);
    } catch (e) {
      pushToast("error", errText(e));
    }
  };

  const pickNode = (node: VpnNodeSummary) => {
    selectNode(node.id);
    setPickerOpen(false);
  };

  const switchMode = async (m: NetMode) => {
    setMode(m);
    if (conn === "connected") {
      try {
        await api.switchMode(m);
      } catch (e) {
        pushToast("error", errText(e));
      }
    }
  };

  return (
    <div className="relative flex h-full flex-col px-6 pb-6">
      {/* 顶部：用户入口 + 模式切换 */}
      <div className="flex items-center justify-between py-2">
        <button
          onClick={onProfile}
          className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm transition hover:bg-white/10"
        >
          <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-gradient text-xs font-bold">
            {(user?.nickname || user?.email || "?").slice(0, 1).toUpperCase()}
          </span>
          <span className="max-w-[120px] truncate text-white/80">
            {user?.nickname || user?.email}
          </span>
        </button>
        <div className="flex rounded-lg bg-white/5 p-0.5 text-xs">
          {([
            ["tun", "全局"],
            ["systemproxy", "代理"],
          ] as const).map(([m, label]) => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              className={`rounded-md px-3 py-1 transition ${
                mode === m ? "bg-brand-gradient font-semibold" : "text-white/55"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* 中部：连接按钮 */}
      <div className="flex flex-1 flex-col items-center justify-center gap-6">
        <ConnectButton conn={conn} onClick={onConnectToggle} />
        <div className="text-center text-sm text-white/60">
          {conn === "connected" && connNodeName
            ? `已连接 · ${connNodeName}`
            : "未连接"}
        </div>
      </div>

      {/* 底部：当前线路 + 统计 */}
      <div className="space-y-3">
        <button
          onClick={() => setPickerOpen(true)}
          className="glass flex w-full items-center justify-between rounded-xl px-4 py-3 text-left transition hover:bg-white/10"
        >
          <div className="flex items-center gap-3">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                selected?.status === "online" ? "bg-emerald-400" : "bg-white/30"
              }`}
            />
            <div>
              <div className="text-sm font-medium">
                {selected ? selected.name : "选择线路"}
              </div>
              <div className="text-[11px] text-white/40">
                {selected ? selected.region : "点击选择节点"}
              </div>
            </div>
          </div>
          <span className="text-white/40">›</span>
        </button>
        <StatsBar />
      </div>

      <NodeList
        open={pickerOpen}
        nodes={nodes}
        selectedId={selectedNodeId}
        onPick={pickNode}
        onClose={() => setPickerOpen(false)}
      />
    </div>
  );
}
