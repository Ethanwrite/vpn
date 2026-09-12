import type { ConnState } from "../lib/types";
import EmblemGraphic from "./EmblemGraphic";
const labels = { disconnected: "一键连接", connecting: "取消连接", connected: "断开连接" };
const states = { disconnected: "未连接", connecting: "正在连接", connected: "已连接" };
export default function ConnectButton({ conn, onClick }: { conn: ConnState; onClick: () => void }) {
  return <div className="connection-control">
    <div className={`em ${conn === "connected" ? "is-on" : conn === "connecting" ? "is-busy" : ""}`} aria-hidden="true">
      <EmblemGraphic animated/>
    </div>
    <div className="connection-label" role="status"><i className={conn === "connected" ? "status-online" : "status-idle"}/>{states[conn]}</div>
    <p className="connection-description">{conn === "connected" ? "连接已建立，安心探索" : conn === "connecting" ? "正在建立安全连接" : "当前网络处于空闲状态"}</p>
    <button onClick={onClick} className="btn-primary connect-action">{labels[conn]}</button>
  </div>;
}
