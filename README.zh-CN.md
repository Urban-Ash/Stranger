# Stranger
注：本项目完全由 AI 编写。

<p align="center">
  <img src="https://img.shields.io/badge/AI%20Authored-100%25-blueviolet?style=for-the-badge" alt="纯 AI 编写 100%" />
  
</p>

一个前后端一体化的 OSINT 信息聚合与检索系统。支持多语言 UI、数据维护、来源详情查看、验证查询与可选的 AI 置信度评估。

## 特性
- 智能搜索：自动识别关键词类型（姓名/手机号/邮箱/QQ/身份证/微博 UID），支持分页、排序与可选聚合。
- 多语言：中文、英文、繁體中文、日文、韩文；语言菜单具备 ARIA 无障碍提示。
- 数据维护：新增/编辑模态框，支持来源增量更新与记录删除。
- 来源详情：点击结果中的来源 Chip，打开弹窗查看命中详情。
- 验证查询：手机号归属地、QQ 头像与昵称、微博 UID 主页信息、身份证结构解析。
- AI 置信度：评估并可选写回主表。
- 健康与指标：统一健康检查与指标接口，便于监控。

## 架构
- 前端：`static/` 模块化 JS，入口 `static/main.js`，模板 `templates/index.html`。
- 后端：Flask 应用 `app/app.py`（`create_app()`），路由 `app/api/routes.py`，统一响应 `app/api/response.py`。
- 数据库：PostgreSQL；主表 `profile`，启动自动创建索引；跨表扫描与动态别名见 `app/models/database.py`。
- 配置：`config/config.py` 统一管理，支持环境变量注入；支持 CORS、压缩与限流。

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
- 开发：`python3 main.py`
- 生产：`gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`

## 访问
- 首页：`http://127.0.0.1:5082/`
- 健康：`http://127.0.0.1:5082/health`
- 指标：`http://127.0.0.1:5082/api/metrics`

## API 概览
- `GET /api/search`：参数 `query`；可选 `page`、`page_size`、`sort`、`order`、`expand`
- `POST /api/customer`：新增记录
- `PUT /api/customer/<id>`：更新部分字段
- `DELETE /api/customer/<id>`：删除记录
- `GET /api/source_detail`：按主体键查看表命中详情（`id_card`、`phones`、`qqs`、`weibo_uid`、`email`、`name`）
- 验证：`/api/validate/phone`、`/api/validate/qq`、`/api/validate/weibo`、`/api/validate/id_card`
- AI：`POST /api/ai/assess_confidence`
- 自省：`GET /api/schema_introspect`
- 健康与指标：`GET /health`、`GET /api/metrics`

## 部署示例
- Gunicorn（前台）：`gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`
- Nginx 反向代理与 systemd 单元示例见英文版 README 对应章节。

## Docker
- 构建：`docker build -t stranger:latest .`
- 运行：`docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`
- 说明：默认命令 `gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`；端口通过 `-p` 与 `FLASK_PORT` 调整；`.dockerignore` 已精简镜像。

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
- `python3 scripts/smoke_test.py` 或指定基地址：`python3 scripts/smoke_test.py http://<host>:<port>`

## 贡献与许可
- 欢迎 issues 与 PR；提交前请跑冒烟测试并更新文档。
- 许可证如未明确，默认为内部使用；如需开源请添加 LICENSE。