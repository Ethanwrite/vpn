SITE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>星隧 - 安全高速网络通道</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #102033;
      --muted: #66758a;
      --soft: #f4fbfa;
      --line: #d9eeeb;
      --mint: #19c5a2;
      --mint-dark: #08a58b;
      --cyan: #2dd7ef;
      --blue: #132b68;
      --purple: #6b5cff;
      --gold: #ff9f1c;
      --danger: #e5484d;
      --surface: rgba(255, 255, 255, .88);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(circle at 78% 10%, rgba(45, 215, 239, .18), transparent 30%),
        radial-gradient(circle at 12% 18%, rgba(25, 197, 162, .12), transparent 28%),
        linear-gradient(180deg, #f8fffd 0, #f1fbff 48%, #ffffff 100%);
      letter-spacing: 0;
    }
    a { color: inherit; text-decoration: none; }
    button, input, select { font: inherit; letter-spacing: 0; }
    button { cursor: pointer; }
    .shell { width: min(1120px, calc(100% - 32px)); margin: 0 auto; }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 10;
      border-bottom: 1px solid rgba(217, 238, 235, .78);
      background: rgba(247, 255, 254, .86);
      backdrop-filter: blur(18px);
    }
    .nav { min-height: 70px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
    .brand { display: inline-flex; align-items: center; gap: 10px; font-weight: 900; font-size: 22px; color: var(--blue); }
    .mark {
      width: 36px; height: 36px; border-radius: 9px;
      background:
        radial-gradient(circle at 65% 32%, #fff 0 8%, transparent 9%),
        linear-gradient(135deg, #112764 0%, #2459e7 44%, #23d4ee 72%, #b4fff1 100%);
      box-shadow: 0 10px 30px rgba(25, 197, 162, .28);
      position: relative;
      overflow: hidden;
    }
    .mark:after {
      content: "";
      position: absolute;
      width: 54px; height: 18px; left: -15px; bottom: 5px;
      border-radius: 100% 100% 0 0;
      background: rgba(184, 243, 255, .74);
      transform: rotate(-28deg);
    }
    .links { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
    .menuToggle { display: none; min-height: 38px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--blue); padding: 0 12px; font-weight: 900; }
    .links a, .ghost, .pill {
      min-height: 38px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      padding: 0 12px;
      color: #355066;
      background: transparent;
      border: 1px solid transparent;
      font-weight: 700;
    }
    .links a.active, .links a:hover, .ghost:hover { background: #edf9f6; color: var(--mint-dark); border-color: var(--line); }
    .links a.telegram {
      color: #06344a;
      background: linear-gradient(135deg, rgba(42, 171, 238, .16), rgba(45, 215, 239, .18));
      border-color: rgba(42, 171, 238, .34);
      gap: 7px;
    }
    .links a.telegram:hover {
      color: #062430;
      background: linear-gradient(135deg, #2AABEE, #2dd7ef);
      transform: translateY(-1px);
      box-shadow: 0 12px 28px rgba(42, 171, 238, .22);
    }
    .tgIcon { width: 17px; height: 17px; fill: currentColor; flex: 0 0 auto; }
    .primary, .secondary, .danger {
      min-height: 46px;
      border-radius: 8px;
      border: 0;
      padding: 0 18px;
      font-weight: 900;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      white-space: nowrap;
    }
    .primary { background: linear-gradient(135deg, #17c7a8, #43c8f4); color: #062430; box-shadow: 0 12px 28px rgba(20, 177, 164, .18); }
    .secondary { border: 1px solid var(--line); color: var(--blue); background: rgba(255,255,255,.92); }
    .danger { background: #fff1f1; color: var(--danger); border: 1px solid #ffd6d6; }
    .hero { min-height: calc(100vh - 70px); display: grid; grid-template-columns: 1.04fr .96fr; gap: 34px; align-items: center; padding: 44px 0 34px; }
    .tag { display: inline-flex; width: fit-content; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 999px; color: #097160; background: #eafbf6; border: 1px solid #c7eee6; font-weight: 900; }
    h1 { margin: 18px 0 14px; font-size: clamp(34px, 5.7vw, 62px); line-height: 1.08; color: var(--blue); letter-spacing: 0; max-width: 760px; }
    .lead { margin: 0; max-width: 690px; color: var(--muted); font-size: clamp(16px, 2vw, 20px); line-height: 1.82; }
    .serviceCloud { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; max-width: 720px; }
    .servicePill {
      min-height: 36px;
      display: inline-flex;
      align-items: center;
      border: 1px solid rgba(217, 238, 235, .9);
      border-radius: 999px;
      padding: 0 12px;
      background: rgba(255, 255, 255, .72);
      color: #355066;
      font-weight: 800;
      box-shadow: 0 8px 20px rgba(57, 104, 122, .05);
    }
    .priceLine { display: flex; align-items: baseline; flex-wrap: wrap; gap: 12px; margin-top: 22px; }
    .now { font-size: clamp(38px, 6vw, 62px); color: var(--mint-dark); font-weight: 950; }
    .old { color: #9aa8b6; text-decoration: line-through; font-size: 18px; }
    .countdown { color: var(--gold); font-weight: 900; }
    .heroActions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }
    .heroPanel {
      position: relative;
      min-height: 540px;
      border-radius: 24px;
      background:
        radial-gradient(circle at 58% 42%, rgba(35, 208, 184, .30), transparent 28%),
        radial-gradient(circle at 28% 18%, rgba(45, 199, 244, .22), transparent 24%),
        linear-gradient(145deg, rgba(8, 24, 53, .96), rgba(12, 53, 78, .92) 48%, rgba(6, 29, 50, .98));
      border: 1px solid rgba(129, 235, 226, .26);
      box-shadow: 0 24px 76px rgba(14, 75, 96, .26);
      overflow: hidden;
      padding: 24px;
      display: grid;
      place-items: center;
      isolation: isolate;
    }
    .heroPanel:before {
      content: "";
      position: absolute;
      inset: 0;
      z-index: -1;
      opacity: .28;
      background:
        linear-gradient(rgba(111, 246, 235, .14) 1px, transparent 1px) 0 0 / 26px 26px,
        linear-gradient(90deg, rgba(111, 246, 235, .12) 1px, transparent 1px) 0 0 / 26px 26px;
      mask-image: radial-gradient(circle at 50% 45%, #000 0 52%, transparent 78%);
    }
    .networkScene {
      position: relative;
      width: min(560px, 100%);
      min-height: 492px;
      z-index: 1;
    }
    .networkScene:before {
      content: "";
      position: absolute;
      inset: 72px 44px 86px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(49, 231, 194, .14), transparent 64%);
      filter: blur(4px);
    }
    .mapStage {
      position: absolute;
      inset: 96px 20px 78px;
      border-radius: 22px;
      background:
        radial-gradient(circle at 52% 48%, rgba(43, 225, 183, .13), transparent 42%),
        linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025));
      border: 1px solid rgba(158, 243, 236, .13);
      box-shadow: inset 0 0 42px rgba(47, 221, 205, .08);
      overflow: hidden;
    }
    .worldMap {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      filter: drop-shadow(0 0 16px rgba(38, 227, 197, .22));
    }
    .mapDot { fill: rgba(131, 246, 231, .64); }
    .mapDot.dim { fill: rgba(118, 190, 210, .28); }
    .originNode { fill: #d4fff7; stroke: #20e7bc; stroke-width: 4; filter: drop-shadow(0 0 9px rgba(32,231,188,.9)); }
    .nodePulse { fill: none; stroke: #30f1c8; stroke-width: 2; opacity: .72; animation: pulseNode 2.4s ease-out infinite; }
    .fiberLine {
      fill: none;
      stroke: url(#fiberGradient);
      stroke-width: 3.2;
      stroke-linecap: round;
      stroke-dasharray: 9 12;
      animation: dashFlow 2.8s linear infinite;
      filter: drop-shadow(0 0 9px rgba(33, 241, 194, .85));
    }
    .fiberLine.alt { animation-duration: 3.4s; opacity: .78; }
    .nodeLabel {
      position: absolute;
      z-index: 6;
      min-width: 132px;
      padding: 9px 11px;
      border-radius: 13px;
      color: #eafffb;
      background: rgba(8, 31, 55, .68);
      border: 1px solid rgba(132, 247, 232, .25);
      box-shadow: 0 16px 34px rgba(0, 0, 0, .20), inset 0 1px 0 rgba(255,255,255,.09);
      backdrop-filter: blur(14px);
      font-size: 13px;
      line-height: 1.35;
    }
    .nodeLabel strong { display: block; color: #ffffff; font-size: 14px; margin-bottom: 2px; }
    .nodeLabel em { color: #42f1c8; font-style: normal; font-weight: 900; }
    .nodeTokyo { right: 26px; top: 210px; }
    .nodeSilicon { left: 26px; top: 220px; }
    .nodeSingapore { right: 92px; bottom: 88px; }
    .nodeFrankfurt { left: 220px; top: 72px; }
    .metricCard {
      position: absolute;
      z-index: 5;
      border-radius: 16px;
      padding: 14px;
      color: #dffefa;
      background: rgba(7, 28, 49, .62);
      border: 1px solid rgba(132, 247, 232, .20);
      box-shadow: 0 18px 42px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.08);
      backdrop-filter: blur(16px);
    }
    .metricCard h3 { margin: 0 0 9px; color: #ffffff; font-size: 14px; letter-spacing: 0; }
    .metricValue { color: #38f2c8; font-size: 22px; font-weight: 950; }
    .metricSub { margin-top: 5px; color: rgba(223,254,250,.72); font-size: 12px; line-height: 1.45; }
    .aiMatrix { left: 0; top: 0; width: 210px; }
    .throughput { left: 8px; bottom: 0; width: 190px; }
    .backbone { right: 0; bottom: 0; width: 214px; }
    .nodeState { right: 0; top: 18px; width: 190px; }
    .appIcons { display: flex; gap: 7px; align-items: center; margin-bottom: 9px; }
    .appIcon {
      width: 30px;
      height: 30px;
      border-radius: 9px;
      display: grid;
      place-items: center;
      font-size: 11px;
      font-weight: 950;
      color: #061f34;
      background: linear-gradient(135deg, #eafffb, #47dfef);
      box-shadow: 0 8px 18px rgba(38, 218, 209, .18);
    }
    .waveLine {
      width: 100%;
      height: 22px;
      margin-top: 7px;
    }
    .waveLine polyline { fill: none; stroke: #36f0c6; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }
    .barChart { display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; align-items: end; height: 52px; margin-top: 8px; }
    .barChart span {
      border-radius: 999px 999px 4px 4px;
      background: linear-gradient(180deg, #34f0c5, #2dc9ef);
      box-shadow: 0 0 18px rgba(48, 230, 207, .26);
    }
    .ringMini {
      width: 62px;
      height: 62px;
      border-radius: 50%;
      background: conic-gradient(#37f1c8 0 74%, rgba(255,255,255,.14) 74% 100%);
      display: grid;
      place-items: center;
      margin-left: auto;
      box-shadow: 0 0 24px rgba(55,241,200,.20);
    }
    .ringMini:after {
      content: "BGP";
      width: 44px;
      height: 44px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      color: #dffefa;
      background: #09213a;
      font-weight: 950;
      font-size: 11px;
    }
    @keyframes dashFlow { to { stroke-dashoffset: -84; } }
    @keyframes pulseNode {
      0% { r: 7; opacity: .8; }
      100% { r: 26; opacity: 0; }
    }
    section.page { display: none; padding: 34px 0 72px; }
    section.page.active { display: block; }
    section.hero.active { display: grid; }
    .sectionHead { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
    .sectionHead h2 { margin: 0; font-size: clamp(28px, 4vw, 44px); color: var(--blue); letter-spacing: 0; }
    .sectionHead p { margin: 8px 0 0; color: var(--muted); line-height: 1.7; }
    .grid { display: grid; gap: 14px; }
    .grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .panel, .plan, .formBox {
      background: rgba(255,255,255,.88);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px;
      box-shadow: 0 10px 28px rgba(57, 104, 122, .06);
    }
    .panel h3, .plan h3, .formBox h2 { margin: 0 0 8px; color: var(--blue); letter-spacing: 0; }
    .panel p, .plan p { margin: 0; color: var(--muted); line-height: 1.7; }
    .formPage { min-height: calc(100vh - 70px); display: grid; place-items: center; padding: 34px 0; }
    .formBox { width: min(440px, 100%); }
    label { display: block; font-weight: 800; color: #304960; margin: 12px 0 8px; }
    input, select {
      width: 100%;
      min-height: 46px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      padding: 0 12px;
      outline-color: var(--mint);
    }
    .formBox .primary, .plan .primary { width: 100%; margin-top: 14px; }
    .muted { color: var(--muted); }
    .status { min-height: 24px; color: var(--muted); line-height: 1.6; }
    .status.error { color: var(--danger); }
    .status.ok { color: var(--mint-dark); }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
    .metric strong { display: block; color: var(--blue); font-size: 22px; margin-top: 6px; overflow-wrap: anywhere; }
    .plan { position: relative; overflow: hidden; }
    .plan.hot { border-color: rgba(255, 159, 28, .44); box-shadow: 0 20px 50px rgba(255,159,28,.12); }
    .badge { display: inline-flex; border-radius: 999px; padding: 6px 10px; color: #764200; background: #fff0cd; font-weight: 900; font-size: 13px; }
    .planLead { margin-top: 12px; color: var(--muted); line-height: 1.65; min-height: 54px; }
    .planBenefits { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    .planBenefits span {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 0 10px;
      border-radius: 999px;
      background: #eefbf8;
      border: 1px solid #d3f0ea;
      color: #096e60;
      font-weight: 900;
      font-size: 13px;
    }
    .planPrice { display: flex; align-items: baseline; gap: 8px; margin: 12px 0; }
    .planPrice b { color: var(--mint-dark); font-size: 34px; }
    .planPrice span { text-decoration: line-through; color: #9aa8b6; }
    .orderBox { display: none; margin-top: 18px; }
    .orderBox.active { display: block; }
    .qr { width: 210px; height: 210px; object-fit: contain; border: 1px solid var(--line); border-radius: 8px; background: white; padding: 8px; }
    .subscriptionCard { margin-top: 14px; }
    .subscriptionCard .status { margin: 10px 0 0; }
    .subscriptionActions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .subscriptionLinkBox { display: none; margin-top: 14px; }
    .subscriptionLinkBox.active { display: block; }
    .subscriptionInput { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; overflow-wrap: anywhere; }
    .importGuide { margin-top: 16px; border-top: 1px solid var(--line); padding-top: 14px; }
    .importGuide h4 { margin: 0 0 10px; color: var(--blue); font-size: 16px; }
    .clientGrid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
    .clientTip {
      min-height: 86px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfffe;
      padding: 12px;
    }
    .clientTip strong { display: block; color: var(--blue); margin-bottom: 5px; }
    .clientTip span { color: var(--muted); line-height: 1.55; font-size: 13px; }
    .guidePanel { margin-top: 14px; }
    .guidePanel h3 { margin-bottom: 10px; }
    .guideList { margin: 0; padding-left: 20px; color: var(--muted); line-height: 1.8; }
    .guideList strong { color: var(--blue); }
    .securityHint {
      margin-top: 12px;
      padding: 10px 12px;
      border-radius: 8px;
      background: #fff7e6;
      border: 1px solid #ffe0a6;
      color: #7a4a00;
      font-weight: 800;
      line-height: 1.6;
    }
    .steps { counter-reset: step; }
    .step { position: relative; padding-left: 48px; min-height: 54px; }
    .step:before {
      counter-increment: step;
      content: counter(step);
      position: absolute; left: 0; top: 0;
      width: 32px; height: 32px; border-radius: 50%;
      display: grid; place-items: center; color: #062430; font-weight: 950;
      background: linear-gradient(135deg, #18d0ad, #23c2ff);
    }
    .centerNav { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
    footer { border-top: 1px solid var(--line); padding: 26px 0; color: var(--muted); background: rgba(255,255,255,.62); }
    @media (max-width: 860px) {
      .nav { min-height: 64px; flex-wrap: wrap; }
      .menuToggle { display: inline-flex; align-items: center; justify-content: center; }
      .links {
        display: none;
        width: 100%;
        padding: 0 0 12px;
        align-items: stretch;
        flex-direction: column;
      }
      .links.open { display: flex; }
      .hero { grid-template-columns: 1fr; padding-top: 28px; }
      .heroPanel { min-height: 620px; padding: 16px; }
      .networkScene { min-height: 590px; }
      .mapStage { inset: 150px 8px 138px; }
      .networkScene:before { inset: 150px 24px 130px; }
      .aiMatrix { left: 0; top: 0; width: min(210px, 56%); }
      .nodeState { right: 0; top: 0; width: min(180px, 42%); }
      .throughput { left: 0; bottom: 0; width: min(190px, 48%); }
      .backbone { right: 0; bottom: 0; width: min(210px, 50%); }
      .nodeLabel { min-width: 116px; padding: 8px 9px; font-size: 12px; }
      .nodeLabel strong { font-size: 13px; }
      .nodeTokyo { right: 4px; top: 268px; }
      .nodeSilicon { left: 4px; top: 268px; }
      .nodeSingapore { right: 52px; bottom: 158px; }
      .nodeFrankfurt { left: 142px; top: 138px; }
      .metricCard { padding: 12px; border-radius: 14px; }
      .metricValue { font-size: 20px; }
      .grid.three, .grid.two, .metrics, .clientGrid { grid-template-columns: 1fr; }
      .sectionHead { align-items: start; flex-direction: column; }
      .links a { min-height: 42px; justify-content: flex-start; padding: 0 12px; }
      .brand { font-size: 20px; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="shell nav">
      <a class="brand" href="/" data-route="home" aria-label="星隧首页"><span class="mark"></span><span>星隧</span></a>
      <button class="menuToggle" id="menuToggle" type="button" aria-expanded="false" aria-controls="nav">菜单</button>
      <nav class="links" id="nav">
        <a href="/" data-route="home">首页</a>
        <a href="/vip" data-route="vip">套餐</a>
        <a href="/download" data-route="download">下载</a>
        <a href="/center" data-route="center">用户中心</a>
        <a href="/guide" data-route="guide">帮助中心</a>
        <a class="telegram" href="https://t.me/+peCBtyuzOzNjNzA1" target="_blank" rel="noopener noreferrer" aria-label="加入星隧 Telegram 官方群">
          <svg class="tgIcon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9.78 15.64 9.39 21c.56 0 .8-.24 1.09-.53l2.62-2.5 5.43 3.98c1 .55 1.7.26 1.97-.92l3.57-16.73c.32-1.48-.53-2.06-1.5-1.7L1.62 10.65c-1.43.56-1.41 1.36-.24 1.72l5.36 1.67L19.2 6.25c.59-.39 1.12-.17.68.22z"/></svg>
          加入官方群
        </a>
        <a href="/login" data-route="login" id="loginLink">登录</a>
      </nav>
    </div>
  </header>

  <main>
    <section class="shell hero page active" id="page-home">
      <div>
        <span class="tag">限时特惠 · 首月 18 元 · ISP 专线 · 住宅节点</span>
        <h1>解锁全球网络，畅连主流 AI 与 8K 流媒体</h1>
        <p class="lead">星隧采用自研协议与智能调度策略，接入 ISP 专线和住宅节点资源，为 AI 工具、海外网站与高清流媒体提供更稳定的连接体验。一键连接高速节点，轻松访问 ChatGPT、Claude、Gemini、YouTube、Netflix 与 8K 高清流媒体。</p>
        <div class="serviceCloud" aria-label="支持的主流服务">
          <span class="servicePill">ISP 专线</span>
          <span class="servicePill">住宅节点</span>
          <span class="servicePill">自研协议</span>
          <span class="servicePill">智能调度</span>
          <span class="servicePill">ChatGPT</span>
          <span class="servicePill">Claude</span>
          <span class="servicePill">Gemini</span>
          <span class="servicePill">YouTube</span>
          <span class="servicePill">Netflix</span>
          <span class="servicePill">海外网站</span>
          <span class="servicePill">8K 流媒体</span>
        </div>
        <div class="priceLine">
          <span class="now" id="homeNow">18 元/月</span>
          <span class="old" id="homeOld">原价 28.8 元</span>
          <span class="countdown" id="homeCountdown">优惠加载中</span>
        </div>
        <div class="heroActions">
          <a class="primary" href="/register" data-route="register">立即注册</a>
          <a class="secondary" href="/download/android">下载 Android APK</a>
          <a class="secondary" href="/download/windows">下载 Windows 版</a>
          <a class="secondary" href="/vip" data-route="vip">查看套餐</a>
        </div>
      </div>
      <div class="heroPanel" aria-label="星隧全球节点网络状态">
        <div class="networkScene">
          <div class="metricCard aiMatrix">
            <h3>AI 专线矩阵</h3>
            <div class="appIcons" aria-label="AI 服务连通">
              <span class="appIcon">GPT</span>
              <span class="appIcon">CL</span>
              <span class="appIcon">GM</span>
            </div>
            <div class="metricValue">100%</div>
            <div class="metricSub">ChatGPT / Claude / Gemini 连通率</div>
            <svg class="waveLine" viewBox="0 0 168 22" aria-hidden="true"><polyline points="0,12 26,12 34,8 42,16 50,12 168,12"/></svg>
          </div>

          <div class="metricCard nodeState">
            <h3>智能调度</h3>
            <div class="metricValue">4 条</div>
            <div class="metricSub">美西 / 日本 / 新加坡 / 法兰克福核心节点</div>
          </div>

          <div class="mapStage">
            <svg class="worldMap" viewBox="0 0 720 430" role="img" aria-label="星隧点阵世界地图与全球光纤线路">
              <defs>
                <linearGradient id="fiberGradient" x1="0" x2="1" y1="0" y2="0">
                  <stop offset="0" stop-color="#b8fff2"/>
                  <stop offset=".45" stop-color="#36f1c8"/>
                  <stop offset="1" stop-color="#35c8ff"/>
                </linearGradient>
              </defs>
              <g opacity=".92">
                <circle class="mapDot" cx="104" cy="154" r="2.4"/><circle class="mapDot" cx="128" cy="144" r="2.4"/><circle class="mapDot" cx="152" cy="148" r="2.4"/><circle class="mapDot" cx="176" cy="164" r="2.4"/><circle class="mapDot" cx="126" cy="176" r="2.4"/><circle class="mapDot" cx="156" cy="190" r="2.4"/><circle class="mapDot dim" cx="184" cy="206" r="2.4"/><circle class="mapDot" cx="210" cy="230" r="2.4"/><circle class="mapDot dim" cx="226" cy="262" r="2.4"/><circle class="mapDot" cx="242" cy="296" r="2.4"/><circle class="mapDot dim" cx="252" cy="330" r="2.4"/>
                <circle class="mapDot" cx="310" cy="136" r="2.4"/><circle class="mapDot" cx="336" cy="126" r="2.4"/><circle class="mapDot" cx="362" cy="134" r="2.4"/><circle class="mapDot" cx="386" cy="152" r="2.4"/><circle class="mapDot" cx="338" cy="168" r="2.4"/><circle class="mapDot" cx="372" cy="186" r="2.4"/><circle class="mapDot dim" cx="398" cy="214" r="2.4"/><circle class="mapDot" cx="416" cy="244" r="2.4"/><circle class="mapDot dim" cx="438" cy="278" r="2.4"/>
                <circle class="mapDot" cx="442" cy="152" r="2.4"/><circle class="mapDot" cx="470" cy="142" r="2.4"/><circle class="mapDot" cx="496" cy="154" r="2.4"/><circle class="mapDot" cx="520" cy="176" r="2.4"/><circle class="mapDot" cx="476" cy="188" r="2.4"/><circle class="mapDot" cx="506" cy="212" r="2.4"/><circle class="mapDot" cx="532" cy="236" r="2.4"/><circle class="mapDot" cx="456" cy="252" r="2.4"/><circle class="mapDot" cx="488" cy="278" r="2.4"/><circle class="mapDot dim" cx="548" cy="288" r="2.4"/>
                <circle class="mapDot" cx="576" cy="250" r="2.4"/><circle class="mapDot" cx="602" cy="268" r="2.4"/><circle class="mapDot dim" cx="626" cy="296" r="2.4"/><circle class="mapDot" cx="650" cy="318" r="2.4"/>
              </g>
              <path class="fiberLine" d="M468 206 C500 196, 520 180, 552 164"/>
              <path class="fiberLine alt" d="M468 206 C358 132, 246 132, 154 158"/>
              <path class="fiberLine" d="M468 206 C450 232, 444 258, 452 292"/>
              <path class="fiberLine alt" d="M468 206 C430 146, 386 132, 352 142"/>
              <circle class="nodePulse" cx="468" cy="206" r="7"/>
              <circle class="originNode" cx="468" cy="206" r="6"/>
              <circle class="originNode" cx="552" cy="164" r="5"/><circle class="originNode" cx="154" cy="158" r="5"/><circle class="originNode" cx="452" cy="292" r="5"/><circle class="originNode" cx="352" cy="142" r="5"/>
            </svg>
          </div>

          <div class="nodeLabel nodeTokyo"><strong>东京节点</strong><span>延迟 <em>28ms</em></span></div>
          <div class="nodeLabel nodeSilicon"><strong>硅谷节点</strong><span>延迟 <em>110ms</em></span></div>

          <div class="metricCard throughput">
            <h3>8K 极速吞吐</h3>
            <div class="appIcons"><span class="appIcon">YT</span><span class="appIcon">NF</span></div>
            <div class="metricValue">145 Mbps</div>
            <div class="metricSub">4K / 8K 预加载完成</div>
          </div>

          <div class="metricCard backbone">
            <h3>骨干网状态</h3>
            <div class="ringMini" aria-hidden="true"></div>
            <div class="metricSub">ISP 专线端到端<br/>BGP 中转 / IEPL 专线</div>
            <div class="barChart" aria-hidden="true"><span style="height:42%"></span><span style="height:68%"></span><span style="height:54%"></span><span style="height:86%"></span><span style="height:72%"></span></div>
          </div>
        </div>
      </div>
    </section>

    <section class="page" id="page-login">
      <div class="shell formPage">
        <form class="formBox" id="loginForm">
          <h2>登录星隧</h2>
          <p class="muted">使用官网注册的邮箱和密码，App 中也使用同一套账号。</p>
          <label for="loginEmail">邮箱</label>
          <input id="loginEmail" type="email" autocomplete="email" required />
          <label for="loginPassword">密码</label>
          <input id="loginPassword" type="password" autocomplete="current-password" minlength="6" required />
          <button class="primary" type="submit">登录</button>
          <p class="status" id="loginStatus"></p>
          <p class="muted">没有账号？<a href="/register" data-route="register">去注册</a></p>
        </form>
      </div>
    </section>

    <section class="page" id="page-register">
      <div class="shell formPage">
        <form class="formBox" id="registerForm">
          <h2>注册星隧</h2>
          <p class="muted">邮箱格式校验即可注册，无需验证码。邀请码可选填。</p>
          <label for="registerEmail">邮箱</label>
          <input id="registerEmail" type="email" autocomplete="email" required />
          <label for="registerPassword">密码</label>
          <input id="registerPassword" type="password" autocomplete="new-password" minlength="6" required />
          <label for="registerInvite">邀请码（选填）</label>
          <input id="registerInvite" type="text" autocomplete="off" />
          <button class="primary" type="submit">注册并进入用户中心</button>
          <p class="status" id="registerStatus"></p>
          <p class="muted">已有账号？<a href="/login" data-route="login">去登录</a></p>
        </form>
      </div>
    </section>

    <section class="shell page" id="page-center">
      <div class="sectionHead">
        <div>
          <h2>用户中心</h2>
          <p>查看账号、VIP、到期时间、设备/登录状态和 App 下载入口。</p>
        </div>
        <button class="secondary" id="logoutButton">退出登录</button>
      </div>
      <div class="grid">
        <div class="panel">
          <h3>账号概览</h3>
          <div class="metrics">
            <div class="metric muted">邮箱<strong id="meEmail">未登录</strong></div>
            <div class="metric muted">VIP 状态<strong id="meVip">-</strong></div>
            <div class="metric muted">到期时间<strong id="meExpiry">-</strong></div>
            <div class="metric muted">邀请码<strong id="meInvite">-</strong></div>
          </div>
          <div class="centerNav">
            <a class="primary" href="/vip" data-route="vip">开通/续费 VIP</a>
            <button class="primary" id="centerSubscriptionButton" type="button">订阅链接</button>
            <a class="secondary" href="/download" data-route="download">下载 App</a>
            <button class="secondary" id="copyInvite">复制邀请码</button>
          </div>
        </div>
        <div class="grid two">
          <div class="panel">
            <h3>登录状态</h3>
            <p id="sessionState">当前浏览器未登录。</p>
            <p class="muted">App 使用同一个邮箱密码登录后，会同步这里的 VIP 状态和到期时间。</p>
          </div>
          <div class="panel">
            <h3>权益信息</h3>
            <p id="trafficState">注册用户可用 30MB 体验流量一键连接；用完后开通 VIP 继续使用。</p>
            <p id="balanceState" class="muted">返现余额：-</p>
          </div>
        </div>
        <div class="panel subscriptionCard" id="subscriptionCard">
          <h3>我的订阅链接</h3>
          <p class="muted">订阅链接用于导入 Clash、sing-box、v2rayN、Shadowrocket、Stash、Quantumult X 等客户端。</p>
          <p class="status" id="subscriptionStatus">请先登录后查看订阅链接。</p>
          <div class="subscriptionActions" id="subscriptionActions">
            <button class="primary" id="exportSubscription">导出订阅链接</button>
            <button class="secondary" id="copySubscription" disabled>复制链接</button>
            <button class="danger" id="resetSubscription" disabled>重置订阅链接</button>
          </div>
          <div class="subscriptionLinkBox" id="subscriptionLinkBox">
            <label for="subscriptionLink">订阅链接</label>
            <input class="subscriptionInput" id="subscriptionLink" type="text" readonly />
            <p class="muted" id="subscriptionMeta"></p>
          </div>
          <div class="securityHint">请勿分享订阅链接。多人同时使用可能导致账号冻结。</div>
          <div class="importGuide">
            <h4>如何导入客户端</h4>
            <p class="muted">复制订阅链接后，在客户端选择“从 URL 导入”“添加订阅”或“Remote Profile”，粘贴链接并更新即可。</p>
            <div class="clientGrid">
              <div class="clientTip"><strong>Clash / Stash</strong><span>Profiles / 配置页添加 URL，保存后点击更新。</span></div>
              <div class="clientTip"><strong>sing-box / v2rayN</strong><span>选择订阅分组，新增订阅地址，然后更新订阅。</span></div>
              <div class="clientTip"><strong>Shadowrocket / Quantumult X</strong><span>右上角添加，类型选择 Subscribe / 订阅，粘贴链接。</span></div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="shell page" id="page-vip">
      <div class="sectionHead">
        <div>
          <h2>VIP 套餐</h2>
          <p>不限流量、不限速，智能匹配稳定线路。首月限时 18 元，季度 38 元，年度 98 元，到账后自动同步官网与 App 会员状态。</p>
        </div>
        <span class="tag" id="vipCountdown">优惠加载中</span>
      </div>
      <div class="grid three" id="plans"></div>
      <div class="panel orderBox" id="orderBox">
        <h3>安全支付</h3>
        <p class="muted" id="orderSummary">订单已生成，请按页面提示完成付款。</p>
        <div class="grid two" style="align-items:center; margin-top: 12px;">
          <div>
            <img class="qr" id="orderQr" alt="收款二维码" />
            <p class="status" id="orderStatus"></p>
          </div>
          <div>
            <label for="payChannel">支付通道</label>
            <select id="payChannel">
              <option value="wechat">微信支付</option>
              <option value="alipay">支付宝支付</option>
            </select>
            <button class="primary" id="submitPaid">我已完成付款</button>
            <p class="muted">提交后订单进入待确认列表，确认到账后 VIP 会同步到官网和 App。</p>
          </div>
        </div>
      </div>
    </section>

    <section class="shell page" id="page-download">
      <div class="sectionHead">
        <div>
          <h2>App 下载</h2>
          <p>安装后使用官网账号登录，自动同步会员状态。打开客户端，选择智能线路，即可开始稳定连接。</p>
        </div>
        <div class="actions">
          <a class="primary" href="/download/android">下载 Android APK</a>
          <a class="secondary" href="/download/windows">下载 Windows 版</a>
        </div>
      </div>
      <div class="grid three">
        <div class="panel"><h3>统一账号</h3><p>官网注册后，App 直接用邮箱和密码登录，下载即可同步使用。</p></div>
        <div class="panel"><h3>智能线路</h3><p>自动匹配可用节点，减少手动配置成本，适合新手直接上手。</p></div>
        <div class="panel"><h3>专线节点</h3><p>接入 ISP 专线与住宅节点资源，面向 AI 工具、海外网站和高清流媒体场景优化。</p></div>
        <div class="panel"><h3>自研协议</h3><p>结合自研协议、混淆参数和智能调度策略，弱网环境下连接更稳。</p></div>
      </div>
    </section>

    <section class="shell page" id="page-guide">
      <div class="sectionHead">
        <div>
          <h2>使用教程</h2>
          <p>从官网注册到 App 连接的完整流程。</p>
        </div>
      </div>
      <div class="panel steps">
        <div class="step"><h3>注册账号</h3><p class="muted">在官网输入邮箱和密码完成注册，可填写好友邀请码。</p></div>
        <div class="step"><h3>开通 VIP</h3><p class="muted">选择套餐，按页面提示完成微信或支付宝付款，再点击“我已完成付款”。</p></div>
        <div class="step"><h3>同步会员</h3><p class="muted">订单完成后，会员到期时间会自动写入账号。</p></div>
        <div class="step"><h3>App 登录</h3><p class="muted">下载 APK 后用同一邮箱密码登录，首页会显示 VIP 状态和节点信息。</p></div>
        <div class="step"><h3>连接网络</h3><p class="muted">App 会自动匹配节点并创建本地隧道，点击连接即可。30MB 体验流量用完后会提示开通会员。</p></div>
      </div>
      <div class="panel guidePanel">
        <h3>订阅链接导入教程</h3>
        <ol class="guideList">
          <li><strong>进入用户中心：</strong>登录官网账号，确认 VIP 状态为“已开通”。</li>
          <li><strong>导出链接：</strong>点击“订阅链接”或“导出订阅链接”，生成后点击“复制链接”。</li>
          <li><strong>导入客户端：</strong>在 Clash、sing-box、v2rayN、Shadowrocket、Stash、Quantumult X 中选择“添加订阅 / 从 URL 导入 / Remote Profile”，粘贴链接并保存。</li>
          <li><strong>更新订阅：</strong>保存后点击“更新订阅”或刷新配置，客户端会拉取最新线路。</li>
          <li><strong>注意安全：</strong>订阅链接等同账号连接凭证，请勿分享给他人；如怀疑泄露，可回到用户中心点击“重置订阅链接”。</li>
        </ol>
      </div>
    </section>
  </main>

  <footer>
    <div class="shell">星隧 · 解锁全球网络 · 畅连 AI 工具与高清流媒体</div>
  </footer>

  <script>
    const state = {
      token: localStorage.getItem('xingsui_token') || '',
      user: JSON.parse(localStorage.getItem('xingsui_user') || 'null'),
      plans: [],
      promo: null,
      currentOrder: null,
      subscription: null,
    };

    const $ = (id) => document.getElementById(id);
    const money = (cents) => {
      const value = cents / 100;
      return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0$/, '');
    };
    const fmtDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-';
    const authHeaders = () => state.token ? { Authorization: `Bearer ${state.token}` } : {};

    async function api(path, options = {}) {
      const headers = { Accept: 'application/json', ...(options.headers || {}) };
      if (options.body) headers['Content-Type'] = 'application/json; charset=utf-8';
      const response = await fetch(path, { ...options, headers: { ...headers, ...authHeaders() } });
      const text = await response.text();
      const data = text ? JSON.parse(text) : null;
      if (!response.ok || data?.success === false) {
        const detail = data?.message || data?.detail?.message || data?.detail || text || `请求失败 ${response.status}`;
        const error = new Error(typeof detail === 'string' ? detail : '请求失败，请稍后重试。');
        error.code = data?.code || data?.detail?.code || '';
        throw error;
      }
      return data;
    }

    function setAuth(session) {
      state.token = session.access_token;
      state.user = session.user;
      localStorage.setItem('xingsui_token', state.token);
      localStorage.setItem('xingsui_user', JSON.stringify(state.user));
      renderAuthState();
    }

    function clearAuth() {
      state.token = '';
      state.user = null;
      localStorage.removeItem('xingsui_token');
      localStorage.removeItem('xingsui_user');
      state.subscription = null;
      renderAuthState();
      renderSubscriptionCard();
    }

    function routeFromPath() {
      const clean = location.pathname.replace(/^\\//, '') || 'home';
      const aliases = { dashboard: 'center', 'account/subscription': 'center', 'user/subscription': 'center' };
      if (aliases[clean]) return aliases[clean];
      return ['home', 'login', 'register', 'center', 'vip', 'download', 'guide'].includes(clean) ? clean : 'home';
    }

    function navigate(route, replace = false) {
      const path = route === 'home' ? '/' : `/${route}`;
      history[replace ? 'replaceState' : 'pushState']({}, '', path);
      renderRoute(route);
    }

    function renderRoute(route = routeFromPath()) {
      document.querySelectorAll('section.page').forEach(page => page.classList.remove('active'));
      const page = $(`page-${route}`);
      if (page) page.classList.add('active');
      document.querySelectorAll('#nav a').forEach(link => link.classList.toggle('active', link.dataset.route === route));
      if (route === 'center') {
        refreshMe();
        if (location.pathname.includes('subscription')) setTimeout(focusSubscriptionCard, 80);
      }
      if (route === 'vip') renderPlans();
    }

    function renderAuthState() {
      const loginLink = $('loginLink');
      if (loginLink) {
        loginLink.textContent = state.token ? '用户中心' : '登录';
        loginLink.dataset.route = state.token ? 'center' : 'login';
        loginLink.setAttribute('href', state.token ? '/center' : '/login');
        loginLink.hidden = Boolean(state.token);
      }
      if (state.user) {
        const previewId = $('previewId');
        const previewVip = $('previewVip');
        if (previewId) previewId.textContent = state.user.id.slice(0, 5).toUpperCase();
        if (previewVip) previewVip.textContent = vipText(state.user.vip_status);
      }
    }

    function vipText(status) {
      if (status === 'active') return '已开通';
      if (status === 'expired') return '已过期';
      return '未开通';
    }

    async function refreshMe() {
      if (!state.token) {
        $('meEmail').textContent = '未登录';
        $('meVip').textContent = '-';
        $('meExpiry').textContent = '-';
        $('meInvite').textContent = '-';
        $('sessionState').textContent = '当前浏览器未登录，请先登录或注册。';
        $('trafficState').textContent = '登录后可查看体验流量和会员同步状态。';
        $('balanceState').textContent = '返现余额：-';
        renderSubscriptionCard();
        return;
      }
      try {
        const me = await api('/me');
        state.user = me;
        localStorage.setItem('xingsui_user', JSON.stringify(me));
        $('meEmail').textContent = me.email;
        $('meVip').textContent = vipText(me.vip_status);
        $('meExpiry').textContent = fmtDate(me.vip_expired_at);
        $('meInvite').textContent = me.invite_code;
        $('sessionState').textContent = `当前浏览器已登录，账号 ID：${me.id}`;
        $('trafficState').textContent = `体验流量剩余 ${(me.free_traffic_remaining_bytes / 1024 / 1024).toFixed(1)} MB；可在 App 内一键连接。`;
        $('balanceState').textContent = `返现余额：${money(me.cash_balance_cents)} 元`;
        renderAuthState();
        renderSubscriptionCard();
      } catch (error) {
        clearAuth();
        $('sessionState').textContent = '登录已失效，请重新登录。';
      }
    }

    function subscriptionErrorMessage(error) {
      const code = error?.code || '';
      if (code === 'VIP_REQUIRED') return '开通 VIP 后即可导出订阅链接。';
      if (code === 'VIP_EXPIRED') return 'VIP 已过期，请续费后继续使用。';
      if (code === 'ACCOUNT_FROZEN') return '账号状态异常，请联系客服。';
      if (code === 'RATE_LIMITED') return '请求过于频繁，请稍后再试。';
      if (code === 'UNAUTHORIZED') return '请先登录后查看订阅链接。';
      return error?.message || '订阅链接生成失败，请稍后重试。';
    }

    function renderSubscriptionCard() {
      const status = $('subscriptionStatus');
      const exportBtn = $('exportSubscription');
      const copyBtn = $('copySubscription');
      const resetBtn = $('resetSubscription');
      const linkBox = $('subscriptionLinkBox');
      const linkInput = $('subscriptionLink');
      const meta = $('subscriptionMeta');
      if (!status || !exportBtn || !copyBtn || !resetBtn) return;
      linkBox.classList.toggle('active', Boolean(state.subscription?.subscription_url));
      linkInput.value = state.subscription?.subscription_url || '';
      meta.textContent = state.subscription
        ? `Token：${state.subscription.masked_token} · 到期：${fmtDate(state.subscription.expires_at)}`
        : '';
      copyBtn.disabled = !state.subscription?.subscription_url;
      resetBtn.disabled = !state.subscription?.subscription_url;

      if (!state.token) {
        status.className = 'status';
        status.textContent = '请先登录后查看订阅链接。';
        exportBtn.textContent = '登录后查看';
        exportBtn.disabled = false;
        copyBtn.disabled = true;
        resetBtn.disabled = true;
        return;
      }
      if (state.user?.vip_status === 'expired') {
        status.className = 'status error';
        status.textContent = 'VIP 已过期，请续费后继续使用。';
        exportBtn.textContent = '续费 VIP';
        exportBtn.disabled = false;
        copyBtn.disabled = true;
        resetBtn.disabled = true;
        return;
      }
      if (state.user?.vip_status !== 'active') {
        status.className = 'status';
        status.textContent = '开通 VIP 后即可导出订阅链接。';
        exportBtn.textContent = '开通 VIP';
        exportBtn.disabled = false;
        copyBtn.disabled = true;
        resetBtn.disabled = true;
        return;
      }
      status.className = 'status ok';
      status.textContent = state.subscription?.subscription_url ? '订阅链接已生成，可复制到客户端使用。' : '点击“导出订阅链接”后生成专属链接。';
      exportBtn.textContent = '导出订阅链接';
      exportBtn.disabled = false;
    }

    function focusSubscriptionCard() {
      const card = $('subscriptionCard');
      if (!card) return;
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
      card.animate(
        [
          { boxShadow: '0 0 0 0 rgba(25, 197, 162, 0)' },
          { boxShadow: '0 0 0 4px rgba(25, 197, 162, .24)' },
          { boxShadow: '0 10px 28px rgba(57, 104, 122, .06)' },
        ],
        { duration: 1100, easing: 'ease-out' },
      );
    }

    async function exportSubscriptionLink() {
      const status = $('subscriptionStatus');
      const exportBtn = $('exportSubscription');
      if (!state.token) {
        navigate('login');
        return;
      }
      if (state.user?.vip_status !== 'active') {
        navigate('vip');
        return;
      }
      exportBtn.disabled = true;
      status.className = 'status';
      status.textContent = '正在生成订阅链接…';
      try {
        state.subscription = await api('/user/subscription-link');
        renderSubscriptionCard();
      } catch (error) {
        status.className = 'status error';
        status.textContent = subscriptionErrorMessage(error);
      } finally {
        exportBtn.disabled = false;
      }
    }

    async function copySubscriptionLink() {
      const value = state.subscription?.subscription_url || $('subscriptionLink').value;
      if (!value) return;
      try {
        await navigator.clipboard.writeText(value);
        $('subscriptionStatus').className = 'status ok';
        $('subscriptionStatus').textContent = '订阅链接已复制。';
      } catch (_) {
        $('subscriptionLinkBox').classList.add('active');
        $('subscriptionLink').focus();
        $('subscriptionLink').select();
        $('subscriptionStatus').className = 'status';
        $('subscriptionStatus').textContent = '复制失败，请手动复制输入框中的订阅链接。';
      }
    }

    async function resetSubscriptionLink() {
      if (!state.subscription?.subscription_url) return;
      if (!confirm('重置后旧订阅链接将立即失效，是否继续？')) return;
      const status = $('subscriptionStatus');
      const resetBtn = $('resetSubscription');
      resetBtn.disabled = true;
      status.className = 'status';
      status.textContent = '正在生成订阅链接…';
      try {
        state.subscription = await api('/user/subscription-link/reset', { method: 'POST' });
        renderSubscriptionCard();
      } catch (error) {
        status.className = 'status error';
        status.textContent = subscriptionErrorMessage(error);
      } finally {
        resetBtn.disabled = false;
      }
    }

    function startCountdown(endsAt, ids) {
      const target = endsAt ? new Date(endsAt).getTime() : Date.now() + 3 * 86400000;
      const tick = () => {
        const diff = Math.max(0, target - Date.now());
        const days = Math.floor(diff / 86400000);
        const hours = Math.floor((diff % 86400000) / 3600000);
        ids.forEach(id => $(id).textContent = `优惠仅剩 ${days} 天 ${hours} 小时`);
      };
      tick();
      setInterval(tick, 60000);
    }

    async function loadOffer() {
      try {
        const [plans, promo] = await Promise.all([
          api('/plans'),
          api('/promotions/active').catch(() => null),
        ]);
        state.plans = plans;
        state.promo = promo;
        const plan = plans.find(item => item.id === (promo?.plan_id || 'plan_month')) || plans[0];
        if (plan) {
          const sale = promo?.promo_price_cents || plan.sale_price_cents;
          $('homeNow').textContent = `${money(sale)} 元/月`;
          $('homeOld').textContent = `原价 ${money(plan.original_price_cents)} 元`;
        }
        startCountdown(promo?.ends_at, ['homeCountdown', 'vipCountdown']);
        renderPlans();
      } catch (_) {
        startCountdown(null, ['homeCountdown', 'vipCountdown']);
      }
    }

    function renderPlans() {
      const box = $('plans');
      if (!box) return;
      const plans = (state.plans.length ? state.plans : [
        { id: 'plan_month', name: '首月会员', duration_days: 30, original_price_cents: 2880, sale_price_cents: 1800 },
        { id: 'plan_quarter', name: '季度会员', duration_days: 90, original_price_cents: 8640, sale_price_cents: 3800 },
        { id: 'plan_year', name: '年度会员', duration_days: 365, original_price_cents: 34560, sale_price_cents: 9800 },
      ]).slice().sort((a, b) => {
        const order = { plan_month: 1, plan_quarter: 2, plan_year: 3 };
        return (order[a.id] || 99) - (order[b.id] || 99);
      });
      box.innerHTML = plans.map(plan => {
        const promo = state.promo?.plan_id === plan.id ? state.promo : null;
        const sale = promo?.promo_price_cents || plan.sale_price_cents;
        const hot = plan.id === 'plan_month' ? ' hot' : '';
        const copy = {
          plan_month: '适合先体验星隧线路质量，AI 工具、海外网站和高清流媒体都能稳定使用。',
          plan_quarter: '适合长期日常使用，价格更划算，稳定覆盖办公、学习和流媒体场景。',
          plan_year: '全年无忧使用，长期稳定连接，多端账号状态自动同步，省心更划算。',
        }[plan.id] || '稳定连接全球网络，适合 AI 工具、海外网站和高清流媒体访问。';
        const benefits = ['不限流量', '不限速', '稳定低延迟'];
        return `<article class="plan${hot}">
          <span class="badge">${promo?.tag || (plan.id === 'plan_month' ? '限时特惠' : '稳定套餐')}</span>
          <h3>${plan.name}</h3>
          <p>${plan.duration_days} 天会员 · 官网与 App 自动同步</p>
          <p class="planLead">${copy}</p>
          <div class="planBenefits">${benefits.map(item => `<span>${item}</span>`).join('')}</div>
          <div class="planPrice"><b>${money(sale)} 元</b><span>${money(plan.original_price_cents)} 元</span></div>
          <button class="primary" data-buy="${plan.id}">选择套餐</button>
        </article>`;
      }).join('');
      box.querySelectorAll('[data-buy]').forEach(button => {
        button.addEventListener('click', () => createOrder(button.dataset.buy));
      });
    }

    async function createOrder(planId) {
      if (!state.token) {
        navigate('login');
        return;
      }
      const channel = $('payChannel')?.value || 'wechat';
      $('orderBox').classList.add('active');
      $('orderStatus').textContent = '正在生成订单...';
      try {
        const promoId = state.promo?.plan_id === planId ? state.promo.id : null;
        const order = await api('/orders', {
          method: 'POST',
          body: JSON.stringify({ plan_id: planId, promotion_id: promoId, pay_channel: channel }),
        });
        state.currentOrder = order;
        renderOrderPayment(order);
        $('orderStatus').className = 'status ok';
        $('orderStatus').textContent = '订单已生成，完成付款后点击确认按钮。';
      } catch (error) {
        $('orderStatus').className = 'status error';
        $('orderStatus').textContent = error.message;
      }
    }

    async function submitPaid() {
      if (!state.currentOrder) {
        $('orderStatus').className = 'status error';
        $('orderStatus').textContent = '请先选择套餐生成订单。';
        return;
      }
      try {
        const order = await api(`/orders/${state.currentOrder.id}/paid`, { method: 'POST' });
        state.currentOrder = order;
        renderOrderPayment(order);
        $('orderStatus').className = 'status ok';
        $('orderStatus').textContent = '已提交确认。二维码和订单信息已保留，管理员确认到账后将自动开通 VIP。';
      } catch (error) {
        $('orderStatus').className = 'status error';
        $('orderStatus').textContent = error.message;
      }
    }

    function renderOrderPayment(order) {
      $('orderQr').src = order.payment_qr_url;
      $('orderQr').style.display = order.payment_qr_url ? 'block' : 'none';
      $('orderSummary').textContent = `订单 ${order.order_no} · 应付 ${money(order.pay_amount_cents)} 元 · ${order.pay_channel === 'wechat' ? '微信支付' : '支付宝支付'}`;
      $('submitPaid').disabled = order.status !== 'pending_payment';
      $('submitPaid').textContent = order.status === 'pending_confirm' ? '已提交，等待确认' : '我已完成付款';
    }

    document.addEventListener('click', (event) => {
      const routeEl = event.target.closest('[data-route]');
      if (!routeEl) return;
      event.preventDefault();
      navigate(routeEl.dataset.route);
      $('nav').classList.remove('open');
      $('menuToggle').setAttribute('aria-expanded', 'false');
    });

    $('menuToggle').addEventListener('click', () => {
      const nav = $('nav');
      const opened = nav.classList.toggle('open');
      $('menuToggle').setAttribute('aria-expanded', String(opened));
    });

    window.addEventListener('popstate', () => renderRoute());

    $('loginForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const status = $('loginStatus');
      status.className = 'status';
      status.textContent = '正在登录...';
      try {
        const session = await api('/auth/email/login', {
          method: 'POST',
          body: JSON.stringify({ email: $('loginEmail').value, password: $('loginPassword').value }),
        });
        setAuth(session);
        status.className = 'status ok';
        status.textContent = '登录成功';
        navigate('center');
      } catch (error) {
        status.className = 'status error';
        status.textContent = error.message;
      }
    });

    $('registerForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const status = $('registerStatus');
      status.className = 'status';
      status.textContent = '正在注册...';
      try {
        const invite = $('registerInvite').value.trim();
        const session = await api('/auth/email/register', {
          method: 'POST',
          body: JSON.stringify({
            email: $('registerEmail').value,
            password: $('registerPassword').value,
            invite_code: invite || null,
          }),
        });
        setAuth(session);
        status.className = 'status ok';
        status.textContent = '注册成功';
        navigate('center');
      } catch (error) {
        status.className = 'status error';
        status.textContent = error.message;
      }
    });

    $('logoutButton').addEventListener('click', () => {
      clearAuth();
      navigate('home');
    });
    $('copyInvite').addEventListener('click', async () => {
      if (!state.user?.invite_code) return;
      await navigator.clipboard.writeText(state.user.invite_code);
    });
    $('centerSubscriptionButton').addEventListener('click', focusSubscriptionCard);
    $('payChannel').addEventListener('change', () => {
      if (state.currentOrder) createOrder(state.currentOrder.plan_id);
    });
    $('submitPaid').addEventListener('click', submitPaid);
    $('exportSubscription').addEventListener('click', exportSubscriptionLink);
    $('copySubscription').addEventListener('click', copySubscriptionLink);
    $('resetSubscription').addEventListener('click', resetSubscriptionLink);

    renderAuthState();
    renderSubscriptionCard();
    renderRoute(routeFromPath());
    loadOffer();
    if (state.token) refreshMe();
  </script>
</body>
</html>"""
