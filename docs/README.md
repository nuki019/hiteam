# HiTeam 本地 HTML 原型

这个目录是一个纯静态原型，不需要后端服务。

## 打开方式

双击 `index.html`，或在浏览器中打开：

`C:\Users\wfy\Desktop\HiTeam\index.html`

### 一键启动本地服务

电脑重启后，双击桌面的 `HiTeam-本地启动.lnk`，或双击项目目录里的 `start-hiteam.cmd` 即可。它会自动启动本地服务并打开：

`http://127.0.0.1:8765/index.html`

如果服务已经启动，脚本只会打开页面，不会重复启动。脚本依赖 Python 3；如果系统没有 Python，会弹出提示。

## 文件结构

- `index.html`：页面入口和各功能视图骨架。
- `assets/styles.css`：布局、响应式、表单和列表样式。
- `assets/app.js`：项目库联想、项目与竞赛关联、标签匹配、发布、申请审核、消息、角色治理和文件管理逻辑。
- `assets/hiteam-board.svg`：本地视觉资产。
- `PRODUCT.md`：产品目标、当前范围、验收标准和下一步优化优先级。
- `DESIGN.md`：HiTeam 的界面设计方向、组件规则、交互与可访问性约束。
- `awesome-design-md/`：复制自 `D:\awesome-design-md` 的外部 DESIGN.md 参考集合。
- `docs/README.md`：本说明。

## 本地数据

原型使用浏览器 `localStorage` 保存数据。文件管理页提供：

- 导出完整 JSON 备份。
- 导入 JSON 恢复数据。
- 附件入库，记录到本地文件库。
- 清空本地数据。
- 恢复演示数据。
