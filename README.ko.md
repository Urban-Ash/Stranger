<div align="center">

<h1>Stranger · OSINT 정보 검색 플랫폼</h1>

<img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python" alt="Python" />
<img src="https://img.shields.io/badge/Flask-2.x-000?logo=flask" alt="Flask" />
<img src="https://img.shields.io/badge/PostgreSQL-13%2B-336791?logo=postgresql" alt="PostgreSQL" />

<p>프론트와 백엔드를 통합한 OSINT 집계·검색 시스템입니다. 다국어 UI, 소스 상세, 검증 유틸, 선택적 AI 신뢰도 평가를 제공하며, 인증·CSRF·레이트 제한·CORS 등 보안 기능을 지원합니다.</p>

</div>

## Stranger를 선택해야 하는 이유
- 다중 소스 집계 및 검색: 이름/전화/이메일/QQ/ID/Weibo UID를 단일 UI에서 검색, 소스 상세 모달로 히트 내용을 확인.
- 다국어 및 접근성: 한국어·일본어·중국어(간/번)·영어. 키보드 내비와 ARIA 지원.
- 선택적 AI 평가: 데이터 신뢰도를 평가하고 필요 시 메인 테이블에 반영.
- 엔지니어링 보안: 인증(옵션), CSRF 보호, CORS, 압축, 레이트 제한. 헬스·메트릭으로 관측성 제공.

## 빠른 시작
- 요구사항: Python 3.9+, PostgreSQL
- 의존성 설치: `pip3 install -r requirements.txt`
- 환경 설정: `.env.example`를 `.env`로 복사하고 다음을 설정:
  - `FLASK_HOST`, `FLASK_PORT`, `FLASK_ENV`, `CORS_ORIGINS`
  - `PG_HOST`, `PG_PORT`, `PG_DATABASE`, `PG_USER`, `PG_PASSWORD`
  - `RATE_LIMIT`(기본 `60 per minute`), `SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`(기본 `60000`)
  - AI 사용 시: `DEEPSEEK_API_KEY`(없으면 AI 자동 비활성화)
- 개발 실행: `python3 main.py`(`http://127.0.0.1:8080`)
- 운영 실행: `gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`(`http://127.0.0.1:5082`)

## 인증과 보안
- 인증 스위치: `AUTH_ENABLED=true`일 때 `/login`·`/health`·`/static/` 등을 제외한 `/api/`는 로그인 필요.
- CSRF 보호: `/api/`의 `POST/PUT/PATCH/DELETE`에 CSRF 검증 적용.
  - 획득: 로그인 후 `GET /api/csrf`가 `{ token }`을 반환하고 `XSRF-TOKEN` 쿠키를 설정.
  - 사용: 변경 요청에 `X-CSRF-Token: <token>` 헤더를 포함.
  - 크로스사이트/HTTPS: `SESSION_COOKIE_SAMESITE` 및 `SESSION_COOKIE_SECURE` 설정에 따라 쿠키/CSRF 동작이 달라집니다.

## API 개요(자주 사용)
- `GET /api/search`: `query`. 옵션 `page/page_size/sort/order/expand`
- `POST /api/customer`: 생성
- `PUT /api/customer/<id>`: 업데이트
- `DELETE /api/customer/<id>`: 삭제
- `GET /api/source_detail`: 주 키(`id_card`, `phones`, `qqs`, `weibo_uid`, `email`, `name`)로 소스 히트 상세
- 검증: `/api/validate/{phone|qq|weibo|id_card}`(`write=1`로 영속화 가능)
- AI: `POST /api/ai/assess_confidence`
- 헬스/메트릭: `GET /health`, `GET /api/metrics`

> 참고: 대형/기밀 조회에 대해 `/api/search`와 `/api/source_detail`은 선택적으로 `POST` JSON(듀얼 스택)을 지원합니다.

## 아키텍처와 디렉터리
- 프론트: `static/` 모듈 JS(엔트리 `static/main.js`), 템플릿 `templates/index.html`.
- 백: Flask `app/app.py`(`create_app()`), 라우트 `app/api/routes.py`, 응답 통일 `app/api/response.py`.
- DB: PostgreSQL 테이블 `profile`, 부팅 시 인덱스 생성. 크로스테이블 스캔은 `app/models/database.py`.
- 설정: `config/config.py`, `config/data_source.json`.
- 프론트 상세: `static/modules/search.js`는 `result-item`을 렌더링하고 `data-index` 이벤트 위임을 구현.

## 엔드투엔드 사용 예(인증+CSRF)
`curl` 사용:
- 로그인:
  - `curl -i -c /tmp/c.txt -d "username=<user>&password=<pass>" http://127.0.0.1:5082/login`
- CSRF 토큰:
  - `curl -b /tmp/c.txt http://127.0.0.1:5082/api/csrf`
- 생성:
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -H "Content-Type: application/json" -d '{"id_card":"110101199001010012","name":"테스트"}' http://127.0.0.1:5082/api/customer`
- 검색:
  - `curl -b /tmp/c.txt "http://127.0.0.1:5082/api/search?query=110101199001010012"`
- 업데이트:
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -H "Content-Type: application/json" -X PUT -d '{"company":"테스트회사"}' http://127.0.0.1:5082/api/customer/<id>`
- 삭제:
  - `curl -b /tmp/c.txt -H "X-CSRF-Token: <token>" -X DELETE http://127.0.0.1:5082/api/customer/<id>`

## 테스트와 자가 점검
- 경량 스모크: `python3 scripts/smoke_test.py --base http://127.0.0.1:5082`
- 종합 E2E: `python3 scripts/test_all.py --base http://127.0.0.1:5082`
  - 옵션: `--include-external`(phone/qq/weibo), `--include-ai`(`DEEPSEEK_API_KEY` 필요)
  - `requests`가 CSRF 획득에 실패하면 자동으로 `curl`로 폴백합니다.

## 배포
- Gunicorn: `pip3 install gunicorn && gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`
- Docker:
  - 빌드: `docker build -t stranger:latest .`
  - 실행: `docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`
- Docker Compose:
  - 시작: `docker compose up -d --build`
  - 로그: `docker compose logs -f stranger`
  - 중지: `docker compose down`
- Nginx/systemd 예시는 영어 README를 참고하세요.

## 문제 해결
- 로그인 후에도 `/api/csrf`가 401:
  - 동일 출처와 쿠키 정책 확인. 필요 시 `curl` 폴백 사용.
- CSRF 토큰 불일치:
  - JSON `token`과 `XSRF-TOKEN` 쿠키 비교. `SameSite`/`Secure` 설정에 유의.
- DB 헬스가 실패해도 기능은 동작:
  - 개발 환경에서는 HTTP 200을 우선. 운영에서는 연결/타임아웃/인덱스를 확인.
- 외부 검증 실패:
  - 프록시 `HTTP_PROXY`/`HTTPS_PROXY`와 아웃바운드 정책/재시도 설정을 확인.

## 기여 및 라이선스
- 이슈/PR 환영. 머지 전 테스트 실행 및 문서 업데이트를 권장합니다.
- 라이선스는 `LICENSE`를 따릅니다.

## 국제화 및 PWA
- 번역은 `static/i18n/`의 외부 JSON만 사용합니다.
- 엔드포인트: `GET /i18n/list`, `GET /i18n/<lang>.json`
- 매니페스트: `GET /manifest.json?lang=<code>`는 `meta.pwa`만 사용. `lang` 없거나 `meta.pwa` 없으면 `400`.