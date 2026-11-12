# weather_fit — 날씨 충격과 패션 수요

서울의 기상(관측·예보·특보)과 네이버 데이터랩 패션 수요 지수를 결합해
**① 날씨 충격이 품목 수요를 얼마나·며칠 움직이는지 분석**하고,
**② 그 시점에 공개된 예보만으로 며칠 뒤 수요 상승 품목을 예측**하고,
**③ 그 결과를 탐색하는 웹 서비스**를 만드는 프로젝트입니다.

![status](https://img.shields.io/badge/status-착수%20전-lightgrey) ![python](https://img.shields.io/badge/python-3.10-blue)

## 문서

| 문서 | 내용 |
|---|---|
| [`docs/prd.md`](docs/prd.md) | 목표, 가설, 예측 문제 정의, 평가 기준, 서비스 요구사항, 일정 — **먼저 읽기** |
| [`docs/datasets.md`](docs/datasets.md) | 데이터 소스별 엔드포인트·인증·한도·응답 함정, 산출 스키마 |
| [`configs/categories.yaml`](configs/categories.yaml) | 수요 타깃 정의(카테고리 cid, 날씨 민감 키워드, 앵커) |
| [`notebooks/01_eda.ipynb`](notebooks/01_eda.ipynb) | 2023-01 ~ 2026-07 탐색적 분석. 데이터 함정과 예비 결론 |

## 빠른 시작

```bash
# 1) 환경 (Python 3.10)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) API 키 — 둘 중 하나만 있으면 됩니다
cp .env.example .env                                   # 또는
cp configs/secrets.example.yaml configs/secrets.yaml

# 3) 키 확인 — 전부 OK 가 나와야 다음 단계로
python scripts/check_keys.py

# 4) 테스트
python -m pytest -q

# 5) 수집 예시 (먼저 --dry-run 으로 배치 구성 확인)
python -m src.collect.datalab_keyword --dry-run
python -m src.collect.weather_asos --start 2023-01-01 --end 2023-01-31
```

필요한 키는 세 가지입니다. 발급 절차는 `docs/datasets.md` §4에 있습니다.

| 키 | 발급처 | 용도 |
|---|---|---|
| `KMA_APIHUB_AUTH_KEY` | 기상청 API 허브 | 관측·중기예보·특보 |
| `NAVER_API_HUB_CLIENT_ID` / `_SECRET` | 네이버클라우드 NAVER API HUB | 데이터랩 쇼핑인사이트·검색어트렌드 |
| `DATA_GO_KR_SERVICE_KEY` | 공공데이터포털 | 공휴일·미세먼지 |

> 네이버 데이터랩은 2026-06 **NAVER API HUB**로 이관됐습니다. 네이버 개발자센터 키는 쓰지 않습니다.

## 저장소 구조

```
configs/        타깃 정의, 키 템플릿
docs/           PRD, 데이터셋 카탈로그 (결정 기록은 docs/adr/ 에 추가)
src/collect/    수집기 — 기상청 4종(관측·중기기온·중기육상·특보), 데이터랩 3종(카테고리·키워드·검색어)
src/transform/  정제 (비어 있음)
scripts/        키 점검
tests/          단위 테스트
data/raw/       원천 데이터. 데이터랩 2023-01 ~ 2026-07 백필(all_years.csv)과 2026-07 샘플
notebooks/      탐색적 분석 (01_eda.ipynb)
reports/ dashboard/   비어 있음
```

`src/model/`, 웹 서비스 디렉터리, `Makefile`, CI 설정은 PRD 일정에 따라 직접 추가합니다.
