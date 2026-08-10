# Biomarker 데이터 파악

`data/all_biomarker_flat.csv` — OncoKB 스타일의 큐레이션된 바이오마커↔약물/진단/예후 연관 테이블. 각 행은 근거 논문(PMID)을 가진 **확립된 참 연관**.

## 규모
- **1,398 행**, 7 컬럼: `setting, gene, alteration, cancer_type, drug, level, pmids`
- PMID: 근거 있는 행 1,356 / 빈 행 42. 총 참조 3,203건, **고유 PMID 1,198개** (행당 평균 2.3, 중앙값 2, 최대 12)

## 컬럼
| 컬럼 | 설명 | 분포 |
|------|------|------|
| setting | Somatic / Germline | Somatic 1,317 · Germline 81 |
| gene | 유전자 (177종) | ABL1 130, EGFR 100, ERBB2 66, BRAF 63, KRAS 58 … |
| alteration | 변이 (286종) | Oncogenic Mutations 363, Fusions 103, Pathogenic Variants 78, Amplification 71 … |
| cancer_type | 암종 (143종) | NSCLC 202, AML 78, All Solid Tumors 76, Breast 75 … |
| drug | 약물 (188종, +빈값 276) | Imatinib 58, Olaparib 49, Trametinib 39 … |
| level | 근거 수준 (아래) | |
| pmids | 근거 PMID (`\|` 구분) | |

## level 의미 (핵심 — hypothesis 틀이 달라짐)
| 카테고리 | level | 행수 | 약물 | 의미 |
|----------|-------|------|------|------|
| **치료(민감)** | 1, 2, 3A, 4 | 959 | 있음 | 변이가 해당 암종에서 **약물 반응(민감성)**을 예측 |
| **내성** | R1, R2 | 163 | 있음 | 변이가 **약물 내성**을 유발 |
| **진단** | Dx1, Dx2, Dx3 | 212 | 없음 | 변이가 해당 질환의 **진단** 바이오마커 |
| **예후** | Px1, Px2, Px3 | 64 | 없음 | 변이가 **예후** 바이오마커 |

- 치료+내성(1,122건)은 drug가 있어 "약물 반응/내성" hypothesis로 변환 가능
- 진단/예후(276건)는 drug 없음 → hypothesis 틀이 다름
- **약물 + PMID 둘 다 있는 행: 1,082건** (가장 깔끔하게 eval 가능한 후보)

## eval 설계 후보 (결정 필요)
이 데이터는 PubMedQA와 달리 **yes/no 정답이 없고 전부 "참" 연관**이라, 평가 축이 다름:

1. **Retriever recall**: 각 연관의 근거 PMID가 believe retriever top-K에 들어오나? (PubMedQA의 reference recall과 동일 방식)
2. **LLM 판정 정밀도**: 그 근거 PMID들에 대해 LLM이 SUPPORT를 주나? (참 연관이므로 SUPPORT가 기대값)
3. **집계 판정**: 연관을 hypothesis로 만들어 top-K 다수결 시 SUPPORT가 우세한가?

→ hypothesis 템플릿(치료/내성/진단/예후별), 포함할 level 범위를 정하면 그에 맞춰 파이프라인을 구성.
