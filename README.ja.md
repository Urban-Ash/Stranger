<div align="center">

<h1>Stranger · OSINT 情報検索プラットフォーム</h1>

<img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python" alt="Python" />
<img src="https://img.shields.io/badge/Flask-2.x-000?logo=flask" alt="Flask" />
<img src="https://img.shields.io/badge/PostgreSQL-13%2B-336791?logo=postgresql" alt="PostgreSQL" />

<p>フロントとバックを一体化した OSINT 集約・検索システム。多言語 UI、ソース詳細、検証ユーティリティ、任意の AI 信頼度評価を備え、認証・CSRF・レート制限・CORS などのセキュリティ機能に対応します。</p>

</div>

## Stranger を選ぶ理由
- 多ソース集約と検索：氏名・電話・メール・QQ・ID・Weibo UID を単一 UI で検索、ソース詳細モーダルでヒット内容を確認。
- 多言語とアクセシビリティ：日本語・中国語・英語・繁体字・韓国語。キーボード操作と ARIA 対応。
- 任意の AI 評価：データ信頼度を評価し、必要に応じてメインテーブルへ書き戻し。
- エンジニアリングセキュリティ：認証（任意）、CSRF 保護、CORS、圧縮、レート制限。ヘルス・メトリクスで可観測性を提供。

## クイックスタート
- 前提：Python 3.9+、PostgreSQL
- 依存インストール：`pip3 install -r requirements.txt`
- 環境設定：`.env.example` を `.env` にコピーし以下を設定：
  - `FLASK_HOST`、`FLASK_PORT`、`FLASK_ENV`、`CORS_ORIGINS`
  - `PG_HOST`、`PG_PORT`、`PG_DATABASE`、`PG_USER`、`PG_PASSWORD`
  - `RATE_LIMIT`（既定 `60 per minute`）、`SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`（既定 `60000`）
  - AI を使う場合：`DEEPSEEK_API_KEY`（未設定なら AI は自動無効化）
- 開発起動：`python3 main.py`（既定 `http://127.0.0.1:8080`）
- 本番起動：`gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`（既定 `http://127.0.0.1:5082`）

## 認証とセキュリティ
- 認証スイッチ：`AUTH_ENABLED=true` の場合、`/login`・`/health`・`/static/` 等を除く `/api/` 配下はログイン必須。
- CSRF 保護：`/api/` の `POST/PUT/PATCH/DELETE` に CSRF 検証を適用。
  - 取得：ログイン後 `GET /api/csrf` が `{ token }` を返し、`XSRF-TOKEN` Cookie を設定。
  - 利用：変更系リクエストはヘッダに `X-CSRF-Token: <token>` を付与。
  - クロスサイト/HTTPS 代理：`SESSION_COOKIE_SAMESITE` や `SESSION_COOKIE_SECURE` の設定により、Cookie と CSRF の挙動が変わります。

## API 概要（よく使う）
- `GET /api/search`：`query`。オプション `page/page_size/sort/order/expand`
- `POST /api/customer`：作成
- `PUT /api/customer/<id>`：更新
- `DELETE /api/customer/<id>`：削除
- `GET /api/source_detail`：主キー（`id_card`、`phones`、`qqs`、`weibo_uid`、`email`、`name`）でソース命中詳細を表示
- 検証：`/api/validate/{phone|qq|weibo|id_card}`（`write=1` で永続化可）
- AI：`POST /api/ai/assess_confidence`
- ヘルス・メトリクス：`GET /health`、`GET /api/metrics`

> 注：大型/機密クエリでは、`/api/search` と `/api/source_detail` は `POST` JSON をオプションでサポート（デュアルスタック）。

## アーキテクチャとディレクトリ
- フロント：`static/` モジュール JS（入口 `static/main.js`）、テンプレート `templates/index.html`。
- バック：Flask `app/app.py`（`create_app()`）、ルート `app/api/routes.py`、レスポンス統一 `app/api/response.py`。
- DB：PostgreSQL テーブル `profile`、起動時にインデックス作成。クロステーブルスキャンは `app/models/database.py`。
- 設定：`config/config.py` と `config/data_source.json`。
- フロント詳細：`static/modules/search.js` は `result-item` を描画し、`data-index` を用いたイベント委譲を実装。

## エンドツーエンド例（認証＋CSRF）
`curl` を使用：
- ログイン：
  - `curl -i -c /tmp/c.txt -d "username=<user>&password=<pass>" http://127.0.0.1:5082/login`
- CSRF 取得：
  - `curl -b /tmp/c.txt http://127.0.0.1:5082/api/csrf`
- 作成：
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -H "Content-Type: application/json" -d '{"id_card":"110101199001010012","name":"テスト"}' http://127.0.0.1:5082/api/customer`
- 検索：
  - `curl -b /tmp/c.txt "http://127.0.0.1:5082/api/search?query=110101199001010012"`
- 更新：
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -H "Content-Type: application/json" -X PUT -d '{"company":"テスト会社"}' http://127.0.0.1:5082/api/customer/<id>`
- 削除：
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -X DELETE http://127.0.0.1:5082/api/customer/<id>`

## テストとセルフチェック
- 軽量スモーク：`python3 scripts/smoke_test.py --base http://127.0.0.1:5082`
- 総合 E2E：`python3 scripts/test_all.py --base http://127.0.0.1:5082`
  - オプション：`--include-external`（phone/qq/weibo）、`--include-ai`（`DEEPSEEK_API_KEY` 必須）
  - `requests` で CSRF 取得に失敗した場合、`curl` に自動フォールバックします。

## デプロイ
- Gunicorn：`pip3 install gunicorn && gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`
- Docker：
  - ビルド：`docker build -t stranger:latest .`
  - 実行：`docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`
- Docker Compose：
  - 開始：`docker compose up -d --build`
  - ログ：`docker compose logs -f stranger`
  - 停止：`docker compose down`
- Nginx/systemd の例は英語 README を参照。

## トラブルシューティング
- ログイン後も `/api/csrf` が 401：
  - 同一オリジンと Cookie ポリシーを確認。必要に応じて `curl` フォールバックを使用。
- CSRF トークン不一致：
  - JSON の `token` と `XSRF-TOKEN` Cookie を比較。`SameSite`/`Secure` 設定に注意。
- DB ヘルスが失敗でも機能は動作：
  - 開発では HTTP 200 を優先。プロダクションでは接続/タイムアウト/インデックスを確認。
- 外部検証失敗：
  - プロキシ `HTTP_PROXY`/`HTTPS_PROXY` と出力ポリシー/再試行設定を確認。

## 貢献・ライセンス
- Issue/PR を歓迎。マージ前にテストを実行し、文書を更新してください。
- ライセンスは `LICENSE` に従います。

## 多言語と PWA
- 翻訳は `static/i18n/` の外部 JSON のみを使用。
- エンドポイント：`GET /i18n/list`、`GET /i18n/<lang>.json`
- Manifest：`GET /manifest.json?lang=<code>` は `meta.pwa` のみを利用。`lang` 不足または `meta.pwa` 欠如時は `400`。