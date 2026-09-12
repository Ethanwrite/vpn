import json

from app.payment_config import PAYMENT_PAGE_CONFIG


PAYMENT_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#F2EDE3" />
  <title>星火 VPN · 支付</title>
  <style>
    :root {
      color-scheme: light;
      --paper: #F2EDE3; --paper-2: #FAF7F0;
      --ink: #0D0D0C; --muted: #6B6459; --faint: #9A9184;
      --gold: #A8801F; --gold-2: #D6B15C; --gold-3: #6E5210;
      --red: #8E1B13;
      --line: rgba(13,13,12,.14); --line-2: rgba(13,13,12,.30);
      font-family: "Helvetica Neue", Helvetica, Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; color: var(--ink); background: var(--paper);
      background-image: linear-gradient(to right, rgba(13,13,12,.05) 1px, transparent 1px),
                        linear-gradient(to bottom, rgba(13,13,12,.03) 1px, transparent 1px);
      background-size: 96px 96px, 96px 96px;
      -webkit-font-smoothing: antialiased;
    }
    button, a { font: inherit; }
    .shell { width: min(100% - 28px, 560px); margin: 0 auto; padding: 22px 0 calc(34px + env(safe-area-inset-bottom)); }
    .top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
    .brand { display: flex; align-items: center; gap: 11px; color: var(--ink); font-size: 16px; font-weight: 800; letter-spacing: .14em; text-decoration: none; }
    .mark { width: 34px; height: 34px; flex: 0 0 auto; }
    .back { color: var(--muted); font-size: 13.5px; font-weight: 700; text-decoration: none; border-bottom: 1px solid var(--gold); }
    .card { padding: 26px 24px; border: 1px solid var(--line-2); border-radius: 2px; background: var(--paper-2); box-shadow: 10px 10px 0 rgba(13,13,12,.08); }
    .eyebrow { margin: 0 0 10px; color: var(--gold-3); font-size: 12px; font-weight: 700; letter-spacing: .26em; text-transform: uppercase; }
    h1 { margin: 0; color: var(--ink); font-size: 27px; font-weight: 800; letter-spacing: -.02em; }
    .summary { display: flex; align-items: end; justify-content: space-between; gap: 14px; margin: 22px 0; padding: 18px; border: 1px solid var(--line); background: var(--paper); }
    .planName { margin: 0 0 6px; font-size: 18px; font-weight: 800; }
    .planMeta { margin: 0; color: var(--muted); font-size: 13px; }
    .price { color: var(--ink); font-size: 34px; font-weight: 800; letter-spacing: -.04em; white-space: nowrap; }
    .price small { font-size: 14px; font-weight: 700; color: var(--faint); letter-spacing: 0; }
    .payButtons { display: grid; gap: 11px; }
    .payButton { min-height: 52px; border: 1px solid var(--ink); border-radius: 2px; font-weight: 700; letter-spacing: .04em; cursor: pointer; transition: box-shadow .2s ease, transform .15s ease; }
    .payButton:active { transform: translateY(1px); }
    .payButton:disabled { cursor: wait; opacity: .5; }
    .wechat { background: var(--ink); color: var(--paper-2); }
    .wechat:hover { box-shadow: 6px 6px 0 rgba(168,128,31,.35); }
    .alipay { background: transparent; color: var(--ink); }
    .alipay:hover { box-shadow: 6px 6px 0 rgba(13,13,12,.14); }
    .status { min-height: 22px; margin: 14px 0 0; color: var(--muted); font-size: 13px; line-height: 1.7; text-align: center; }
    .status.error { color: var(--red); }
    .status.ok { color: var(--gold-3); }
    .fallback { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--line); }
    .fallback h2 { margin: 0 0 6px; color: var(--ink); font-size: 17px; font-weight: 800; }
    .fallback > p { margin: 0 0 14px; color: var(--muted); font-size: 13px; line-height: 1.7; }
    .qrGrid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .qrCard { padding: 11px; border: 1px solid var(--line); background: #fff; text-align: center; }
    .qrCard img { display: block; width: 100%; aspect-ratio: 1; object-fit: contain; background: #fff; }
    .qrCard strong { display: block; margin-top: 10px; font-size: 13.5px; font-weight: 700; }
    .notice { margin: 20px 0 0; padding: 14px; border: 1px solid rgba(168,128,31,.4); background: rgba(214,177,92,.12); color: var(--gold-3); font-size: 13px; font-weight: 700; line-height: 1.75; }
    .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }
    .actions button, .actions a { min-height: 46px; display: flex; align-items: center; justify-content: center; border-radius: 2px; font-weight: 700; text-decoration: none; }
    .done { border: 0; background: linear-gradient(135deg, var(--gold-2), var(--gold)); color: #1A1405; cursor: pointer; }
    .done:disabled { opacity: .55; cursor: default; }
    .support { border: 1px solid var(--line-2); background: transparent; color: var(--ink); }
    .submitToast { position: fixed; z-index: 30; top: calc(18px + env(safe-area-inset-top)); left: 50%; width: min(calc(100% - 28px), 520px); padding: 15px 16px; border-radius: 2px; background: var(--ink); color: var(--paper-2); font-size: 14px; font-weight: 700; line-height: 1.7; text-align: center; box-shadow: 8px 8px 0 rgba(168,128,31,.3); opacity: 0; pointer-events: none; transform: translate(-50%, -18px); transition: .2s ease; }
    .submitToast.active { opacity: 1; transform: translate(-50%, 0); }
    .submitToast.error { background: var(--red); box-shadow: 8px 8px 0 rgba(13,13,12,.2); }
    .submitToast.ok { background: var(--ink); }
    @media (max-width: 380px) { .card { padding: 20px 18px; } .summary { align-items: start; flex-direction: column; } .qrGrid, .actions { grid-template-columns: 1fr; } .qrCard img { width: min(100%, 260px); margin: 0 auto; } }
  </style>
</head>
<body>
  <main class="shell">
    <div class="top">
      <a class="brand" href="/">
        <svg class="mark" viewBox="0 0 200 200" aria-hidden="true">
          <defs><linearGradient id="payGold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E6C87C"/><stop offset="1" stop-color="#A8801F"/></linearGradient></defs>
          <circle cx="100" cy="100" r="96" fill="#0D0D0C"/>
          <circle cx="100" cy="100" r="86" fill="none" stroke="url(#payGold)" stroke-width="2.5"/>
          <g fill="url(#payGold)">
            <path d="M126 38A57.29 57.29 0 0 1 136 150A80.78 80.78 0 0 0 126 38Z"/>
            <path d="M68.72 159.97L130.54 155.48A7.5 7.5 0 0 0 130.06 140.5L68.08 140A10 10 0 1 0 68.72 159.97Z"/>
            <path d="M75.51 88.82L135.2 145.09A7 7 0 0 0 144.92 135.03L86.63 77.31L75.51 88.82Z"/>
            <path d="M94.27 53.64L102.77 68.36A2 2 0 0 1 102.03 71.09L60.47 95.09A2 2 0 0 1 57.73 94.36L49.23 79.64A2 2 0 0 1 49.97 76.91L91.53 52.91A2 2 0 0 1 94.27 53.64Z"/>
            <path d="M47.5 86A4.5 4.5 0 1 0 56.5 86A4.5 4.5 0 1 0 47.5 86Z"/>
          </g>
        </svg>
        <span>MARX VPN</span>
      </a>
      <a class="back" href="/#pricing">返回套餐</a>
    </div>
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
      if (!selectedPlan) return;
      if (!token) { sessionStorage.setItem('xingsui_checkout_plan', selectedPlan.id); location.href = '/dashboard'; return; }
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
      const waitingMessage = '正在提交订单，请稍候...';
      const successMessage = '订单已提交成功！请等待管理员确认到账，确认后 VIP 会自动开通。';
      const doneButton = document.getElementById('paymentDone');
      showSubmitToast(waitingMessage);
      setStatus(waitingMessage, 'ok');
      doneButton.disabled = true;
      let submitted = false;
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      try {
        if (!currentOrder?.id) {
          const pending = JSON.parse(localStorage.getItem('xingsui_pending_payment') || 'null');
          if (!pending?.plan_id || !pending?.pay_channel) {
            showSubmitToast('请先选择微信或支付宝完成付款。', 'error');
            setStatus('请先选择微信或支付宝完成付款。', 'error');
            return;
          }
          currentOrder = await api('/orders', { method: 'POST', body: JSON.stringify(pending) });
          localStorage.setItem('xingsui_payment_order', JSON.stringify(currentOrder));
        }
        currentOrder = await api(`/orders/${currentOrder.id}/paid`, { method: 'POST' });
        localStorage.setItem('xingsui_payment_order', JSON.stringify(currentOrder));
        localStorage.removeItem('xingsui_pending_payment');
        submitted = true;
        showSubmitToast(successMessage, 'ok');
        setStatus(successMessage, 'ok');
        doneButton.textContent = '已提交，等待确认';
      } catch (error) {
        showSubmitToast(error.message, 'error');
        setStatus(error.message, 'error');
      } finally {
        // 提交成功后保持按钮禁用，避免重复提交；失败时恢复可点击。
        doneButton.disabled = submitted;
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
