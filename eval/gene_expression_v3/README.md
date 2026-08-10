# gene_expression_v3 — believe는 context-aware한가

## 프로젝트 메시지
believe는 단순 문헌 검색기가 아니라 **context-aware 추론 시스템**임을 보인다:
맥락(조직)을 바꾸면 결론이 **올바르게** 바뀌고, 그 변화 폭이 실제 생물학적 맥락 의존도에 비례한다.

### 핵심 증거 (`figures/context_aware.png`)
1. **Context-modulation**: believe의 조직 간 답 변동 vs 실제 발현의 조직 간 변동 — Spearman 0.48. housekeeping(맥락 무관)은 believe도 안 변하고, tissue-specific은 believe도 변함.
2. **Counterfactual (결정적)**: 같은 유전자에서 정답 조직 vs 틀린 조직 believe 신호 — 중앙값 **7.6배**(정답 6.0 vs 틀림 0.79), 48/60, **Wilcoxon p=2.7e-8**. 유전자 인기에 무관(같은 유전자 내 비교)하게 believe가 정답 맥락에 신호를 몰아줌.
3. 단일 유전자 예시 (`figures/examples.png`): INS→췌장, NPPA→심장, MYH2→근육 등 정답 조직을 believe가 1등으로.

이 context-awareness는 3개 독립 축에서 일관: **조직**(여기) · **변이**(biomarker ablation) · **방향**(biomarker resistance flip).

## (보조 목표) housekeeping vs tissue-specific 구분
believe가 어떤 유전자가 **맥락에 따라 발현이 변하는지(tissue-specific)** vs **어디서나 안정적인지(housekeeping)** 구분 — AUC 0.806 (데이터 tau로 선정한 HK 60/TS 60).

## 핵심 아이디어 (스마트한 가설)
"유전자가 조직마다 변한다" 같은 **메타 진술**을 직접 묻지 않는다 (그런 논문이 거의 없음).
대신 실제 논문이 보고하는 형태 — **특정 context에서 up/down 변화를 보였다** — 로 묻고, 여러 context에 걸쳐 집계한다.

가설 (gene × context):
> `In {context}, {gene} expression is up- or down-regulated.`
- SUPPORT = 그 context에서 변화(↑/↓)를 보였다는 연구 있음
- REJECT  = 변화 없음/안정적이라 보고 (housekeeping 신호)
- NEUTRAL = 다룬 논문 없음

집계: `believe_sensitivity(gene)` = context 패널 전체 net-support = (#SUPPORT − #REJECT)/패널수.
- context-sensitive → 높음, housekeeping → 낮음(또는 음수).

## context 패널 (질병 ~15)
DE(차등발현) 문헌이 가장 풍부한 잘 연구된 질병. CELLxGENE에도 disease 메타데이터가 있어 데이터 비교 가능.

## gene set (~60, 라벨 보유)
- **housekeeping (~20)**: 확립된 reference 유전자 (ACTB, GAPDH, B2M …) → 기대 LOW
- **context-sensitive (~40)**: 잘 알려진 질병/맥락 조절 유전자 (IL6, TP53, GFAP, INS …) → 기대 HIGH
- group 태그(inflammation/cancer/neuro/metabolic/tissue-marker)로 세부 분석.

## 평가
1. **분류**: believe_sensitivity가 housekeeping(낮음) vs sensitive(높음)를 가르나 — boxplot, ROC-AUC.
2. **top-K 효과**: 집계 K별 분리도.
3. (선택, 후속) CELLxGENE에서 같은 질병 패널의 실제 발현 변동과 상관.

## 파이프라인
- `extract_groundtruth.py` : CELLxGENE 20개 조직 전체 셀 스트리밍 집계 → `data/gt_expr.csv`, `data/gt_tau.csv` (py3.11 `cxgene` conda env)
- `prepare.py`  : gene(60) × tissue(20) 가설 → `data/pairs.json` ("{gene} is highly expressed in human {tissue}")
- `submit.py`   : believe 제출 (qwen + LLM), 상태 `runs/jobs.json` (1,200 job)
- `analyze.py`  : believe 조직 프로파일 → peak/total support, 데이터 tau와 비교 + figure

## 최종 설계 (데이터 기반)
- gene: CELLxGENE tau로 **데이터 기반 선정** — housekeeping 30(tau 최저: 리보솜/번역 단백질) + tissue-specific 30(tau≈1: INS, SFTPC, MYH2, UMOD, 췌장효소·각질·모유단백 등). `rank_genes.py` → `data/selected_genes.json`
- 가설: `In human {tissue}, {gene} expression has been reported to be up- or down-regulated.` (변화/조절 보고 기반)
- ground truth: `data/gene_ranking.csv` (조직 tau, top_tissue)

## 결과 (120 유전자: HK 60 + TS 60, 2,400 job; 기존 60유전자 결과 재사용)
- **AUC(believe peak-support, HK vs TS) = 0.806** — 좋은 구분 (60유전자 땐 0.754 → 2배로 늘려 향상)
- HK median peak-support = 3 vs TS = 13 (`figures/v2_box.png`)
- Spearman(peak-support, tau) = +0.451 (p=2.3e-7)
- believe 최고조직 == 데이터 최고조직: 42% (25/60)
- 잘 분리되는 TS(16/30): INS(144), MYH2, SFTPA2, SYCN, UMOD, PGA3 등 — 유명+실제 조절받는 유전자
- 묻히는 TS(14/30): CELA3A/B, CTRB1/2, RALGPS2-AS1(lncRNA), casein 등 — **obscure paralog/구성적 마커**라 "up/down regulated" 문헌이 적음

### 핵심 방법론 발견 (가설 wording이 측정 대상을 바꿈)
- **"highly expressed in {tissue}"** (초기, 손라벨 famous genes): 조직 특이성(공간)과 강하게 일치 → ρ=0.625, HK 2 vs TS 57. (`figures/tau_*.png`, `runs/tau_compare.csv`)
- **"up/down regulated in {tissue}"** (최종, 데이터 genes): "조절/변화"를 물어서 **구성적 조직 마커엔 약함** → AUC 0.754.
- 즉 데이터 tau = "어디에 발현되나(공간)" vs 가설 = "조건 따라 변하나(조절)" — 살짝 다른 개념이라 상관이 약화. (spatial vs dynamic 구분이 결과로 드러남)
