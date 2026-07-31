# 插件依赖宿主预装 Python 包

## 现象
系统或 Homebrew Python 缺少 PyYAML/jsonschema 时 CLI 与 Hook 无法启动。
## 影响
插件安装成功不代表可执行。
## 根因
控制程序直接 import 第三方包，插件包未携带运行时。
## 旧门禁为何没拦截
回归只在已安装依赖的开发 Python 中运行。
## 修复
随插件携带 PyYAML 纯 Python 运行时，并提供覆盖现有 Schema 关键字的标准库验证 fallback。
## 回归
使用 `/usr/bin/python3` 执行 doctor。
## 预防规则
插件启动链不得依赖宿主偶然存在的 Python site-packages。
