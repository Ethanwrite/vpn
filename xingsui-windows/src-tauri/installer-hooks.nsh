; 星火 VPN —— NSIS 安装钩子
;
; 背景：1.0.24 把 productName 从「星隧VPN」改成「星火VPN」。而 Tauri 的模板里
;   !define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCTNAME}"
; 卸载注册表键与安装目录都由 productName 决定，所以改名后新版**认不出**老版：
; 老用户会留下两条「添加或删除程序」记录，外加一个含旧 sing-box / wintun.dll 的
; 孤儿目录 C:\Program Files\星隧VPN\。
;
; 因此在复制文件之前先把旧产品静默卸干净。卸载失败不阻断安装（只打日志），
; 宁可多留一条记录，也不能让用户装不上。
;
; 注意：本文件以 UTF-8 (BOM) 保存 —— installer.nsi 开了 Unicode true，
; 没有 BOM 时 NSIS 可能按 ANSI 解析，里面的中文产品名就会对不上注册表键。

!define XF_LEGACY_NAME "星隧VPN"
!define XF_LEGACY_UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${XF_LEGACY_NAME}"

!macro NSIS_HOOK_PREINSTALL
  Push $0
  Push $1

  ; ---------- perMachine 安装（当前配置就是这个，主要路径） ----------
  ClearErrors
  ReadRegStr $0 HKLM "${XF_LEGACY_UNINSTKEY}" "UninstallString"
  IfErrors xf_legacy_hklm_done
  StrCmp $0 "" xf_legacy_hklm_done

  ReadRegStr $1 HKLM "${XF_LEGACY_UNINSTKEY}" "InstallLocation"
  StrCmp $1 "" 0 +2
    StrCpy $1 "$PROGRAMFILES64\${XF_LEGACY_NAME}"

  DetailPrint "检测到旧版 ${XF_LEGACY_NAME}，正在移除：$1"
  ; _?= 让卸载器就地同步执行（不自拷到临时目录），ExecWait 才真的等得到它结束；
  ; 代价是卸载器自身不会自删，所以下面手动清。
  ExecWait '"$1\uninstall.exe" /S _?=$1'
  Delete "$1\uninstall.exe"
  RMDir "$1"
  DeleteRegKey HKLM "${XF_LEGACY_UNINSTKEY}"
xf_legacy_hklm_done:

  ; ---------- perUser 安装（历史配置可能留下的，顺带清掉） ----------
  ClearErrors
  ReadRegStr $0 HKCU "${XF_LEGACY_UNINSTKEY}" "UninstallString"
  IfErrors xf_legacy_hkcu_done
  StrCmp $0 "" xf_legacy_hkcu_done

  ReadRegStr $1 HKCU "${XF_LEGACY_UNINSTKEY}" "InstallLocation"
  StrCmp $1 "" 0 +2
    StrCpy $1 "$LOCALAPPDATA\${XF_LEGACY_NAME}"

  DetailPrint "检测到旧版 ${XF_LEGACY_NAME}（当前用户），正在移除：$1"
  ExecWait '"$1\uninstall.exe" /S _?=$1'
  Delete "$1\uninstall.exe"
  RMDir "$1"
  DeleteRegKey HKCU "${XF_LEGACY_UNINSTKEY}"
xf_legacy_hkcu_done:

  ; ---------- 残留快捷方式 ----------
  Delete "$SMPROGRAMS\${XF_LEGACY_NAME}.lnk"
  Delete "$DESKTOP\${XF_LEGACY_NAME}.lnk"

  Pop $1
  Pop $0
!macroend
