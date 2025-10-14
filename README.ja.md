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

## 画面・UX
- PWA 対応：デスクトップインストール、オフラインマニフェスト・サービスワーカー。
- ダーク/ライトテーマと UI からの言語切り替え。
- キーボードナビゲーションと ARIA ラベル対応のアクセシブルコンポーネント。

## スクリーンショット

<div align="center">

<img src="docs/screenshots/stranger-home-zh.png" alt="Stranger ホーム（中国語 UI）" width="720" />

<br/>

<img src="docs/screenshots/stranger-home-en.png" alt="Stranger Home（英語 UI）" width="720" />

</div>

## アーキテクチャ
- フロントエンド：`static/` モジュラー JS、エントリ `static/main.js`、テンプレート `templates/index.html`。
- バックエンド：Flask アプリ `app/app.py`（`create_app()`）、ルート `app/api/routes.py`、統一レスポンス `app/api/response.py`。
- データベース：PostgreSQL。メインテーブル `profile`、起動時インデックス作成。クロステーブルスキャンと動的エイリアスは `app/models/database.py`。
- 設定：`config/config.py` で一元化、環境変数注入。CORS、圧縮、レート制限対応。
  - CORS：`flask-cors` で有効化。`CORS_ORIGINS` で許可オリジン設定（既定 `*`）。
  - 圧縮：`Flask-Compress` で JSON/テキストレスポンス圧縮。
  - レート制限：`flask-limiter` で有効化。既定 `RATE_LIMIT=60 per minute`。
  - 認証：`AUTH_ENABLED=true` の場合、全非静的ルートでログイン必須。

## データソース
- `config/data_source.json` でフレンドリー名と日付を設定。
- アプリは利用可能時に DB メタデータから不足エントリを自動同期。
- テンプレート例：
  ```json
  {
    "example_table": { "name": "サンプルデータソース", "date": "YYYY-MM-DD" }
  }
  ```

## ディレクトリ
- `app/` バックエンド（API、サービス、DB モデル、アプリ初期化）
- `static/` フロントエンドアセット（JS/CSS/アイコン）
- `templates/` Jinja テンプレート
- `config/` 設定とマニフェスト
- `scripts/` ヘルパースクリプト（スモークテスト、DB 検査）

## クイックスタート
- 要件：Python 3.9+、PostgreSQL
- 依存関係インストール：`pip3 install -r requirements.txt`
- 環境設定：`.env.example` を `.env` にコピーして設定：
  - `FLASK_HOST`、`FLASK_PORT`、`FLASK_ENV`、`CORS_ORIGINS`
  - `PG_HOST`、`PG_PORT`、`PG_DATABASE`、`PG_USER`、`PG_PASSWORD`
  - `SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`（既定 `60000` ms）
  - オプションのプロキシ・クローラー：`CRAWLER_TIMEOUT`、`CRAWLER_RETRIES`、`CRAWLER_BACKOFF`、`HTTP_PROXY`/`HTTPS_PROXY`
- 開発実行：`python3 main.py`（既定 `http://127.0.0.1:8080`）
- 本番実行：`gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`（既定 `http://127.0.0.1:5082`）

## アクセス
- 開発：`http://127.0.0.1:8080/`（`python3 main.py` 経由）
- 本番/Docker：`http://127.0.0.1:5082/`
- ヘルス：`/health`
- メトリクス：`/api/metrics`

## API 概要
- `GET /api/search`：パラメータ `query`。オプション `page`、`page_size`、`sort`、`order`、`expand`
- `POST /api/customer`：レコード作成
- `PUT /api/customer/<id>`：許可フィールド更新
- `DELETE /api/customer/<id>`：レコード削除
- `GET /api/source_detail`：サブジェクトキー（`id_card`、`phones`、`qqs`、`weibo_uid`、`email`、`name`）でテーブルヒット詳細を検査
- バリデーター：
  - `GET /api/validate/phone` — パラメータ：`number`（必須）、`write`（`1|true|yes` で永続化）、オプション `id_card`、`merge_phone`。帰属情報（`province`、`city`、`carrier`、`area_code`、`postcode`）と `updated`/`id` を返す。
  - `GET /api/validate/qq` — パラメータ：`qq`（必須）、`write`（`1|true|yes`）、オプション `id_card`、`merge_phone`。`name`、`logo`、`updated`/`id` を返す。
  - `GET /api/validate/weibo` — パラメータ：`uid` または `weibo_uid`（必須）、`write`（`1|true|yes`）、オプション `id_card`。プロフィール概要（`name`、`gender`、`avatar`、`fans`、`follows`、`rpz`、`posts`）と `updated`/`id` を返す。
  - `GET /api/validate/id_card` — パラメータ：`id_card`（必須）、`write`（`1|true|yes`）。解析フィールド（`birth_date`、`gender`、`native_place`、`valid`）と既存との整合性を返す。
