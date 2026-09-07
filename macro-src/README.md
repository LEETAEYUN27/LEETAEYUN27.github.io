# 글로벌 경제 관제실 — 소스

배포본: `/macro/index.html` (https://leetaeyun27.github.io/macro/)
이 폴더는 그 페이지를 매일 다시 만드는 코드다. 페이지를 직접 고치지 말고 여기를 고친 뒤 워크플로를 돌린다.

| 파일 | 역할 |
|---|---|
| `collect.py` | 시세(Yahoo chart API) · 거시(NY연준·시카고연준·BLS·multpl·Zillow) · 기관 13F(SEC EDGAR) |
| `collect_kr.py` | 한국부동산원 R-ONE 주간 아파트 매매·전세 지수. 키는 `RONE_KEY` 시크릿에서만 읽는다 |
| `build_extra.py` | 연방기금 선물 내재금리 → 금리 확률, FOMC 일정, 시나리오 |
| `build_ci.py` | 위 결과를 조립해 `template.html`에 주입 → `/macro/index.html` 생성 |
| `template.html` | 페이지 뼈대 + CSS + JS (`/*__DATA__*/` 자리에 데이터가 들어간다) |
| `raw/` | 수집 원본 JSON (워크플로가 커밋한다) |

## 자동 갱신
`.github/workflows/macro-console.yml` — 평일 07:20 KST. 수동 실행은 Actions 탭 → macro-console → Run workflow.
개별 수집이 실패해도 워크플로는 계속 진행되며, 실패한 항목은 직전 `raw/` 데이터를 그대로 쓴다.

## 필요한 시크릿
`RONE_KEY` — 한국부동산원 R-ONE Open API 인증키. 없으면 한국 부동산 섹션만 빠지고 나머지는 정상 생성된다.
