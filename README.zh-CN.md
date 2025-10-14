<div align="center">

<h1>Stranger · OSINT 信息检索平台</h1>

<img src="https://img.shields.io/badge/AI%20Authored-100%25-blueviolet?style=flat" alt="纯 AI 编写 100%" />
<img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python" alt="Python" />
<img src="https://img.shields.io/badge/Flask-2.x-000?logo=flask" alt="Flask" />
<img src="https://img.shields.io/badge/PostgreSQL-13%2B-336791?logo=postgresql" alt="PostgreSQL" />

<p>一个前后端一体化的 OSINT 信息聚合与检索系统，支持多语言 UI、数据源模板、验证工具与可选 AI 置信度评估。</p>

</div>

## 特性
- 智能搜索：自动识别关键词类型（姓名/手机号/邮箱/QQ/身份证/微博 UID），支持分页、排序与可选聚合。
- 多语言：中文、英文、繁體中文、日文、韩文；语言菜单具备 ARIA 无障碍提示。
- 数据维护：新增/编辑模态框，支持来源增量更新与记录删除。
- 来源详情：点击结果中的来源 Chip，打开弹窗查看命中详情。
- 验证查询：手机号归属地、QQ 头像与昵称、微博 UID 主页信息、身份证结构解析。
- AI 置信度：评估并可选写回主表。
- 健康与指标：统一健康检查与指标接口，便于监控。
- 安全特性：CORS（`flask-cors`，`CORS_ORIGINS` 配置）、压缩（`Flask-Compress`）、速率限制（`flask-limiter`，`RATE_LIMIT` 配置，默认 `60 per minute`）。认证启用时（`AUTH_ENABLED=true`）非静态路由需要登录。

## 体验与无障碍
- 支持 PWA 安装与离线清单；Service Worker 与 Manifest 已配置。
- 支持深浅色主题与语言切换；键盘导航与 ARIA 标签。

## 截图与体验

<div align="center">
<img src="docs/screenshots/stranger-home-zh.png" alt="Stranger 首页（中文界面）" width="720" />
</div>

## 架构
- 前端：`static/` 模块化 JS，入口 `static/main.js`，模板 `templates/index.html`。
- 后端：Flask 应用 `app/app.py`（`create_app()`），路由 `app/api/routes.py`，统一响应 `app/api/response.py`。
- 数据库：PostgreSQL；主表 `profile`，启动自动创建索引；跨表扫描与动态别名见 `app/models/database.py`。
- 配置：`config/config.py` 统一管理，支持环境变量注入；支持 CORS、压缩与限流。

## 数据源配置
- 在 `config/data_source.json` 配置友好名称与日期。
- 应用在运行时会从数据库元信息补齐缺失条目（若可用）。
- 模板示例：
  ```json
  {
    "example_table": { "name": "示例数据源", "date": "YYYY-MM-DD" }
  }
  ```

## 目录
- `app/` 后端（API/服务/模型/初始化）
- `static/` 前端静态资源（JS/CSS/图标）
- `templates/` Jinja 模板
- `config/` 配置与清单
- `scripts/` 辅助脚本（冒烟测试、DB 检查）

## 快速开始
- 环境：Python 3.9+、PostgreSQL
- 依赖：`pip3 install -r requirements.txt`
- 配置：复制 `.env.example` 为 `.env`，设置：
  - `FLASK_HOST`、`FLASK_PORT`、`FLASK_ENV`、`CORS_ORIGINS`
  - `PG_HOST`、`PG_PORT`、`PG_DATABASE`、`PG_USER`、`PG_PASSWORD`
  - `SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`（默认 `60000` ms）
  - 可选代理与爬虫：`CRAWLER_TIMEOUT`、`CRAWLER_RETRIES`、`CRAWLER_BACKOFF`、`HTTP_PROXY`/`HTTPS_PROXY`
- 开发：`python3 main.py`（默认 `http://127.0.0.1:8080`）
- 生产：`gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`（默认 `http://127.0.0.1:5082`）

## 访问
- 开发：`http://127.0.0.1:8080/`（通过 `python3 main.py`）
- 生产/Docker：`http://127.0.0.1:5082/`
- 健康：`/health`
- 指标：`/api/metrics`

