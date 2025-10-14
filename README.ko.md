# Stranger
참고: 이 프로젝트는 전적으로 AI에 의해 작성되었습니다.

<p align="center">
  <img src="https://img.shields.io/badge/AI%20Authored-100%25-blueviolet?style=for-the-badge" alt="AI 작성 100%" />
  
</p>

프론트엔드와 백엔드를 통합한 OSINT 통합·검색 시스템입니다. 다국어 UI, 데이터 관리, 소스 상세 보기, 검증 쿼리, 선택적 AI 신뢰도 평가를 제공합니다.

## 주요 기능
- 스마트 검색: 질의 유형(이름/전화/이메일/QQ/신분증/웨이보 UID) 자동 판별, 페이지네이션/정렬/집계 지원.
- 다국어: 한국어, 중국어, 영어, 번체, 일본어. ARIA 지원 언어 메뉴.
- 데이터 관리: 추가/편집 모달, 소스 증분 업데이트, 레코드 삭제.
- 소스 상세: 결과의 소스 칩 클릭 시 상세 모달 표시.
- 검증: 전화 지역, QQ 프로필, Weibo UID 정보, 신분증 구조 파싱.
- AI 신뢰도: 평가 후 주 테이블에 선택적으로 반영.
- 헬스/메트릭: 모니터링용 통합 엔드포인트.
- 보안: CORS(`flask-cors`, `CORS_ORIGINS` 설정), 압축(`Flask-Compress`), 레이트 제한(`flask-limiter`, `RATE_LIMIT` 설정, 기본 `60 per minute`). 인증 활성화 시(`AUTH_ENABLED=true`) 비정적 라우트에서 로그인 필요.

## 아키텍처
- 프론트엔드: `static/` 모듈형 JS, 엔트리 `static/main.js`, 템플릿 `templates/index.html`.
- 백엔드: Flask 앱 `app/app.py`(`create_app()`), 라우트 `app/api/routes.py`, 응답 통일 `app/api/response.py`.
- 데이터베이스: PostgreSQL. 메인 테이블 `profile`, 시작 시 인덱스 생성. 크로스 테이블 스캔과 동적 별칭은 `app/models/database.py`.
- 설정: `config/config.py`로 일원화, 환경 변수 주입. CORS/압축/레이트 리밋 지원.

## 디렉터리
- `app/` 백엔드 (API/서비스/모델/초기화)
- `static/` 프론트 자산 (JS/CSS/아이콘)
- `templates/` Jinja 템플릿
- `config/` 설정 및 매니페스트
- `scripts/` 스크립트 (스모크 테스트/DB 점검)

## 시작하기
- 요구 사항: Python 3.9+, PostgreSQL
- 의존성 설치: `pip3 install -r requirements.txt`
- 환경 설정: `.env.example`를 `.env`로 복사하고 다음을 설정
  - `FLASK_HOST`, `FLASK_PORT`, `FLASK_ENV`, `CORS_ORIGINS`
  - `PG_HOST`, `PG_PORT`, `PG_DATABASE`, `PG_USER`, `PG_PASSWORD`
  - `SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`(기본 `60000` ms)
  - 선택: 프록시/크롤러 `CRAWLER_TIMEOUT`, `CRAWLER_RETRIES`, `CRAWLER_BACKOFF`, `HTTP_PROXY`/`HTTPS_PROXY`
- 개발 실행: `python3 main.py` (기본 `http://127.0.0.1:8080`)
- 프로덕션: `gunicorn -w 4 -b 0.0.0.0:5082 app.app:app` (기본 `http://127.0.0.1:5082`)

## 스크린샷

<div align="center">

<img src="docs/screenshots/stranger-home-zh.png" alt="Stranger 홈 (중국어 UI)" width="720" />

<br/>

<img src="docs/screenshots/stranger-home-en.png" alt="Stranger Home (영어 UI)" width="720" />

</div>

## 접속
- 개발: `http://127.0.0.1:8080/` (`python3 main.py` 경유)
- 프로덕션/Docker: `http://127.0.0.1:5082/`
- 헬스: `/health`
- 메트릭: `/api/metrics`

## API 개요
- `GET /api/search`: `query`, 옵션 `page`, `page_size`, `sort`, `order`, `expand`
- `POST /api/customer`: 생성
- `PUT /api/customer/<id>`: 일부 필드 업데이트
- `DELETE /api/customer/<id>`: 삭제
- `GET /api/source_detail`: 주 키(`id_card`, `phones`, `qqs`, `weibo_uid`, `email`, `name`)로 상세
- 검증:
  - `GET /api/validate/phone` — 매개변수: `number`(필수), `write`(`1|true|yes`로 지속화), 선택 `id_card`, `merge_phone`; 반환: 지역 정보(`province`, `city`, `carrier`, `area_code`, `postcode`)와 `updated`/`id`.
  - `GET /api/validate/qq` — 매개변수: `qq`(필수), `write`(`1|true|yes`로 지속화), 선택 `id_card`, `merge_phone`; 반환: 프로필(`nickname`, `avatar`, `level`, `vip`)과 `updated`/`id`.
  - `GET /api/validate/weibo` — 매개변수: `uid|weibo_uid`(필수), `write`(`1|true|yes`로 지속화), 선택 `id_card`; 반환: 프로필(`screen_name`, `followers_count`, `verified`, `description`)과 `updated`/`id`.
  - `GET /api/validate/id_card` — 매개변수: `id_card`(필수), 선택 `write`(`1|true|yes`로 지속화); 반환: 검증 결과(`valid`, `address_code`, `birth_date`, `gender`, `consistency_check`)와 `updated`/`id`.
- AI: `POST /api/ai/assess_confidence`
- 자가 점검: `GET /api/schema_introspect`
- 헬스/메트릭: `GET /health`, `GET /api/metrics`

## 보안 주의사항
- 프로덕션에서는 `SECRET_KEY`, `PG_PASSWORD`, `AUTH_PASSWORD`를 변경하세요.
- `CORS_ORIGINS`를 신뢰할 수 있는 도메인으로 제한하세요 (기본 `*`).
- `RATE_LIMIT`를 적절히 설정하세요 (기본 `60 per minute`).

## 배포 예시
- Gunicorn(포그라운드): `gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`
- Nginx 리버스 프록시 및 systemd 예시는 영문 README 참고.

## Docker
- 빌드: `docker build -t stranger:latest .`
- 실행: `docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`

## Docker Compose
- 시작: `docker compose up -d --build`
- 로그: `docker compose logs -f stranger`
- 중지: `docker compose down`

## 성능 및 안정성 팁
- 인덱스 친화적인 등가 조건을 우선 사용, 전체 스캔 회피.
- 크로스 테이블 스캔 예산 제어. 일반 열에 대한 표현식 인덱스 유지.

## 스모크 테스트
- `python3 scripts/smoke_test.py` 또는 베이스 URL 지정 (기본 `http://127.0.0.1:5082`).
- 6개 엔드포인트 테스트: `/`, `/api/metrics`, `/api/search`, `/api/source_detail`, `/api/schema_introspect`, `/api/validate/id_card`.

## 기여 및 라이선스
- Issue/PR 환영. 스모크 테스트 실행과 문서 갱신을 권장합니다.