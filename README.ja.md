# Stranger
注記: 本プロジェクトは完全にAIによって作成されています。

<p align="center">
  <img src="https://img.shields.io/badge/AI%20Authored-100%25-blueviolet?style=for-the-badge" alt="AI による作成 100%" />
  
</p>

フロントエンドとバックエンドを統合した OSINT 集約・検索システムです。多言語 UI、データメンテナンス、ソース詳細閲覧、検証クエリ、AI 信頼度評価（任意）を提供します。

## 特長
- スマート検索：クエリ種別（氏名/電話/メール/QQ/ID/Weibo UID）を自動判別。ページング、ソート、集約に対応。
- 多言語：日本語、中文、英語、繁体字、韓国語。ARIA 対応の言語メニュー。
- データメンテナンス：追加/編集モーダル、ソースの増分更新、レコード削除。
- ソース詳細：結果のソースチップをクリックして詳細モーダルを表示。
- 検証：電話の地域、QQ プロフィール、Weibo UID 情報、ID カード解析。
- AI 信頼度：評価して主テーブルへ書き戻し可能。
- ヘルス/メトリクス：監視用の統一エンドポイント。
- セキュリティ：CORS（`flask-cors`、`CORS_ORIGINS` 設定）、圧縮（`Flask-Compress`）、レート制限（`flask-limiter`、`RATE_LIMIT` 設定、既定 `60 per minute`）。認証有効時（`AUTH_ENABLED=true`）は非静的ルートでログイン必須。

## スクリーンショット

<div align="center">

<img src="docs/screenshots/stranger-home-zh.png" alt="Stranger ホーム（中国語 UI）" width="720" />

<br/>

<img src="docs/screenshots/stranger-home-en.png" alt="Stranger Home（英語 UI）" width="720" />

</div>

## アーキテクチャ
- フロント：`static/` モジュール化 JS、エントリ `static/main.js`、テンプレート `templates/index.html`。
- バックエンド：Flask アプリ `app/app.py`（`create_app()`）、ルート `app/api/routes.py`、レスポンス共通化 `app/api/response.py`。
- DB：PostgreSQL。メインテーブル `profile`、起動時にインデックス作成。クロステーブル検索と動的エイリアスは `app/models/database.py`。
- 設定：`config/config.py` で一元管理。環境変数注入、CORS/圧縮/レート制限対応。

## ディレクトリ
- `app/` バックエンド（API/サービス/モデル/初期化）
- `static/` フロント資産（JS/CSS/アイコン）
- `templates/` Jinja テンプレート
- `config/` 設定・マニフェスト
- `scripts/` スクリプト（スモークテスト/DB チェック）

## クイックスタート
- 要件：Python 3.9+、PostgreSQL
- 依存関係：`pip3 install -r requirements.txt`
- 設定：`.env.example` を `.env` にコピーし、以下を設定：
  - `FLASK_HOST`、`FLASK_PORT`、`FLASK_ENV`、`CORS_ORIGINS`
  - `PG_HOST`、`PG_PORT`、`PG_DATABASE`、`PG_USER`、`PG_PASSWORD`
  - `SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`（既定 `60000` ms）
  - 任意のプロキシ/クローラ設定：`CRAWLER_TIMEOUT`、`CRAWLER_RETRIES`、`CRAWLER_BACKOFF`、`HTTP_PROXY`/`HTTPS_PROXY`
- 開発：`python3 main.py`（既定 `http://127.0.0.1:8080`）
- 本番：`gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`（既定 `http://127.0.0.1:5082`）

## アクセス
- 開発：`http://127.0.0.1:8080/`（`python3 main.py` 経由）
- 本番/Docker：`http://127.0.0.1:5082/`
- ヘルス：`/health`
- メトリクス：`/api/metrics`

## API 概要
- `GET /api/search`：`query`、任意 `page`、`page_size`、`sort`、`order`、`expand`
- `POST /api/customer`：作成
- `PUT /api/customer/<id>`：一部フィールド更新
- `DELETE /api/customer/<id>`：削除
- `GET /api/source_detail`：主体キー（`id_card`、`phones`、`qqs`、`weibo_uid`、`email`、`name`）で詳細
- 検証：
  - `GET /api/validate/phone` — パラメータ：`number`（必須）、`write`（`1|true|yes` で永続化）、任意 `id_card`、`merge_phone`；戻り値：地域情報（`province`、`city`、`carrier`、`area_code`、`postcode`）と `updated`/`id`。
  - `GET /api/validate/qq` — パラメータ：`qq`（必須）、`write`（`1|true|yes` で永続化）、任意 `id_card`、`merge_phone`；戻り値：プロフィール（`nickname`、`avatar`、`level`、`vip`）と `updated`/`id`。
  - `GET /api/validate/weibo` — パラメータ：`uid|weibo_uid`（必須）、`write`（`1|true|yes` で永続化）、任意 `id_card`；戻り値：プロフィール（`screen_name`、`followers_count`、`verified`、`description`）と `updated`/`id`。
  - `GET /api/validate/id_card` — パラメータ：`id_card`（必須）、任意 `write`（`1|true|yes` で永続化）；戻り値：検証結果（`valid`、`address_code`、`birth_date`、`gender`、`consistency_check`）と `updated`/`id`。
- AI：`POST /api/ai/assess_confidence`
- 自己診断：`GET /api/schema_introspect`
- ヘルス/メトリクス：`GET /health`、`GET /api/metrics`

## セキュリティ注意事項
- 本番では `SECRET_KEY`、`PG_PASSWORD`、`AUTH_PASSWORD` を変更してください。
- `CORS_ORIGINS` を信頼できるドメインに制限してください（既定 `*`）。
- `RATE_LIMIT` を適切に設定してください（既定 `60 per minute`）。

## デプロイ例
- Gunicorn（前面）：`gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`
- Nginx 逆プロキシと systemd の例は英語版 README の該当章を参照。

## Docker
- ビルド：`docker build -t stranger:latest .`
- 実行：`docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`

## Docker Compose
- 起動：`docker compose up -d --build`
- ログ：`docker compose logs -f stranger`
- 停止：`docker compose down`

## パフォーマンスのヒント
- インデックス利用に適した等価条件を優先、全表走査を回避。
- クロステーブル検索の予算を制御。一般列に式インデックスを維持。

## スモークテスト
- `python3 scripts/smoke_test.py` または基底 URL を指定（既定 `http://127.0.0.1:5082`）。
- 6 エンドポイントをテスト：`/`、`/api/metrics`、`/api/search`、`/api/source_detail`、`/api/schema_introspect`、`/api/validate/id_card`。

## 貢献・ライセンス
- Issue/PR 歓迎。スモークテスト実行と文書更新をお願いします。