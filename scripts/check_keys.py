"""발급받은 API 키와 엔드포인트를 최소 호출로 검증한다.

    python scripts/check_keys.py

각 항목마다 OK / FAIL / SKIP(키 미입력) 을 출력한다.
특히 [KMA-3] 중기예보 과거 조회는 이 프로젝트 설계의 전제이므로 반드시 OK 여야 한다.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "configs" / "secrets.yaml"
KMA = "https://apihub.kma.go.kr/api/typ01/url"
TIMEOUT = 30

PASS, FAIL, SKIP = "\033[32mOK  \033[0m", "\033[31mFAIL\033[0m", "\033[33mSKIP\033[0m"


def report(tag: str, status: str, detail: str = "") -> bool:
    print(f"  [{status}] {tag}" + (f" — {detail}" if detail else ""))
    return status == PASS


def preview(text: str, n: int = 160) -> str:
    """응답 앞부분을 한 줄로."""
    return " ".join(text.split())[:n]


def kma_ok(text: str) -> tuple[bool, str]:
    """API 허브 응답 판정.

    정상: `#START7777` ~ `#7777END` 로 감싼 텍스트, 그 사이가 데이터 행.
    실패: JSON 에러 바디 (403 활용신청 필요, 인증 실패 등) — 상태코드가 200인 경우도 있다.
    """
    t = text.strip()
    if t.startswith("{"):
        try:
            return False, json.loads(t)["result"]["message"]
        except Exception:
            return False, preview(t)
    rows = [ln for ln in t.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not rows:
        return False, f"데이터 0행 — {preview(t, 80)}"
    return True, f"{len(rows)}행 수신"


def check_kma(key: str) -> None:
    print("\n■ 기상청 API 허브")
    if not key:
        report("전체", SKIP, "kma_apihub.auth_key 비어 있음")
        return

    # 1) 지상관측 일자료 — 백필의 기준선
    r = requests.get(f"{KMA}/kma_sfcdd3.php", timeout=TIMEOUT, params={
        "tm1": "20230101", "tm2": "20230107", "stn": "108", "disp": "1", "help": "0", "authKey": key})
    ok, msg = kma_ok(r.text)
    report("[KMA-1] 지상관측 일자료 (서울 108, 2023-01-01~07)", PASS if ok else FAIL, msg)

    # 2) 특보 발표 이력
    r = requests.get(f"{KMA}/wrn_met_data.php", timeout=TIMEOUT, params={
        "tmfc1": "20230101", "tmfc2": "20230131", "disp": "1", "help": "0", "authKey": key})
    ok, msg = kma_ok(r.text)
    report("[KMA-2] 기상특보 이력 (2023-01)", PASS if ok else FAIL, msg)

    # 3) 중기 기온예보 과거 발표분 — ★ 설계 전제. 실패 시 모델 입력 전략을 바꿔야 한다
    r = requests.get(f"{KMA}/fct_afs_wc.php", timeout=TIMEOUT, params={
        "tmfc1": "2023010106", "tmfc2": "2023010218", "reg": "11B10101",
        "disp": "1", "help": "0", "authKey": key})
    ok, msg = kma_ok(r.text)
    report("[KMA-3] ★ 중기 기온예보 과거 발표분 (2023-01)", PASS if ok else FAIL, msg)
    if not ok and "활용신청" not in msg:
        # 403(권한)은 설계 문제가 아니다. 데이터가 정말 안 올 때만 설계 재검토 대상.
        print("         └ 과거 발표분 조회 불가 → 예보 피처는 오늘부터 축적으로 전환,")
        print("           3년 백필은 관측(KMA-1)만 사용하도록 설계 변경 필요")

    # 4) 중기 육상예보
    r = requests.get(f"{KMA}/fct_afs_wl.php", timeout=TIMEOUT, params={
        "tmfc1": "2023010106", "tmfc2": "2023010218", "reg": "11B00000",
        "disp": "1", "help": "0", "authKey": key})
    ok, msg = kma_ok(r.text)
    report("[KMA-4] 중기 육상예보 과거 발표분", PASS if ok else FAIL, msg)


def check_naver(hub_id: str, hub_secret: str) -> None:
    """데이터랩은 NAVER API HUB(네이버클라우드)로 이관됐다.

    - 2026-06-25 HUB 출시, 2026-07-31 개발자센터 신규 신청 차단
    - 개발자센터 키로는 HUB 를 호출할 수 없다. 새로 시작하는 사람은 HUB 키만 발급하면 된다.
    - 쇼핑인사이트·검색어트렌드는 별개 API 라 Application 에 둘 다 추가해야 한다.
    경로·헤더 출처: api.ncloud-docs.com/docs/naver-api-hub-* (2026-09-17 갱신본)
    """
    span = {"startDate": "2026-07-01", "endDate": "2026-07-07", "timeUnit": "date"}
    shopping = {**span, "category": [{"name": "패션의류", "param": ["50000000"]}]}
    trend = {**span, "keywordGroups": [{"groupName": "패딩", "keywords": ["패딩"]}]}

    print("\n■ 네이버 데이터랩 — NAVER API HUB")
    if not (hub_id and hub_secret):
        report("전체", SKIP, "NAVER_API_HUB_CLIENT_ID / NAVER_API_HUB_CLIENT_SECRET 비어 있음")
        return

    hdr = {"X-NCP-APIGW-API-KEY-ID": hub_id, "X-NCP-APIGW-API-KEY": hub_secret,
           "Content-Type": "application/json"}
    base = "https://naverapihub.apigw.ntruss.com"
    for tag, path, body, hint in [
        ("[HUB-1] 쇼핑인사이트 카테고리", "/shopping/v1/categories", shopping,
         "Application 에 '쇼핑인사이트' API 가 추가돼 있는지 확인"),
        ("[HUB-2] 검색어트렌드", "/search-trend/v1/search", trend,
         "'검색어 트렌드'는 쇼핑인사이트와 별도 API — Application 에 따로 추가"),
    ]:
        try:
            r = requests.post(base + path, headers=hdr, timeout=TIMEOUT, json=body)
        except requests.RequestException as e:
            report(tag, FAIL, str(e)[:120])
            continue
        if r.status_code == 200:
            report(tag, PASS, f"{len(r.json()['results'][0]['data'])}일치 수신")
            continue
        report(tag, FAIL, f"{r.status_code} {preview(r.text)}")
        if r.status_code == 401:
            print("         └ 개발자센터 키·NCP IAM 키가 아니라 HUB Application 의 Client ID/Secret 인지 확인")
        elif r.status_code == 429:
            print("         └ 50 RPS 초과 또는 월 한도 소진 — NCP 콘솔 사용량 화면 확인")
        else:
            print(f"         └ {hint}")

    print("\n■ 네이버 쇼핑 검색 API")
    report("[NAVER-3] /v1/search/shop.json", SKIP,
           "2026-07-31 종료, HUB 대체 없음 → 데이터셋 T6 폐기")


def check_datagokr(key: str) -> None:
    print("\n■ 공공데이터포털")
    if not key:
        report("공휴일", SKIP, "data_go_kr.service_key 비어 있음")
        return
    r = requests.get(
        "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo",
        timeout=TIMEOUT,
        params={"serviceKey": key, "solYear": "2025", "_type": "json", "numOfRows": 30})
    # 인증 실패는 resultCode 로 판정한다. 본문에 "NORMAL SERVICE" 가 들어가므로
    # 문자열 'SERVICE' 유무로 판정하면 정상 응답을 실패로 오판한다.
    ok, detail = False, preview(r.text)
    if r.status_code == 200:
        try:
            body = json.loads(r.text)["response"]
            code = body["header"]["resultCode"]
            ok = code == "00"
            detail = f"{len(body['body']['items']['item'])}건 수신" if ok else f"resultCode={code}"
        except Exception:
            ok = False  # XML 에러 바디 (SERVICE_KEY_IS_NOT_REGISTERED_ERROR 등)
    report("[GOV-1] 공휴일 (특일 정보 2025)", PASS if ok else FAIL, detail)
    if not ok:
        print("         └ Decoding 키를 넣었는지 확인 (Encoding 키는 이중 인코딩되어 실패)")


def main() -> int:
    # 키는 .env / 환경변수 / configs/secrets.yaml 어디에 있어도 된다.
    sys.path.insert(0, str(ROOT))
    from src.collect._common import load_secrets

    try:
        s = load_secrets()
    except FileNotFoundError as e:
        print(e)
        return 1

    get = lambda *ks: (s.get(ks[0]) or {}).get(ks[1]) or ""

    sources = [name for name, exists in
               [(".env", (ROOT / ".env").exists()),
                ("configs/secrets.yaml", SECRETS.exists()),
                ("환경변수", any(os.getenv(v) for v in
                               ("KMA_APIHUB_AUTH_KEY", "NAVER_API_HUB_CLIENT_ID")))]
               if exists]
    print(f"키 출처: {' + '.join(sources) or '없음'}")
    check_kma(get("kma_apihub", "auth_key"))
    check_naver(get("naver_api_hub", "client_id"), get("naver_api_hub", "client_secret"))
    check_datagokr(get("data_go_kr", "service_key"))
    print("\n※ [KMA-3] 이 FAIL 이면 데이터 수집 전에 설계를 먼저 조정해야 한다.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
