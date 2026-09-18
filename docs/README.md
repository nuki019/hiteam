# HiTeam 本地应用说明

当前版本是单页 HTML/CSS/JavaScript 前端加无依赖 Python/SQLite 后端。认证、档案、招募、申请、审核、消息、目录和草稿使用后端持久化；文件附件、界面偏好和 JSON 备份仍保存在当前浏览器。

## 打开方式

不要直接双击 `index.html` 作为完整运行方式。当前页面启动时会请求认证接口，请先启动本地服务。

### 一键启动本地服务

电脑重启后，双击项目目录里的 `start-hiteam.cmd`。脚本会自动启动静态服务和后端，并打开：

`http://127.0.0.1:8765/index.html`

如果服务已经启动，脚本只会打开页面，不会重复启动。脚本依赖 Python 3；如果系统没有 Python，会弹出提示。

## 文件结构

- `index.html`：页面入口和各功能视图骨架。
- `assets/styles.css`：布局、响应式、表单和列表样式。
- `assets/app.js`：项目库联想、项目与竞赛关联、标签匹配、发布、申请审核、消息、角色治理和文件管理逻辑。
- `assets/hiteam-board.svg`：本地视觉资产。
- `backend/server.py`：认证、SQLite 数据模型和 HTTP API。
- `PRODUCT.md`：产品目标、当前范围、验收标准和下一步优化优先级。
- `DESIGN.md`：HiTeam 的界面设计方向、组件规则、交互与可访问性约束。
- `awesome-design-md/`：复制自 `D:\awesome-design-md` 的外部 DESIGN.md 参考集合。
- `docs/README.md`：本说明。

## 本地数据

文件管理页使用浏览器本地存储提供：

- 导出完整 JSON 备份。
- 导入 JSON 恢复本地缓存与附件。
- 附件入库，记录到本地文件库。
- 清空或重置本地缓存；服务器上的招募、申请、消息和草稿不会被删除。
