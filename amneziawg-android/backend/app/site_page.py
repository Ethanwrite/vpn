SITE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>星隧 - 智能全球网络</title>
  <style>
    :root {
      color-scheme: dark;
      --ink: #e9f2ff;
      --muted: #93a7c6;
      --faint: #64789a;
      --line: rgba(150, 198, 255, .11);
      --line-strong: rgba(150, 198, 255, .2);
      --glass: rgba(12, 27, 52, .52);
      --glass-deep: rgba(8, 19, 39, .74);
      --cyan: #5ee7d0;
      --ice: #7ec8ff;
      --gold: #e6c680;
      --danger: #ff8087;
      --grad: linear-gradient(135deg, #54e0c6 0%, #58b7ff 100%);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(1100px 700px at 84% -12%, rgba(64, 150, 255, .16), transparent 62%),
        radial-gradient(900px 620px at -12% 28%, rgba(84, 224, 198, .10), transparent 60%),
        radial-gradient(1300px 900px at 52% 118%, rgba(96, 112, 255, .10), transparent 62%),
        linear-gradient(180deg, #050e20 0%, #081831 52%, #050d1d 100%);
      background-attachment: fixed;
      letter-spacing: 0;
    }
    body:before {
      content: "";
      position: fixed;
      inset: -20% -10%;
      z-index: -1;
      pointer-events: none;
      background:
        radial-gradient(620px 340px at 70% 18%, rgba(94, 231, 208, .07), transparent 70%),
        radial-gradient(720px 420px at 22% 64%, rgba(126, 200, 255, .06), transparent 70%);
      animation: auroraDrift 36s ease-in-out infinite alternate;
    }
    @keyframes auroraDrift {
      0% { transform: translate3d(0, 0, 0); opacity: .8; }
      100% { transform: translate3d(3%, 2%, 0); opacity: 1; }
    }
    a { color: inherit; text-decoration: none; }
    button, input, select { font: inherit; letter-spacing: 0; }
    button { cursor: pointer; }
    .shell { width: min(1140px, calc(100% - 36px)); margin: 0 auto; }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 10;
      border-bottom: 1px solid var(--line);
      background: rgba(6, 15, 31, .66);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
    }
    .nav { min-height: 72px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
    .brand { display: inline-flex; align-items: center; gap: 11px; font-weight: 800; font-size: 21px; color: var(--ink); }
    .mark {
      width: 34px; height: 34px; border-radius: 10px;
      background:
        radial-gradient(circle at 66% 30%, rgba(255,255,255,.9) 0 8%, transparent 9%),
        linear-gradient(135deg, #123a7a 0%, #2b6ae0 46%, #35cfe0 78%, #aefaea 100%);
      box-shadow: 0 8px 26px rgba(64, 190, 230, .28);
      position: relative;
      overflow: hidden;
    }
    .mark:after {
      content: "";
      position: absolute;
      width: 52px; height: 17px; left: -14px; bottom: 4px;
      border-radius: 100% 100% 0 0;
      background: rgba(196, 246, 255, .6);
      transform: rotate(-28deg);
    }
    .links { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; justify-content: flex-end; }
    .menuToggle { display: none; min-height: 38px; border: 1px solid var(--line-strong); border-radius: 10px; background: transparent; color: var(--ink); padding: 0 14px; font-weight: 600; }
    .links a, .ghost {
      min-height: 38px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 10px;
      padding: 0 13px;
      color: var(--muted);
      background: transparent;
      border: 1px solid transparent;
      font-weight: 600;
      transition: color .3s, background .3s;
    }
    .links a.active, .links a:hover, .ghost:hover { color: var(--ink); background: rgba(126, 200, 255, .08); }
    .links a.telegram { color: #9fd2f5; gap: 7px; }
    .links a.telegram:hover { color: #cfeaff; background: rgba(42, 171, 238, .12); }
    .tgIcon { width: 16px; height: 16px; fill: currentColor; flex: 0 0 auto; }
    .primary, .secondary, .unavailable, .danger {
      min-height: 46px;
      border-radius: 11px;
      border: 0;
      padding: 0 20px;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      white-space: nowrap;
      transition: transform .35s ease, box-shadow .35s ease, background .35s ease, border-color .35s ease;
    }
    .primary { background: var(--grad); color: #04263a; box-shadow: 0 12px 34px rgba(84, 190, 255, .2); }
    .primary:hover { transform: translateY(-1px); box-shadow: 0 16px 40px rgba(84, 190, 255, .28); }
    .secondary { border: 1px solid var(--line-strong); color: var(--ink); background: rgba(14, 30, 56, .5); }
    .secondary:hover { border-color: rgba(150, 198, 255, .38); background: rgba(20, 40, 72, .6); }
    .unavailable { border: 1px solid var(--line); color: var(--faint); background: rgba(10, 22, 42, .5); cursor: not-allowed; }
    .danger { background: rgba(255, 110, 118, .1); color: var(--danger); border: 1px solid rgba(255, 110, 118, .26); }

    /* ---------- 首页 ---------- */
    .hero { min-height: calc(100vh - 72px); display: grid; grid-template-columns: 1fr 1fr; gap: 48px; align-items: center; padding: 56px 0 48px; }
    .eyebrow {
      margin: 0;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--faint);
      font-size: 13px;
      font-weight: 600;
      letter-spacing: .18em;
    }
    .eyebrow:before { content: ""; width: 26px; height: 1px; background: linear-gradient(90deg, var(--cyan), transparent); }
    h1 { margin: 22px 0 18px; font-size: clamp(30px, 4.1vw, 48px); line-height: 1.22; font-weight: 700; color: var(--ink); max-width: 640px; }
    h1 em {
      font-style: normal;
      background: linear-gradient(120deg, #8ff3de 0%, #7ec8ff 90%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
    .lead { margin: 0; max-width: 540px; color: var(--muted); font-size: clamp(15px, 1.6vw, 17px); line-height: 1.95; }
    .keyline { display: flex; align-items: center; flex-wrap: wrap; gap: 14px; margin-top: 26px; color: #b7cbe8; font-size: 14px; font-weight: 600; letter-spacing: .06em; }
    .keyline i { width: 3px; height: 3px; border-radius: 50%; background: var(--faint); }
    .heroActions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 30px; }
    .heroDeal { margin: 22px 0 0; color: var(--faint); font-size: 14px; }
    .heroDeal b { color: var(--gold); font-weight: 700; font-size: 16px; }

    /* 智能网络核心舱 */
    .heroPanel {
      position: relative;
      border-radius: 26px;
      background:
        radial-gradient(560px 380px at 52% 34%, rgba(52, 132, 226, .16), transparent 70%),
        linear-gradient(158deg, rgba(13, 30, 58, .66), rgba(7, 17, 36, .78));
      border: 1px solid var(--line);
      box-shadow: 0 30px 90px rgba(3, 12, 28, .5), inset 0 1px 0 rgba(180, 224, 255, .07);
      overflow: hidden;
      padding: 26px 26px 0;
      isolation: isolate;
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
    }
    .coreCaption { display: flex; justify-content: space-between; align-items: center; color: var(--faint); font-size: 12px; letter-spacing: .22em; font-weight: 600; }
    .coreCaption span:last-child { display: inline-flex; align-items: center; gap: 7px; letter-spacing: .08em; color: #7fd9c4; }
    .coreCaption span:last-child:before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 10px var(--cyan); animation: breathe 3.6s ease-in-out infinite; }
    @keyframes breathe { 0%, 100% { opacity: .5; } 50% { opacity: 1; } }
    .coreScene { position: relative; margin: 0 auto; width: min(520px, 100%); transition: transform .7s cubic-bezier(.22, .61, .36, 1); will-change: transform; }
    .coreScene svg { display: block; width: 100%; height: auto; }
    .coreStats {
      display: flex;
      margin: 4px -26px 0;
      padding: 16px 10px;
      border-top: 1px solid var(--line);
      background: rgba(6, 14, 30, .4);
    }
    .coreStats > div { flex: 1; text-align: center; padding: 2px 6px; }
    .coreStats > div + div { border-left: 1px solid var(--line); }
    .coreStats b { display: block; color: var(--ink); font-size: 17px; font-weight: 700; }
    .coreStats span { color: var(--faint); font-size: 12px; }

    .orbitRing { fill: none; stroke: rgba(140, 206, 255, .14); stroke-width: 1; }
    .orbitDot { fill: #9fe2ff; opacity: .8; }
    .orbitDot.small { opacity: .5; }
    .globeLine { fill: none; stroke: rgba(150, 214, 255, .13); stroke-width: 1; }
    .globeEdge { fill: url(#globeBody); stroke: rgba(150, 214, 255, .2); stroke-width: 1; }
    .beamPath { fill: none; stroke: url(#beamGrad); stroke-width: 1.4; opacity: .55; stroke-linecap: round; }
    .particle { fill: #c8f7ec; filter: drop-shadow(0 0 4px rgba(120, 240, 214, .9)); }
    .nodeCore { fill: #eafffa; stroke: rgba(94, 231, 208, .9); stroke-width: 1.6; filter: drop-shadow(0 0 6px rgba(94, 231, 208, .8)); }
    .nodeHalo { fill: none; stroke: rgba(94, 231, 208, .5); stroke-width: 1.2; animation: haloPulse 4.4s ease-out infinite; transform-box: fill-box; transform-origin: center; }
    @keyframes haloPulse {
      0% { transform: scale(.5); opacity: .7; }
      70% { transform: scale(1.9); opacity: 0; }
      100% { transform: scale(1.9); opacity: 0; }
    }
    .nodeText { fill: rgba(206, 230, 255, .72); font-size: 11.5px; font-weight: 600; letter-spacing: .04em; }
    .nodeText.origin { fill: rgba(240, 250, 255, .9); font-size: 12px; }

    /* ---------- 页面通用 ---------- */
    section.page { display: none; padding: 48px 0 88px; }
    section.page.active { display: block; }
    section.hero.active { display: grid; }
    .sectionHead { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 30px; }
    .sectionHead h2 { margin: 0; font-size: clamp(26px, 3.6vw, 40px); font-weight: 700; color: var(--ink); }
    .sectionHead p { margin: 12px 0 0; color: var(--muted); line-height: 1.8; max-width: 560px; }
    .grid { display: grid; gap: 16px; }
    .grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .panel, .formBox {
      background: var(--glass);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 24px;
      box-shadow: 0 16px 44px rgba(3, 12, 28, .3);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
    }
    .panel h3, .formBox h2 { margin: 0 0 10px; color: var(--ink); font-weight: 700; }
    .panel p { margin: 0; color: var(--muted); line-height: 1.8; }
    .formPage { min-height: calc(100vh - 72px); display: grid; place-items: center; padding: 40px 0; }
    .formBox { width: min(440px, 100%); padding: 30px; }
    label { display: block; font-weight: 600; color: #b8cbe8; margin: 14px 0 8px; }
    input, select {
      width: 100%;
      min-height: 46px;
      border: 1px solid var(--line-strong);
      border-radius: 10px;
      background: rgba(7, 17, 34, .66);
      color: var(--ink);
      padding: 0 13px;
      outline: none;
      transition: border-color .3s, box-shadow .3s;
    }
    input:focus, select:focus { border-color: rgba(94, 231, 208, .55); box-shadow: 0 0 0 3px rgba(94, 231, 208, .12); }
    .formBox .primary { width: 100%; margin-top: 18px; }
    .muted { color: var(--muted); }
    .muted a { color: var(--ice); }
    .status { min-height: 24px; color: var(--muted); line-height: 1.6; }
    .status.error { color: var(--danger); }
    .status.ok { color: var(--cyan); }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
    .metric strong { display: block; color: var(--ink); font-size: 20px; margin-top: 6px; overflow-wrap: anywhere; font-weight: 700; }

    /* ---------- 套餐 ---------- */
    .dealTag {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 16px;
      border-radius: 12px;
      color: var(--gold);
      background: rgba(230, 198, 128, .08);
      border: 1px solid rgba(230, 198, 128, .24);
      font-weight: 700;
      white-space: nowrap;
    }
    .plansGrid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; align-items: stretch; padding-top: 14px; }
    .plan {
      position: relative;
      display: flex;
      flex-direction: column;
      border-radius: 20px;
      padding: 28px 26px;
      background: var(--glass);
      border: 1px solid var(--line);
      box-shadow: 0 16px 44px rgba(3, 12, 28, .3);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      transition: transform .45s ease, box-shadow .45s ease, border-color .45s ease;
    }
    .plan:hover { transform: translateY(-4px); }
    .plan h3 { margin: 0; color: var(--ink); font-size: 21px; font-weight: 700; }
    .planTagline { margin: 8px 0 0; color: var(--muted); font-size: 14px; line-height: 1.7; }
    .planTag {
      position: absolute;
      top: -13px;
      left: 26px;
      padding: 5px 13px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 700;
      color: #06301f;
      background: var(--grad);
      box-shadow: 0 8px 22px rgba(84, 224, 198, .3);
    }
    .planPrice { display: flex; align-items: baseline; gap: 6px; margin: 24px 0 4px; }
    .planPrice em { font-style: normal; color: var(--ink); font-size: 18px; font-weight: 700; }
    .planPrice b { color: var(--ink); font-size: 42px; font-weight: 800; line-height: 1; }
    .planPrice span { color: var(--faint); font-size: 14px; }
    .perMonth { margin: 6px 0 0; color: var(--faint); font-size: 13px; min-height: 18px; }
    .planFeatures { list-style: none; margin: 22px 0 26px; padding: 0; display: grid; gap: 12px; flex: 1; }
    .planFeatures li { display: flex; align-items: start; gap: 10px; color: var(--muted); font-size: 14.5px; line-height: 1.55; }
    .planFeatures li:before {
      content: "✓";
      flex: 0 0 auto;
      width: 18px; height: 18px;
      margin-top: 2px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      font-size: 11px;
      font-weight: 800;
      color: var(--cyan);
      background: rgba(94, 231, 208, .1);
      border: 1px solid rgba(94, 231, 208, .28);
    }
    .planBtn {
      width: 100%;
      min-height: 46px;
      border-radius: 11px;
      border: 1px solid var(--line-strong);
      background: rgba(14, 30, 56, .5);
      color: var(--ink);
      font-weight: 700;
      transition: transform .35s ease, box-shadow .35s ease, background .35s ease, border-color .35s ease;
    }
    .planBtn:hover { border-color: rgba(150, 198, 255, .4); background: rgba(20, 40, 72, .65); }

    .plan.featured {
      transform: translateY(-12px);
      border: 1px solid transparent;
      background:
        linear-gradient(rgba(11, 26, 50, .92), rgba(11, 26, 50, .92)) padding-box,
        linear-gradient(165deg, rgba(94, 231, 208, .7), rgba(88, 183, 255, .4) 55%, rgba(94, 231, 208, .2)) border-box;
      box-shadow: 0 34px 80px rgba(4, 16, 36, .55), 0 0 70px rgba(72, 200, 220, .1);
    }
    .plan.featured:hover { transform: translateY(-18px); box-shadow: 0 42px 90px rgba(4, 16, 36, .6), 0 0 90px rgba(72, 200, 220, .16); }
    .plan.featured .planBtn { background: var(--grad); border: 0; color: #04263a; box-shadow: 0 12px 32px rgba(84, 190, 255, .22); }
    .plan.featured .planBtn:hover { transform: translateY(-1px); box-shadow: 0 16px 38px rgba(84, 190, 255, .3); }

    .plan.gold { background: linear-gradient(168deg, rgba(9, 20, 42, .9), rgba(6, 13, 29, .94)); border-color: rgba(230, 198, 128, .22); }
    .plan.gold:before {
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 1px;
      border-radius: 1px;
      background: linear-gradient(90deg, transparent, rgba(230, 198, 128, .55), transparent);
    }
    .plan.gold .planTag { color: #3d2c07; background: linear-gradient(135deg, #f2ddac, #d9b878); box-shadow: 0 8px 22px rgba(217, 184, 120, .24); }
    .plan.gold .planPrice b, .plan.gold .planPrice em { color: #f0dcae; }
    .plan.gold .planFeatures li:before {
      color: var(--gold);
      background: rgba(230, 198, 128, .08);
      border-color: rgba(230, 198, 128, .3);
    }
    .plan.gold .planBtn { border-color: rgba(230, 198, 128, .3); color: #f0dcae; background: rgba(230, 198, 128, .06); }
    .plan.gold .planBtn:hover { border-color: rgba(230, 198, 128, .5); background: rgba(230, 198, 128, .12); }

    .planFootnote { margin: 26px 0 0; color: var(--faint); font-size: 13.5px; line-height: 1.8; text-align: center; }
    .faqPanel { margin-top: 40px; }
    .faqPanel h3 { margin-bottom: 16px; }
    .faqItem + .faqItem { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line); }
    .faqItem strong { display: block; color: #c6d8f2; margin-bottom: 5px; font-size: 15px; }
    .faqItem span { color: var(--muted); font-size: 14px; line-height: 1.75; }

    .orderBox { display: none; margin-top: 26px; }
    .orderBox.active { display: block; }
    .qr { width: 210px; height: 210px; object-fit: contain; border: 1px solid var(--line-strong); border-radius: 12px; background: #fff; padding: 8px; }

    /* ---------- 用户中心 / 其它 ---------- */
    .subscriptionCard { margin-top: 16px; }
    .subscriptionCard .status { margin: 10px 0 0; }
    .subscriptionActions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
    .subscriptionLinkBox { display: none; margin-top: 14px; }
    .subscriptionLinkBox.active { display: block; }
    .subscriptionInput { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; overflow-wrap: anywhere; }
    .clientGrid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
    .clientTip { min-height: 86px; border: 1px solid var(--line); border-radius: 12px; background: rgba(9, 20, 40, .5); padding: 14px; }
    .clientTip strong { display: block; color: var(--ink); margin-bottom: 5px; }
    .clientTip span { color: var(--muted); line-height: 1.6; font-size: 13px; }
    .guidePanel { margin-top: 16px; }
    .guidePanel h3 { margin-bottom: 10px; }
    .securityHint {
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 10px;
      background: rgba(230, 198, 128, .07);
      border: 1px solid rgba(230, 198, 128, .22);
      color: #dfc48d;
      font-weight: 600;
      line-height: 1.6;
    }
    .steps { counter-reset: step; display: grid; gap: 22px; }
    .step { position: relative; padding-left: 50px; }
    .step:before {
      counter-increment: step;
      content: counter(step);
      position: absolute; left: 0; top: 0;
      width: 32px; height: 32px; border-radius: 50%;
      display: grid; place-items: center; color: #04263a; font-weight: 800;
      background: var(--grad);
      box-shadow: 0 8px 20px rgba(84, 190, 255, .2);
    }
    .step h3 { margin: 3px 0 6px; color: var(--ink); }
    .centerNav { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
    .vipGold { color: var(--gold); }
    footer { border-top: 1px solid var(--line); padding: 30px 0; color: var(--faint); background: rgba(5, 12, 26, .5); font-size: 14px; }

    @media (prefers-reduced-motion: reduce) {
      *, *:before, *:after { animation: none !important; transition: none !important; }
    }
    @media (max-width: 920px) {
      .nav { min-height: 64px; flex-wrap: wrap; }
      .menuToggle { display: inline-flex; align-items: center; justify-content: center; }
      .links { display: none; width: 100%; padding: 0 0 12px; align-items: stretch; flex-direction: column; }
      .links.open { display: flex; }
      .links a { min-height: 44px; justify-content: flex-start; }
      .hero { grid-template-columns: 1fr; gap: 34px; padding-top: 36px; min-height: 0; }
      h1 { font-size: clamp(30px, 8vw, 40px); }
      .heroPanel { padding: 20px 20px 0; border-radius: 22px; }
      .coreCaption { font-size: 10.5px; letter-spacing: .12em; }
      .coreCaption span { white-space: nowrap; }
      .coreStats { margin: 2px -20px 0; flex-wrap: wrap; }
      .coreStats > div { flex: 1 1 40%; padding: 8px 6px; }
      .coreStats > div:nth-child(3) { border-left: 0; }
      .plansGrid { grid-template-columns: 1fr; gap: 26px; padding-top: 6px; }
      .plan.featured { transform: none; }
      .plan.featured:hover { transform: translateY(-4px); }
      .grid.three, .grid.two, .metrics, .clientGrid { grid-template-columns: 1fr; }
      .sectionHead { align-items: start; flex-direction: column; }
      .brand { font-size: 19px; }
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
          官方群
        </a>
        <a href="/login" data-route="login" id="loginLink">登录</a>
      </nav>
    </div>
  </header>

  <main>
    <section class="shell hero page active" id="page-home">
      <div class="heroCopy">
        <p class="eyebrow">XINGSUI · 智能网络服务</p>
        <h1>更快抵达世界，<br/><em>更稳定连接每一次灵感</em></h1>
        <p class="lead">面向 AI 工具、全球网站与高清流媒体的智能网络服务。自动匹配更优线路，在不同网络环境下依然保持稳定连接。</p>
        <div class="keyline"><span>稳定</span><i></i><span>AI 专线</span><i></i><span>低延迟</span><i></i><span>智能调度</span></div>
        <div class="heroActions">
          <a class="primary" href="/register" data-route="register">立即开始</a>
          <a class="secondary" href="/vip" data-route="vip">查看套餐</a>
          <a class="ghost" href="/download" data-route="download">下载客户端</a>
        </div>
        <p class="heroDeal">新用户首月 <b id="homeNow">¥18</b> · 不限流量 · 多端会员同步</p>
      </div>

      <div class="heroPanel" id="heroPanel" aria-label="星隧智能网络核心">
        <div class="coreCaption"><span>GLOBAL NETWORK CORE</span><span>智能调度运行中</span></div>
        <div class="coreScene" id="coreScene">
          <svg viewBox="0 0 560 540" role="img" aria-label="星隧全球智能网络：从国内出发通往日本、美国、新加坡、澳大利亚、法国与新西兰的线路">
            <defs>
              <radialGradient id="coreGlow" cx="50%" cy="46%" r="55%">
                <stop offset="0" stop-color="rgba(96, 205, 255, .16)"/>
                <stop offset=".55" stop-color="rgba(70, 150, 255, .06)"/>
                <stop offset="1" stop-color="rgba(70, 150, 255, 0)"/>
              </radialGradient>
              <radialGradient id="globeBody" cx="38%" cy="30%" r="80%">
                <stop offset="0" stop-color="rgba(64, 130, 220, .18)"/>
                <stop offset=".5" stop-color="rgba(24, 58, 116, .14)"/>
                <stop offset="1" stop-color="rgba(8, 20, 44, .3)"/>
              </radialGradient>
              <linearGradient id="beamGrad" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0" stop-color="#5ee7d0"/>
                <stop offset="1" stop-color="#58b7ff"/>
              </linearGradient>
            </defs>

            <circle cx="280" cy="252" r="252" fill="url(#coreGlow)"/>

            <g transform="rotate(-14 280 252)">
              <ellipse class="orbitRing" cx="280" cy="252" rx="252" ry="84"/>
              <circle class="orbitDot" r="3">
                <animateMotion dur="52s" repeatCount="indefinite" path="M 28,252 a 252,84 0 1 0 504,0 a 252,84 0 1 0 -504,0"/>
              </circle>
              <circle class="orbitDot small" r="2">
                <animateMotion dur="52s" begin="-26s" repeatCount="indefinite" path="M 28,252 a 252,84 0 1 0 504,0 a 252,84 0 1 0 -504,0"/>
              </circle>
            </g>
            <g transform="rotate(22 280 252)">
              <ellipse class="orbitRing" cx="280" cy="252" rx="226" ry="112" style="opacity:.6"/>
              <circle class="orbitDot small" r="2.4">
                <animateMotion dur="68s" repeatCount="indefinite" path="M 54,252 a 226,112 0 1 0 452,0 a 226,112 0 1 0 -452,0"/>
              </circle>
            </g>

            <circle class="globeEdge" cx="280" cy="252" r="168"/>
            <g>
              <ellipse class="globeLine" cx="280" cy="252" rx="56" ry="168"/>
              <ellipse class="globeLine" cx="280" cy="252" rx="112" ry="168"/>
              <ellipse class="globeLine" cx="280" cy="252" rx="158" ry="168"/>
              <ellipse class="globeLine" cx="280" cy="252" rx="168" ry="52"/>
              <ellipse class="globeLine" cx="280" cy="252" rx="168" ry="108"/>
              <ellipse class="globeLine" cx="280" cy="252" rx="168" ry="150"/>
            </g>

            <g>
              <path class="beamPath" id="arcJP" d="M322,215 Q350,196 372,203"/>
              <path class="beamPath" id="arcUS" d="M322,215 Q240,138 158,203"/>
              <path class="beamPath" id="arcSG" d="M322,215 Q332,254 316,289"/>
              <path class="beamPath" id="arcAU" d="M322,215 Q354,276 350,336"/>
              <path class="beamPath" id="arcNZ" d="M322,215 Q396,282 400,352"/>
              <path class="beamPath" id="arcFR" d="M322,215 Q266,152 198,145"/>
            </g>
            <g>
              <circle class="particle" r="2.4"><animateMotion dur="6.5s" repeatCount="indefinite" path="M322,215 Q350,196 372,203"/></circle>
              <circle class="particle" r="2.4"><animateMotion dur="9s" begin="-3s" repeatCount="indefinite" path="M322,215 Q240,138 158,203"/></circle>
              <circle class="particle" r="2.4"><animateMotion dur="7s" begin="-1.5s" repeatCount="indefinite" path="M322,215 Q332,254 316,289"/></circle>
              <circle class="particle" r="2.4"><animateMotion dur="8s" begin="-5s" repeatCount="indefinite" path="M322,215 Q354,276 350,336"/></circle>
              <circle class="particle" r="2.4"><animateMotion dur="9.5s" begin="-2s" repeatCount="indefinite" path="M322,215 Q396,282 400,352"/></circle>
              <circle class="particle" r="2.4"><animateMotion dur="8.5s" begin="-6s" repeatCount="indefinite" path="M322,215 Q266,152 198,145"/></circle>
            </g>

            <g>
              <circle class="nodeHalo" cx="322" cy="215" r="9"/>
              <circle class="nodeCore" cx="322" cy="215" r="5"/>
              <text class="nodeText origin" x="316" y="200" text-anchor="end">国内智能接入</text>

              <circle class="nodeHalo" cx="372" cy="203" r="7" style="animation-delay:-1s"/>
              <circle class="nodeCore" cx="372" cy="203" r="3.6"/>
              <text class="nodeText" x="382" y="199">日本</text>

              <circle class="nodeHalo" cx="158" cy="203" r="7" style="animation-delay:-2.2s"/>
              <circle class="nodeCore" cx="158" cy="203" r="3.6"/>
              <text class="nodeText" x="148" y="196" text-anchor="end">美国</text>

              <circle class="nodeHalo" cx="316" cy="289" r="7" style="animation-delay:-3.1s"/>
              <circle class="nodeCore" cx="316" cy="289" r="3.6"/>
              <text class="nodeText" x="300" y="304" text-anchor="end">新加坡</text>

              <circle class="nodeHalo" cx="350" cy="336" r="7" style="animation-delay:-1.7s"/>
              <circle class="nodeCore" cx="350" cy="336" r="3.6"/>
              <text class="nodeText" x="336" y="356" text-anchor="end">澳大利亚</text>

              <circle class="nodeHalo" cx="400" cy="352" r="7" style="animation-delay:-4s"/>
              <circle class="nodeCore" cx="400" cy="352" r="3.6"/>
              <text class="nodeText" x="410" y="364">新西兰</text>

              <circle class="nodeHalo" cx="198" cy="145" r="7" style="animation-delay:-2.8s"/>
              <circle class="nodeCore" cx="198" cy="145" r="3.6"/>
              <text class="nodeText" x="188" y="134" text-anchor="end">法国</text>
            </g>
          </svg>
        </div>
        <div class="coreStats">
          <div><b>6+</b><span>全球区域</span></div>
          <div><b>99.9%</b><span>连接可用性</span></div>
          <div><b>48ms</b><span>平均延迟</span></div>
          <div><b>全天候</b><span>智能调度</span></div>
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
            <p id="trafficState">VPN 连接需要有效 VIP，每次连接都会向服务器申请短期安全配置。</p>
            <p id="balanceState" class="muted">返现余额：-</p>
          </div>
        </div>
        <div class="panel subscriptionCard" id="subscriptionCard">
          <h3>订阅链接</h3>
          <p class="muted">VIP 会员可导出专属订阅链接，导入 Clash、sing-box 等第三方开源客户端使用。链接与账号绑定，请勿分享；如泄露可随时点击“重置”使旧链接立即失效。</p>
          <p class="status" id="subscriptionStatus"></p>
          <div class="subscriptionActions">
            <button class="primary" id="exportSubscription" type="button">导出订阅链接</button>
            <button class="secondary" id="copySubscription" type="button" disabled>复制链接</button>
            <button class="secondary" id="resetSubscription" type="button" disabled>重置</button>
          </div>
          <div class="subscriptionLinkBox" id="subscriptionLinkBox">
            <input class="subscriptionInput" id="subscriptionLink" type="text" readonly onclick="this.select()" aria-label="订阅链接" />
            <p class="muted" id="subscriptionMeta"></p>
          </div>
        </div>
      </div>
    </section>

    <section class="shell page" id="page-vip">
      <div class="sectionHead">
        <div>
          <h2>选择适合你的连接周期</h2>
          <p>所有套餐均包含不限流量、智能线路、节点自动切换与多端会员同步。</p>
        </div>
        <span class="dealTag" id="vipDeal">新用户首月 ¥18</span>
      </div>
      <div class="plansGrid" id="plans"></div>
      <p class="planFootnote">适合经常使用 ChatGPT、Claude、YouTube 与海外网站的用户。支付后由人工确认开通，会员状态自动同步官网与 App。</p>
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
            <button class="primary" id="submitPaid" style="width:100%; margin-top:14px;">我已完成付款</button>
            <p class="muted">提交后订单进入待确认列表，确认到账后 VIP 会同步到官网和 App。</p>
          </div>
        </div>
      </div>
      <div class="panel faqPanel">
        <h3>常见问题</h3>
        <div class="faqItem"><strong>会员在 App 和官网通用吗？</strong><span>通用。官网注册的邮箱账号在 Android、Windows 客户端直接登录，会员状态与到期时间自动同步。</span></div>
        <div class="faqItem"><strong>支付后多久开通？</strong><span>提交付款后由人工确认到账，通常几分钟内完成，开通后无需任何额外操作。</span></div>
        <div class="faqItem"><strong>可以在多台设备上使用吗？</strong><span>支持手机与电脑同时在线，VIP 还可导出订阅链接在 Clash 等第三方客户端中使用。</span></div>
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
          <a class="secondary" href="/download/windows">下载 Windows 客户端</a>
        </div>
      </div>
      <div class="grid two">
        <div class="panel"><h3>统一账号</h3><p>官网注册后，App 直接用邮箱和密码登录，下载即可同步使用。</p></div>
        <div class="panel"><h3>智能线路</h3><p>自动匹配可用节点，减少手动配置成本，适合新手直接上手。</p></div>
        <div class="panel"><h3>专线节点</h3><p>接入 ISP 专线与优质节点资源，面向 AI 工具、海外网站和高清流媒体场景优化。</p></div>
        <div class="panel"><h3>稳定连接</h3><p>结合自研协议与智能调度策略，弱网环境下连接更稳。</p></div>
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
        <div class="step"><h3>连接网络</h3><p class="muted">App 会在线验证有效 VIP，然后匹配对应平台的节点并申请短期租约。</p></div>
      </div>
      <div class="panel guidePanel"><h3>关于订阅链接</h3><p class="muted">VIP 会员可在用户中心导出订阅链接，导入第三方开源客户端（Clash、sing-box 等）使用。链接经签名校验、限频保护，服务端全程 HTTPS，并对访问日志做脱敏处理；如担心泄露，可随时“重置”让旧链接立即失效。非会员开通 VIP 后即可导出。</p></div>
    </section>
  </main>

  <footer>
    <div class="shell">星隧 · 智能全球网络 · 让 AI 与灵感触手可及</div>
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
        $('trafficState').textContent = '登录后可查看会员同步状态。';
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
        $('meVip').classList.toggle('vipGold', me.vip_status === 'active');
        $('meExpiry').textContent = fmtDate(me.vip_expired_at);
        $('meInvite').textContent = me.invite_code;
        $('sessionState').textContent = `当前浏览器已登录，账号 ID：${me.id}`;
        $('trafficState').textContent = me.vip_status === 'active' ? 'VIP 有效；官方 App 将在每次连接前签发短期租约。' : '请开通有效 VIP 后连接。';
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
          { boxShadow: '0 0 0 0 rgba(94, 231, 208, 0)' },
          { boxShadow: '0 0 0 4px rgba(94, 231, 208, .22)' },
          { boxShadow: '0 16px 44px rgba(3, 12, 28, .3)' },
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

    async function loadOffer() {
      try {
        const [plans, promo] = await Promise.all([
          api('/plans'),
          api('/promotions/active').catch(() => null),
        ]);
        state.plans = plans;
        state.promo = promo;
        const monthPlan = plans.find(item => item.id === 'plan_month');
        if (monthPlan) {
          const sale = (state.promo?.plan_id === 'plan_month' && state.promo?.promo_price_cents) || monthPlan.sale_price_cents;
          const homeNow = $('homeNow');
          const vipDeal = $('vipDeal');
          if (homeNow) homeNow.textContent = `¥${money(sale)}`;
          if (vipDeal) vipDeal.textContent = `新用户首月 ¥${money(sale)}`;
        }
        renderPlans();
      } catch (_) {
        renderPlans();
      }
    }

    const PLAN_META = {
      plan_month: {
        title: '月度体验',
        tagline: '适合首次使用和短期需求',
        features: ['全部优质节点', 'AI 与海外网站支持', 'App 与官网状态同步'],
        cta: '开始体验',
        theme: '',
      },
      plan_quarter: {
        title: '季度会员',
        tagline: '稳定使用，综合性价比更高',
        features: ['包含月度全部权益', '长期线路优化', '多设备使用'],
        cta: '选择季度会员',
        theme: 'featured',
        tag: '最多用户选择',
      },
      plan_year: {
        title: '年度会员',
        tagline: '适合长期使用，单月成本更低',
        features: ['包含全部会员权益', '一年内无需重复续费', '优先体验新增节点'],
        cta: '选择年度会员',
        theme: 'gold',
        tag: '年度最省',
      },
    };

    function renderPlans() {
      const box = $('plans');
      if (!box) return;
      const plans = (state.plans.length ? state.plans : [
        { id: 'plan_month', name: '月度体验', duration_days: 30, original_price_cents: 2880, sale_price_cents: 1800 },
        { id: 'plan_quarter', name: '季度会员', duration_days: 90, original_price_cents: 8640, sale_price_cents: 4800 },
        { id: 'plan_year', name: '年度会员', duration_days: 365, original_price_cents: 34560, sale_price_cents: 15800 },
      ]).slice().sort((a, b) => {
        const order = { plan_month: 1, plan_quarter: 2, plan_year: 3 };
        return (order[a.id] || 99) - (order[b.id] || 99);
      });
      box.innerHTML = plans.map(plan => {
        const promo = state.promo?.plan_id === plan.id ? state.promo : null;
        const sale = promo?.promo_price_cents || plan.sale_price_cents;
        const meta = PLAN_META[plan.id] || {
          title: plan.name,
          tagline: '稳定连接全球网络',
          features: ['不限流量不限速', '智能线路调度', '多端会员同步'],
          cta: '选择套餐',
          theme: '',
        };
        const months = Math.round(plan.duration_days / 30);
        const per = months > 1 ? Math.round((sale / 100 / months) * 10) / 10 : 0;
        const perText = months > 1 ? `折合 ¥${per} / 月` : '新用户首次开通特惠价';
        return `<article class="plan ${meta.theme}">
          ${meta.tag ? `<span class="planTag">${meta.tag}</span>` : ''}
          <h3>${meta.title}</h3>
          <p class="planTagline">${meta.tagline}</p>
          <div class="planPrice"><em>¥</em><b>${money(sale)}</b><span>/ ${plan.duration_days} 天</span></div>
          <p class="perMonth">${perText}</p>
          <ul class="planFeatures">${meta.features.map(item => `<li>${item}</li>`).join('')}</ul>
          <button class="planBtn" data-buy="${plan.id}">${meta.cta}</button>
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
      const params = new URLSearchParams({ plan_id: planId });
      location.href = `/payment?${params.toString()}`;
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

    // 核心舱视差：鼠标 / 触摸移动时轻微偏移
    (function initParallax() {
      const panel = $('heroPanel');
      const scene = $('coreScene');
      if (!panel || !scene) return;
      if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      panel.addEventListener('pointermove', (event) => {
        const rect = panel.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;
        scene.style.transform = `translate3d(${(x * 12).toFixed(1)}px, ${(y * 9).toFixed(1)}px, 0)`;
      });
      panel.addEventListener('pointerleave', () => { scene.style.transform = ''; });
    })();

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

    $('logoutButton').addEventListener('click', async () => {
      try {
        if (state.token) await api('/auth/logout', { method: 'POST' });
      } finally {
        clearAuth();
        navigate('home');
      }
    });
    $('copyInvite').addEventListener('click', async () => {
      if (!state.user?.invite_code) return;
      await navigator.clipboard.writeText(state.user.invite_code);
    });
    $('payChannel').addEventListener('change', () => {
      if (state.currentOrder) createOrder(state.currentOrder.plan_id);
    });
    $('submitPaid').addEventListener('click', submitPaid);
    $('exportSubscription')?.addEventListener('click', exportSubscriptionLink);
    $('copySubscription')?.addEventListener('click', copySubscriptionLink);
    $('resetSubscription')?.addEventListener('click', resetSubscriptionLink);

    renderAuthState();
    renderSubscriptionCard();
    renderRoute(routeFromPath());
    loadOffer();
    if (state.token) refreshMe();
  </script>
</body>
</html>"""
