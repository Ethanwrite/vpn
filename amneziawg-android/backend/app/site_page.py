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
        linear-gradient(135deg, rgba(25, 197, 162, .08) 0 25%, transparent 25% 50%, rgba(45, 215, 239, .08) 50% 75%, transparent 75%) 0 0 / 28px 28px,
        radial-gradient(circle at 72% 8%, rgba(107, 92, 255, .16), transparent 34%),
        linear-gradient(180deg, #f7fffe 0, #eff9ff 44%, #ffffff 100%);
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
    .links a.active, .links a:hover, .ghost:hover { background: #e8fbf7; color: var(--mint-dark); border-color: var(--line); }
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
    .primary { background: linear-gradient(135deg, #18d0ad, #23c2ff); color: #062430; box-shadow: 0 14px 34px rgba(20, 177, 164, .22); }
    .secondary { border: 1px solid var(--line); color: var(--blue); background: #fff; }
    .danger { background: #fff1f1; color: var(--danger); border: 1px solid #ffd6d6; }
    .hero { min-height: calc(100vh - 70px); display: grid; grid-template-columns: 1.08fr .92fr; gap: 28px; align-items: center; padding: 40px 0 28px; }
    .tag { display: inline-flex; width: fit-content; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 999px; color: #8a4b00; background: #fff1d5; border: 1px solid #ffd89a; font-weight: 900; }
    h1 { margin: 16px 0 10px; font-size: clamp(42px, 7vw, 76px); line-height: 1; color: var(--blue); letter-spacing: 0; }
    .lead { margin: 0; max-width: 650px; color: var(--muted); font-size: clamp(17px, 2.3vw, 22px); line-height: 1.75; }
    .priceLine { display: flex; align-items: baseline; flex-wrap: wrap; gap: 12px; margin-top: 22px; }
    .now { font-size: clamp(38px, 6vw, 62px); color: var(--mint-dark); font-weight: 950; }
    .old { color: #9aa8b6; text-decoration: line-through; font-size: 18px; }
    .countdown { color: var(--gold); font-weight: 900; }
    .heroActions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }
    .heroPanel {
      position: relative;
      min-height: 540px;
      border-radius: 28px;
      background:
        radial-gradient(circle at 50% 35%, rgba(25, 197, 162, .18), transparent 32%),
        linear-gradient(180deg, rgba(255, 255, 255, .93), rgba(247, 255, 254, .82));
      border: 1px solid var(--line);
      box-shadow: 0 24px 80px rgba(48, 97, 118, .18);
      overflow: hidden;
      padding: 24px;
      display: grid;
      place-items: center;
    }
    .heroPanel:before {
      content: "";
      position: absolute;
      inset: 0;
      opacity: .5;
      background: linear-gradient(135deg, rgba(25, 197, 162, .16) 0 25%, transparent 25% 50%, rgba(25, 197, 162, .13) 50% 75%, transparent 75%) 0 0 / 18px 18px;
    }
    .phone {
      position: relative;
      z-index: 1;
      width: min(330px, 100%);
      border-radius: 34px;
      background: var(--surface);
      border: 1px solid rgba(217, 238, 235, .9);
      box-shadow: 0 28px 80px rgba(16, 46, 78, .2);
      padding: 20px;
    }
    .userRow, .nodeRow, .miniNav { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .avatar { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #1ed3b1, #6b5cff); box-shadow: inset 0 0 0 5px rgba(255,255,255,.7); }
    .cardTitle { font-size: 13px; color: var(--muted); margin: 0; }
    .cardValue { margin: 4px 0 0; color: var(--ink); font-weight: 900; }
    .charge { min-height: 42px; border: 0; border-radius: 8px; padding: 0 16px; color: white; font-weight: 900; background: linear-gradient(135deg, #ffad2f, #ff7a1a); }
    .switch { margin-left: auto; width: 62px; height: 34px; border-radius: 999px; background: #d9e3e8; padding: 4px; }
    .switch span { display:block; width: 26px; height: 26px; border-radius: 50%; background: #9ba8ae; }
    .power { width: 210px; height: 210px; border-radius: 50%; margin: 54px auto 40px; display: grid; place-items: center; background: rgba(25,197,162,.18); box-shadow: 0 0 0 32px rgba(25,197,162,.07); }
    .powerInner { width: 132px; height: 132px; border-radius: 50%; display: grid; place-items: center; background: white; border: 1px solid var(--line); box-shadow: 0 12px 30px rgba(34, 113, 115, .14); color: var(--mint-dark); font-size: 24px; font-weight: 950; }
    .nodeRow { border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; background: #fff; }
    .smart { margin-top: 14px; border: 0; color: #063323; background: linear-gradient(135deg, #20d0a3, #0dc27f); min-height: 54px; width: 100%; border-radius: 12px; font-weight: 900; font-size: 16px; }
    .miniNav { margin: 32px 16px 4px; color: #8fa1ad; font-weight: 800; }
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
      box-shadow: 0 12px 36px rgba(57, 104, 122, .08);
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
    .planPrice { display: flex; align-items: baseline; gap: 8px; margin: 12px 0; }
    .planPrice b { color: var(--mint-dark); font-size: 34px; }
    .planPrice span { text-decoration: line-through; color: #9aa8b6; }
    .orderBox { display: none; margin-top: 18px; }
    .orderBox.active { display: block; }
    .qr { width: 210px; height: 210px; object-fit: contain; border: 1px solid var(--line); border-radius: 8px; background: white; padding: 8px; }
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
      .heroPanel { min-height: 480px; }
      .grid.three, .grid.two, .metrics { grid-template-columns: 1fr; }
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
        <span class="tag">限时特惠 · 新人专享 · 30MB 免费体验</span>
        <h1>星隧</h1>
        <p class="lead">为日常网络加速和安全连接打造的轻量 VPN 产品。官网注册、App 登录、会员状态自动同步，新用户自带 30MB 体验流量，打开 App 即可一键连接。</p>
        <div class="priceLine">
          <span class="now" id="homeNow">18 元/月</span>
          <span class="old" id="homeOld">原价 28.8 元</span>
          <span class="countdown" id="homeCountdown">优惠加载中</span>
        </div>
        <div class="heroActions">
          <a class="primary" href="/register" data-route="register">立即注册</a>
          <a class="secondary" href="/download" data-route="download">下载 Android APK</a>
          <a class="secondary" href="/vip" data-route="vip">查看套餐</a>
        </div>
      </div>
      <div class="heroPanel" aria-label="App 界面预览">
        <div class="phone">
          <div class="userRow">
            <div class="avatar"></div>
            <div>
              <p class="cardTitle">ID：<span id="previewId">52036</span></p>
              <p class="cardValue">VIP：<span id="previewVip">待开通</span></p>
            </div>
            <button class="charge" data-route="vip">充值</button>
          </div>
          <div class="userRow" style="margin-top: 36px;">
            <span class="muted">局部模式</span>
            <div class="switch"><span></span></div>
          </div>
          <div class="power"><div class="powerInner">Start</div></div>
          <div class="nodeRow">
            <strong>当前节点：智能匹配</strong>
            <span style="color: var(--mint-dark); font-size: 24px;">›</span>
          </div>
          <button class="smart">智能匹配最快节点</button>
          <div class="miniNav"><span style="color: var(--mint-dark);">首页</span><span>我的</span></div>
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
            <p id="trafficState">注册用户可用 30MB 体验流量一键连接；用完后开通 VIP 继续使用。</p>
            <p id="balanceState" class="muted">返现余额：-</p>
          </div>
        </div>
      </div>
    </section>

    <section class="shell page" id="page-vip">
      <div class="sectionHead">
        <div>
          <h2>VIP 套餐</h2>
          <p>当前月度会员限时 18 元，下单后按页面提示完成付款，到账后自动同步会员状态。</p>
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
          <p>安装后使用官网账号登录，会员状态实时同步。</p>
        </div>
        <div class="actions">
          <a class="primary" href="/download/android">下载 Android APK</a>
          <a class="secondary" href="/download/windows">下载 Windows 版</a>
        </div>
      </div>
      <div class="grid three">
        <div class="panel"><h3>统一账号</h3><p>官网注册后，App 直接用邮箱和密码登录。</p></div>
        <div class="panel"><h3>会员同步</h3><p>订单完成后，App 首页会刷新 VIP 状态。</p></div>
        <div class="panel"><h3>连接入口</h3><p>App 首页有明显连接按钮，非 VIP 会引导开通。</p></div>
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
    </section>
  </main>

  <footer>
    <div class="shell">星隧 · 安全高速网络通道 · 官网账号与 App 会员状态同步</div>
  </footer>

  <script>
    const state = {
      token: localStorage.getItem('xingsui_token') || '',
      user: JSON.parse(localStorage.getItem('xingsui_user') || 'null'),
      plans: [],
      promo: null,
      currentOrder: null,
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
      if (!response.ok) throw new Error(data?.detail || text || `请求失败 ${response.status}`);
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
      renderAuthState();
    }

    function routeFromPath() {
      const clean = location.pathname.replace(/^\\//, '') || 'home';
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
      if (route === 'center') refreshMe();
      if (route === 'vip') renderPlans();
    }

    function renderAuthState() {
      $('loginLink').textContent = state.token ? '用户中心' : '登录';
      $('loginLink').dataset.route = state.token ? 'center' : 'login';
      $('loginLink').setAttribute('href', state.token ? '/center' : '/login');
      if (state.user) {
        $('previewId').textContent = state.user.id.slice(0, 5).toUpperCase();
        $('previewVip').textContent = vipText(state.user.vip_status);
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
      } catch (error) {
        clearAuth();
        $('sessionState').textContent = '登录已失效，请重新登录。';
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
      const plans = state.plans.length ? state.plans : [
        { id: 'plan_month', name: '月度会员', duration_days: 30, original_price_cents: 2880, sale_price_cents: 1800 },
        { id: 'plan_quarter', name: '季度会员', duration_days: 90, original_price_cents: 8640, sale_price_cents: 5800 },
        { id: 'plan_year', name: '年度会员', duration_days: 365, original_price_cents: 34560, sale_price_cents: 19800 },
      ];
      box.innerHTML = plans.map(plan => {
        const promo = state.promo?.plan_id === plan.id ? state.promo : null;
        const sale = promo?.promo_price_cents || plan.sale_price_cents;
        const hot = plan.id === 'plan_month' ? ' hot' : '';
        return `<article class="plan${hot}">
          <span class="badge">${promo?.tag || (plan.id === 'plan_month' ? '限时特惠' : '稳定套餐')}</span>
          <h3>${plan.name}</h3>
          <p>${plan.duration_days} 天会员 · 官网与 App 自动同步</p>
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
    $('payChannel').addEventListener('change', () => {
      if (state.currentOrder) createOrder(state.currentOrder.plan_id);
    });
    $('submitPaid').addEventListener('click', submitPaid);

    renderAuthState();
    renderRoute(routeFromPath());
    loadOffer();
    if (state.token) refreshMe();
  </script>
</body>
</html>"""
