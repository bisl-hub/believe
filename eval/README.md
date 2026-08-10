# believe Evaluations

believe를 평가하는 독립적인 eval 모음. 각 eval은 자체 폴더에 데이터·스크립트·결과를 가짐.

| eval | 설명 | 상태 |
|------|------|------|
| [pubmedqa/](pubmedqa/) | PubMedQA `pqa_labeled` yes/no 890개. question을 hypothesis+쿼리로 사용, top-K Support/Reject 다수결 정확도. | ✅ 완료 ([REPORT](pubmedqa/REPORT.md)) |
| [biomarker/](biomarker/) | OncoKB 스타일 바이오마커-약물 연관 1,398건. 큐레이션된 참 연관을 believe가 확인(SUPPORT)하는지. | 🚧 설계 중 ([DATA](biomarker/DATA.md)) |

## 공통 규약
- 각 eval 폴더: `data/`(입력), `runs/`(산출물), `*.py`(스크립트), `REPORT.md`/`DATA.md`.
- believe job 등록: v1 API (`X-Api-Key`), 프로젝트 `believe-eval-v1` (id 31).
- LLM: `openai/gpt-oss-120b` @ 143.248.74.105:11434/v1, retriever: `Qwen__Qwen3-Embedding-0.6B`.
