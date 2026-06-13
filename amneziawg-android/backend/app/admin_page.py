ADMIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>星隧 Admin</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #060e1c;
      --panel: #0b1a2e;
      --panel2: #0e2038;
      --line: #1e3850;
      --text: #eef7ff;
      --muted: #7a9bb5;
      --cyan: #20e6d2;
      --cyan-dim: rgba(32,230,210,.1);
      --gold: #ffd36a;
      --danger: #ff6b7a;
      --danger-dim: rgba(255,107,122,.1);
      --success: #4ade80;
      --warning: #fbbf24;
    }
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);display:flex;height:100dvh;overflow:hidden;}

    /* ── Sidebar ── */
    nav{width:196px;flex-shrink:0;background:#040c17;border-right:1px solid var(--line);display:flex;flex-direction:column;padding:0;}
    .nav-logo{padding:18px 18px 14px;border-bottom:1px solid var(--line);}
    .nav-logo h1{font-size:16px;color:var(--cyan);letter-spacing:.02em;}
    .nav-logo span{font-size:11px;color:var(--muted);}
    .nav-item{display:flex;align-items:center;gap:9px;padding:11px 18px;color:var(--muted);cursor:pointer;font-size:13px;border-left:3px solid transparent;transition:all .15s;user-select:none;}
    .nav-item:hover{color:var(--text);background:var(--cyan-dim);}
    .nav-item.active{color:var(--cyan);border-left-color:var(--cyan);background:var(--cyan-dim);}
    .nav-icon{font-size:15px;width:18px;text-align:center;}
    .nav-footer{margin-top:auto;padding:14px 18px;border-top:1px solid var(--line);}
    .nav-footer a{color:var(--muted);font-size:12px;text-decoration:none;}
    .nav-footer a:hover{color:var(--danger);}

    /* ── Content ── */
    .content{flex:1;overflow-y:auto;display:flex;flex-direction:column;min-width:0;}
    .content-header{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 22px;display:flex;align-items:center;gap:10px;}
    .content-header h2{font-size:15px;flex:1;}
    .section{padding:18px 22px;display:none;}
    .section.active{display:block;}

    /* ── Stats ── */
    .stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(138px,1fr));gap:10px;margin-bottom:18px;}
    .stat{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:13px 15px;}
    .stat-label{font-size:11px;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:.04em;}
    .stat-value{font-size:20px;font-weight:700;}
    .stat.cyan .stat-value{color:var(--cyan);}
    .stat.gold .stat-value{color:var(--gold);}
    .stat.danger .stat-value{color:var(--danger);}
    .stat.success .stat-value{color:var(--success);}
    .stat.warn .stat-value{color:var(--warning);}

    /* ── Panel / Table ── */
    .panel{background:var(--panel);border:1px solid var(--line);border-radius:9px;overflow:hidden;margin-bottom:18px;}
    .panel-header{padding:12px 15px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;}
    .panel-header h3{font-size:13px;flex:1;}
    table{width:100%;border-collapse:collapse;}
    th,td{padding:10px 14px;text-align:left;font-size:13px;border-bottom:1px solid var(--line);vertical-align:top;}
    th{color:var(--muted);font-weight:600;background:var(--panel);font-size:11px;text-transform:uppercase;letter-spacing:.04em;}
    tr:last-child td{border-bottom:0;}
    tr:hover td{background:var(--panel2);}

    /* ── Controls ── */
    button,select,input,textarea{border:1px solid var(--line);background:#0c1e34;color:var(--text);border-radius:6px;padding:7px 11px;font:inherit;font-size:13px;}
    button{cursor:pointer;transition:border-color .15s,background .15s;white-space:nowrap;}
    button:hover:not(:disabled){border-color:#4a7fa0;}
    button:disabled{opacity:.4;cursor:not-allowed;}
    input,textarea{outline:none;}
    input:focus,textarea:focus{border-color:var(--cyan);}
    select{cursor:pointer;}
    .btn-primary{border-color:var(--cyan);color:var(--cyan);}
    .btn-primary:hover:not(:disabled){background:var(--cyan-dim);}
    .btn-danger{border-color:var(--danger);color:var(--danger);}
    .btn-danger:hover:not(:disabled){background:var(--danger-dim);}
    .btn-sm{padding:4px 9px;font-size:12px;}
    .btn-icon{padding:5px 7px;border-color:transparent;background:transparent;}

    /* ── Form ── */
    .form-grid{display:grid;grid-template-columns:1fr 1fr;gap:11px;}
    .form-group{display:flex;flex-direction:column;gap:4px;}
    .form-group label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em;}
    .form-group input,.form-group select,.form-group textarea{width:100%;}
    .form-actions{display:flex;gap:8px;margin-top:18px;justify-content:flex-end;}
    .full-col{grid-column:1/-1;}

    /* ── Tags ── */
    .tag{display:inline-flex;align-items:center;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:600;line-height:1.4;}
    .tag-gold{color:var(--gold);background:rgba(255,211,106,.1);border:1px solid rgba(255,211,106,.25);}
    .tag-cyan{color:var(--cyan);background:var(--cyan-dim);border:1px solid rgba(32,230,210,.25);}
    .tag-danger{color:var(--danger);background:var(--danger-dim);border:1px solid rgba(255,107,122,.25);}
    .tag-muted{color:var(--muted);background:rgba(122,155,181,.08);border:1px solid rgba(122,155,181,.18);}
    .tag-success{color:var(--success);background:rgba(74,222,128,.08);border:1px solid rgba(74,222,128,.2);}

    /* ── Dot ── */
    .dot{width:8px;height:8px;border-radius:50%;background:#2d4a63;display:inline-block;flex-shrink:0;}
    .dot-online{background:var(--success);box-shadow:0 0 7px rgba(74,222,128,.5);}
    .dot-warn{background:var(--warning);}

    /* ── Progress ── */
    .progress{height:4px;background:var(--line);border-radius:2px;overflow:hidden;margin-top:5px;}
    .progress-fill{height:100%;border-radius:2px;transition:width .4s;}
    .pf-low{background:var(--success);}
    .pf-mid{background:var(--warning);}
    .pf-high{background:var(--danger);}

    /* ── Node cards ── */
    .node-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px;}
    .node-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:15px;}
    .node-card.disabled{opacity:.55;}
    .nc-header{display:flex;align-items:flex-start;gap:9px;margin-bottom:11px;}
    .nc-info{flex:1;min-width:0;}
    .nc-name{font-weight:600;font-size:13px;display:flex;align-items:center;gap:6px;}
    .nc-meta{font-size:11px;color:var(--muted);margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .nc-stats{display:grid;grid-template-columns:1fr 1fr;gap:7px;font-size:12px;margin-bottom:10px;}
    .nc-stat-label{color:var(--muted);font-size:11px;}
    .nc-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;}

    /* ── Toast ── */
    #toasts{position:fixed;top:18px;right:18px;z-index:9999;display:flex;flex-direction:column;gap:7px;pointer-events:none;}
    .toast{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:9px 15px;font-size:13px;max-width:300px;opacity:0;transform:translateX(16px);transition:all .22s;pointer-events:auto;box-shadow:0 4px 16px rgba(0,0,0,.35);}
    .toast.show{opacity:1;transform:translateX(0);}
    .toast-success{border-color:rgba(74,222,128,.35);}
    .toast-error{border-color:rgba(255,107,122,.35);color:var(--danger);}
    .toast-info{border-color:rgba(32,230,210,.25);color:var(--cyan);}

    /* ── Modal ── */
    .overlay{position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:1000;display:none;align-items:center;justify-content:center;padding:18px;}
    .overlay.open{display:flex;}
    .modal{background:var(--panel);border:1px solid var(--line);border-radius:11px;width:100%;max-width:580px;max-height:90dvh;overflow-y:auto;}
    .modal-hdr{padding:15px 18px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;}
    .modal-hdr h3{flex:1;font-size:14px;}
    .modal-body{padding:18px;}
    .modal-ftr{padding:13px 18px;border-top:1px solid var(--line);display:flex;justify-content:flex-end;gap:8px;}

    /* ── Misc ── */
    .toolbar{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap;}
    .actions{display:flex;gap:6px;flex-wrap:wrap;align-items:center;}
    .muted{color:var(--muted);}
    .small{font-size:12px;}
    .empty{color:var(--muted);font-size:13px;padding:18px 14px;}
    @keyframes spin{to{transform:rotate(360deg);}}
    .spin{animation:spin .7s linear infinite;display:inline-block;}

    /* ── Mobile ── */
    @media(max-width:700px){
      body{flex-direction:column;}
      nav{width:100%;height:auto;flex-direction:row;overflow-x:auto;border-right:none;border-bottom:1px solid var(--line);}
      .nav-logo,.nav-footer{display:none;}
      .nav-item{border-left:none;border-bottom:3px solid transparent;padding:11px 14px;flex-direction:column;gap:2px;font-size:10px;}
      .nav-item.active{border-bottom-color:var(--cyan);border-left:none;}
      .content{height:0;flex:1;}
      .form-grid{grid-template-columns:1fr;}
      .node-grid{grid-template-columns:1fr;}
      .stats{grid-template-columns:repeat(2,1fr);}
    }
  </style>
