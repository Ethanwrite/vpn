import json

from app.payment_config import PAYMENT_PAGE_CONFIG


PAYMENT_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#f5fffc" />
  <title>星隧支付</title>
  <style>
    :root { color-scheme: light; --ink: #102033; --muted: #69798b; --line: #d9eeeb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; color: var(--ink); background: radial-gradient(circle at 88% 4%, rgba(45,215,239,.22), transparent 28%), radial-gradient(circle at 8% 20%, rgba(25,197,162,.15), transparent 25%), linear-gradient(180deg, #f8fffd, #eefaff 55%, #fff); }
    button, a { font: inherit; }
    .shell { width: min(100% - 28px, 560px); margin: 0 auto; padding: 18px 0 calc(30px + env(safe-area-inset-bottom)); }
    .top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
    .brand { display: flex; align-items: center; gap: 9px; color: #132b68; font-size: 20px; font-weight: 900; text-decoration: none; }
    .mark { width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(135deg, #112764, #2459e7 45%, #23d4ee 75%, #b4fff1); box-shadow: 0 9px 24px rgba(25,197,162,.25); }
    .back { color: #426071; font-size: 14px; font-weight: 800; text-decoration: none; }
    .card { padding: 22px; border: 1px solid rgba(217,238,235,.95); border-radius: 20px; background: rgba(255,255,255,.94); box-shadow: 0 22px 60px rgba(38,89,110,.12); backdrop-filter: blur(16px); }
    .eyebrow { margin: 0 0 7px; color: #0c9d84; font-size: 13px; font-weight: 900; }
    h1 { margin: 0; color: #132b68; font-size: 25px; }
    .summary { display: flex; align-items: end; justify-content: space-between; gap: 14px; margin: 20px 0; padding: 16px; border-radius: 14px; background: linear-gradient(135deg, #edf9f6, #edf7ff); }
    .planName { margin: 0 0 5px; font-size: 18px; font-weight: 900; }
    .planMeta { margin: 0; color: var(--muted); font-size: 13px; }
    .price { color: #0b9e84; font-size: 29px; font-weight: 950; white-space: nowrap; }
    .price small { font-size: 14px; }
    .payButtons { display: grid; gap: 11px; }
    .payButton { min-height: 52px; border: 0; border-radius: 13px; color: #fff; font-weight: 900; cursor: pointer; box-shadow: 0 12px 26px rgba(22,70,88,.12); }
    .payButton:disabled { cursor: wait; opacity: .68; }
    .wechat { background: linear-gradient(135deg, #15b764, #08a94d); }
    .alipay { background: linear-gradient(135deg, #1688ff, #1768e8); }
    .status { min-height: 22px; margin: 12px 0 0; color: var(--muted); font-size: 13px; line-height: 1.6; text-align: center; }
    .status.error { color: #d54848; }
    .status.ok { color: #0b8f78; }
    .fallback { margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--line); }
    .fallback h2 { margin: 0 0 5px; color: #132b68; font-size: 18px; }
    .fallback > p { margin: 0 0 14px; color: var(--muted); font-size: 13px; line-height: 1.6; }
    .qrGrid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .qrCard { padding: 11px; border: 1px solid var(--line); border-radius: 14px; background: #fff; text-align: center; }
    .qrCard img { display: block; width: 100%; aspect-ratio: 1; object-fit: contain; border-radius: 9px; background: #f7fafb; }
    .qrCard strong { display: block; margin-top: 9px; font-size: 14px; }
    .notice { margin: 18px 0 0; padding: 13px 14px; border: 1px solid #ffe0a6; border-radius: 12px; background: #fff8e9; color: #714900; font-size: 13px; font-weight: 800; line-height: 1.7; }
    .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 13px; }
    .actions button, .actions a { min-height: 44px; display: flex; align-items: center; justify-content: center; border-radius: 11px; font-weight: 900; text-decoration: none; }
    .done { border: 0; background: linear-gradient(135deg, #17c7a8, #43c8f4); color: #062430; cursor: pointer; }
    .support { border: 1px solid var(--line); background: #fff; color: #132b68; }
    .submitToast { position: fixed; z-index: 30; top: calc(18px + env(safe-area-inset-top)); left: 50%; width: min(calc(100% - 28px), 520px); padding: 14px 16px; border-radius: 13px; background: #102f47; color: #fff; font-size: 14px; font-weight: 800; line-height: 1.6; text-align: center; box-shadow: 0 16px 44px rgba(6,31,48,.28); opacity: 0; pointer-events: none; transform: translate(-50%, -18px); transition: .2s ease; }
    .submitToast.active { opacity: 1; transform: translate(-50%, 0); }
    .submitToast.error { background: #b93838; }
    @media (max-width: 380px) { .card { padding: 18px; } .summary { align-items: start; flex-direction: column; } .qrGrid, .actions { grid-template-columns: 1fr; } .qrCard img { width: min(100%, 260px); margin: 0 auto; } }
  </style>
</head>
<body>
  <main class="shell">
    <div class="top"><a class="brand" href="/"><span class="mark"></span><span>星隧</span></a><a class="back" href="/vip">返回套餐</a></div>
    <section class="card">
      <p class="eyebrow">安全支付 · 人工到账确认</p>
      <h1>选择支付方式</h1>
      <div class="summary"><div><p class="planName" id="planName">正在加载套餐...</p><p class="planMeta" id="planMeta">请稍候</p></div><div class="price"><span id="amount">--</span><small> 元</small></div></div>
      <div class="payButtons"><button class="payButton wechat" type="button" data-channel="wechat">微信支付</button><button class="payButton alipay" type="button" data-channel="alipay">支付宝支付</button></div>
      <p class="status" id="status">点击支付按钮后将尝试打开对应支付 App。</p>
      <div class="fallback">
        <h2>无法跳转？请扫码支付</h2>
        <div class="qrGrid"><div class="qrCard"><img id="wechatQr" alt="微信收款二维码" /><strong>微信支付</strong></div><div class="qrCard"><img id="alipayQr" alt="支付宝收款二维码" /><strong>支付宝支付</strong></div></div>
      </div>
      <p class="notice">支付完成后，点“我已经完成支付”提交订单。</p>
      <div class="actions"><button class="done" id="paymentDone" type="button">我已经完成支付</button><a class="support" id="supportLink" target="_blank" rel="noopener noreferrer">联系客服</a></div>
    </section>
  </main>
  <div class="submitToast" id="submitToast" role="alert" aria-live="assertive"></div>
  <script>
    const config = __PAYMENT_CONFIG__;
    const params = new URLSearchParams(location.search);
    const planId = params.get('plan_id') || 'plan_month';
    const token = localStorage.getItem('xingsui_token') || '';
    const status = document.getElementById('status');
    let selectedPlan = null;
    let selectedPromotion = null;
    let currentOrder = JSON.parse(localStorage.getItem('xingsui_payment_order') || 'null');
    const money = (cents) => { const value = cents / 100; return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0$/, ''); };
    const authHeaders = () => token ? { Authorization: `Bearer ${token}` } : {};
    const setStatus = (message, type = '') => { status.textContent = message; status.className = `status ${type}`.trim(); };
    const showSubmitToast = (message, type = '') => {
      const toast = document.getElementById('submitToast');
      toast.textContent = message;
      toast.className = `submitToast active ${type}`.trim();
    };
    async function api(path, options = {}) {
      const headers = { Accept: 'application/json', ...(options.headers || {}), ...authHeaders() };
      if (options.body) headers['Content-Type'] = 'application/json; charset=utf-8';
      const response = await fetch(path, { ...options, headers });
      const text = await response.text();
      const data = text ? JSON.parse(text) : null;
      if (!response.ok) { const detail = data?.detail?.message || data?.detail || data?.message || '请求失败，请稍后重试。'; throw new Error(typeof detail === 'string' ? detail : '请求失败，请稍后重试。'); }
      return data;
    }
    async function loadPlan() {
      try {
        const [plans, promotion] = await Promise.all([api('/plans'), api('/promotions/active').catch(() => null)]);
        selectedPlan = plans.find(plan => plan.id === planId);
        if (!selectedPlan) throw new Error('套餐不存在，请返回重新选择。');
        selectedPromotion = promotion?.plan_id === selectedPlan.id ? promotion : null;
        const amount = selectedPromotion?.promo_price_cents || selectedPlan.sale_price_cents;
        document.getElementById('planName').textContent = selectedPlan.name;
        document.getElementById('planMeta').textContent = `${selectedPlan.duration_days} 天会员 · 不限流量 · 不限速`;
        document.getElementById('amount').textContent = money(amount);
      } catch (error) { setStatus(error.message, 'error'); document.querySelectorAll('[data-channel]').forEach(button => button.disabled = true); }
    }
    function paymentTarget(channel) {
      const payment = config[channel];
      const userAgent = navigator.userAgent || '';
      if (/Android/i.test(userAgent) && payment.android_intent) return payment.android_intent;
      if (channel === 'alipay' && /iPhone|iPad|iPod/i.test(userAgent) && payment.universal_link) return payment.universal_link;
      return payment.deep_link;
    }
    function launchPayment(channel, target) {
      let pageHidden = false;
      const onVisibilityChange = () => { if (document.hidden) pageHidden = true; };
      document.addEventListener('visibilitychange', onVisibilityChange, { once: true });
      const link = document.createElement('a');
      link.href = target;
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => {
        if (!pageHidden) {
          const message = channel === 'wechat'
            ? '微信未能直接打开，请在微信中扫描下方收款码。'
            : `${config[channel].label}未能自动打开，请使用下方二维码付款。`;
          setStatus(message, 'error');
          if (channel === 'wechat') document.querySelector('.fallback').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 1800);
    }
    function startPayment(channel) {
      if (!token) { location.href = '/login'; return; }
      if (!selectedPlan) return;
      const target = paymentTarget(channel);
      if (!target) { setStatus('支付跳转暂未配置，请使用下方二维码完成付款。', 'error'); return; }
      currentOrder = null;
      localStorage.removeItem('xingsui_payment_order');
      localStorage.setItem('xingsui_pending_payment', JSON.stringify({
        plan_id: selectedPlan.id,
        promotion_id: selectedPromotion?.id || null,
        pay_channel: channel,
      }));
      setStatus('正在打开支付 App；支付后请返回本页提交订单。', 'ok');
      launchPayment(channel, target);
    }
    async function markPaymentDone() {
      const waitingMessage = '订单已提交，请稍候，正在确认支付状态...';
      const doneButton = document.getElementById('paymentDone');
      showSubmitToast(waitingMessage);
      setStatus(waitingMessage, 'ok');
      doneButton.disabled = true;
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      try {
        if (!currentOrder?.id) {
          const pending = JSON.parse(localStorage.getItem('xingsui_pending_payment') || 'null');
          if (!pending?.plan_id || !pending?.pay_channel) {
            setStatus('请先选择微信或支付宝完成付款。', 'error');
            return;
          }
          currentOrder = await api('/orders', { method: 'POST', body: JSON.stringify(pending) });
          localStorage.setItem('xingsui_payment_order', JSON.stringify(currentOrder));
        }
        currentOrder = await api(`/orders/${currentOrder.id}/paid`, { method: 'POST' });
        localStorage.setItem('xingsui_payment_order', JSON.stringify(currentOrder));
        localStorage.removeItem('xingsui_pending_payment');
      } catch (error) {
        showSubmitToast(error.message, 'error');
        setStatus(error.message, 'error');
      } finally {
        doneButton.disabled = false;
      }
    }
    document.getElementById('wechatQr').src = config.wechat.qr_url;
    document.getElementById('alipayQr').src = config.alipay.qr_url;
    document.getElementById('supportLink').href = config.support_url;
    document.querySelectorAll('[data-channel]').forEach(button => button.addEventListener('click', () => startPayment(button.dataset.channel)));
    document.getElementById('paymentDone').addEventListener('click', markPaymentDone);
    loadPlan();
  </script>
</body>
</html>"""


def render_payment_page() -> str:
    config_json = json.dumps(PAYMENT_PAGE_CONFIG, ensure_ascii=False).replace("<", "\\u003c")
    return PAYMENT_HTML_TEMPLATE.replace("__PAYMENT_CONFIG__", config_json)
