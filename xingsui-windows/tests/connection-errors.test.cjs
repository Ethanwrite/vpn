const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function load(file, dependencies) {
  const source = fs.readFileSync(file, 'utf8');
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  });
  const exports = {};
  vm.runInNewContext(outputText, { exports, require: (name) => {
    if (!(name in dependencies)) throw new Error(`Unexpected import ${name}`);
    return dependencies[name];
  }});
  return exports;
}

const apiModule = load('src/lib/api.ts', {
  '@tauri-apps/api/core': { invoke: async () => {} },
  '@tauri-apps/api/event': { listen: async () => {} },
});
const exhausted = '免费体验流量已用完，请前往官网开通会员后继续使用';
const expired = '登录已过期，请重新登录后连接';

function homeHarness(rejection, selectedNodeId = 'node-test', locked = false, connected = false) {
  const toasts = [];
  const calls = [];
  const effects = [];
  const state = {
    user: { email: 'test@example.com' },
    nodes: [{ id: 'node-test', status: 'online', locked, load_percent: 0 }],
    selectedNodeId, conn: connected ? 'connected' : 'disconnected', mode: 'global',
    setNodes() {}, selectNode() {}, setMode() {},
    pushToast(kind, text) { toasts.push({ kind, text }); },
  };
  const fail = async (id) => { calls.push(id); throw rejection; };
  const { default: Home } = load('src/pages/Home.tsx', {
    react: { useEffect: (fn) => effects.push(fn), useMemo: (fn) => fn(), useState: () => [false, () => {}] },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
    '../components/ConnectButton': { default: 'ConnectButton' },
    '../components/StatsBar': { default: 'StatsBar' },
    '../components/NodeList': { default: 'NodeList' },
    '../lib/format': { formatNodeDetail: () => '' },
    '../store/useStore': { useStore: (selector) => selector(state) },
    '../lib/api': { ...apiModule, api: { connect: fail, switchMode: fail, disconnect: fail } },
  });
  const tree = Home({ onProfile() {} });
  const find = (node, type) => {
    if (!node || typeof node !== 'object') return;
    if (node.type === type) return node;
    for (const child of [node.props?.children].flat(Infinity)) {
      const match = find(child, type);
      if (match) return match;
    }
  };
  return { toasts, calls, connect: () => find(tree, 'ConnectButton').props.onClick() };
}

test('actual Home connect handler preserves free-quota and expired-login messages', async () => {
  for (const reason of [exhausted, expired]) {
    const h = homeHarness(reason);
    await h.connect();
    assert.equal(h.toasts.at(-1).text, reason);
  }
});

test('stale locked node can ask the server again after membership activation', async () => {
  const h = homeHarness(exhausted, '', true);
  await h.connect();
  assert.equal(h.calls[0], 'node-test');
  assert.equal(h.toasts.at(-1).text, exhausted);
});

test('raw configuration errors stay private in actual Home connect handler', async () => {
  const h = homeHarness('internal-secret-config');
  await h.connect();
  assert.equal(h.toasts.at(-1).text, apiModule.CONNECTION_SYNC_ERROR);
});

test('frontend whitelist handles serialized errors and rejects unknown bodies', () => {
  assert.equal(apiModule.connectionErrorText({ message: exhausted }), exhausted);
  assert.equal(apiModule.connectionErrorText({ message: 'private-token' }), apiModule.CONNECTION_SYNC_ERROR);
});
