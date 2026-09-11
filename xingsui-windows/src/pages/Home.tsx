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
          className="grid h-10 w-10 place-items-center rounded-brand border border-ink-900/20 bg-paper-raised transition hover:border-ink-900 hover:shadow-block"
          aria-label="打开我的页面"
        >
          <span className="grid h-8 w-8 place-items-center rounded-brand bg-ink-900 text-sm font-bold text-gold-light">
            {(user?.nickname || user?.email || "?").slice(0, 1).toUpperCase()}
          </span>
        </button>
        <div className="flex rounded-brand border border-ink-900/15 bg-paper-raised p-0.5 text-xs">
          {([
            ["global", "全局"],
            ["rule", "规则"],
            ["systemproxy", "代理"],
          ] as const).map(([m, label]) => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              className={`rounded-[2px] px-3 py-1 font-semibold transition ${
                mode === m ? "bg-ink-900 text-paper-raised" : "text-ink-500"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <ConnectButton conn={conn} onClick={onConnectToggle} />
        <div className="text-center text-[13px] text-ink-500">
          {conn === "connected" && connNodeName
            ? `世界已经接通 · ${connNodeName}`
            : conn === "connecting"
            ? "锤子与镰刀正在扣合"
            : "锤子与镰刀分离 · 等待连接"}
        </div>
      </div>

      <div className="space-y-3">
        <button
          onClick={() => setPickerOpen(true)}
          className="card flex w-full items-center justify-between px-4 py-3 text-left transition hover:shadow-block"
        >
          <div className="flex items-center gap-3">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                selected?.status === "online" ? "bg-gold" : "bg-ink-300"
              }`}
            />
            <div>
              <div className="text-sm font-bold text-ink-900">
                {selected ? selected.name : "选择线路"}
              </div>
              <div className="mt-0.5 text-[11px] text-ink-500">
                {selected ? formatNodeDetail(selected) : "点击选择节点"}
              </div>
            </div>
          </div>
          <span className="text-ink-300">›</span>
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
