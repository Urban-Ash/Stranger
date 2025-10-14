# Stranger
註：本專案完全由 AI 編寫。

<p align="center">
  <img src="https://img.shields.io/badge/AI%20Authored-100%25-blueviolet?style=for-the-badge" alt="純 AI 編寫 100%" />
  
</p>

一個前後端一體化的 OSINT 資訊聚合與檢索系統。支援多語言 UI、資料維護、來源詳情檢視、驗證查詢與可選的 AI 置信度評估。

## 特性
- 智慧搜尋：自動辨識關鍵詞類型（姓名/手機號/電子郵件/QQ/身分證/微博 UID），支援分頁、排序與可選聚合。
- 多語言：中文、英文、繁體中文、日文、韓文；語言選單具備 ARIA 無障礙提示。
- 資料維護：新增/編輯對話框，支援來源增量更新與記錄刪除。
- 來源詳情：點擊結果中的來源標籤，開啟彈窗檢視命中詳情。
- 驗證查詢：手機歸屬地、QQ 頭像與暱稱、微博 UID 主頁資訊、身分證結構解析。
- AI 置信度：評估並可選寫回主表。
- 健康與指標：統一健康檢查與指標端點，便於監控。

## 架構
- 前端：`static/` 模組化 JS，入口 `static/main.js`，模板 `templates/index.html`。
- 後端：Flask 應用 `app/app.py`（`create_app()`），路由 `app/api/routes.py`，統一回應 `app/api/response.py`。
- 資料庫：PostgreSQL；主表 `profile`，啟動自動建立索引；跨表掃描與動態別名見 `app/models/database.py`。
- 設定：`config/config.py` 統一管理，可由環境變數注入；支援 CORS、壓縮與限流。

## 目錄
- `app/` 後端（API/服務/模型/初始化）
- `static/` 前端靜態資源（JS/CSS/圖示）
- `templates/` Jinja 模板
- `config/` 設定與清單
- `scripts/` 輔助腳本（冒煙測試、DB 檢查）

## 快速開始
- 環境：Python 3.9+、PostgreSQL
- 依賴安裝：`pip3 install -r requirements.txt`
- 設定：複製 `.env.example` 為 `.env`，並設定：
  - `FLASK_HOST`、`FLASK_PORT`、`FLASK_ENV`、`CORS_ORIGINS`
  - `PG_HOST`、`PG_PORT`、`PG_DATABASE`、`PG_USER`、`PG_PASSWORD`
  - `SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`（預設 `60000` ms）
  - 選用代理與爬蟲：`CRAWLER_TIMEOUT`、`CRAWLER_RETRIES`、`CRAWLER_BACKOFF`、`HTTP_PROXY`/`HTTPS_PROXY`
- 開發：`python3 main.py`
- 生產：`gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`

## 存取
- 首頁：`http://127.0.0.1:5082/`
- 健康：`http://127.0.0.1:5082/health`
- 指標：`http://127.0.0.1:5082/api/metrics`

## API 概覽
- `GET /api/search`：參數 `query`；可選 `page`、`page_size`、`sort`、`order`、`expand`
- `POST /api/customer`：新增記錄
- `PUT /api/customer/<id>`：更新部分欄位
- `DELETE /api/customer/<id>`：刪除記錄
- `GET /api/source_detail`：依主體鍵檢視表命中詳情（`id_card`、`phones`、`qqs`、`weibo_uid`、`email`、`name`）
- 驗證：`/api/validate/phone`、`/api/validate/qq`、`/api/validate/weibo`、`/api/validate/id_card`
- AI：`POST /api/ai/assess_confidence`
- 自我檢視：`GET /api/schema_introspect`
- 健康與指標：`GET /health`、`GET /api/metrics`

## 部署示例
- Gunicorn（前台）：`gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`
- Nginx 反向代理與 systemd 單元示例請參見英文版 README 對應章節。

## Docker
- 建置：`docker build -t stranger:latest .`
- 執行：`docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`
- 說明：預設命令 `gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`；以 `-p` 與 `FLASK_PORT` 調整埠；`.dockerignore` 已精簡鏡像。

## Docker Compose
- 啟動：`docker compose up -d --build`
- 日誌：`docker compose logs -f stranger`
- 停止：`docker compose down`
- 說明：主機埠來自 `FLASK_PORT`（預設 `5082`）；Compose 會讀取 `.env`，容器內以 Gunicorn 啟動。

## 效能與穩定性建議
- 電話匹配優先使用等值條件，避免全表掃描；維護常用欄位的表達式索引。
- 控制跨表掃描預算：`SCAN_MAX_TABLES`、`SCAN_LIMIT_PER_TABLE`、`SCAN_TOTAL_TIME_BUDGET_MS`。
- 連線管理：建議連線池或請求級連線；多副本限流存放建議使用 Redis。
- 日誌與可觀測性：結構化日誌、輪替與等級控制。

## 冒煙測試
- `python3 scripts/smoke_test.py` 或指定基底位址：`python3 scripts/smoke_test.py http://<host>:<port>`

## 貢獻與授權
- 歡迎 issues 與 PR；提交前請執行冒煙測試並更新文件。
- 授權如未明確，默認為內部使用；如需開源請新增 LICENSE。