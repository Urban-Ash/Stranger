<div align="center">

<h1>Stranger · OSINT 信息检索平台</h1>

<img src="https://img.shields.io/badge/AI%20Authored-100%25-blueviolet?style=flat" alt="纯 AI 编写 100%" />
<img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python" alt="Python" />
<img src="https://img.shields.io/badge/Flask-2.x-000?logo=flask" alt="Flask" />
<img src="https://img.shields.io/badge/PostgreSQL-13%2B-336791?logo=postgresql" alt="PostgreSQL" />

<p>一个前后端一体化的 OSINT 信息聚合与检索系统，提供多语言 UI、来源详情、验证工具与可选 AI 置信度评估，并具备认证、CSRF、限流与跨域等安全特性。</p>

</div>

## 为什么选择 Stranger
- 多源聚合与检索：支持姓名、手机号、邮箱、QQ、身份证、微博 UID 等主体的统一搜索与来源详情。
- 多语言与可访问性：中文、英文、繁体中文、日文、韩文；支持键盘导航与 ARIA 标签。
- 可选 AI 评估：数据置信度智能评估，可选写回主表。
- 工程化安全：认证（可选）、CSRF 保护、CORS、压缩、限流；接口健康与指标可观测。

## 快速开始
- 运行环境：Python 3.9+、PostgreSQL
- 安装依赖：`pip3 install -r requirements.txt`
- 配置环境：复制 `.env.example` 为 `.env`，设置至少以下变量：
  - `FLASK_HOST`、`FLASK_PORT`、`FLASK_ENV`、`CORS_ORIGINS`
  - `PG_HOST`、`PG_PORT`、`PG_DATABASE`、`PG_USER`、`PG_PASSWORD`
  - `RATE_LIMIT`（默认 `60 per minute`）、`SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`（默认 `60000`）
  - 若使用 AI：`DEEPSEEK_API_KEY`（未设置时自动禁用 AI 功能）
- 本地启动：`python3 main.py`（默认 `http://127.0.0.1:8080`）
- 生产模式：`gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`（默认 `http://127.0.0.1:5082`）

## 认证与安全
- 认证开关：设置 `AUTH_ENABLED=true` 后，除 `/login`、`/health`、`/static/` 等少量路径外，`/api/` 下所有路由需要登录。
- CSRF 保护：对 `/api/` 下的 `POST/PUT/PATCH/DELETE` 强制校验 CSRF。
  - 获取令牌：登录后 `GET /api/csrf` 返回 `{ token }`，同时设置 `XSRF-TOKEN` Cookie。
  - 使用令牌：前端/客户端在变更类请求中附加头部 `X-CSRF-Token: <token>`。
  - 跨域与 Cookie：`SESSION_COOKIE_SAMESITE`、`SESSION_COOKIE_SECURE` 会影响会话与 CSRF，在跨域或 HTTPS 代理下请按需调整。
- 其他安全：`CORS_ORIGINS` 控制跨域来源；`RATE_LIMIT` 控制速率；默认开启 `Flask-Compress`。

## API 概览（常用）
- `GET /api/search`：参数 `query`；可选 `page/page_size/sort/order/expand`
- `POST /api/customer`：新增记录
- `PUT /api/customer/<id>`：更新记录
- `DELETE /api/customer/<id>`：删除记录
- `GET /api/source_detail`：按主体键查看来源命中详情（`id_card`、`phones`、`qqs`、`weibo_uid`、`email`、`name`）
- 验证接口：
  - `GET /api/validate/phone` — 归属地与运营商；可设置 `write=1` 持久化
  - `GET /api/validate/qq` — QQ 资料；可设置 `write=1` 持久化
  - `GET /api/validate/weibo` — 微博资料；可设置 `write=1` 持久化
  - `GET /api/validate/id_card` — 身份证结构与一致性检查
- AI：`POST /api/ai/assess_confidence`
- 健康与指标：`GET /health`、`GET /api/metrics`

> 提示：对于较大或敏感的查询，`/api/search` 与 `/api/source_detail` 可选支持 `POST` JSON（双栈）。

## 架构与目录
- 前端：`static/` 模块化 JS（入口 `static/main.js`）；模板 `templates/index.html`。
- 后端：Flask 应用 `app/app.py`（`create_app()`），路由 `app/api/routes.py`，统一响应 `app/api/response.py`。
- 数据库：PostgreSQL 主表 `profile`；索引在启动时创建；跨表扫描与动态别名见 `app/models/database.py`。
- 配置：`config/config.py` 统一管理，支持环境注入；`config/data_source.json` 管理来源元信息。
- 结构与脚本：
  - `static/modules/search.js` 渲染 `result-item`，使用 `data-index` 做事件委托。
  - `scripts/` 包含自检脚本与数据库检查脚本。

## 端到端用法示例（带认证与 CSRF）
以下示例使用 `curl`：
- 登录：
  - `curl -i -c /tmp/c.txt -d "username=<user>&password=<pass>" http://127.0.0.1:5082/login`
- 获取 CSRF：
  - `curl -b /tmp/c.txt http://127.0.0.1:5082/api/csrf`（返回 `token` 并设置 `XSRF-TOKEN`）
- 新增客户：
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -H "Content-Type: application/json" -d '{"id_card":"110101199001010012","name":"张三"}' http://127.0.0.1:5082/api/customer`
- 查询客户：
  - `curl -b /tmp/c.txt "http://127.0.0.1:5082/api/search?query=110101199001010012"`
- 更新客户：
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -H "Content-Type: application/json" -X PUT -d '{"company":"测试公司"}' http://127.0.0.1:5082/api/customer/<id>`
- 删除客户：
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -X DELETE http://127.0.0.1:5082/api/customer/<id>`

## 测试与自检
- 轻量冒烟（只测 GET 与数据查询）：
  - `python3 scripts/smoke_test.py --base http://127.0.0.1:5082`
- 全量 E2E 冒烟（含登录、CSRF、CRUD、校验、可选 AI）：
  - `python3 scripts/test_all.py --base http://127.0.0.1:5082`
  - 可选参数：`--include-external`（启用外部校验接口）、`--include-ai`（启用 AI 评估）
  - 脚本会在 `requests` 认证失败时自动回退为 `curl` 模式，并附带 `X-CSRF-Token` 完成变更类请求。

## 部署
- Gunicorn：`pip3 install gunicorn && gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`
- Docker：
  - 构建：`docker build -t stranger:latest .`
  - 运行：`docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`
- Docker Compose：
  - 启动：`docker compose up -d --build`
  - 日志：`docker compose logs -f stranger`
  - 停止：`docker compose down`
- Nginx 反代与 systemd 单元可参考英文 README 示例。

## 故障排查
- 登录后访问 `/api/csrf` 仍返回 401：
  - 确认同源（域名/端口）与 Cookie 策略；必要时使用脚本中的 `curl` 回退。
  - 检查 `AUTH_ENABLED` 是否开启且会话 Cookie 已设置。
- CSRF Token 不一致：
  - 对比返回 JSON 中的 `token` 与 `XSRF-TOKEN` Cookie；在代理或跨域场景注意 `SameSite`/`Secure` 设置。
- 健康检查显示 DB 异常但功能可用：
  - 开发环境可先以接口 `200` 为准；生产应排查连接、超时与索引。
- 外部校验失败：
  - 配置代理 `HTTP_PROXY`/`HTTPS_PROXY`，并检查出网策略与重试参数。

## 贡献与许可
- 欢迎提交 Issue 与 PR；请在合入前运行自检脚本并同步更新文档。
- 许可证以仓库中的 `LICENSE` 为准。