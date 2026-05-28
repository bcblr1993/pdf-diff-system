# PDF / Word 差异对比系统

合同 / 文档审核工作台。把**原件**（电子矢量 PDF 或 Word）和**对方版本**（盖章扫描 PDF 或修改后 Word）扔进来，系统自动 OCR + 字符流 diff + 双视图高亮，再逐条人工审核确认/忽略/批注，最后导出归档报告。

## ⚡ 30 秒上手

```bash
git clone https://github.com/bcblr1993/pdf-diff-system.git
cd pdf-diff-system
cp .env.example .env
docker compose up -d                  # 起 5 个容器：postgres+redis+api+worker+frontend
```

打开 http://localhost:8080 → 用 `admin / admin123` 登录 → 拖两份文档 → 自动对比 → 审核 → 导出。

**生产部署看 [DEPLOYMENT.md](./DEPLOYMENT.md)**。

---

## 核心能力

| 维度 | 能力 |
|---|---|
| **输入格式** | PDF（电子版 + 扫描版）、Word（.docx）任意混搭 |
| **算法** | 全文档字符流 diff + 块位移识别 + OCR 噪声归一 + 章遮挡识别（v10 演进而来） |
| **准确性** | 样本合同 14-15 页对比，23 条真实差异 0 误报，关键字段全命中 |
| **性能** | 首次 35s（含 OCR），缓存命中 4s（同文件二次） |
| **审核** | 逐条 ✓/✗ + 批注 + 快捷键 + 完成审核归档 |
| **批量** | 1 份原件 × N 份扫描件，共享 OCR 缓存 |
| **导出** | Excel / HTML 快照 / PDF 三种归档格式 |
| **集成** | API Key 鉴权 + Webhook 推送 + 完整 OpenAPI 文档 |
| **多用户** | 内置登录 + 管理员/普通两角色 + 完整审计日志 |

---

## 系统截图速览

```
┌─ 任务列表（首页）──────────────────────────────────────┐
│ #5  合同对比 v2   done   真实23  ★7   审核 12/23      │
│ #6  批量×3       running                              │
│ ...                                                    │
└────────────────────────────────────────────────────────┘

┌─ 详情页（双 PDF / Word 并排）─────────────────────────┐
│ 原件 P5            │ 扫描件 P6        │ 差异侧栏       │
│ ┌──────────────┐   │ ┌──────────────┐ │ #2★ XX-C-...  │
│ │ 合同编号...  │   │ │ XX-C-260520  │ │ #38★ 仟→任    │
│ │ ...          │   │ │ ...          │ │ ...           │
│ │ [仟]→[任]🟡  │   │ │ ...          │ │               │
│ └──────────────┘   │ └──────────────┘ │ ↑↓ Y N U 快捷键│
└────────────────────────────────────────────────────────┘
```

颜色：🟢 新增 / 🔴 删除 / 🟡 修改 / ⚪ 章遮挡 / 🔵 位置移动 / ★ 关键字段

---

## 架构

```
                  ┌──────────────┐
                  │   浏览器     │  React + pdf.js + Tailwind
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │   Nginx :80  │  ← 前端静态 + API/WS 反代
                  └──────┬───────┘
                         │
              ┌──────────▼───────┐    ┌─────────────┐
              │ FastAPI :8000    │◄──►│  Postgres   │
              │  • Auth (JWT)    │    │  16-alpine  │
              │  • 任务管理      │    └─────────────┘
              │  • 差异+审核     │
              │  • WebSocket     │    ┌─────────────┐
              │  • Webhook       │    │   Redis 7   │
              │  • OpenAPI       │◄──►│             │
              └──────────┬───────┘    └─────┬───────┘
                         │ enqueue          │
                         ▼                  │ pub/sub 进度
              ┌──────────────────┐          │
              │  Worker (RQ)     │◄─────────┘
              │  Pipeline:       │
              │   ┌─ PDF: extract→ocr→stamp→diff
              │   └─ Word: extract→diff
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ 卷: storage/     │  按 SHA1 去重存 PDF / Word
              │ 卷: cache/       │  OCR 结果缓存
              └──────────────────┘
```

---

## 算法效果（一份样本合同的演进）

样本：14 页电子版合同 vs 15 页盖章扫描件，含手写填空、红章、表格内容错位、OCR 易混字。

| 迭代 | 真实差异 / 噪声 | 关键改进 |
|---|---|---|
| v1 行级 diff | 662 全是噪声 | 基础跑通 |
| v3 页级 diff | 81，但 P9 整页是错的 | 引入页对齐 |
| v4 全文档 diff | 96 | **根治页号错位** |
| v7 拆 replace + move | 39 | **表格位移识别** |
| **v10 最终** | **23 真实差异** | 单字噪声折叠 + 下划线忽略 |

v10 的 23 条全部命中真实问题：合同编号填空 / 错字（仟/任、‰/%、甲/申）/ 缺失条款 / 新增联系人电话 / 章遮挡区 / 签字栏布局变化 ——**零误报**。

详见 `backend/pipeline/diff.py` 注释。

---

## 仓库结构

