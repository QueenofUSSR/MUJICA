# Multi-Agent System

## 项目概述
Multi-Agent（多智能体协作平台）是一个用于演示与运行多智能体协作任务的示例平台，结合 AI 聊天、任务分解与集中调度，支持将复杂任务拆解为多个专业子Agent并行执行，提供实时日志、任务可视化与用户接管功能。

## 核心功能
- 多智能体任务分解、分发与结果整合（中心化协调器模式）
- 支持自定义 Agent 注册与角色定义
- 实时展示 Agent 状态与执行日志（前端轮询或 WebSocket 可选）
- AI 聊天界面（保留原有聊天功能）
- 用户可中断 / 接管子任务并查看执行历史
- 可扩展接入外部模型、浏览器或工具（后续集成）

## 技术栈
- 后端：Python + FastAPI + SQLAlchemy
- 前端：Vue.js 3 + Vite + Pinia
- 异步/实时：uvicorn (ASGI)、可选 WebSocket 支持
- 数据库（开发）：SQLite（可选）
- 数据库（生产）：Postgres 或你选择的 RDBMS

## 快速启动（开发环境）
下面提供本地快速运行说明（假设已安装 Python 3.10+ 与 Node.js）：

### 1) 后端（开发）
在 `backend/` 目录下：

```powershell
cd backend; 
python -m venv .venv; 
.\.venv\Scripts\Activate.ps1; 
python -m pip install --upgrade pip; 
pip install -r requirements.txt
# 如果使用 Postgres，请先创建数据库并执行初始化脚本（可选）
# psql -h localhost -p 5432 -U postgres -d agent_db -f static/init_db.sql
# 启动开发服务器
uvicorn main:app --reload
```
访问： http://localhost:8000/docs

说明：默认代码可在 SQLite 下直接运行（方便本地调试）。如果你计划用 Postgres，请调整 `backend` 中的数据库连接配置。

### 2) 前端（开发）
在 `frontend/` 目录下：

```powershell
cd frontend; 
npm install; 
npm run dev
```
访问： http://localhost:5173

### 3) 生产部署提示
- 使用 Gunicorn/UVicorn 或容器化部署（Docker）。
- 生产环境建议使用 Postgres、Redis（任务队列或缓存）、并配置 HTTPS 与反向代理（Nginx）。

## 项目结构（高层）
- `backend/` - FastAPI 后端
  - `main.py` - 应用入口
  - `routers/` - 各类 API 路由（auth、agent、user、ai 等）
  - `agents/` - 多智能体相关运行时（示例 Coordinator/Agent）
  - `core/` - 工具库、日志和持久化模型
  - `requirements.txt` - Python 依赖
- `frontend/` - Vue 3 前端代码
  - `src/views/` - 页面视图（包含 Login、AI Chat、Profile、MultiAgent 仪表盘）
  - `src/stores/` - Pinia 状态管理

## 开发建议与扩展方向
- 增加 WebSocket 或 Server-Sent Events 以实现前端实时推送 Agent 状态
- 引入任务队列（Celery / RQ）或后台 Worker 管理长期任务
- 集成模型上下文协议（MCP）与自动安装工具以便快速接入模型
- 提供更完善的 RBAC（角色权限）与审计日志

## 常见问题
- 如果前端无法访问后端，请确认 `frontend` 的代理设置或 CORS 已在后端启用。
- 如果需要演示真实的长时任务，请在 `backend/agents/` 中实现长时执行逻辑或接入后台队列。

## 许可证
MIT License - 详见 `LICENSE` 文件。

---

