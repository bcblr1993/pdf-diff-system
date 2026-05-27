# PDF 差异对比系统

合同 / 文档审核工作台。把"原件"（电子矢量 PDF）和"扫描件"（盖章扫描 PDF）拖进来，自动 OCR + 字符流 diff + 高亮报告，再逐条人工确认/忽略/批注，导出归档。

## 快速开始（生产部署）

```bash
cd /Users/chenxu/ideaprojects/pdf-diff
cp .env.example .env           # 按需改 SECRET_KEY / 端口
docker compose up -d
```

容器全部 healthy 后访问：

| 入口 | 地址 |
|---|---|
| **前端 Web** | http://localhost:8080 |
| 后端 API + Swagger | http://localhost:8000/docs |
| 数据库（外部连） | localhost:5433 |

默认管理员账号：`admin / admin123`（在 `.env` 里改）。

```bash
# 自定义初始管理员
bash scripts/init-admin.sh

# 查看日志
docker compose logs -f api worker

# 停止所有服务
docker compose down

# 完全重置（清数据）
docker compose down -v
```

## 开发模式

```bash
# 1. 起后端依赖（postgres + redis + api + worker）
docker compose up -d postgres redis api worker

# 2. 起前端 dev server（热重载）
cd frontend
export PATH="/opt/homebrew/opt/node/bin:$PATH"
npm run dev
# → http://localhost:5173
```

Vite dev server 已配置代理：`/api` → `:8000`，`/ws` → `:8000`。

## 系统功能

### 1. 任务列表（首页）
- 全部对比任务一览：标题、状态、差异统计、审核进度、创建时间
- 筛选：处理状态、审核状态、仅看我创建的
- 关键字段（合同编号/金额/账号等）★ 标记
- 处理中任务每 3 秒自动刷新进度

### 2. 新建对比
- 拖拽上传两份 PDF（原件 + 扫描件）
- 高级设置：OCR DPI（150/200/250/300）
- 上传后跳转详情页实时看进度

### 3. 对比详情页（核心）
- 左侧并排原件 + 右侧扫描件，差异处自动高亮
- 右侧差异列表，支持：
  - 类别筛选（修改/删除/新增/手写/章遮挡/位移）
  - 严重度筛选（关键/普通/信息）
  - 审核状态筛选（已审/未审）
  - 显示/隐藏噪声（位移、页脚、单字符）
- 点击差异 → PDF 自动滚动到对应位置，差异框闪烁高亮

### 4. 审核工作流
- 逐条 **确认 / 忽略 / 批注**
- 快捷键：
  - `↑ / ↓` 切换上下条
  - `Y` 标记确认（关键问题）
  - `N` 标记忽略（非问题）
  - `U` 撤销审核标记
- "完成审核"：未审条目自动归 ignored，任务进入 completed 状态

### 5. WebSocket 实时进度
- 处理中页面通过 `/ws/comparisons/{id}/progress` 推送阶段+百分比
- 自动回退到 HTTP 轮询（每 3 秒）

## 颜色含义

| 颜色 | 含义 |
|---|---|
| 🟢 绿 | **新增**（扫描件多出的内容 / 手写填空）|
| 🔴 红 | **删除**（原件有但扫描件没了）|
| 🟡 黄 | **修改**（内容被改动，如 仟→任、‰→%）|
| ⚪ 灰 | **章遮挡**（红章覆盖区，OCR 不可信，需人工复核）|
| 🔵 蓝 | **位置移动**（同内容跨位置匹配，默认隐藏）|
| ★ | **关键字段**（合同编号 / 金额 / 账号等）|

## 架构

```
                  ┌──────────────┐
                  │   浏览器     │
                  │  React+pdf.js│
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │   Nginx :80  │  ← 前端静态 + API/WS 反代
                  └──────┬───────┘
                         │
              ┌──────────▼───────┐    ┌─────────────┐
              │ FastAPI :8000    │◄──►│  Postgres   │
              │  • 认证          │    │  :5432      │
              │  • 任务管理      │    └─────────────┘
              │  • 差异 + 审核   │
              │  • WebSocket     │    ┌─────────────┐
              └──────────┬───────┘    │   Redis     │
                         │ enqueue    │   :6379     │
                         ▼            └─────┬───────┘
              ┌──────────────────┐          │
              │  Worker (RQ)     │          │
              │  • Pipeline:     │          │
              │   extract→ocr→   │◄─────────┘  pub/sub 进度
              │   stamp→diff     │
              └────────┬─────────┘
                       │ 持久化文件 + OCR 缓存
                       ▼
              ┌──────────────────┐
              │ 卷: storage/     │  按 SHA1 去重存 PDF
              │ 卷: cache/       │  OCR 结果缓存
              └──────────────────┘
```

