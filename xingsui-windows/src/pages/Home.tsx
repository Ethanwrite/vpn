import { useEffect, useMemo, useState } from "react";
import ConnectButton from "../components/ConnectButton";
import StatsBar from "../components/StatsBar";
import NodeList from "../components/NodeList";
import { api, CONNECTION_SYNC_ERROR } from "../lib/api";
import { formatNodeDetail } from "../lib/format";
import { useStore } from "../store/useStore";
import type { NetMode, VpnNodeSummary } from "../lib/types";

interface Props {
  onProfile: () => void;
}

function bestNode(nodes: VpnNodeSummary[]): VpnNodeSummary | undefined {
  return nodes
    .filter((n) => !n.locked && n.status === "online")
    .slice()
    .sort((a, b) => {
      return a.load_percent - b.load_percent;
    })[0];
}

function orderNodes(nodes: VpnNodeSummary[]): VpnNodeSummary[] {
  return nodes.slice().sort((a, b) => {
    const availableA = !a.locked && a.status === "online";
    const availableB = !b.locked && b.status === "online";
    if (availableA !== availableB) return availableA ? -1 : 1;
    return a.load_percent - b.load_percent;
  });
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

  useEffect(() => {
    (async () => {
      try {
        const list = orderNodes(await api.listNodes());
        setNodes(list);
        const fastest = bestNode(list);
        if (fastest) selectNode(fastest.id);
      } catch {
        pushToast("error", CONNECTION_SYNC_ERROR);
      }
    })();
  }, [setNodes, selectNode, pushToast]);

  const selected: VpnNodeSummary | undefined = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId),
    [nodes, selectedNodeId]
  );

  const onConnectToggle = async () => {
    if (conn === "connected" || conn === "connecting") {
      try {
        await api.disconnect();
      } catch {
        pushToast("error", CONNECTION_SYNC_ERROR);
      }
      return;
    }

    const fastest = bestNode(nodes);
    const targetNodeId = selectedNodeId || fastest?.id;
    if (!targetNodeId) {
      pushToast("error", "请先选择线路");
      setPickerOpen(true);
      return;
    }

    try {
      if (!selectedNodeId && fastest) {
        selectNode(fastest.id);
      }
      await api.connect(targetNodeId, mode);
    } catch {
      pushToast("error", CONNECTION_SYNC_ERROR);
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
      } catch {
        pushToast("error", CONNECTION_SYNC_ERROR);
      }
    }
  };

  return (
    <div className="relative flex h-full flex-col px-6 pb-6">
      <div className="flex items-center justify-between py-2">
        <button
          onClick={onProfile}
          className="grid h-10 w-10 place-items-center rounded-full border border-white/10 bg-white/5 transition hover:border-brand-glow/50 hover:bg-white/10"
          aria-label="打开我的页面"
        >
          <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-gradient text-sm font-bold shadow-glow">
            {(user?.nickname || user?.email || "?").slice(0, 1).toUpperCase()}
          </span>
        </button>
        <div className="flex rounded-lg bg-white/5 p-0.5 text-xs">
          {([
            ["global", "全局"],
            ["rule", "规则"],
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

      <div className="flex flex-1 flex-col items-center justify-center gap-6">
        <ConnectButton conn={conn} onClick={onConnectToggle} />
        <div className="text-center text-sm text-white/60">
          {conn === "connected" && connNodeName
            ? `已连接 · ${connNodeName}`
            : "未连接"}
        </div>
      </div>

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
                {selected ? formatNodeDetail(selected) : "点击选择节点"}
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
