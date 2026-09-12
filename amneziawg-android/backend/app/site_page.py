"""星火 VPN（MARX VPN）官网单页。

设计基调：奶油白背景 / 黑色大标题 / 扁平线性 Logo / 巨大无衬线 MARX /
构成主义几何线条 / 金色网络节点 / 极少量暗红只做状态强调。

页面职责划分：
  - ``/``          纯品牌与销售页，7 屏：Hero → 全球节点 → 纲领 → 客户端 → 套餐 → 步骤 → Footer
  - ``/dashboard`` 登录 / 注册 / 用户中心 / 订阅链接 / 设备与会员状态（``/login`` ``/register``
                   ``/center`` 均为其别名，老链接与 App 内跳转继续可用）

注意：首屏世界地图上的节点卡片是**展示数据**（``WORLD_NODES``），真实节点列表在
``GET /vpn/nodes``，该接口需要登录态，故公开首页不拉取。调整文案时不要把它当成实时数据。
"""

SITE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>星火 VPN · MARX VPN — 连接世界，消除网络边界</title>
  <meta name="description" content="星火 VPN（MARX VPN）：面向 AI、全球网站与流媒体的智能网络服务。自动选择更优线路，让信息自由抵达。" />
  <style>
    :root {
      color-scheme: light;
      --paper: #F6F4EF;
      --paper-2: #FCFBF8;
      --paper-3: #EAE6DF;
      --ink: #282825;
      --ink-2: #1E1C19;
      --muted: #6B6459;
      --faint: #9A9184;
      --gold: #922D28;
      --gold-2: #B86C61;
      --gold-3: #87342F;
      --red: #922D28;
      --line: rgba(13, 13, 12, .14);
      --line-2: rgba(13, 13, 12, .30);
      --sans: "Helvetica Neue", Helvetica, Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
      --mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
      font-family: var(--sans);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; scroll-padding-top: 78px; }
    body {
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
    }
    a { color: inherit; text-decoration: none; }
    button, input, select { font: inherit; color: inherit; }
    button { cursor: pointer; background: none; border: 0; }
    img { max-width: 100%; }
    ::selection { background: var(--ink); color: var(--paper); }
    .shell { width: min(1220px, calc(100% - 40px)); margin: 0 auto; }

    /* ============ 构成主义底纹：极细几何线 ============ */
    .grain {
      position: fixed; inset: 0; z-index: 0; pointer-events: none;
      background-image:
        linear-gradient(to right, rgba(13,13,12,.055) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(13,13,12,.035) 1px, transparent 1px);
      background-size: 96px 96px, 96px 96px;
      mask-image: radial-gradient(120% 90% at 50% 0%, #000 25%, transparent 78%);
      -webkit-mask-image: radial-gradient(120% 90% at 50% 0%, #000 25%, transparent 78%);
    }
    main, header, footer { position: relative; z-index: 1; }

    /* ============ 顶栏 ============ */
    .topbar {
      position: sticky; top: 0; z-index: 40;
      border-bottom: 1px solid transparent;
      transition: background .35s ease, border-color .35s ease, backdrop-filter .35s ease;
    }
    .topbar.stuck {
      background: rgba(242, 237, 227, .72);
      border-bottom-color: var(--line);
      backdrop-filter: saturate(160%) blur(18px);
      -webkit-backdrop-filter: saturate(160%) blur(18px);
    }
    .nav { min-height: 76px; display: flex; align-items: center; gap: 26px; }
    .brand { display: inline-flex; align-items: center; gap: 12px; flex: 0 0 auto; }
    .brandMark { width: 38px; height: 38px; display: block; flex: 0 0 auto; }
    .brandName { font-size: 17px; font-weight: 800; letter-spacing: .14em; color: var(--ink); }
    .navLinks { display: flex; align-items: center; gap: 4px; margin-left: 8px; flex: 1 1 auto; }
    .navLinks a {
      padding: 9px 13px; border-radius: 2px; font-size: 14px; font-weight: 600;
      color: var(--muted); transition: color .25s ease, background .25s ease;
    }
    .navLinks a:hover, .navLinks a.active { color: var(--ink); background: rgba(13,13,12,.05); }
    .navRight { display: flex; align-items: center; gap: 10px; flex: 0 0 auto; }
    .menuToggle { display: none; width: 42px; height: 38px; border: 1px solid var(--line-2); border-radius: 2px; }
    .menuToggle span { display: block; width: 18px; height: 1.5px; background: var(--ink); margin: 3px auto; }

    /* ============ 按钮 ============ */
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 9px;
      min-height: 48px; padding: 0 22px; border-radius: 14px;
      font-size: 14.5px; font-weight: 700; letter-spacing: .02em; white-space: nowrap;
      border: 1px solid transparent; transition: transform .2s ease, background .25s ease, color .25s ease, border-color .25s ease, box-shadow .25s ease;
    }
    .btn:active { transform: translateY(1px); }
    .btn-ink { background: var(--ink); color: var(--paper-2); }
    .btn-ink:hover { background: #000; box-shadow: none; }
    .btn-gold { background: var(--red); color: var(--paper-2); }
    .btn-gold:hover { box-shadow: none; }
    .btn-line { border-color: var(--line-2); color: var(--ink); }
    .btn-line:hover { border-color: var(--ink); box-shadow: none; }
    .btn-sm { min-height: 38px; padding: 0 15px; font-size: 13.5px; }
    .btn[disabled] { opacity: .45; cursor: not-allowed; transform: none; box-shadow: none; }

    /* ============ 排版 ============ */
    .kicker {
      display: inline-flex; align-items: center; gap: 12px;
      font-size: 12px; font-weight: 700; letter-spacing: .34em; color: var(--gold-3);
      text-transform: uppercase;
    }
    .kicker:before { content: ""; width: 34px; height: 1px; background: var(--gold); }
    h1, h2, h3 { margin: 0; color: var(--ink); font-weight: 800; letter-spacing: -.02em; }
    h1 { font-size: clamp(40px, 5vw, 70px); line-height: 1.02; }
    h2 { font-size: clamp(32px, 4.4vw, 58px); line-height: 1.08; }
    .lead { margin: 0; color: var(--muted); font-size: clamp(15px, 1.35vw, 17px); line-height: 1.9; max-width: 40em; }
    .rule { height: 1px; background: var(--line); border: 0; margin: 0; }
    .sectionNum { font-family: var(--mono); font-size: 12px; letter-spacing: .2em; color: var(--faint); }

    /* ============ 第一屏 Hero ============ */
    .hero { position: relative; padding: clamp(40px, 6vw, 86px) 0 clamp(56px, 7vw, 104px); overflow: hidden; }
    .heroGrid { display: grid; grid-template-columns: minmax(0, 1.02fr) minmax(0, .98fr); gap: clamp(30px, 5vw, 72px); align-items: center; }
    .marxWord {
      position: absolute; left: -2.2vw; bottom: -3.6vw; z-index: 0; pointer-events: none;
      font-size: clamp(180px, 27vw, 420px); font-weight: 800; letter-spacing: -.055em; line-height: .72;
      color: transparent; -webkit-text-stroke: 1.5px rgba(13,13,12,.10);
      user-select: none;
    }
    .heroCopy { position: relative; z-index: 1; }
    .heroCopy h1 { margin: 26px 0 0; }
    .heroCopy h1 .gold { color: var(--gold); }
    .heroCopy .lead { margin-top: 24px; }
    .heroActions { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 34px; }
    .heroMeta { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; margin: 28px 0 0; color: var(--faint); font-size: 13px; font-weight: 600; letter-spacing: .06em; }
    .heroMeta i { width: 3px; height: 3px; border-radius: 50%; background: var(--gold); display: inline-block; }

    /* ---- 黑金锤镰核心 ---- */
    .emblemStage { position: relative; z-index: 1; display: grid; justify-items: center; gap: 22px; }
    .emblemBox {
      position: relative; width: min(430px, 100%); aspect-ratio: 1;
      display: grid; place-items: center; cursor: pointer;
    }
    .emblemBox:focus-visible { outline: 2px solid var(--red); outline-offset: 5px; border-radius: 16px; }
    .emblemBox:focus:not(:focus-visible) { outline: none; }
    .emblemBox svg { width: 100%; height: 100%; display: block; overflow: visible; }
    mask .emPart { animation: none !important; }
    .emPart { transform-origin: 100px 100px; transition: transform .7s ease, opacity .4s ease; }
    .emSickle { transform: translate(5px, 4px); }
    .emHammer { transform: translate(-7px, -5px); }
    .is-connecting .emPart, .is-locked .emPart { transform: none; }
    .is-connecting .emPart { animation: emLoading 1.4s ease-in-out infinite alternate; }
    @keyframes emLoading { from { opacity: .45; } to { opacity: 1; } }
    .emStage-locked b:before { content: ""; display: inline-block; width: 7px; height: 7px; margin-right: 9px; border-radius: 50%; background: #287853; }
    @media (prefers-reduced-motion: reduce) { .emPart { animation: none !important; transition: none !important; } }

    .emReadout {
      display: grid; gap: 7px; justify-items: center; text-align: center; min-height: 62px;
    }
    .emReadout b {
      font-family: var(--mono); font-size: 12.5px; font-weight: 700; letter-spacing: .26em;
      color: var(--faint); transition: color .4s ease;
    }
    .is-locked ~ .emReadout b, .emStage-locked b { color: var(--gold-3); }
    .emReadout span { font-size: 13.5px; color: var(--muted); letter-spacing: .04em; }
    .emReadout .lost { color: var(--red); }
    .emHint { font-size: 12px; color: var(--faint); letter-spacing: .1em; }

    /* ============ 第二屏 全球节点 ============ */
    .worldSection { padding: clamp(56px, 7vw, 110px) 0; border-top: 1px solid var(--line); }
    .worldHead { display: grid; gap: 18px; margin-bottom: clamp(28px, 4vw, 52px); }
    .worldWrap {
      position: relative; border: 1px solid var(--line); background: var(--paper-2);
      padding: clamp(14px, 2.4vw, 30px); overflow: hidden;
    }
    .worldWrap:before, .worldWrap:after {
      content: ""; position: absolute; width: 14px; height: 14px; border: 1px solid var(--gold); opacity: .6;
    }
    .worldWrap:before { left: 10px; top: 10px; border-right: 0; border-bottom: 0; }
    .worldWrap:after { right: 10px; bottom: 10px; border-left: 0; border-top: 0; }
    .worldMap { position: relative; width: 100%; }
    .worldMap svg { display: block; width: 100%; height: auto; overflow: visible; }
    .landDot { fill: rgba(13,13,12,.30); }
    .routeLine { fill: none; stroke: rgba(168,128,31,.55); stroke-width: .9; stroke-dasharray: 2.4 3.4; }
    .routeFlow { fill: var(--gold-2); }
    .nodeHit { cursor: pointer; }
    .nodeGlow { fill: rgba(168,128,31,.16); }
    .nodeDot { fill: var(--gold); stroke: var(--paper-2); stroke-width: .8; }
    .nodePing { fill: none; stroke: var(--gold); stroke-width: .8; transform-box: fill-box; transform-origin: center; animation: nodePing 3.6s ease-out infinite; }
    @keyframes nodePing { 0% { transform: scale(.4); opacity: .75; } 70%, 100% { transform: scale(2.6); opacity: 0; } }
    .nodeLabel { font-family: var(--mono); font-size: 5.2px; letter-spacing: .14em; fill: rgba(13,13,12,.55); }
    .nodeHit:hover .nodeDot { fill: var(--red); }

    .nodeCard {
      position: absolute; z-index: 5; min-width: 196px; padding: 14px 16px;
      background: var(--ink); color: var(--paper-2); border-radius: 2px;
      box-shadow: none;
      opacity: 0; transform: translateY(6px); pointer-events: none; transition: opacity .22s ease, transform .22s ease;
    }
    .nodeCard.show { opacity: 1; transform: translateY(0); }
    .nodeCard h4 { margin: 0; font-family: var(--mono); font-size: 12.5px; letter-spacing: .2em; font-weight: 700; color: var(--gold-2); }
    .nodeCard dl { margin: 11px 0 0; display: grid; grid-template-columns: auto 1fr; gap: 5px 14px; font-size: 12.5px; }
    .nodeCard dt { color: rgba(250,247,240,.5); }
    .nodeCard dd { margin: 0; text-align: right; font-family: var(--mono); }
    .nodeCard .go { display: block; margin-top: 12px; font-size: 12.5px; font-weight: 700; color: var(--gold-2); letter-spacing: .08em; }

    .worldStats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid var(--line); margin-top: clamp(18px, 2.6vw, 32px); }
    .worldStats > div { padding: 22px 8px 4px; }
    .worldStats > div + div { border-left: 1px solid var(--line); padding-left: 22px; }
    .worldStats b { display: block; font-size: clamp(26px, 3vw, 38px); font-weight: 800; letter-spacing: -.03em; }
    .worldStats span { display: block; margin-top: 6px; font-size: 12.5px; color: var(--muted); letter-spacing: .08em; }

    /* ============ 第三屏 纲领 ============ */
    .manifesto { padding: clamp(56px, 7vw, 110px) 0; border-top: 1px solid var(--line); }
    .manifestoHead { display: flex; align-items: baseline; justify-content: space-between; gap: 20px; flex-wrap: wrap; }
    .manifestoTitle { font-size: clamp(34px, 5.6vw, 76px); font-weight: 800; letter-spacing: -.035em; }
    .manifestoGrid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: var(--line); margin-top: clamp(30px, 4vw, 54px); border: 1px solid var(--line); }
    .mCard { background: var(--paper); padding: clamp(26px, 3vw, 40px); transition: background .3s ease; }
    .mCard:hover { background: var(--paper-2); }
    .mCard .no { font-family: var(--mono); font-size: 12.5px; letter-spacing: .22em; color: var(--gold); }
    .mCard h3 { margin: 22px 0 0; font-size: 21px; letter-spacing: 0; }
    .mCard .slogan { margin: 18px 0 0; font-size: clamp(20px, 2vw, 26px); font-weight: 800; line-height: 1.42; letter-spacing: -.02em; }
    .mCard p { margin: 18px 0 0; color: var(--muted); font-size: 14.5px; line-height: 1.85; }
    .mCard .mLine { display: block; width: 46px; height: 2px; background: var(--ink); margin-top: 26px; }

    /* ============ 第四屏 客户端 ============ */
    .clients { padding: clamp(56px, 7vw, 110px) 0; border-top: 1px solid var(--line); }
    .clientGrid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; margin-top: clamp(28px, 4vw, 48px); }
    .clientCard { border: 1px solid var(--line); background: var(--paper-2); padding: 28px; display: flex; flex-direction: column; }
    .clientCard .os { font-family: var(--mono); font-size: 12px; letter-spacing: .22em; color: var(--faint); }
    .clientCard h3 { margin: 14px 0 0; font-size: 20px; letter-spacing: 0; }
    .clientCard p { margin: 12px 0 24px; color: var(--muted); font-size: 14px; line-height: 1.8; flex: 1; }
    .clientCard .btn { width: 100%; }
    .clientNote { margin: 22px 0 0; color: var(--faint); font-size: 13px; line-height: 1.8; }

    /* ============ 第五屏 套餐 ============ */
    .pricing { padding: clamp(56px, 7vw, 110px) 0; border-top: 1px solid var(--line); }
    .planGrid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; margin-top: clamp(28px, 4vw, 48px); align-items: stretch; }
    .plan {
      position: relative; display: flex; flex-direction: column;
      border: 1px solid var(--line-2); background: var(--paper-2); padding: 32px 30px 30px;
      transition: transform .3s ease, box-shadow .3s ease, border-color .3s ease;
    }
    .plan:hover { transform: translateY(-4px); box-shadow: none; }
    .plan .tag {
      position: absolute; top: -1px; right: -1px; padding: 6px 12px;
      background: var(--ink); color: var(--paper-2); font-size: 11.5px; font-weight: 700; letter-spacing: .14em;
    }
    .plan h3 { font-size: 26px; letter-spacing: -.01em; }
    .plan .tagline { margin: 12px 0 0; color: var(--muted); font-size: 14.5px; line-height: 1.7; min-height: 44px; }
    .plan .price { display: flex; align-items: baseline; gap: 7px; margin: 26px 0 0; }
    .plan .price em { font-style: normal; font-size: 20px; font-weight: 700; }
    .plan .price b { font-size: 54px; font-weight: 800; letter-spacing: -.045em; line-height: .9; }
    .plan .price span { color: var(--faint); font-size: 14px; }
    .plan .per { margin: 10px 0 0; color: var(--faint); font-size: 12.5px; min-height: 18px; font-family: var(--mono); }
    .plan ul { list-style: none; margin: 26px 0 28px; padding: 22px 0 0; border-top: 1px solid var(--line); display: grid; gap: 13px; flex: 1; }
    .plan li { display: flex; gap: 11px; color: var(--ink-2); font-size: 14.5px; }
    .plan li:before { content: "✓"; color: var(--gold); font-weight: 800; }
    .plan.featured { background: var(--ink); border-color: var(--ink); color: var(--paper-2); }
    .plan.featured h3, .plan.featured .price b, .plan.featured .price em { color: var(--paper-2); }
    .plan.featured .tagline, .plan.featured li { color: rgba(250,247,240,.78); }
    .plan.featured .per { color: rgba(250,247,240,.45); }
    .plan.featured ul { border-top-color: rgba(250,247,240,.16); }
    .plan.featured .tag { background: var(--gold-2); color: #1A1405; }
    .plan.featured li:before { color: var(--gold-2); }
    .plan.gold { border-color: var(--gold); }
    .plan.gold .tag { background: var(--red); color: var(--paper-2); }
    .planFoot { margin: 26px 0 0; color: var(--faint); font-size: 13px; line-height: 1.9; }

    /* ============ 第六屏 步骤 ============ */
    .steps { padding: clamp(56px, 7vw, 110px) 0; border-top: 1px solid var(--line); }
    .stepGrid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); margin-top: clamp(28px, 4vw, 48px); }
    .step { background: var(--paper); padding: 30px 26px 34px; }
    .step .no { font-family: var(--mono); font-size: 12.5px; letter-spacing: .2em; color: var(--gold); }
    .step h3 { margin: 18px 0 0; font-size: 18px; letter-spacing: 0; }
    .step p { margin: 12px 0 0; color: var(--muted); font-size: 14px; line-height: 1.8; }
    .faqWrap { margin-top: clamp(34px, 4vw, 56px); border-top: 1px solid var(--line); }
    .faq { border-bottom: 1px solid var(--line); }
    .faq summary { list-style: none; cursor: pointer; padding: 22px 4px; display: flex; align-items: center; justify-content: space-between; gap: 18px; font-size: 16px; font-weight: 700; }
    .faq summary::-webkit-details-marker { display: none; }
    .faq summary:after { content: "+"; color: var(--gold); font-size: 20px; font-weight: 400; }
    .faq[open] summary:after { content: "−"; }
    .faq p { margin: 0 4px 24px; color: var(--muted); font-size: 14.5px; line-height: 1.9; max-width: 62em; }

    /* ============ Footer ============ */
    footer { border-top: 1px solid var(--line); background: var(--ink); color: rgba(250,247,240,.6); }
    .footGrid { display: grid; grid-template-columns: minmax(0, 1.4fr) repeat(3, minmax(0, 1fr)); gap: 34px; padding: clamp(40px, 5vw, 66px) 0 30px; }
    .footBrand .brandName { color: var(--paper-2); }
    .footBrand p { margin: 18px 0 0; font-size: 13.5px; line-height: 1.9; max-width: 26em; }
    .footCol h4 { margin: 0 0 16px; color: var(--paper-2); font-size: 13px; letter-spacing: .18em; font-weight: 700; }
    .footCol a { display: block; padding: 6px 0; font-size: 13.5px; transition: color .2s ease; }
    .footCol a:hover { color: var(--gold-2); }
    .footBar { display: flex; flex-wrap: wrap; gap: 12px 24px; justify-content: space-between; padding: 20px 0 30px; border-top: 1px solid rgba(250,247,240,.12); font-size: 12.5px; font-family: var(--mono); letter-spacing: .06em; }

    /* ============ Dashboard ============ */
    .page { display: none; }
    .page.active { display: block; }
    .dash { padding: clamp(34px, 5vw, 66px) 0 clamp(56px, 7vw, 96px); min-height: 68vh; }
    .dashHead { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-bottom: 34px; }
    .dashHead h2 { font-size: clamp(30px, 3.6vw, 46px); }
    .authWrap { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: clamp(28px, 5vw, 70px); align-items: center; }
    .authAside h2 { font-size: clamp(30px, 4vw, 52px); }
    .authAside p { margin: 22px 0 0; color: var(--muted); line-height: 1.9; font-size: 15px; }
    .authAside ul { list-style: none; margin: 30px 0 0; padding: 0; display: grid; gap: 12px; }
    .authAside li { display: flex; gap: 12px; color: var(--ink-2); font-size: 14.5px; }
    .authAside li:before { content: "—"; color: var(--gold); }
    .authBox { border: 1px solid var(--line-2); background: var(--paper-2); padding: clamp(26px, 3vw, 38px); }
    .tabs { display: flex; gap: 0; border-bottom: 1px solid var(--line); margin-bottom: 24px; }
    .tabs button { padding: 12px 2px; margin-right: 26px; font-size: 15px; font-weight: 700; color: var(--faint); border-bottom: 2px solid transparent; }
    .tabs button.active { color: var(--ink); border-bottom-color: var(--gold); }
    label { display: block; margin: 18px 0 8px; font-size: 13px; font-weight: 700; letter-spacing: .06em; color: var(--ink-2); }
    input, select {
      width: 100%; min-height: 48px; padding: 0 14px; border-radius: 2px;
      border: 1px solid var(--line-2); background: var(--paper); outline: none;
      transition: border-color .2s ease, box-shadow .2s ease;
    }
    input:focus, select:focus { border-color: var(--ink); box-shadow: none; }
    .authBox .btn { width: 100%; margin-top: 24px; }
    .status { min-height: 22px; margin: 14px 0 0; font-size: 13.5px; line-height: 1.7; color: var(--muted); }
    .status.err { color: var(--red); }
    .status.ok { color: var(--gold-3); }
    .switchLine { margin: 16px 0 0; font-size: 13.5px; color: var(--muted); }
    .switchLine button { font-weight: 700; color: var(--ink); border-bottom: 1px solid var(--gold); }

    .dashGrid { display: grid; gap: 20px; }
    .card { border: 1px solid var(--line); background: var(--paper-2); padding: 26px; }
    .card h3 { font-size: 17px; letter-spacing: .02em; }
    .card > p { margin: 12px 0 0; color: var(--muted); font-size: 14px; line-height: 1.85; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); margin-top: 20px; }
    .metric { background: var(--paper-2); padding: 18px 20px; }
    .metric span { font-size: 12px; color: var(--faint); letter-spacing: .1em; }
    .metric strong { display: block; margin-top: 8px; font-size: 18px; font-weight: 800; overflow-wrap: anywhere; }
    .metric strong.gold { color: var(--gold); }
    .rowActions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 22px; }
    .dashTwo { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
    .subInput { font-family: var(--mono); font-size: 13px; margin-top: 14px; }
    .subMeta { margin: 10px 0 0; font-size: 12.5px; color: var(--faint); font-family: var(--mono); overflow-wrap: anywhere; }
    .hidden { display: none !important; }

    /* ---- 镰刀弧 loading ring ---- */
    .spinner { width: 16px; height: 16px; display: inline-block; }
    .spinner circle { fill: none; stroke: currentColor; stroke-width: 2.6; stroke-linecap: round; stroke-dasharray: 30 44; transform-origin: center; animation: spin .9s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ============ 404 ============ */
    .lost404 { min-height: 62vh; display: grid; place-items: center; text-align: center; padding: 80px 0; }
    .lost404 .code { font-size: clamp(90px, 16vw, 200px); font-weight: 800; letter-spacing: -.06em; color: transparent; -webkit-text-stroke: 2px var(--line-2); }
    .lost404 h2 { margin: 18px 0 0; font-size: clamp(24px, 3vw, 36px); }
    .lost404 p { margin: 16px 0 30px; color: var(--muted); }

    @media (prefers-reduced-motion: reduce) {
      *, *:before, *:after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
      html { scroll-behavior: auto; }
    }
    @media (max-width: 1024px) {
      .manifestoGrid, .clientGrid, .planGrid { grid-template-columns: 1fr; }
      .stepGrid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .footGrid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 900px) {
      html { scroll-padding-top: 68px; }
      .nav { min-height: 64px; flex-wrap: wrap; gap: 12px; }
      .menuToggle { display: block; order: 3; margin-left: auto; }
      .navRight { order: 2; margin-left: auto; }
      .navRight .btn:not(.btn-ink) { display: none; }
      .navLinks {
        order: 4; width: 100%; display: none; flex-direction: column; align-items: stretch;
        gap: 0; padding-bottom: 12px; border-top: 1px solid var(--line); margin-left: 0;
      }
      .navLinks.open { display: flex; }
      .navLinks a { padding: 14px 2px; border-bottom: 1px solid var(--line); }
      .heroGrid, .authWrap, .dashTwo { grid-template-columns: 1fr; }
      .emblemStage { order: -1; }
      .emblemBox { width: min(320px, 82%); }
      /* 窄屏上把 MARX 收小并整体放进视口，避免只露出「MAR」看起来像截断 */
      .marxWord { font-size: clamp(110px, 29vw, 190px); left: 4vw; bottom: auto; top: 42vh; opacity: .75; }
      .worldStats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .worldStats > div { border-left: 0 !important; padding-left: 8px !important; border-top: 1px solid var(--line); }
      .worldStats > div:nth-child(-n+2) { border-top: 0; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .stepGrid { grid-template-columns: 1fr; }
      .footGrid { grid-template-columns: 1fr; gap: 24px; }
    }
  </style>
</head>
<body>
  <div class="grain" aria-hidden="true"></div>

  <header class="topbar" id="topbar">
    <div class="shell nav">
      <a class="brand" href="/" data-route="home" aria-label="星火 VPN 首页">
        <svg class="brandMark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" fill="none" stroke="#922D28" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round">
<defs><mask id="nav-cutout" maskUnits="userSpaceOnUse" x="-20" y="-20" width="240" height="240"><rect x="-20" y="-20" width="240" height="240" fill="white" stroke="none"/><g fill="black" stroke="black"><path d="M72 82L157 172Q164 179 171 172Q178 165 169 157L84 70Z"/><path d="M38 79L76 41L101 45Q106 46 102 51L55 99Q52 102 49 99L37 87Q34 84 38 79Z"/></g></mask></defs>
<g mask="url(#nav-cutout)"><g><path d="M116 24C159 43 181 78 174 115C168 149 143 172 109 174C86 176 64 168 49 155L30 175Q23 182 18 175Q14 170 21 163L39 144Q37 137 43 136L49 131Q52 129 56 134C77 155 109 160 137 143C158 130 165 107 158 82C152 59 137 40 116 24Z"/></g></g><g><path d="M72 82L157 172Q164 179 171 172Q178 165 169 157L84 70Z"/><path d="M38 79L76 41L101 45Q106 46 102 51L55 99Q52 102 49 99L37 87Q34 84 38 79Z"/></g></svg>
        <span class="brandName">MARX VPN</span>
      </a>

      <nav class="navLinks" id="navLinks">
        <a href="/" data-route="home" data-anchor="top">首页</a>
        <a href="/#nodes" data-route="home" data-anchor="nodes">全球节点</a>
        <a href="/#pricing" data-route="home" data-anchor="pricing">套餐</a>
        <a href="/#clients" data-route="home" data-anchor="clients">客户端下载</a>
        <a href="/#steps" data-route="home" data-anchor="steps">指南</a>
        <a href="/dashboard" data-route="dashboard">用户中心</a>
      </nav>

      <div class="navRight">
        <a class="btn btn-line btn-sm" href="/dashboard" data-route="dashboard" id="navAuth">登录</a>
        <a class="btn btn-ink btn-sm" href="/#pricing" data-route="home" data-anchor="pricing">开始连接</a>
      </div>

      <button class="menuToggle" id="menuToggle" type="button" aria-label="菜单" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>
    </div>
  </header>

  <main>
    <!-- ================= 首页 ================= -->
    <section class="page active" id="page-home">

      <!-- 1 / Hero -->
      <section class="hero" id="top">
        <div class="marxWord" aria-hidden="true">MARX</div>
        <div class="shell heroGrid">
          <div class="heroCopy">
            <p class="kicker">MARX VPN · 星火</p>
            <h1>连接世界。<br/>消除<span class="gold">网络边界</span>。</h1>
            <p class="lead">面向 AI、全球网站与流媒体的智能网络服务。自动选择更优线路，让信息自由抵达。</p>
            <div class="heroActions">
              <a class="btn btn-ink" href="/dashboard" data-route="dashboard">立即连接</a>
              <a class="btn btn-line" href="/#clients" data-route="home" data-anchor="clients">下载客户端</a>
            </div>
            <p class="heroMeta">
              <span>不限流量</span><i></i><span>智能选线</span><i></i><span>多端同步</span><i></i><span>全球节点</span>
            </p>
          </div>

          <div class="emblemStage">
            <div class="emblemBox" id="emblemBox" role="button" aria-label="播放连接动画演示">
              <svg id="emblemSvg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" fill="none" stroke="#922D28" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round">
<defs><mask id="hero-cutout" maskUnits="userSpaceOnUse" x="-20" y="-20" width="240" height="240"><rect x="-20" y="-20" width="240" height="240" fill="white" stroke="none"/><g class="emPart emHammer" fill="black" stroke="black"><path d="M72 82L157 172Q164 179 171 172Q178 165 169 157L84 70Z"/><path d="M38 79L76 41L101 45Q106 46 102 51L55 99Q52 102 49 99L37 87Q34 84 38 79Z"/></g></mask></defs>
<g mask="url(#hero-cutout)"><g class="emPart emSickle"><path d="M116 24C159 43 181 78 174 115C168 149 143 172 109 174C86 176 64 168 49 155L30 175Q23 182 18 175Q14 170 21 163L39 144Q37 137 43 136L49 131Q52 129 56 134C77 155 109 160 137 143C158 130 165 107 158 82C152 59 137 40 116 24Z"/></g></g><g class="emPart emHammer"><path d="M72 82L157 172Q164 179 171 172Q178 165 169 157L84 70Z"/><path d="M38 79L76 41L101 45Q106 46 102 51L55 99Q52 102 49 99L37 87Q34 84 38 79Z"/></g></svg>
            </div>

            <div class="emReadout" id="emReadout">
              <b id="emState" aria-live="polite">未连接</b>
              <span id="emDetail">当前网络处于空闲状态</span>
              <span class="emHint" id="emHint">连接状态演示</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 2 / 全球节点 -->
      <section class="worldSection" id="nodes">
        <div class="shell">
          <div class="worldHead">
            <p class="kicker">02 — Global Network</p>
            <h2>全世界的网络，连接起来。</h2>
            <p class="lead">线路按延迟、负载与可用性实时调度。你不需要知道数据走了哪条路，只需要它一定抵达。</p>
          </div>

          <div class="worldWrap">
            <div class="worldMap" id="worldMap">
              <svg viewBox="0 0 360 190" id="worldSvg" role="img" aria-label="全球节点分布图"></svg>
              <div class="nodeCard" id="nodeCard" aria-hidden="true">
                <h4 id="ncName">SINGAPORE 01</h4>
                <dl>
                  <dt>延迟</dt><dd id="ncPing">38 ms</dd>
                  <dt>负载</dt><dd id="ncLoad">21%</dd>
                  <dt>服务</dt><dd id="ncProto">智能连接</dd>
                </dl>
                <span class="go">立即连接 →</span>
              </div>
            </div>

            <div class="worldStats">
              <div><b>6+</b><span>全球区域</span></div>
              <div><b>99.9%</b><span>连接可用性</span></div>
              <div><b>48<i style="font-size:.5em;font-style:normal;">ms</i></b><span>平均延迟</span></div>
              <div><b>24/7</b><span>全天候智能调度</span></div>
            </div>
          </div>
        </div>
      </section>

      <!-- 3 / 纲领 -->
      <section class="manifesto" id="manifesto">
        <div class="shell">
          <div class="manifestoHead">
            <div class="manifestoTitle">NETWORK<br/>MANIFESTO</div>
            <p class="lead" style="max-width:26em;">三件事决定一条连接的好坏：谁来选路、能去哪里、谁看得到你。</p>
          </div>

          <div class="manifestoGrid">
            <article class="mCard">
              <span class="no">01 / 智能调度</span>
              <p class="slogan">不选择线路。<br/>让线路选择你。</p>
              <p>实时根据延迟、负载与可用性自动调度。连接遇到问题会自动尝试恢复，不需要你手动比较节点。</p>
              <span class="mLine"></span>
            </article>
            <article class="mCard">
              <span class="no">02 / 全球连接</span>
              <p class="slogan">地理有边界，<br/>网络不应该有。</p>
              <p>AI 工具、海外网站、高清流媒体，一套连接覆盖。手机、电脑与第三方客户端共用同一个账号。</p>
              <span class="mLine"></span>
            </article>
            <article class="mCard">
              <span class="no">03 / 隐私</span>
              <p class="slogan">你的通信，<br/>只属于你。</p>
              <p>保护每一次连接，让你专注于阅读、工作与探索。账户中的设备可以随时查看与管理。</p>
              <span class="mLine"></span>
            </article>
          </div>
        </div>
      </section>

      <!-- 4 / 客户端 -->
      <section class="clients" id="clients">
        <div class="shell">
          <p class="kicker">04 — Clients</p>
          <h2 style="margin-top:18px;">一个账号，所有设备。</h2>
          <div class="clientGrid">
            <div class="clientCard">
              <span class="os">ANDROID</span>
              <h3>星火 VPN for Android</h3>
              <p>轻点连接，自动选择合适线路。从日常浏览到移动办公，随时从容开启。</p>
              <a class="btn btn-ink" href="/download/android">下载 Android 版</a>
            </div>
            <div class="clientCard">
              <span class="os">WINDOWS</span>
              <h3>星火 VPN for Windows</h3>
              <p>为桌面工作准备的简洁连接工具。安装后，用同一邮箱登录即可开始。</p>
              <a class="btn btn-ink" href="/download/windows">下载安装包</a>
            </div>
            <div class="clientCard">
              <span class="os">THIRD PARTY</span>
              <h3>订阅链接</h3>
              <p>会员可在用户中心导出专属订阅链接，导入 兼容的客户端；泄露可随时重置。</p>
              <a class="btn btn-line" href="/dashboard" data-route="dashboard">前往用户中心</a>
            </div>
          </div>
          <p class="clientNote">客户端与官网共用账号体系，会员状态、到期时间实时同步。Android 与 Windows 均由官方签名分发，请只从本站下载。</p>
        </div>
      </section>

      <!-- 5 / 套餐 -->
      <section class="pricing" id="pricing">
        <div class="shell">
          <p class="kicker">05 — Plans</p>
          <h2 style="margin-top:18px;">从一次连接开始。</h2>
          <div class="planGrid" id="planGrid"></div>
          <p class="planFoot">价格为人民币，支持微信 / 支付宝。付款后由人工确认到账，通常几分钟内开通，会员状态自动同步官网与客户端。</p>
        </div>
      </section>

      <!-- 6 / 步骤 -->
      <section class="steps" id="steps">
        <div class="shell">
          <p class="kicker">06 — How it works</p>
          <h2 style="margin-top:18px;">四步接通。</h2>
          <div class="stepGrid">
            <div class="step"><span class="no">01</span><h3>注册账号</h3><p>邮箱加密码即可注册，无需验证码。有邀请码可一并填写。</p></div>
            <div class="step"><span class="no">02</span><h3>选择计划</h3><p>火种 / 燎原 / 远征，按周期选择，微信或支付宝付款。</p></div>
            <div class="step"><span class="no">03</span><h3>下载客户端</h3><p>Android、Windows 或第三方客户端导入订阅链接，任选其一。</p></div>
            <div class="step"><span class="no">04</span><h3>开始连接</h3><p>用同一邮箱登录，点击连接。自动为你选择合适线路。</p></div>
          </div>

          <div class="faqWrap">
            <details class="faq"><summary>会员在客户端和官网通用吗？</summary><p>通用。官网注册的邮箱账号可以直接在 Android、Windows 客户端登录，会员状态与到期时间自动同步，不需要额外绑定。</p></details>
            <details class="faq"><summary>付款后多久开通？</summary><p>提交付款后进入待确认队列，由人工核对到账，通常几分钟内完成。开通后客户端下次刷新即可看到会员状态。</p></details>
            <details class="faq"><summary>可以在几台设备上同时使用？</summary><p>同一账号支持手机与电脑同时在线。会员还可以导出订阅链接，在第三方开源客户端里使用；订阅链接与账号绑定，请勿分享。</p></details>
            <details class="faq"><summary>新账号有免费额度吗？</summary><p>新注册账号有一份免费体验流量，用完后需要开通会员继续使用。免费额度按实际使用流量计算。</p></details>
          </div>
        </div>
      </section>
    </section>

    <!-- ================= 用户中心 ================= -->
    <section class="page" id="page-dashboard">
      <div class="shell dash">

        <!-- 未登录：登录 / 注册 -->
        <div id="authView">
          <div class="authWrap">
            <div class="authAside">
              <p class="kicker">Dashboard</p>
              <h2 style="margin-top:22px;">登录，<br/>接管你的连接。</h2>
              <p>账号、会员状态、订阅链接与付款记录都在这里。官网只负责把产品讲清楚，其余全部收进用户中心。</p>
              <ul>
                <li>官网与客户端共用同一套账号</li>
                <li>会员到期时间实时同步</li>
                <li>订阅链接可随时重置，旧链接立即失效</li>
              </ul>
            </div>

            <div class="authBox">
              <div class="tabs">
                <button type="button" id="tabLogin" class="active">登录</button>
                <button type="button" id="tabRegister">注册</button>
              </div>

              <form id="loginForm">
                <label for="loginEmail">邮箱</label>
                <input id="loginEmail" type="email" autocomplete="email" required />
                <label for="loginPassword">密码</label>
                <input id="loginPassword" type="password" autocomplete="current-password" minlength="6" required />
                <button class="btn btn-ink" type="submit">登录</button>
                <p class="status" id="loginStatus"></p>
                <p class="switchLine">还没有账号？<button type="button" id="goRegister">去注册</button></p>
              </form>

              <form id="registerForm" class="hidden">
                <label for="registerEmail">邮箱</label>
                <input id="registerEmail" type="email" autocomplete="email" required />
                <label for="registerPassword">密码</label>
                <input id="registerPassword" type="password" autocomplete="new-password" minlength="6" required />
                <label for="registerInvite">邀请码（选填）</label>
                <input id="registerInvite" type="text" autocomplete="off" />
                <button class="btn btn-ink" type="submit">注册并进入用户中心</button>
                <p class="status" id="registerStatus"></p>
                <p class="switchLine">已经有账号？<button type="button" id="goLogin">去登录</button></p>
              </form>
            </div>
          </div>
        </div>

        <!-- 已登录：用户中心 -->
        <div id="centerView" class="hidden">
          <div class="dashHead">
            <div>
              <p class="kicker">Dashboard</p>
              <h2 style="margin-top:18px;">用户中心</h2>
            </div>
            <div class="rowActions" style="margin:0;">
              <a class="btn btn-gold btn-sm" href="/#pricing" data-route="home" data-anchor="pricing">开通 / 续费</a>
              <button class="btn btn-line btn-sm" id="logoutButton" type="button">退出登录</button>
            </div>
          </div>

          <div class="dashGrid">
            <div class="card">
              <h3>账号概览</h3>
              <div class="metrics">
                <div class="metric"><span>邮箱</span><strong id="meEmail">—</strong></div>
                <div class="metric"><span>会员状态</span><strong id="meVip">—</strong></div>
                <div class="metric"><span>到期时间</span><strong id="meExpiry">—</strong></div>
                <div class="metric"><span>邀请码</span><strong id="meInvite">—</strong></div>
              </div>
              <div class="rowActions">
                <a class="btn btn-line btn-sm" href="/download/android">下载 Android</a>
                <a class="btn btn-line btn-sm" href="/download/windows">下载 Windows</a>
                <button class="btn btn-line btn-sm" id="copyInvite" type="button">复制邀请码</button>
              </div>
            </div>

            <div class="dashTwo">
              <div class="card">
                <h3>连接权益</h3>
                <p id="trafficState">正在读取账号状态…</p>
                <p id="balanceState" style="margin-top:10px;">返现余额：—</p>
              </div>
              <div class="card">
                <h3>登录状态</h3>
                <p id="sessionState">正在读取登录状态…</p>
                <p style="margin-top:10px;">同一账号最多保留 2 个活跃会话（手机 + 电脑），第三次登录会挤掉最早的一个。</p>
              </div>
            </div>

            <div class="card" id="subscriptionCard">
              <h3>订阅链接</h3>
              <p>会员可导出专属订阅链接，导入 兼容的客户端。链接与账号绑定，请勿分享；如已泄露，点击“重置”即可让旧链接立即失效。</p>
              <p class="status" id="subscriptionStatus"></p>
              <div class="rowActions">
                <button class="btn btn-ink btn-sm" id="exportSubscription" type="button">导出订阅链接</button>
                <button class="btn btn-line btn-sm" id="copySubscription" type="button" disabled>复制链接</button>
                <button class="btn btn-line btn-sm" id="resetSubscription" type="button" disabled>重置</button>
              </div>
              <div class="hidden" id="subscriptionLinkBox">
                <input class="subInput" id="subscriptionLink" type="text" readonly onclick="this.select()" aria-label="订阅链接" />
                <p class="subMeta" id="subscriptionMeta"></p>
              </div>
            </div>
          </div>
        </div>

      </div>
    </section>

    <!-- ================= 404 ================= -->
    <section class="page" id="page-notfound">
      <div class="shell lost404">
        <div>
          <div class="code">404</div>
          <h2>这里暂时没有生产资料。</h2>
          <p>你要找的页面不在这条线路上。</p>
          <a class="btn btn-ink" href="/" data-route="home">返回首页 →</a>
        </div>
      </div>
    </section>
  </main>

  <footer>
    <div class="shell">
      <div class="footGrid">
        <div class="footBrand">
          <span class="brandName">MARX VPN · 星火</span>
          <p>连接世界，消除网络边界。面向 AI、全球网站与流媒体的智能网络服务。</p>
        </div>
        <div class="footCol">
          <h4>产品</h4>
          <a href="/#nodes" data-route="home" data-anchor="nodes">全球节点</a>
          <a href="/#pricing" data-route="home" data-anchor="pricing">套餐</a>
          <a href="/#clients" data-route="home" data-anchor="clients">客户端下载</a>
        </div>
        <div class="footCol">
          <h4>账户</h4>
          <a href="/dashboard" data-route="dashboard">用户中心</a>
          <a href="/dashboard" data-route="dashboard">订阅链接</a>
          <a href="/#steps" data-route="home" data-anchor="steps">使用指南</a>
        </div>
        <div class="footCol">
          <h4>联系</h4>
          <a href="https://t.me/+peCBtyuzOzNjNzA1" target="_blank" rel="noopener noreferrer">Telegram 官方群</a>
          <a href="/#steps" data-route="home" data-anchor="steps">常见问题</a>
        </div>
      </div>
      <div class="footBar">
        <span>© <span id="year">2026</span> MARX VPN — 星火</span>
        <span>UNLIMITED · SMART ROUTING · MULTI-DEVICE</span>
      </div>
    </div>
  </footer>

  <script>
    'use strict';

    const state = {
      token: localStorage.getItem('xingsui_token') || '',
      user: JSON.parse(localStorage.getItem('xingsui_user') || 'null'),
      plans: [],
      promo: null,
      subscription: null,
    };

    const $ = (id) => document.getElementById(id);
    const money = (cents) => {
      const value = cents / 100;
      return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0$/, '');
    };
    const fmtDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—';
    const authHeaders = () => state.token ? { Authorization: 'Bearer ' + state.token } : {};

    async function api(path, options = {}) {
      const headers = { Accept: 'application/json', ...(options.headers || {}) };
      if (options.body) headers['Content-Type'] = 'application/json; charset=utf-8';
      const response = await fetch(path, { ...options, headers: { ...headers, ...authHeaders() } });
      const text = await response.text();
      const data = text ? JSON.parse(text) : null;
      if (!response.ok || (data && data.success === false)) {
        const detail = (data && (data.message || (data.detail && data.detail.message) || data.detail)) || text || ('请求失败 ' + response.status);
        const error = new Error(typeof detail === 'string' ? detail : '请求失败，请稍后重试。');
        error.code = (data && (data.code || (data.detail && data.detail.code))) || '';
        throw error;
      }
      return data;
    }

    /* ================= 路由 ================= */
    const ROUTES = ['home', 'dashboard', 'notfound'];
    const PATH_TO_ROUTE = {
      '': 'home',
      'dashboard': 'dashboard',
      'center': 'dashboard',
      'login': 'dashboard',
      'register': 'dashboard',
      'account/subscription': 'dashboard',
      'user/subscription': 'dashboard',
      'vip': 'home',
      'download': 'home',
      'guide': 'home',
    };
    const PATH_TO_ANCHOR = { vip: 'pricing', download: 'clients', guide: 'steps' };

    function cleanPath() {
      let p = location.pathname;
      while (p.startsWith('/')) p = p.slice(1);
      while (p.endsWith('/')) p = p.slice(0, -1);
      return p;
    }

    function routeFromPath() {
      const p = cleanPath();
      if (p in PATH_TO_ROUTE) return PATH_TO_ROUTE[p];
      return 'notfound';
    }

    function renderRoute(route, anchor) {
      if (!ROUTES.includes(route)) route = 'notfound';
      document.querySelectorAll('section.page').forEach((page) => page.classList.remove('active'));
      const target = $('page-' + route);
      if (target) target.classList.add('active');
      document.querySelectorAll('.navLinks a').forEach((link) => {
        link.classList.toggle('active', link.dataset.route === route && (route !== 'home' || !anchor || link.dataset.anchor === anchor));
      });
      if (route === 'dashboard') refreshMe();
      if (route === 'home') {
        renderPlans();
        requestAnimationFrame(() => {
          const el = anchor ? $(anchor) : null;
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          else window.scrollTo({ top: 0, behavior: 'auto' });
        });
      } else {
        window.scrollTo({ top: 0, behavior: 'auto' });
      }
    }

    function navigate(route, anchor, replace) {
      let path = route === 'home' ? '/' : '/' + route;
      if (route === 'home' && anchor && anchor !== 'top') path = '/#' + anchor;
      history[replace ? 'replaceState' : 'pushState']({ route: route, anchor: anchor || '' }, '', path);
      renderRoute(route, anchor);
    }

    function bootRoute() {
      const p = cleanPath();
      const route = routeFromPath();
      const anchor = PATH_TO_ANCHOR[p] || (location.hash ? location.hash.slice(1) : '');
      renderRoute(route, anchor);
    }

    /* ================= 顶栏 ================= */
    const topbar = $('topbar');
    const onScroll = () => topbar.classList.toggle('stuck', window.scrollY > 12);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    $('menuToggle').addEventListener('click', () => {
      const open = $('navLinks').classList.toggle('open');
      $('menuToggle').setAttribute('aria-expanded', String(open));
    });

    document.addEventListener('click', (event) => {
      const el = event.target.closest('[data-route]');
      if (!el) return;
      event.preventDefault();
      navigate(el.dataset.route, el.dataset.anchor || '');
      $('navLinks').classList.remove('open');
      $('menuToggle').setAttribute('aria-expanded', 'false');
    });

    window.addEventListener('popstate', () => bootRoute());

    /* ================= 首屏锤镰动画 ================= */
    // 演示：锤镰平移扣合，连接中轻微明暗变化，成功由绿点与文字表达。
    const emblem = (function initEmblem() {
      const box = $('emblemBox');
      if (!box) return null;
      const readout = $('emReadout');
      const stateText = $('emState');
      const detailText = $('emDetail');
      const hintText = $('emHint');
      let timer = null;
      let phase = 'idle';

      function setPhase(next) {
        phase = next;
        box.classList.toggle('is-connecting', next === 'connecting');
        box.classList.toggle('is-locked', next === 'locked');
        readout.classList.toggle('emStage-locked', next === 'locked');
        if (next === 'connecting') {
          stateText.textContent = '正在连接';
          detailText.textContent = '正在建立安全连接';
          detailText.classList.remove('lost');
          hintText.textContent = '连接状态演示';
        } else if (next === 'locked') {
          stateText.textContent = '已连接';
          detailText.textContent = '连接动画演示 · 请在客户端建立实际连接';
          detailText.classList.remove('lost');
          hintText.textContent = '连接状态演示';
        } else {
          stateText.textContent = '连接已断开';
          detailText.textContent = '重新建立连接 →';
          detailText.classList.add('lost');
          hintText.textContent = '连接状态演示';
        }
      }

      function connect() {
        if (phase !== 'idle') return;
        setPhase('connecting');
        clearTimeout(timer);
        timer = setTimeout(() => setPhase('locked'), 1550);
      }

      function reset() {
        clearTimeout(timer);
        box.classList.remove('is-connecting', 'is-locked');
        readout.classList.remove('emStage-locked');
        phase = 'idle';
        stateText.textContent = '未连接';
        detailText.textContent = '当前网络处于空闲状态';
        detailText.classList.remove('lost');
        hintText.textContent = '连接状态演示';
      }

      box.addEventListener('mouseenter', connect);
      box.addEventListener('click', () => {
        if (phase === 'locked') { reset(); setTimeout(connect, 260); } else { connect(); }
      });
      box.tabIndex = 0;
      box.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); connect(); } });

      // 首次加载自动演示一次
      setTimeout(connect, 620);
      return { connect: connect, reset: reset };
    })();

    /* ================= 世界地图 ================= */
    // 5° 网格的陆地掩码：row = (90 - lat) / 5，col = (lon + 180) / 5。
    // 每行若干 [起列, 止列] 区间；只用于视觉，不参与任何业务判断。
    const LAND = {
      2:  [[12,22],[24,31],[39,40],[46,47],[54,56]],
      3:  [[11,22],[24,32],[40,41],[43,64]],
      4:  [[3,8],[9,22],[25,31],[38,42],[43,66]],
      5:  [[2,9],[10,22],[26,28],[31,32],[37,42],[43,68]],
      6:  [[2,8],[9,23],[34,36],[37,42],[43,69]],
      7:  [[10,24],[34,36],[37,42],[43,71]],
      8:  [[11,25],[35,42],[43,63],[64,65]],
      9:  [[11,22],[24,25],[34,42],[43,47],[48,62],[62,65]],
      10: [[11,20],[34,36],[38,44],[45,62],[62,65]],
      11: [[12,20],[34,42],[43,48],[49,62],[63,65]],
      12: [[13,20],[33,43],[43,48],[49,62]],
      13: [[14,16],[19,21],[32,43],[43,48],[49,61]],
      14: [[15,18],[20,23],[32,43],[43,47],[49,55],[55,61],[59,61]],
      15: [[18,19],[21,24],[32,44],[44,47],[50,54],[56,61],[59,61]],
      16: [[19,24],[33,45],[45,46],[51,52],[56,60],[59,61]],
      17: [[20,26],[33,45],[55,62]],
      18: [[19,29],[37,44],[55,64]],
      19: [[20,29],[38,44],[57,64],[64,66]],
      20: [[20,28],[38,44],[44,46],[58,62],[61,65],[64,66]],
      21: [[21,28],[38,44],[44,46],[58,66]],
      22: [[21,28],[38,43],[44,46],[58,66]],
      23: [[21,26],[39,42],[58,66]],
      24: [[21,25],[39,42],[59,65]],
      25: [[21,24],[64,65],[69,70]],
      26: [[21,23],[69,71]],
      27: [[21,22],[70,71]],
      28: [[21,22]],
      29: [[21,22]],
    };

    // 展示用节点（真实节点列表需要登录态，见 /vpn/nodes）
    const WORLD_NODES = [
      { id: 'beijing',   name: 'BEIJING 01',    cn: '北京',     lat: 39.9,  lon: 116.4, ping: '12 ms', load: '34%', proto: '智能接入', anchor: true },
      { id: 'tokyo',     name: 'TOKYO 01',      cn: '东京',     lat: 35.7,  lon: 139.7, ping: '31 ms', load: '18%', proto: '智能连接' },
      { id: 'hongkong',  name: 'HONG KONG 01',  cn: '香港',     lat: 22.3,  lon: 114.2, ping: '26 ms', load: '42%', proto: '智能连接' },
      { id: 'singapore', name: 'SINGAPORE 01',  cn: '新加坡',   lat: 1.35,  lon: 103.8, ping: '38 ms', load: '21%', proto: '智能连接' },
      { id: 'frankfurt', name: 'FRANKFURT 01',  cn: '法兰克福', lat: 50.1,  lon: 8.7,   ping: '164 ms', load: '12%', proto: '智能连接' },
      { id: 'losangeles',name: 'LOS ANGELES 01',cn: '洛杉矶',   lat: 34.05, lon: -118.2,ping: '148 ms', load: '27%', proto: '智能连接' },
      { id: 'sydney',    name: 'SYDNEY 01',     cn: '悉尼',     lat: -33.9, lon: 151.2, ping: '119 ms', load: '9%',  proto: '智能连接' },
    ];

    const ROUTES_PAIRS = [
      ['beijing', 'tokyo'], ['beijing', 'hongkong'], ['hongkong', 'singapore'],
      ['singapore', 'frankfurt'], ['tokyo', 'losangeles'], ['singapore', 'sydney'],
    ];

    (function drawWorld() {
      const svg = $('worldSvg');
      if (!svg) return;
      const W = 360, H = 190;
      const CELL = W / 72;             // 5° 一格
      const TOP_ROW = 2, BOTTOM_ROW = 30;
      const rows = BOTTOM_ROW - TOP_ROW;
      const rowH = H / rows;
      const x = (lon) => (lon + 180) / 360 * W;
      const y = (lat) => ((90 - lat) / 5 - TOP_ROW) * rowH;

      let dots = '';
      Object.keys(LAND).forEach((rowKey) => {
        const row = Number(rowKey);
        const cy = (row - TOP_ROW + 0.5) * rowH;
        LAND[row].forEach((range) => {
          for (let c = range[0]; c <= range[1]; c += 1) {
            const cx = (c + 0.5) * CELL;
            dots += '<circle class="landDot" cx="' + cx.toFixed(2) + '" cy="' + cy.toFixed(2) + '" r="0.82"/>';
          }
        });
      });

      const byId = {};
      WORLD_NODES.forEach((n) => { byId[n.id] = n; });

      let lines = '';
      ROUTES_PAIRS.forEach((pair, index) => {
        const a = byId[pair[0]], b = byId[pair[1]];
        if (!a || !b) return;
        const ax = x(a.lon), ay = y(a.lat), bx = x(b.lon), by = y(b.lat);
        const mx = (ax + bx) / 2, my = (ay + by) / 2 - Math.abs(bx - ax) * 0.16 - 6;
        const d = 'M' + ax.toFixed(1) + ' ' + ay.toFixed(1) + ' Q' + mx.toFixed(1) + ' ' + my.toFixed(1) + ' ' + bx.toFixed(1) + ' ' + by.toFixed(1);
        lines += '<path class="routeLine" id="route' + index + '" d="' + d + '"/>';
        lines += '<circle class="routeFlow" r="1.1"><animateMotion dur="' + (7 + index * 1.4).toFixed(1) +
                 's" repeatCount="indefinite" path="' + d + '"/></circle>';
      });

      let nodes = '';
      WORLD_NODES.forEach((n) => {
        const nx = x(n.lon), ny = y(n.lat);
        nodes += '<g class="nodeHit" data-node="' + n.id + '" transform="translate(' + nx.toFixed(2) + ',' + ny.toFixed(2) + ')">' +
                 '<circle class="nodeGlow" r="6"/>' +
                 '<circle class="nodePing" r="3"/>' +
                 '<circle class="nodeDot" r="' + (n.anchor ? 2.6 : 2.1) + '"/>' +
                 '<circle r="9" fill="transparent"/>' +
                 '<text class="nodeLabel" x="6" y="-4">' + n.cn + '</text>' +
                 '</g>';
      });

      svg.innerHTML =
        '<g>' + dots + '</g>' +
        '<g>' + lines + '</g>' +
        '<g>' + nodes + '</g>';

      const card = $('nodeCard');
      const wrap = $('worldMap');
      let hideTimer = null;

      function showCard(node, clientX, clientY) {
        clearTimeout(hideTimer);
        $('ncName').textContent = node.name;
        $('ncPing').textContent = node.ping;
        $('ncLoad').textContent = node.load;
        $('ncProto').textContent = node.proto;
        const rect = wrap.getBoundingClientRect();
        let left = clientX - rect.left + 16;
        let top = clientY - rect.top + 14;
        left = Math.min(left, rect.width - 212);
        left = Math.max(8, left);
        top = Math.max(8, Math.min(top, rect.height - 130));
        card.style.left = left + 'px';
        card.style.top = top + 'px';
        card.classList.add('show');
      }

      svg.querySelectorAll('.nodeHit').forEach((group) => {
        const node = byId[group.dataset.node];
        group.addEventListener('mouseenter', (e) => showCard(node, e.clientX, e.clientY));
        group.addEventListener('mousemove', (e) => showCard(node, e.clientX, e.clientY));
        group.addEventListener('mouseleave', () => {
          hideTimer = setTimeout(() => card.classList.remove('show'), 120);
        });
        group.addEventListener('click', () => navigate('home', 'pricing'));
      });
    })();

    /* ================= 套餐 ================= */
    const PLAN_META = {
      plan_month: {
        title: '火种计划',
        tagline: '第一次连接世界。',
        features: ['全球优质节点', '无限流量', 'AI 专线', '多设备同步'],
        cta: '开始连接 →',
        theme: '',
      },
      plan_quarter: {
        title: '燎原计划',
        tagline: '最受欢迎。稳定使用，综合成本更低。',
        features: ['包含火种计划全部权益', '长期线路优化', '手机 + 电脑同时在线', '订阅链接导出'],
        cta: '选择燎原 →',
        theme: 'featured',
        tag: '最受欢迎',
      },
      plan_year: {
        title: '远征计划',
        tagline: '长期连接，无需反复续费。',
        features: ['包含全部会员权益', '一年内无需续费', '优先体验新增节点', '订阅链接导出'],
        cta: '选择远征 →',
        theme: 'gold',
        tag: '年度最省',
      },
    };

    const FALLBACK_PLANS = [
      { id: 'plan_month', name: '火种计划', duration_days: 30, original_price_cents: 2880, sale_price_cents: 1800 },
      { id: 'plan_quarter', name: '燎原计划', duration_days: 90, original_price_cents: 8640, sale_price_cents: 4800 },
      { id: 'plan_year', name: '远征计划', duration_days: 365, original_price_cents: 34560, sale_price_cents: 15800 },
    ];

    function renderPlans() {
      const box = $('planGrid');
      if (!box) return;
      const order = { plan_month: 1, plan_quarter: 2, plan_year: 3 };
      const plans = (state.plans.length ? state.plans : FALLBACK_PLANS)
        .slice()
        .sort((a, b) => (order[a.id] || 99) - (order[b.id] || 99));

      box.innerHTML = plans.map((plan) => {
        const promo = (state.promo && state.promo.plan_id === plan.id) ? state.promo : null;
        const sale = (promo && promo.promo_price_cents) || plan.sale_price_cents;
        const meta = PLAN_META[plan.id] || {
          title: plan.name, tagline: '稳定连接全球网络。',
          features: ['不限流量', '智能线路调度', '多端同步'], cta: '选择套餐 →', theme: '',
        };
        const months = Math.round(plan.duration_days / 30);
        const per = months > 1 ? Math.round((sale / 100 / months) * 10) / 10 : 0;
        const perText = months > 1 ? ('折合 ¥' + per + ' / 月') : '首次开通特惠';
        return '<article class="plan ' + meta.theme + '">' +
          (meta.tag ? '<span class="tag">' + meta.tag + '</span>' : '') +
          '<h3>' + meta.title + '</h3>' +
          '<p class="tagline">' + meta.tagline + '</p>' +
          '<div class="price"><em>¥</em><b>' + money(sale) + '</b><span>/ ' + plan.duration_days + ' 天</span></div>' +
          '<p class="per">' + perText + '</p>' +
          '<ul>' + meta.features.map((f) => '<li>' + f + '</li>').join('') + '</ul>' +
          '<button class="btn ' + (meta.theme === 'featured' ? 'btn-gold' : 'btn-ink') + '" data-buy="' + plan.id + '">' + meta.cta + '</button>' +
          '</article>';
      }).join('');

      box.querySelectorAll('[data-buy]').forEach((button) => {
        button.addEventListener('click', () => startOrder(button.dataset.buy));
      });
    }

    function startOrder(planId) {
      if (!state.token) {
        navigate('dashboard');
        return;
      }
      location.href = '/payment?' + new URLSearchParams({ plan_id: planId }).toString();
    }

    async function loadOffer() {
      try {
        const results = await Promise.all([
          api('/plans'),
          api('/promotions/active').catch(() => null),
        ]);
        state.plans = results[0] || [];
        state.promo = results[1];
      } catch (_) { /* 接口不可用时用兜底价渲染 */ }
      renderPlans();
    }

    /* ================= 账号 ================= */
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
      state.subscription = null;
      localStorage.removeItem('xingsui_token');
      localStorage.removeItem('xingsui_user');
      renderAuthState();
    }

    function renderAuthState() {
      const navAuth = $('navAuth');
      if (navAuth) navAuth.textContent = state.token ? '用户中心' : '登录';
      $('authView').classList.toggle('hidden', Boolean(state.token));
      $('centerView').classList.toggle('hidden', !state.token);
    }

    function vipText(status) {
      if (status === 'active') return '会员有效';
      if (status === 'expired') return '已过期';
      return '未开通';
    }

    async function refreshMe() {
      renderAuthState();
      if (!state.token) return;
      try {
        const me = await api('/me');
        state.user = me;
        localStorage.setItem('xingsui_user', JSON.stringify(me));
        $('meEmail').textContent = me.email;
        $('meVip').textContent = vipText(me.vip_status);
        $('meVip').classList.toggle('gold', me.vip_status === 'active');
        $('meExpiry').textContent = fmtDate(me.vip_expired_at);
        $('meInvite').textContent = me.invite_code;
        $('sessionState').textContent = '当前浏览器已登录，账号 ID：' + me.id + '。';
        $('trafficState').textContent = me.vip_status === 'active'
          ? '会员有效，不限流量。登录客户端即可开始使用。'
          : '当前为免费额度，用完后需要开通会员继续连接。';
        $('balanceState').textContent = '返现余额：' + money(me.cash_balance_cents) + ' 元';
        renderSubscriptionCard();
      } catch (error) {
        clearAuth();
        $('loginStatus').className = 'status err';
        $('loginStatus').textContent = '登录已失效，请重新登录。';
      }
    }

    /* ---- 订阅链接 ---- */
    function subscriptionErrorMessage(error) {
      const code = (error && error.code) || '';
      if (code === 'VIP_REQUIRED') return '开通会员后即可导出订阅链接。';
      if (code === 'VIP_EXPIRED') return '会员已过期，请续费后继续使用。';
      if (code === 'ACCOUNT_FROZEN') return '账号状态异常，请联系客服。';
      if (code === 'RATE_LIMITED') return '请求过于频繁，请稍后再试。';
      if (code === 'UNAUTHORIZED') return '请先登录后查看订阅链接。';
      return (error && error.message) || '订阅链接生成失败，请稍后重试。';
    }

    function renderSubscriptionCard() {
      const status = $('subscriptionStatus');
      const exportBtn = $('exportSubscription');
      const copyBtn = $('copySubscription');
      const resetBtn = $('resetSubscription');
      const linkBox = $('subscriptionLinkBox');
      const linkInput = $('subscriptionLink');
      const meta = $('subscriptionMeta');
      if (!status) return;

      const url = state.subscription && state.subscription.subscription_url;
      linkBox.classList.toggle('hidden', !url);
      linkInput.value = url || '';
      meta.textContent = state.subscription
        ? ('Token ' + state.subscription.masked_token + ' · 到期 ' + fmtDate(state.subscription.expires_at))
        : '';
      copyBtn.disabled = !url;
      resetBtn.disabled = !url;

      const vip = state.user && state.user.vip_status;
      if (vip === 'expired') {
        status.className = 'status err';
        status.textContent = '会员已过期，请续费后继续使用。';
        exportBtn.textContent = '去续费';
      } else if (vip !== 'active') {
        status.className = 'status';
        status.textContent = '开通会员后即可导出订阅链接。';
        exportBtn.textContent = '去开通';
      } else {
        status.className = 'status ok';
        status.textContent = url ? '订阅链接已生成，可复制到第三方客户端使用。' : '点击“导出订阅链接”生成专属链接。';
        exportBtn.textContent = '导出订阅链接';
      }
    }

    async function exportSubscriptionLink() {
      const status = $('subscriptionStatus');
      const exportBtn = $('exportSubscription');
      if (!state.token) { navigate('dashboard'); return; }
      if (!state.user || state.user.vip_status !== 'active') { navigate('home', 'pricing'); return; }
      exportBtn.disabled = true;
      status.className = 'status';
      status.textContent = '正在生成订阅链接…';
      try {
        state.subscription = await api('/user/subscription-link');
        renderSubscriptionCard();
      } catch (error) {
        status.className = 'status err';
        status.textContent = subscriptionErrorMessage(error);
      } finally {
        exportBtn.disabled = false;
      }
    }

    async function copySubscriptionLink() {
      const value = (state.subscription && state.subscription.subscription_url) || $('subscriptionLink').value;
      if (!value) return;
      try {
        await navigator.clipboard.writeText(value);
        $('subscriptionStatus').className = 'status ok';
        $('subscriptionStatus').textContent = '订阅链接已复制。';
      } catch (_) {
        $('subscriptionLinkBox').classList.remove('hidden');
        $('subscriptionLink').focus();
        $('subscriptionLink').select();
        $('subscriptionStatus').className = 'status';
        $('subscriptionStatus').textContent = '复制失败，请手动复制输入框中的链接。';
      }
    }

    async function resetSubscriptionLink() {
      if (!state.subscription || !state.subscription.subscription_url) return;
      if (!confirm('重置后旧订阅链接将立即失效，是否继续？')) return;
      const status = $('subscriptionStatus');
      const resetBtn = $('resetSubscription');
      resetBtn.disabled = true;
      status.className = 'status';
      status.textContent = '正在重置…';
      try {
        state.subscription = await api('/user/subscription-link/reset', { method: 'POST' });
        renderSubscriptionCard();
      } catch (error) {
        status.className = 'status err';
        status.textContent = subscriptionErrorMessage(error);
      } finally {
        resetBtn.disabled = false;
      }
    }

    /* ================= 登录 / 注册表单 ================= */
    function showAuthTab(which) {
      const isLogin = which === 'login';
      $('tabLogin').classList.toggle('active', isLogin);
      $('tabRegister').classList.toggle('active', !isLogin);
      $('loginForm').classList.toggle('hidden', !isLogin);
      $('registerForm').classList.toggle('hidden', isLogin);
    }

    $('tabLogin').addEventListener('click', () => showAuthTab('login'));
    $('tabRegister').addEventListener('click', () => showAuthTab('register'));
    $('goRegister').addEventListener('click', () => showAuthTab('register'));
    $('goLogin').addEventListener('click', () => showAuthTab('login'));

    $('loginForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const status = $('loginStatus');
      status.className = 'status';
      status.textContent = '正在登录…';
      try {
        const session = await api('/auth/email/login', {
          method: 'POST',
          body: JSON.stringify({ email: $('loginEmail').value, password: $('loginPassword').value }),
        });
        setAuth(session);
        status.className = 'status ok';
        status.textContent = '登录成功';
        refreshMe();
      } catch (error) {
        status.className = 'status err';
        status.textContent = error.message;
      }
    });

    $('registerForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const status = $('registerStatus');
      status.className = 'status';
      status.textContent = '正在注册…';
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
        refreshMe();
      } catch (error) {
        status.className = 'status err';
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
      if (!state.user || !state.user.invite_code) return;
      try { await navigator.clipboard.writeText(state.user.invite_code); } catch (_) { /* 忽略 */ }
    });

    $('exportSubscription').addEventListener('click', exportSubscriptionLink);
    $('copySubscription').addEventListener('click', copySubscriptionLink);
    $('resetSubscription').addEventListener('click', resetSubscriptionLink);

    /* ================= 启动 ================= */
    $('year').textContent = String(new Date().getFullYear());
    renderAuthState();
    renderSubscriptionCard();
    bootRoute();
    loadOffer();
    if (state.token) refreshMe();
  </script>
</body>
</html>"""