</head>
<body>
  <nav>
    <div class="nav-logo"><h1>星隧</h1><span>Admin Console</span></div>
    <div class="nav-item active" data-sec="dashboard" onclick="go('dashboard')"><span class="nav-icon">📊</span>概览</div>
    <div class="nav-item" data-sec="orders" onclick="go('orders')"><span class="nav-icon">📋</span>订单</div>
    <div class="nav-item" data-sec="users" onclick="go('users')"><span class="nav-icon">👥</span>用户</div>
    <div class="nav-item" data-sec="nodes" onclick="go('nodes')"><span class="nav-icon">🌐</span>节点</div>
    <div class="nav-item" data-sec="finance" onclick="go('finance')"><span class="nav-icon">💰</span>财务</div>
    <div class="nav-footer"><a href="/admin/logout">退出登录</a></div>
  </nav>

  <div class="content">
    <div class="content-header">
      <h2 id="secTitle">概览</h2>
      <button id="arBtn" class="btn-primary" onclick="toggleAR()" title="自动刷新">⟳ 自动刷新</button>
      <button id="rfBtn" onclick="manualRefresh()">刷新</button>
    </div>

    <div class="section active" id="sec-dashboard">
      <div class="stats" id="stats"></div>
      <div class="stats" id="sysStats"></div>
    </div>

    <div class="section" id="sec-orders">
      <div class="toolbar">
        <select id="orderStatus" onchange="loadOrders()">
          <option value="pending_confirm">待确认</option>
          <option value="pending_payment">待支付</option>
          <option value="completed">已完成</option>
          <option value="rejected">已驳回</option>
          <option value="">全部</option>
        </select>
      </div>
      <div class="panel"><table>
        <thead><tr><th>订单</th><th>用户</th><th>金额</th><th>渠道</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>
        <tbody id="orders"></tbody>
      </table></div>
    </div>

    <div class="section" id="sec-users">
      <div class="toolbar">
        <input id="userQ" placeholder="搜索邮箱" oninput="loadUsers()" style="width:210px"/>
        <span class="muted small">最近 500 位用户</span>
      </div>
      <div class="panel"><table>
        <thead><tr><th>邮箱</th><th>注册</th><th>VIP</th><th>到期</th><th>最近登录</th><th>操作</th></tr></thead>
        <tbody id="users"></tbody>
      </table></div>
    </div>

    <div class="section" id="sec-nodes">
      <div class="toolbar">
        <span class="muted small">边缘节点池 · 实时健康监控</span>
        <button class="btn-primary" onclick="openNodeModal(null)">＋ 新增节点</button>
      </div>
      <div class="node-grid" id="nodes"></div>
    </div>

    <div class="section" id="sec-finance">
      <div class="form-grid" style="margin-bottom:18px">
        <div class="panel">
          <div class="panel-header"><h3>收款码配置</h3></div>
          <div id="paySettings" style="padding:12px"></div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <h3>提现审核</h3>
            <select id="wdStatus" onchange="loadWithdrawals()" style="width:auto;padding:4px 8px;font-size:12px">
              <option value="pending">待审核</option><option value="completed">已完成</option>
              <option value="rejected">已驳回</option><option value="">全部</option>
            </select>
          </div>
          <table><thead><tr><th>用户</th><th>金额</th><th>状态</th><th>操作</th></tr></thead>
          <tbody id="withdrawals"></tbody></table>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header"><h3>优惠活动</h3></div>
        <div id="promotions" style="padding:12px"></div>
      </div>
    </div>
  </div>

  <!-- Node modal -->
  <div class="overlay" id="nodeOverlay" onclick="if(event.target===this)closeNodeModal()">
    <div class="modal">
      <div class="modal-hdr"><h3 id="nodeModalTitle">新增节点</h3><button class="btn-icon" onclick="closeNodeModal()">✕</button></div>
      <div class="modal-body">
        <div class="form-grid">
          <div class="form-group"><label>节点 ID <span class="muted">(留空自动生成)</span></label><input id="node_id" placeholder="auto"/></div>
          <div class="form-group"><label>名称 *</label><input id="node_name" placeholder="大阪 CN2 GIA"/></div>
          <div class="form-group"><label>区域</label><input id="node_region" value="智能线路"/></div>
          <div class="form-group"><label>入口 Endpoint *</label><input id="node_endpoint" placeholder="1.2.3.4:443"/></div>
          <div class="form-group"><label>Agent 主机 *</label><input id="node_agent_host" placeholder="1.2.3.4"/></div>
          <div class="form-group"><label>Agent 端口</label><input id="node_agent_port" type="number" value="51821"/></div>
          <div class="form-group full-col"><label>服务端公钥 *</label><input id="node_server_public_key" placeholder="base64"/></div>
          <div class="form-group"><label>客户端网段</label><input id="node_client_network" value="10.66.66.0/24"/></div>
          <div class="form-group"><label>DNS</label><input id="node_dns" value="1.1.1.1"/></div>
          <div class="form-group"><label>AllowedIPs</label><input id="node_allowed_ips" value="0.0.0.0/0"/></div>
          <div class="form-group"><label>Keepalive (秒)</label><input id="node_keepalive" type="number" value="25"/></div>
          <div class="form-group"><label>MTU</label><input id="node_mtu" type="number" value="1420"/></div>
          <div class="form-group"><label>权重</label><input id="node_weight" type="number" value="100"/></div>
          <div class="form-group"><label>最大客户端 (0=不限)</label><input id="node_max_clients" type="number" value="0"/></div>
          <div class="form-group"><label>仅 VIP</label><select id="node_vip_only"><option value="false">否</option><option value="true">是</option></select></div>
          <div class="form-group"><label>启用</label><select id="node_enabled"><option value="true">是</option><option value="false">否</option></select></div>
          <div class="form-group full-col"><label>混淆参数 JSON (需与边缘节点 init 脚本输出一致)</label><textarea id="node_params" rows="3" placeholder='{"Jc":"4","S1":"86","H1":"..."}'></textarea></div>
        </div>
      </div>
      <div class="modal-ftr"><button onclick="closeNodeModal()">取消</button><button class="btn-primary" onclick="saveNode()">保存节点</button></div>
    </div>
  </div>

  <div id="toasts"></div>

  <script>
    // ── utils ─────────────────────────────────────────────────────────────────
    const money = c => `¥${(c/100).toFixed(c%100===0?0:2)}`;
    const fmtDate = v => v ? new Date(v).toLocaleString('zh-CN',{hour12:false}) : '-';
    const fmtBytes = b => { const u=['B','KB','MB','GB','TB'];let v=Number(b||0),i=0;while(v>=1024&&i<u.length-1){v/=1024;i++;}return `${v.toFixed(i===0?0:1)} ${u[i]}`; };
    const stText = {pending:'待审核',pending_payment:'待支付',pending_confirm:'待确认',completed:'已完成',rejected:'已驳回',cancelled:'已取消'};
    const vipText = {active:'VIP 有效',expired:'已过期',inactive:'未开通'};
    const vipCls = {active:'tag-gold',expired:'tag-danger',inactive:'tag-muted'};

    function toast(msg, type='info', ms=3200) {
      const el = Object.assign(document.createElement('div'),{className:`toast toast-${type}`,textContent:msg});
      document.getElementById('toasts').appendChild(el);
      requestAnimationFrame(()=>el.classList.add('show'));
      setTimeout(()=>{ el.classList.remove('show'); setTimeout(()=>el.remove(),250); }, ms);
    }

    async function api(path, opts) {
      const r = await fetch(path,{headers:{'Content-Type':'application/json'},...opts});
      if(!r.ok) throw new Error(await r.text());
      return r.json();
    }

    // ── navigation ────────────────────────────────────────────────────────────
    const secNames = {dashboard:'概览',orders:'订单',users:'用户',nodes:'节点',finance:'财务'};
    let curSec = 'dashboard';

    function go(id) {
      document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
      document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
      document.getElementById(`sec-${id}`).classList.add('active');
      document.querySelector(`[data-sec="${id}"]`).classList.add('active');
      document.getElementById('secTitle').textContent = secNames[id]||id;
      curSec = id; loadSec(id);
    }

    function loadSec(id) {
      if(id==='dashboard'){loadDash();loadSys();}
      else if(id==='orders') loadOrders();
      else if(id==='users') loadUsers();
      else if(id==='nodes') loadNodes();
      else if(id==='finance'){loadPaySettings();loadWithdrawals();loadPromotions();}
    }

    // ── auto-refresh ──────────────────────────────────────────────────────────
    let arTimer=null, arSecs=0;
    function toggleAR() {
      if(arTimer){ clearInterval(arTimer); arTimer=null; document.getElementById('arBtn').textContent='⟳ 自动刷新'; return; }
      arSecs=30;
      arTimer=setInterval(()=>{ arSecs--; if(arSecs<=0){arSecs=30;loadSec(curSec);} document.getElementById('arBtn').textContent=`⟳ ${arSecs}s`; },1000);
    }

    async function manualRefresh() {
      const btn=document.getElementById('rfBtn');
      btn.disabled=true; btn.innerHTML='<span class="spin">⟳</span>';
      try{await Promise.resolve(loadSec(curSec));}catch(e){toast(e.message,'error');}
      setTimeout(()=>{btn.disabled=false;btn.textContent='刷新';},600);
    }

    // ── dashboard ─────────────────────────────────────────────────────────────
    async function loadDash() {
      const d = await api('/admin/dashboard');
      document.getElementById('stats').innerHTML=[
        ['总用户',d.total_users,'cyan'],['今日新增',d.today_new_users,''],
        ['在线用户',d.online_users,'success'],['VIP 用户',d.vip_users,'gold'],
        ['即将到期',d.expiring_soon_users,d.expiring_soon_users>0?'warn':''],
        ['总订单',d.total_orders,''],
        ['待确认',d.pending_confirm_orders,d.pending_confirm_orders>0?'danger':''],
        ['收入',money(d.revenue_cents),'gold'],
        ['待提现',`${d.pending_withdrawal_count} 笔`,d.pending_withdrawal_count>0?'warn':''],
        ['有效邀请',d.paid_invite_count,'']
      ].map(([l,v,c])=>`<div class="stat ${c}"><div class="stat-label">${l}</div><div class="stat-value">${v}</div></div>`).join('');
    }

    async function loadSys() {
      const d = await api('/admin/system-health');
      const cpuC=d.cpu_load_1m>2?'danger':d.cpu_load_1m>1?'warn':'success';
      const memC=d.memory_used_percent>85?'danger':d.memory_used_percent>65?'warn':'';
      document.getElementById('sysStats').innerHTML=[
        ['CPU 负载',d.cpu_load_1m,cpuC],['内存',`${d.memory_used_percent}%`,memC],
        ['入站',fmtBytes(d.network_rx_bytes),''],['出站',fmtBytes(d.network_tx_bytes),''],
        ['活跃设备',d.active_vpn_devices,''],['节点 Peer',d.wireguard_peers,''],
        ['控制面',d.node_status==='online'?'在线':'离线',d.node_status==='online'?'success':'danger']
      ].map(([l,v,c])=>`<div class="stat ${c}"><div class="stat-label">${l}</div><div class="stat-value">${v}</div></div>`).join('');
    }

    // ── orders ────────────────────────────────────────────────────────────────
    async function loadOrders() {
      const s=document.getElementById('orderStatus').value;
      const rows=await api(`/admin/orders${s?`?status=${s}`:''}`);
      document.getElementById('orders').innerHTML=rows.map(o=>`
        <tr>
          <td><strong>${o.order_no}</strong><br><span class="muted small">${o.id}</span></td>
          <td><strong>${o.user_email||o.user_id}</strong></td>
          <td>${money(o.pay_amount_cents)}<br><span class="muted small">原 ${money(o.original_amount_cents)}</span></td>
          <td>${o.pay_channel==='wechat'?'微信':'支付宝'}</td>
          <td>${stText[o.status]||o.status}</td>
          <td class="muted small">${fmtDate(o.created_at)}</td>
          <td><div class="actions">
            <button class="btn-primary btn-sm" onclick="confirmOrder('${o.id}')" ${o.status==='completed'?'disabled':''}>确认开通</button>
            <button class="btn-danger btn-sm" onclick="rejectOrder('${o.id}')" ${o.status==='completed'||o.status==='rejected'?'disabled':''}>驳回</button>
          </div></td>
        </tr>`).join('')||`<tr><td colspan="7" class="empty">暂无订单</td></tr>`;
    }

    async function confirmOrder(id){
      try{await api(`/admin/orders/${id}/confirm`,{method:'POST',body:JSON.stringify({reviewed_by:'admin',note:'人工确认到账'})});toast('已确认开通 VIP','success');loadOrders();loadDash();}
      catch(e){toast(e.message,'error');}
    }
    async function rejectOrder(id){
      const note=prompt('驳回原因','未查询到收款记录');if(note===null)return;
      try{await api(`/admin/orders/${id}/reject`,{method:'POST',body:JSON.stringify({reviewed_by:'admin',note})});toast('订单已驳回','info');loadOrders();}
      catch(e){toast(e.message,'error');}
    }

    // ── users ─────────────────────────────────────────────────────────────────
    async function loadUsers() {
      const q=document.getElementById('userQ').value.trim();
      const rows=await api(`/admin/users${q?`?q=${encodeURIComponent(q)}`:''}`);
      document.getElementById('users').innerHTML=rows.map(u=>`
        <tr>
          <td><strong>${u.email}</strong><br><span class="muted small">${u.id}</span></td>
          <td class="muted small">${fmtDate(u.created_at)}</td>
          <td><span class="tag ${vipCls[u.vip_status]||'tag-muted'}">${vipText[u.vip_status]||u.vip_status}</span></td>
          <td class="small">${fmtDate(u.vip_expired_at)}</td>
          <td class="small">${fmtDate(u.last_login_at)}</td>
          <td><div class="actions">
            <button class="btn-sm btn-primary" onclick="grantVip('${u.id}','${u.email.replace(/'/g,"\\'")}')">授 VIP</button>
            ${u.vip_status==='active'?`<button class="btn-sm btn-danger" onclick="revokeVip('${u.id}')">撤销</button>`:''}
          </div></td>
        </tr>`).join('')||`<tr><td colspan="6" class="empty">暂无用户</td></tr>`;
    }

    async function grantVip(id, email) {
      const days=prompt(`为 ${email} 授予 VIP 天数：`,'30');
      if(!days||isNaN(Number(days)))return;
      try{await api(`/admin/users/${id}/grant-vip`,{method:'POST',body:JSON.stringify({days:Number(days)})});toast('VIP 已授予','success');loadUsers();}
      catch(e){toast(e.message,'error');}
    }
    async function revokeVip(id) {
      if(!confirm('确认撤销该用户 VIP？'))return;
      try{await api(`/admin/users/${id}/revoke-vip`,{method:'POST',body:'{}',});toast('VIP 已撤销','info');loadUsers();}
      catch(e){toast(e.message,'error');}
    }

    // ── nodes ─────────────────────────────────────────────────────────────────
    let _nc={};

    function loadPct(peers,max){if(!max)return null;return Math.min(Math.round(peers/max*100),100);}
    function loadBar(pct){
      if(pct===null)return '<span class="muted small">不限</span>';
      const cls=pct<60?'pf-low':pct<85?'pf-mid':'pf-high';
      return `<span class="small">${pct}%</span><div class="progress"><div class="progress-fill ${cls}" style="width:${pct}%"></div></div>`;
    }

    async function loadNodes(){
      const rows=await api('/admin/nodes');
      _nc={};rows.forEach(n=>_nc[n.id]=n);
      const el=document.getElementById('nodes');
      if(!rows.length){el.innerHTML='<p class="muted" style="padding:20px">暂无节点，点击「新增节点」添加边缘节点。</p>';return;}
      el.innerHTML=rows.map(n=>{
        const pct=loadPct(n.peer_count,n.max_clients);
        const hb=n.last_heartbeat_at?fmtDate(n.last_heartbeat_at):'无心跳';
        return `<div class="node-card ${n.enabled?'':'disabled'}">
          <div class="nc-header">
            <span class="dot ${n.online?'dot-online':''}"></span>
            <div class="nc-info">
              <div class="nc-name">${n.name}${n.vip_only?' <span class="tag tag-gold">VIP</span>':''}</div>
              <div class="nc-meta">${n.region} · ${n.endpoint}</div>
            </div>
            <span class="tag ${n.online?'tag-success':'tag-muted'}" style="margin-left:auto">${n.online?'在线':'离线'}</span>
          </div>
          <div class="nc-stats">
            <div><div class="nc-stat-label">Peers / 上限</div><div>${n.peer_count}${n.max_clients?'/'+n.max_clients:' (不限)'}</div></div>
            <div><div class="nc-stat-label">权重</div><div>${n.weight}</div></div>
            <div><div class="nc-stat-label">CPU</div><div>${n.cpu_load||'-'}</div></div>
            <div><div class="nc-stat-label">内存</div><div>${n.mem_used_percent!=null?n.mem_used_percent+'%':'-'}</div></div>
          </div>
          <div style="margin-bottom:10px"><div class="nc-stat-label">负载</div>${loadBar(pct)}</div>
          <div class="muted small" style="margin-bottom:10px">Agent: ${n.agent_host}:${n.agent_port} · 心跳: ${hb}</div>
          <div class="nc-actions">
            <button class="btn-sm" onclick="openNodeModal('${n.id}')">编辑</button>
            <button class="btn-sm ${n.enabled?'btn-danger':'btn-primary'}" onclick="toggleNode('${n.id}',${!n.enabled})">${n.enabled?'停用':'启用'}</button>
            <button class="btn-danger btn-sm" onclick="deleteNode('${n.id}')">删除</button>
          </div>
        </div>`;
      }).join('');
    }

    let _editNid=null;
    function openNodeModal(nid){
      _editNid=nid; const n=nid?_nc[nid]:null;
      document.getElementById('nodeModalTitle').textContent=n?'编辑节点':'新增节点';
      document.getElementById('node_id').value=n?.id||'';
      document.getElementById('node_id').readOnly=!!n;
      document.getElementById('node_name').value=n?.name||'';
      document.getElementById('node_region').value=n?.region||'智能线路';
      document.getElementById('node_endpoint').value=n?.endpoint||'';
      document.getElementById('node_agent_host').value=n?.agent_host||'';
      document.getElementById('node_agent_port').value=n?.agent_port??51821;
      document.getElementById('node_server_public_key').value=n?.server_public_key||'';
      document.getElementById('node_client_network').value=n?.client_network||'10.66.66.0/24';
      document.getElementById('node_dns').value=n?.dns||'1.1.1.1';
      document.getElementById('node_allowed_ips').value=n?.allowed_ips||'0.0.0.0/0';
      document.getElementById('node_keepalive').value=n?.persistent_keepalive??25;
      document.getElementById('node_mtu').value=n?.mtu??1420;
      document.getElementById('node_weight').value=n?.weight??100;
      document.getElementById('node_max_clients').value=n?.max_clients??0;
      document.getElementById('node_vip_only').value=n?.vip_only?'true':'false';
      document.getElementById('node_enabled').value=(n?n.enabled:true)?'true':'false';
      document.getElementById('node_params').value=n?JSON.stringify(n.params||{},null,2):'{}';
      document.getElementById('nodeOverlay').classList.add('open');
    }
    function closeNodeModal(){document.getElementById('nodeOverlay').classList.remove('open');}

    async function saveNode(){
      let params={};
      const raw=document.getElementById('node_params').value.trim();
      if(raw){try{params=JSON.parse(raw);}catch(e){toast('混淆参数 JSON 格式有误','error');return;}}
      const g=id=>document.getElementById(id).value.trim();
      const body={
        name:g('node_name'),region:g('node_region')||'智能线路',endpoint:g('node_endpoint'),
        agent_host:g('node_agent_host'),agent_port:Number(g('node_agent_port')||51821),
        server_public_key:g('node_server_public_key'),client_network:g('node_client_network'),
        dns:g('node_dns'),allowed_ips:g('node_allowed_ips'),
        persistent_keepalive:Number(g('node_keepalive')||25),mtu:Number(g('node_mtu')||1420),
        params,weight:Number(g('node_weight')||100),
        vip_only:document.getElementById('node_vip_only').value==='true',
        max_clients:Number(g('node_max_clients')||0),
        enabled:document.getElementById('node_enabled').value==='true'
      };
      if(!body.name||!body.endpoint||!body.agent_host||!body.server_public_key){toast('名称、入口、Agent 主机与服务端公钥为必填项','error');return;}
      try{
        if(_editNid) await api(`/admin/nodes/${_editNid}`,{method:'PUT',body:JSON.stringify(body)});
        else{ const id=document.getElementById('node_id').value.trim(); await api('/admin/nodes',{method:'POST',body:JSON.stringify({...body,id:id||null})}); }
        closeNodeModal();toast('节点已保存','success');loadNodes();
      }catch(e){toast(e.message,'error');}
    }

    async function toggleNode(id,enabled){
      const n=_nc[id];if(!n){toast('请先刷新节点列表','error');return;}
      const{params,params_fingerprint,status,online,peer_count,cpu_load,mem_used_percent,last_heartbeat_at,created_at,updated_at,...body}=n;
      body.params=params;body.enabled=enabled;
      try{await api(`/admin/nodes/${id}`,{method:'PUT',body:JSON.stringify(body)});toast(enabled?'节点已启用':'节点已停用','success');loadNodes();}
      catch(e){toast(e.message,'error');}
    }

    async function deleteNode(id){
      if(!confirm(`确认删除节点 ${id}？`))return;
      const r=await fetch(`/admin/nodes/${id}`,{method:'DELETE'});
      if(!r.ok&&r.status!==204){toast(await r.text(),'error');return;}
      toast('节点已删除','info');loadNodes();
    }

    // ── finance ───────────────────────────────────────────────────────────────
    async function loadPaySettings(){
      const rows=await api('/admin/payment-settings');
      document.getElementById('paySettings').innerHTML=rows.map(s=>`
        <div style="display:flex;gap:8px;align-items:center;margin-bottom:9px">
          <span style="width:48px;font-size:13px;flex-shrink:0">${s.channel==='wechat'?'微信':'支付宝'}</span>
          <input id="qr_${s.channel}" value="${s.qr_url}" style="flex:1"/>
          <button class="btn-primary btn-sm" onclick="savePaySetting('${s.channel}')">保存</button>
        </div>`).join('')||'<p class="muted small">暂无配置</p>';
    }

    async function savePaySetting(ch){
      const qr=document.getElementById(`qr_${ch}`).value;
      try{await api(`/admin/payment-settings/${ch}`,{method:'PUT',body:JSON.stringify({display_name:ch==='wechat'?'微信收款码':'支付宝收款码',qr_url:qr,enabled:true})});toast('收款码已保存','success');}
      catch(e){toast(e.message,'error');}
    }

    function toLocalDT(v){const d=new Date(v),p=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;}

    async function loadPromotions(){
      const rows=await api('/admin/promotions');
      document.getElementById('promotions').innerHTML=rows.map(r=>`
        <div style="display:grid;grid-template-columns:1.4fr .65fr .7fr .55fr auto;gap:8px;align-items:center;padding:7px 0;border-bottom:1px solid var(--line)">
          <input id="pn_${r.id}" value="${r.name}"/>
          <input id="pp_${r.id}" type="number" min="1" value="${r.promo_price_cents/100}" placeholder="价格"/>
          <input id="pe_${r.id}" type="datetime-local" value="${toLocalDT(r.ends_at)}"/>
          <select id="ps_${r.id}"><option value="active" ${r.status==='active'?'selected':''}>启用</option><option value="inactive" ${r.status!=='active'?'selected':''}>停用</option></select>
          <button class="btn-primary btn-sm" onclick="savePromo('${r.id}','${r.starts_at}','${r.plan_id}')">保存</button>
        </div>`).join('')||'<p class="muted small">暂无优惠活动</p>';
    }

    async function savePromo(id,sa,pid){
      const py=Number(document.getElementById(`pp_${id}`).value||0);
      const ea=new Date(document.getElementById(`pe_${id}`).value);
      try{
        await api(`/admin/promotions/${id}`,{method:'PUT',body:JSON.stringify({name:document.getElementById(`pn_${id}`).value,tag:'限时特惠',plan_id:pid,starts_at:sa,ends_at:ea.toISOString(),promo_price_cents:Math.round(py*100),invite_extra_discount_cents:500,stackable:false,new_user_only:true,countdown_enabled:true,status:document.getElementById(`ps_${id}`).value})});
        toast('优惠活动已保存','success');
      }catch(e){toast(e.message,'error');}
    }

    async function loadWithdrawals(){
      const s=document.getElementById('wdStatus').value;
      const rows=await api(`/admin/withdrawals${s?`?status=${s}`:''}`);
      document.getElementById('withdrawals').innerHTML=rows.map(r=>`
        <tr>
          <td><strong>${r.user_email||r.user_id}</strong></td>
          <td>${money(r.amount_cents)}</td>
          <td>${stText[r.status]||r.status}</td>
          <td><div class="actions">
            <button class="btn-primary btn-sm" onclick="approveWd('${r.id}')" ${r.status!=='pending'?'disabled':''}>打款</button>
            <button class="btn-danger btn-sm" onclick="rejectWd('${r.id}')" ${r.status!=='pending'?'disabled':''}>驳回</button>
          </div></td>
        </tr>`).join('')||`<tr><td colspan="4" class="empty">暂无提现申请</td></tr>`;
    }

    async function approveWd(id){
      try{await api(`/admin/withdrawals/${id}/approve`,{method:'POST',body:JSON.stringify({reviewed_by:'admin',note:'人工确认已打款'})});toast('提现已确认打款','success');loadWithdrawals();}
      catch(e){toast(e.message,'error');}
    }
    async function rejectWd(id){
      const note=prompt('驳回原因','提现账号信息不完整');if(note===null)return;
      try{await api(`/admin/withdrawals/${id}/reject`,{method:'POST',body:JSON.stringify({reviewed_by:'admin',note})});toast('提现已驳回','info');loadWithdrawals();}
      catch(e){toast(e.message,'error');}
    }

    // ── init ──────────────────────────────────────────────────────────────────
    go('dashboard');
  </script>
</body>
</html>"""
