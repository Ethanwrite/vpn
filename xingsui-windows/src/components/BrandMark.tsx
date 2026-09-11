// 星火 VPN 黑金标志（实心版）：黑盘 + 金环 + 锤镰剪影。
// ≤48px 的场景一律用实心——空心线框在这个尺寸会糊成一团。
// 轮廓数据与官网、Android 完全同源。

interface Props {
  className?: string;
}

export default function BrandMark({ className = "h-8 w-8" }: Props) {
  return (
    <svg className={className} viewBox="0 0 200 200" aria-hidden="true">
      <defs>
        <linearGradient id="brandMarkGold" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#E6C87C" />
          <stop offset="1" stopColor="#A8801F" />
        </linearGradient>
      </defs>
      <circle cx="100" cy="100" r="96" fill="#0D0D0C" />
      <circle
        cx="100"
        cy="100"
        r="86"
        fill="none"
        stroke="url(#brandMarkGold)"
        strokeWidth="2.5"
      />
      <g fill="url(#brandMarkGold)">
        <path d="M126 38A57.29 57.29 0 0 1 136 150A80.78 80.78 0 0 0 126 38Z" />
        <path d="M68.72 159.97L130.54 155.48A7.5 7.5 0 0 0 130.06 140.5L68.08 140A10 10 0 1 0 68.72 159.97Z" />
        <path d="M75.51 88.82L135.2 145.09A7 7 0 0 0 144.92 135.03L86.63 77.31L75.51 88.82Z" />
        <path d="M94.27 53.64L102.77 68.36A2 2 0 0 1 102.03 71.09L60.47 95.09A2 2 0 0 1 57.73 94.36L49.23 79.64A2 2 0 0 1 49.97 76.91L91.53 52.91A2 2 0 0 1 94.27 53.64Z" />
        <path d="M47.5 86A4.5 4.5 0 1 0 56.5 86A4.5 4.5 0 1 0 47.5 86Z" />
      </g>
    </svg>
  );
}
