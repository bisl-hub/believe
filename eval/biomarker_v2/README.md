# biomarker_v2

OncoKB 바이오마커 eval의 두 번째 버전. v1과의 차이:

- **3축 분류**: `drug` + `biomarker(gene+mutation 묶음)` + `cancer type`
- **gene와 mutation을 분리하지 않음** — biomarker = `"{gene} {alteration}"` 단일 단위로 취급
- 대상: drug 있는 행(치료+내성) 1,122 삼중쌍 (진단/예후 제외)

## 데이터
- `data/all_biomarker_flat.csv` — 원본 (v1과 동일)
- `data/triples.json` — `prepare.py` 산출. 필드: triple_id, drug, biomarker, gene, alteration, cancer_type, level, category, expected, pmids

## 분포 (distribution.py)
| 축 | 고유 수 |
|---|---|
| biomarker (gene+mutation) | 334 |
| drug | 188 |
| cancer type | 87 |
| 삼중쌍 | 1,122 (중복 0) |

- biomarker 334개 중 141개(42%)는 1회만 등장 (long tail), 최다 ERBB2 Amplification(34)
- `figures/distributions.png`

## 스크립트
- `prepare.py` — csv → triples.json
- `distribution.py` — 3축 분포 figure

(이후 평가 단계는 TBD)
