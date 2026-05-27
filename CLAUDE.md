# CLAUDE.md

本文件供 AI 助手（如 Claude Code）理解项目结构和开发规范。

## 项目定位

**PDF 差异对比系统** —— 用于合同/文档审核场景，对比电子原件与盖章扫描件，自动识别差异并支持人工审核归档。

核心价值：**准确 + 好用 + 通用**。算法已验证 23 条真实差异 0 误报。

## 技术栈

| 层 | 技术 |
|---|---|
| 算法 | PyMuPDF（矢量抽文字）+ RapidOCR（PP-OCRv4 中文 OCR）+ difflib + 自研字符流 diff |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2 + Alembic + RQ + Redis + PostgreSQL 16 |
| 前端 | React 19 + TypeScript + Vite + Tailwind v3 + TanStack Query + Zustand + pdf.js |
| 部署 | Docker Compose（postgres + redis + api + worker + frontend）|

## 项目结构

```
pdf-diff/
├── backend/
│   ├── pipeline/          ← 核心 diff 算法（独立可单跑）
│   │   ├── extract.py     PyMuPDF 直抽矢量文字
│   │   ├── ocr.py         RapidOCR 扫描件识别
│   │   ├── stamp_mask.py  HSV 红章检测
│   │   ├── stream.py      字符流 + 反查表构建
│   │   ├── normalize.py   规范化（OCR 形近字白名单）
│   │   ├── diff.py        全文档 diff + move 检测 + 分类聚合
│   │   └── cache.py       按 SHA1 缓存 OCR
│   ├── app/
│   │   ├── main.py        FastAPI 入口（lifespan: 自动迁移 + 初始管理员）
│   │   ├── cli.py         保留命令行入口
│   │   ├── core/          config / security / deps / logging
│   │   ├── db/models/     User / File / Comparison / Diff / AuditLog
│   │   ├── schemas/       Pydantic
│   │   ├── api/           auth / comparisons / diffs / health
│   │   ├── services/      file_storage / bootstrap / audit
│   │   ├── workers/       RQ worker（调用 pipeline）
│   │   └── ws/            WebSocket 进度推送
│   ├── alembic/           数据库迁移
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/         Login / List / New / Detail
│   │   ├── components/    AppShell / RequireAuth / PdfDocument / PdfPage / DiffSidebar / ProgressPanel
│   │   ├── api/           axios + endpoints
│   │   ├── stores/        Zustand auth
│   │   └── types.ts       与后端 schema 对齐
│   ├── Dockerfile         多阶段：build → nginx
│   └── nginx.conf         反代 /api、/ws
├── scripts/init-admin.sh  交互式创建管理员
├── docker-compose.yml     一键起所有服务
└── .env.example
```

## 开发约定

### Python
- 强制 `from __future__ import annotations` 顶部
- 类型注解齐全
- 业务逻辑放 `app/services/`，路由层只做参数校验 + 调用
- 写入 DB 前用 `flush()`，提交在路由层 commit
- 关键操作必须写 `audit_logs`

### TypeScript / React
- 函数组件 + Hooks
- 服务端状态用 TanStack Query（不要 useState 存接口数据）
- 客户端持久状态用 Zustand + persist
- 样式优先 Tailwind utility class，复用样式用 `@layer components` 抽到 `index.css`

### 算法核心（重要）
1. **页号不可信**：原件 14 页 vs 扫描件 15 页很常见，必须用**全文档字符流**对齐，不能按页对
2. **OCR 顺序不稳**：表格里 OCR 读序常和原件不同 → 用 move detection 识别"同内容跨位置"
3. **关键字段加强**：合同编号 / 金额 / 账号 / 税号 / 电话 / 签订日期 / 甲乙方 / 法定代表人 → 标 critical
4. **噪声分级折叠**：
   - `moved`（位置移动）- 同内容跨位置
   - `footer`（页眉页脚）- 系统性差异
   - 单字符 / 双字符的 d/i 残留 - 降级为 `info`
   - 下划线字符 `_` `¯` `﹍` - 直接忽略（合同填空线）
5. **章遮挡处理**：HSV 红色 mask → 落入红章区的差异标 `stamp_covered` 灰色，不当作真差异

## 颜色规范（前后端统一）

| 类别 | 含义 | 颜色 |
|---|---|---|
| insert / handwritten | 新增 / 手写填空 | 🟢 绿 |
| delete | 删除 | 🔴 红 |
| replace | 修改 | 🟡 黄 |
| stamp_covered | 章遮挡 | ⚪ 灰 |
| moved | 位置移动 | 🔵 蓝（默认隐藏）|
| critical | 关键字段 | ★ 红星 |

## 提交规范

中文 + emoji。格式：`<emoji> <类型>: <简短描述>`

类型词参考：
- ✨ feat: 新功能
- 🐛 fix: bug 修复
- 📝 docs: 文档
- 🎨 style: 样式 / 格式
- ♻️ refactor: 重构
- ⚡️ perf: 性能优化
- ✅ test: 测试
- 🔧 chore: 构建 / 工具配置
- 🚀 deploy: 部署
- 🗄️ db: 数据库 / 迁移
- 🔒 security: 安全相关
- 🌐 i18n: 国际化
- 🎉 init: 项目初始化

例：
```
✨ feat: 新增审核工作流，支持逐条确认/忽略/批注
🐛 fix: 修复 nginx MIME 配置导致 HTML 直接下载的问题
♻️ refactor: 重构页对齐为全文档字符流 diff，根治页号错位
```

## 常用命令

```bash
# 启动
docker compose up -d

# 重建后端
docker compose build api worker && docker compose up -d --force-recreate api worker

# 重建前端
docker compose build frontend && docker compose up -d --force-recreate frontend

# 查日志
docker compose logs -f api worker

# 进 API 容器 Python shell
docker compose exec api python

# 强制清 OCR 缓存
docker compose exec api sh -c "rm -rf /data/cache/*"

# 数据库迁移（修改模型后）
docker compose exec api alembic revision --autogenerate -m "描述"
docker compose exec api alembic upgrade head
```

## 算法验证

样本：14 页电子合同 vs 15 页盖章扫描件（含手写填空、红章、表格错位、OCR 易混字）

| 迭代 | 真实差异 | 关键改进 |
|---|---|---|
| v1（行级 diff）| 662 全是噪声 | 基础跑通 |
| v3（页级 diff）| 81 + 整页误报 | 引入页对齐 |
| v4（全文档 diff）| 96 | 根治页号错位 |
| v7（拆 replace + move）| 39 | 表格位移识别 |
| **v10（当前）** | **23 真实差异** | 单字噪声折叠、下划线忽略 |

23 条全部命中真实问题：合同编号填空、错字（仟→任、‰→%、甲→申）、缺失条款、新增联系人电话、章遮挡区、签字栏布局变化。**零误报**。

性能：首次 ~35s（OCR 占 30s），缓存命中 ~4s。

## 待办

- M3：导出 Excel / PDF 审核报告
- M4：批量对比（1 原件 vs N 扫描件，共享 OCR）
- M5：API 集成（API Key + Webhook）
- M6：内网生产部署文档

## 注意事项

- 永远不要把 `samples/` 里的真实合同 PDF 提交到仓库（已在 `.gitignore`）
- `.env` 含密钥不入库，复制 `.env.example` 用
- 修改算法后必须用样本回归测试，确认真实差异数稳定在 23 左右
- 前端改 nginx.conf 后必须 `docker compose build frontend`
