<div align="center">

<h1>Stranger · OSINT 資訊檢索平台</h1>

<img src="https://img.shields.io/badge/AI%20Authored-100%25-blueviolet?style=flat" alt="AI Authored 100%" />
<img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python" alt="Python" />
<img src="https://img.shields.io/badge/Flask-2.x-000?logo=flask" alt="Flask" />
<img src="https://img.shields.io/badge/PostgreSQL-13%2B-336791?logo=postgresql" alt="PostgreSQL" />

<p>整合前後端的 OSINT 集合與搜尋系統。提供多語 UI、來源詳情、驗證工具，以及可選的 AI 信心評估；同時支援認證、CSRF、限流與 CORS 等安全機制。</p>

</div>

## 為什麼選擇 Stranger
- 多來源整合與搜尋：在同一 UI 搜尋姓名/電話/Email/QQ/身分證/Weibo UID，結果可開啟來源詳情對話框。
- 多語與易用性：支援繁/簡/英/日/韓；鍵盤操作與 ARIA 無障礙提示。
- 選配 AI 評估：可對資料的可信度進行評分，視需要寫回主表。
- 工程級安全：可選認證、CSRF 保護、CORS、壓縮與限流；健康與指標端點便於觀測。

## 快速開始
- 需求：Python 3.9+、PostgreSQL
- 安裝依賴：`pip3 install -r requirements.txt`
- 設定環境：將 `.env.example` 複製為 `.env`，並設定：
  - `FLASK_HOST`、`FLASK_PORT`、`FLASK_ENV`、`CORS_ORIGINS`
  - `PG_HOST`、`PG_PORT`、`PG_DATABASE`、`PG_USER`、`PG_PASSWORD`
  - `RATE_LIMIT`（預設 `60 per minute`）、`SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`（預設 `60000`）
  - 使用 AI 時：`DEEPSEEK_API_KEY`（未設則自動停用 AI）
- 開發啟動：`python3 main.py`（預設 `http://127.0.0.1:8080`）
- 生產啟動：`gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`（預設 `http://127.0.0.1:5082`）

## 認證與安全
- 認證開關：`AUTH_ENABLED=true` 時，除 `/login`、`/health`、`/static/` 外的 `/api/` 需登入。
- CSRF 保護：`/api/` 下的 `POST/PUT/PATCH/DELETE` 需要 CSRF Token。
  - 取得：登入後 `GET /api/csrf` 回傳 `{ token }` 並設定 `XSRF-TOKEN` Cookie。
  - 使用：修改類請求需在 Header 加 `X-CSRF-Token: <token>`。
  - 代理/HTTPS：`SESSION_COOKIE_SAMESITE`、`SESSION_COOKIE_SECURE` 會影響 Cookie 與 CSRF 行為。

## API 概覽（常用）
- `GET /api/search`：`query`；可選 `page/page_size/sort/order/expand`
- `POST /api/customer`：新增
- `PUT /api/customer/<id>`：更新
- `DELETE /api/customer/<id>`：刪除
- `GET /api/source_detail`：依主鍵（`id_card`、`phones`、`qqs`、`weibo_uid`、`email`、`name`）檢視命中詳情
- 驗證：`/api/validate/{phone|qq|weibo|id_card}`（`write=1` 可持久化）
- AI：`POST /api/ai/assess_confidence`
- 健康與指標：`GET /health`、`GET /api/metrics`

> 提示：對於大型或敏感查詢，`/api/search` 與 `/api/source_detail` 可選支援 `POST` JSON（雙棧）。

## 架構與目錄
- 前端：`static/` 模組化 JS（入口 `static/main.js`）；模板 `templates/index.html`。
- 後端：Flask `app/app.py`（`create_app()`）、路由 `app/api/routes.py`、統一回應 `app/api/response.py`。
- DB：PostgreSQL 主表 `profile`；啟動時建索引；跨表掃描見 `app/models/database.py`。
- 設定：`config/config.py` 與 `config/data_source.json`。
- 前端細節：`static/modules/search.js` 渲染 `result-item`，以 `data-index` 做事件委派。

## 端到端用法示例（含認證與 CSRF）
使用 `curl`：
- 登入：
  - `curl -i -c /tmp/c.txt -d "username=<user>&password=<pass>" http://127.0.0.1:5082/login`
- 取得 CSRF：
  - `curl -b /tmp/c.txt http://127.0.0.1:5082/api/csrf`
- 新增客戶：
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -H "Content-Type: application/json" -d '{"id_card":"110101199001010012","name":"測試"}' http://127.0.0.1:5082/api/customer`
- 搜尋客戶：
  - `curl -b /tmp/c.txt "http://127.0.0.1:5082/api/search?query=110101199001010012"`
- 更新客戶：
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -H "Content-Type: application/json" -X PUT -d '{"company":"測試公司"}' http://127.0.0.1:5082/api/customer/<id>`
- 刪除客戶：
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -X DELETE http://127.0.0.1:5082/api/customer/<id>`

## 測試與自檢
- 輕量冒煙：`python3 scripts/smoke_test.py --base http://127.0.0.1:5082`
- 綜合 E2E：`python3 scripts/test_all.py --base http://127.0.0.1:5082`
  - 選項：`--include-external`（phone/qq/weibo）、`--include-ai`（需 `DEEPSEEK_API_KEY`）
  - 若 `requests` 無法取得 CSRF，會自動回退至 `curl` 模式。

## 部署
- Gunicorn：`pip3 install gunicorn && gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`
- Docker：
  - 建置：`docker build -t stranger:latest .`
  - 執行：`docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`
- Docker Compose：
  - 啟動：`docker compose up -d --build`
  - 日誌：`docker compose logs -f stranger`
  - 停止：`docker compose down`
- Nginx/systemd 範例請參見英文版 README。

## 故障排除
- 登入後 `/api/csrf` 仍 401：
  - 檢查同源與 Cookie 策略；必要時使用 `curl` 回退。
- CSRF Token 不一致：
  - 比對 JSON `token` 與 `XSRF-TOKEN` Cookie；注意 `SameSite`/`Secure` 設定。
- 健康檢查顯示 DB 異常但功能可用：
  - 開發環境以 HTTP 200 為準；生產需檢查連線、逾時與索引。
- 外部驗證失敗：
  - 設定代理 `HTTP_PROXY`/`HTTPS_PROXY`，並檢查出網策略與重試參數。

## 貢獻與授權
- 歡迎 Issue/PR；合入前請執行測試並更新文件。
- 授權以倉庫中的 `LICENSE` 為準。

## 多語與 PWA
- 翻譯來源僅為 `static/i18n/` 的外部 JSON。
- 端點：`GET /i18n/list`、`GET /i18n/<lang>.json`
- Manifest：`GET /manifest.json?lang=<code>` 僅使用對應語言 JSON 的 `meta.pwa`；若缺 `lang` 或無 `meta.pwa` 則回 `400`。