```
pdf-diff-system/
├── README.md                    本文档
├── DEPLOYMENT.md                内网部署 + 运维手册
├── CLAUDE.md                    给 AI 助手的开发约定 + 算法说明
├── LICENSE                      MIT
│
├── docker-compose.yml           开发用 compose
├── docker-compose.prod.yml      生产 overlay（资源限制 + 日志轮转）
├── .env.example                 环境变量模板
│
├── scripts/                     运维脚本
│   ├── init-admin.sh            初始化首个管理员（交互式）
│   ├── backup.sh                备份 DB + 文件存储
│   ├── restore.sh               从备份恢复
│   └── health-check.sh          巡检脚本（cron 友好）
│
├── backend/                     Python 后端
│   ├── pipeline/                ← 核心 diff 算法
│   │   ├── extract.py           PDF 矢量文字抽取（PyMuPDF）
│   │   ├── ocr.py               扫描 PDF OCR（RapidOCR）
│   │   ├── word.py              Word 文本抽取（python-docx）
│   │   ├── stamp_mask.py        红章检测
│   │   ├── stream.py            字符流构建
│   │   ├── normalize.py         规范化（OCR 形近字）
│   │   ├── diff.py              全文档 diff + move 识别
│   │   └── cache.py             按 SHA1 缓存
│   ├── app/
│   │   ├── main.py              FastAPI 入口
│   │   ├── cli.py               保留命令行入口
│   │   ├── core/                config / security / deps / logging
│   │   ├── db/models/           7 个 ORM 表
│   │   ├── schemas/             Pydantic
│   │   ├── api/                 内部 API（auth/comparisons/diffs/batches/...）
│   │   │   └── v1/              外部 API（X-API-Key 鉴权）
│   │   ├── services/            业务逻辑（webhook / api_key / file_storage / ...）
│   │   ├── workers/             RQ Worker + compare_job
│   │   ├── exporters/           xlsx / pdf_report / html_report / batch_xlsx
│   │   └── ws/                  WebSocket 进度
│   ├── alembic/                 数据库迁移（4 个版本）
│   └── Dockerfile
│
└── frontend/                    React + TypeScript
    ├── src/
    │   ├── pages/               Login / List / New / Detail / BatchList /
    │   │                        BatchDetail / Integrations
    │   ├── components/          AppShell / PdfDocument / DocxViewer /
    │   │                        DiffSidebar / ProgressPanel / ...
    │   ├── api/                 axios 客户端 + endpoints
    │   ├── stores/              Zustand
    │   └── App.tsx
    ├── Dockerfile               Nginx 静态服务 + API 反代
    └── nginx.conf
```

---

## 功能模块速查

| 想做的事 | 操作 |
|---|---|
| 上传两份文档对比 | `POST /api/comparisons`（multipart：orig, scan, title）|
| 查任务列表 | `GET /api/comparisons` |
| 看差异详情 | `GET /api/comparisons/{id}` + `GET /api/comparisons/{id}/diffs` |
| 审核一条差异 | `PATCH /api/diffs/{id}` body `{review_action, review_note}` |
| 完成整任务审核 | `POST /api/comparisons/{id}/review/complete` |
| 导出报告 | `GET /api/comparisons/{id}/export.xlsx` (或 .html / .pdf) |
| 批量对比 | `POST /api/batches`（1 原件 + N 扫描件）|
| 创建外部 API Key | `POST /api/api-keys`（仅管理员）|
| 注册 Webhook | `POST /api/webhooks`（仅管理员）|
| 用 API Key 调用 | Header `X-API-Key: <key>`, 端点 `/api/v1/comparisons` |
| 实时进度 | WebSocket `/ws/comparisons/{id}/progress` |

完整 OpenAPI：http://localhost:8080/docs

---

## 开发模式

```bash
# 起后端依赖
docker compose up -d postgres redis api worker

# 前端 dev server（热重载）
cd frontend
export PATH="/opt/homebrew/opt/node/bin:$PATH"  # macOS brew node
npm install
npm run dev    # → http://localhost:5173
```

Vite 已配置代理：`/api` → `:8000`，`/ws` → `:8000`。

---

## 开发路线（已完成）

| 阶段 | 内容 | 状态 |
|---|---|---|
| MVP | 命令行 PDF 对比 + HTML 报告 | ✅ |
| M1 | FastAPI 后端 + DB + Worker + 15 个端点 | ✅ |
| M2 | React 前端 + 双 PDF Viewer + 审核交互 | ✅ |
| M3 | Excel / PDF / HTML 三种报告导出 | ✅ |
| M4 | 批量对比（1 原件 × N 扫描件）| ✅ |
| M5 | API Key + Webhook + 外部 API v1 | ✅ |
| M7 | Word (.docx) 文档对比支持 | ✅ |
| M6 | 生产部署 + 备份/恢复/巡检脚本 + 部署文档 | ✅ |

---

## License

MIT。商用请关注：仓库代码可自由使用，但 RapidOCR 内置 PP-OCRv4 模型采用 Apache 2.0，PyMuPDF AGPL（商用需评估）。