## API 概览
- `GET /api/search`：参数 `query`；可选 `page`、`page_size`、`sort`、`order`、`expand`
- `POST /api/customer`：新增记录
- `PUT /api/customer/<id>`：更新部分字段
- `DELETE /api/customer/<id>`：删除记录
- `GET /api/source_detail`：按主体键查看表命中详情（`id_card`、`phones`、`qqs`、`weibo_uid`、`email`、`name`）
- 验证：
  - `GET /api/validate/phone` — 参数：`number`（必需）、`write`（`1|true|yes` 持久化）、可选 `id_card`、`merge_phone`；返回：归属地信息（`province`、`city`、`carrier`、`area_code`、`postcode`）和 `updated`/`id`。
  - `GET /api/validate/qq` — 参数：`qq`（必需）、`write`（`1|true|yes` 持久化）、可选 `id_card`、`merge_phone`；返回：资料（`nickname`、`avatar`、`level`、`vip`）和 `updated`/`id`。
  - `GET /api/validate/weibo` — 参数：`uid|weibo_uid`（必需）、`write`（`1|true|yes` 持久化）、可选 `id_card`；返回：资料（`screen_name`、`followers_count`、`verified`、`description`）和 `updated`/`id`。
  - `GET /api/validate/id_card` — 参数：`id_card`（必需）、可选 `write`（`1|true|yes` 持久化）；返回：验证结果（`valid`、`address_code`、`birth_date`、`gender`、`consistency_check`）和 `updated`/`id`。
- AI：`POST /api/ai/assess_confidence`
- 自省：`GET /api/schema_introspect`
- 健康与指标：`GET /health`、`GET /api/metrics`

> 提示：对于较大或敏感的查询，`/api/search` 与 `/api/source_detail` 可选支持 `POST` JSON（双栈设计）。

## 部署示例
- Gunicorn（前台）：`gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`
- Nginx 反向代理与 systemd 单元示例见英文版 README 对应章节。

## 多语言与 PWA
- 前端仅使用 `static/i18n/` 外部 JSON 语言包，不再合并内置词典。
- 后端端点：
  - `GET /i18n/list` — 返回可用语言列表（`code`、`native_label`）。
  - `GET /i18n/<lang>.json` — 返回语言 JSON。示例：
    ```json
    {
      "meta": {
        "native_label": "English",
        "pwa": {
          "name": "Stranger OSINT",
          "short_name": "Stranger",
          "description": "OSINT query platform, installable and offline-ready",
          "shortcuts": [
            { "name": "Quick Search", "short_name": "Search", "description": "Open home and start searching", "url": "/?action=search" }
          ]
        }
      },
      "strings": {
        "login_title": "Login to Stranger",
        "login_username": "Username",
        "login_password": "Password",
        "login_submit": "Login"
      }
    }
    ```
- Manifest：`GET /manifest.json?lang=<code>` 要求显式传入 `lang` 参数，仅使用语言 JSON 的 `meta.pwa`；若缺失 `lang` 或语言 JSON 未提供 `meta.pwa`，返回 `400`；不再提供内置回退。
- 前端行为：语言菜单由 `/i18n/list` 动态生成；切换语言后拉取 `/i18n/<lang>.json`，直接应用外部文案并刷新 PWA Manifest；请求失败时不修改当前视图。

## 主题
- 支持 `prefers-color-scheme`；若系统检测不可用或失败，默认浅色主题。
- 主题切换会把选择写入 `localStorage` 的 `theme`。

## Docker
- 构建：`docker build -t stranger:latest .`
- 运行：`docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`
- 说明：默认命令 `gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`；端口通过 `-p` 与 `FLASK_PORT` 调整；`.dockerignore` 已精简镜像。

## 安全建议
- 生产环境请更改 `SECRET_KEY`、`PG_PASSWORD`、`AUTH_PASSWORD`。
- 将 `CORS_ORIGINS` 限制为可信域名（默认 `*`）。
- 合理设置 `RATE_LIMIT`（默认 `60 per minute`）。
- `.env` 不要提交；密钥通过环境变量注入（DB、API Keys）。
- 若曾共享过真实凭据，请在发布前轮换；使用 `.env.example` 放占位。
- 对外开放前，请收敛 `CORS_ORIGINS` 并设置合理限流。

## Docker Compose
- 启动：`docker compose up -d --build`
- 日志：`docker compose logs -f stranger`
- 停止：`docker compose down`
- 说明：主机端口来自 `FLASK_PORT`（默认 `5082`）；Compose 自动读取 `.env`，容器内使用 Gunicorn。

## 性能与稳定性建议
- 电话匹配优先使用等值条件，避免全表扫描；维护常用列表达式索引。
- 控制跨表扫描预算：`SCAN_MAX_TABLES`、`SCAN_LIMIT_PER_TABLE`、`SCAN_TOTAL_TIME_BUDGET_MS`。
- 连接管理：建议连接池或请求级连接；限流存储多副本建议使用 Redis。
- 日志与可观测性：结构化日志、轮转与级别控制。

## 冒烟测试
- `python3 scripts/smoke_test.py` 或指定基地址：`python3 scripts/smoke_test.py http://<host>:<port>`（默认 `http://127.0.0.1:5082`）
- 测试 6 个端点：`/`、`/api/metrics`、`/api/search`、`/api/source_detail`、`/api/schema_introspect`、`/api/validate/id_card`。

## 贡献与许可
- 欢迎 issues 与 PR；提交前请跑冒烟测试并更新文档。
- 许可证以仓库中的 `LICENSE` 为准。