- AI：`POST /api/ai/assess_confidence`
- イントロスペクション：`GET /api/schema_introspect`
- ヘルス・メトリクス：`GET /health`、`GET /api/metrics`

> 注：大規模またはプライバシー重要なクエリの場合、`/api/search` と `/api/source_detail` は `POST` JSON ボディをオプションでサポート（デュアルスタック設計）。

## デプロイ例
**Gunicorn（フォアグラウンドテスト）**
- `pip3 install gunicorn`
- `gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`

**Nginx リバースプロキシ**
```
upstream stranger_app {
    server 127.0.0.1:5082;
}

server {
    listen 80;
    server_name your.domain.com;

    location / {
        proxy_pass http://stranger_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 75s;
        proxy_send_timeout 75s;
    }

    location /static/ {
        proxy_pass http://stranger_app;
    }
}
```

**systemd サービス**
- 環境ファイル：`/etc/stranger/stranger.env`（`.env.example` 参照）
- ユニット：`/etc/systemd/system/stranger.service`
```
[Unit]
Description=Stranger API Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/stranger
EnvironmentFile=/etc/stranger/stranger.env
ExecStart=/usr/bin/gunicorn -w 4 -b 0.0.0.0:${FLASK_PORT} app.app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Docker
本番イメージをビルド（Python 3.12-slim + Gunicorn）：

**ビルド**
- `docker build -t stranger:latest .`

**実行**（コンテナ 5082 をホスト 5082 にマップ）
- `docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`

**注記**
- 既定コマンド：`gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`。
- `-p <host_port>:<container_port>` と `FLASK_PORT` でホストポート変更。
- `.dockerignore` でイメージサイズ削減。

## セキュリティ注意事項
- `.env` をコミットしない。シークレット（DB、API キー）は環境経由で注入。
- 以前共有した場合は認証情報をローテート。プレースホルダーには `.env.example` を使用。
- エンドポイント公開前に `CORS_ORIGINS` と `RATE_LIMIT` を確認。
- `AUTH_ENABLED=true` の場合、`AUTH_USERNAME` と `AUTH_PASSWORD`（または `AUTH_PASSWORD_HASH`）を設定。

## Docker Compose
`docker-compose.yml` でワンコマンドビルド・実行。

- 開始：`docker compose up -d --build`
- ログ：`docker compose logs -f stranger`
- 停止：`docker compose down`

注記：
- ホストポートは `FLASK_PORT`（既定 `5082`）から。コンテナ `5082` にマップ。
- Compose は `.env` を自動読み込み。Gunicorn はコンテナ内で `app.app:app` を実行。

## パフォーマンス・安定性のヒント
- 電話マッチングにはインデックス対応の等価条件を優先。フルスキャン回避。
- `SOURCE_DETAIL_STATEMENT_TIMEOUT_MS` を調整。一般列の式インデックスを維持。
- クロステーブルスキャン予算制御：`SCAN_MAX_TABLES`、`SCAN_LIMIT_PER_TABLE`、`SCAN_TOTAL_TIME_BUDGET_MS`。
- 接続管理：プール（`ThreadedConnectionPool`）またはリクエストスコープ接続を検討。
- レート制限ストレージ：マルチレプリカデプロイには共有ストア（例：Redis）を使用。
- ログ・可観測性：構造化ログ、ローテーション、適切なレベル。

## スモークテスト
- `python3 scripts/smoke_test.py` または `python3 scripts/smoke_test.py http://<host>:<port>`
- カバー範囲：`/`、`/api/metrics`、`/api/search`、`/api/source_detail`、`/api/schema_introspect`、`/api/validate/id_card`
- 期待結果：`PASS (6 passed, 0 failed)`

## トラブルシューティング
- 503 / タイムアウト：`statement timeout` のログを確認。タイムアウト増加またはクエリ最適化。インデックス確認。
- 遅いクロステーブルスキャン：予算を下げるかキーベース集約に切り替え。
- 外部リクエスト失敗：プロキシと再試行設定を設定。アウトバウンドネットワークポリシーを確認。

## 貢献・ライセンス
- Issue と PR を歓迎。提出前にスモークテストを実行し、ドキュメントを更新してください。
- `LICENSE` の条項でライセンス。