## 项目结构

```
pdf-diff/
├── docker-compose.yml          一键部署
├── .env / .env.example         环境变量
├── scripts/init-admin.sh       初始化管理员
│
├── backend/                    Python 后端
│   ├── pipeline/                ← 核心 diff 算法（MVP 演进而来）
│   │   ├── extract.py          原件文字抽取（PyMuPDF）
│   │   ├── ocr.py              扫描件 OCR（RapidOCR）
│   │   ├── stamp_mask.py       红章检测
│   │   ├── stream.py           字符流构建
│   │   ├── normalize.py        规范化（OCR 形近字）
│   │   ├── diff.py             全文档 diff + move 识别
│   │   └── cache.py            按 SHA1 缓存
│   ├── app/
│   │   ├── main.py             FastAPI 入口
│   │   ├── cli.py              保留的命令行入口
│   │   ├── core/               config / security / deps / logging
│   │   ├── db/models/          5 个 ORM 模型
│   │   ├── schemas/            Pydantic
│   │   ├── api/                4 个路由模块
│   │   ├── services/           业务逻辑
│   │   ├── workers/            RQ Worker
│   │   └── ws/                 WebSocket
│   ├── alembic/                数据库迁移
│   ├── pyproject.toml
│   └── Dockerfile
│
└── frontend/                   React 前端
    ├── src/
    │   ├── pages/              Login / List / New / Detail
    │   ├── components/         AppShell / RequireAuth /
    │   │                       PdfDocument / PdfPage /
    │   │                       DiffSidebar / ProgressPanel
    │   ├── api/                axios 客户端 + 端点
    │   ├── stores/auth.ts      Zustand
    │   ├── types.ts            与后端 schema 对齐
    │   └── lib/utils.ts
    ├── package.json
    ├── Dockerfile
    └── nginx.conf
```

## 算法效果（基于样本合同验证）

样本：14 页原件 vs 15 页扫描件，含手写填空、红章、表格内容错位、OCR 易混字。

| 迭代 | 真实差异 / 噪声 | 关键改进 |
|---|---|---|
| v1 行级 diff | 662 全是噪声 | 基础跑通 |
| v3 页级 diff | 81 + 错位 | 引入页对齐 |
| v4 全文档 diff | 96 | 根治页号错位 |
| v7 拆 replace + move | 39 | 表格位移识别 |
| **v10 最终** | **23 真实差异** | 单字噪声折叠、下划线忽略 |

23 条全部命中真实问题：合同编号填空、错字（仟/任、‰/%、甲/申）、缺失条款、新增联系人电话、章遮挡区、签字栏布局变化。**零误报**。

性能：首次处理 14-15 页约 35-60 秒，命中 OCR 缓存后 4-5 秒。

## 调试 / 运维

```bash
# 健康检查
curl http://localhost:8000/api/health

# 看 worker 实时日志
docker compose logs -f worker

# 手动进 Python shell
docker compose exec api python

# 重置数据库（保留 OCR 缓存）
docker compose down
docker volume rm pdf-diff_pgdata
docker compose up -d

# 强制重新 OCR（不用缓存）
# 在新建对比 API 用 dpi 参数稍微变一下即可
```

## 已知边界

- OCR 上限：RapidOCR 中文准确率 ~95%，章压字 / 极小字会漏识
- 大表格重复内容（"航天联志 / 台" 在原件出现 8 次）少量配对错位会作为 info 噪声折叠
- 单文件 100MB 上限（nginx 配的 client_max_body_size）
- 手写不识别具体内容，只识别位置

## 下阶段路线（M3-M6）

- **M3**：导出 Excel / PDF 审核报告
- **M4**：批量对比（1 原件 vs N 扫描件，共享 OCR）
- **M5**：API 集成端点（API Key + Webhook）
- **M6**：内网生产部署文档

——

设计与算法详见 `backend/pipeline/diff.py` 注释。
