# Python validation review

상태: 진행 중. 주 코호트 실행 승인 아님.

- 범위: `validation`의 합성 입력·출력 비교·실행 제어·관측기와 `analysis`의 수치 계산. 실제 모델, GPU 동작, 물리적 타당성은 본 검토에서 실행하거나 확인하지 않음.
- 검토 기준: Ponytail review 및 ECC code review. 범위 밖 작업 트리 변경은 판단하지 않음.
- 초기 HIGH 발견 3건: 동일 누락 source group 및 receptor 검출 실패, NaN 배출량 장부 통과, GPU 모니터 오류 미전파. 수정 소스에서 각각 기대 집합 검사, finite 검사, 오류 전파를 확인. 최종 통합 및 회귀 재확인 필요.
- 분석의 0/0 분산비는 원래 0으로 표시되었으며 `uninformative_zero`와 null로 수정 중. 전체 요약과 부트스트랩까지 최종 확인 필요.
- 관측기 상황별 시각은 seed 기록부터 상황 종료 이벤트까지이며 비동기 출력 drain 이전이다. 상황 간 준비시간과 최종 drain이 빠지므로 전체 상황 벽시계 시간으로 해석하지 않는다. warmup 종료와 최종 종료 경계는 별도로 drain 후 기록한다.
- 필수 미검증: production candidate와 overlay offset 0의 실제 수치 일치, 여섯 offset의 실제 seed 차이 및 CPU/GPU 쌍 일치, 마지막 시간 계수 패딩의 실제 엔진 적용, GPU receptor 사례, 모든 완료/텔레메트리/분석 진입 게이트.
- 독립 단위시험: 분석 7개 통과, 검증 하네스 12개 통과. 해당 시점 코드 기준이며 모델 실행 증거가 아니다. Ruff, mypy, pylint, black 명령은 PATH에서 확인되지 않았다.

추가 검토(통합 분석):
- HIGH: `analysis/analyze_study.py`의 timing_summary는 현재 warmup 이후 경계 사이의 벽시계 시간을 보고하지 않는다. 상황별 seed→end 합계는 준비 간격과 출력 drain을 제외한다. observer boundary를 사용해 별도 집계해야 한다.
- HIGH: 분석 진입 시 GPU 관측값, 각 상황 메모리 표본, observer 완료 및 boundary가 없어도 통과할 수 있다. 필수 증거 누락은 INVALID여야 한다.
- HIGH: `validation/compare.py` CLI는 기대 source group과 receptor를 요구하지 않아 양쪽의 동일 누락을 놓칠 수 있다. 실행 내부의 완료 검사는 기대 집합을 전달한다.
- Bootstrap 분모 0은 양의 분자와 0/0을 구분해야 한다. 수정을 담당자에게 요청했다.
- `fixtures.py`에서 4시간 측정 시 5번째 입력 행과 `area_receptor1` GPU 설정을 확인했다. 엔진이 이를 실제로 사용하는지는 아직 미검증이다.

최신 재확인:
- `compare.py` CLI는 기준 입력 manifest의 source group·deposition·receptor 기대값을 사용한다. 관련 동일 누락 음성 시험과 GPU 질의 실패 시험이 추가되었다. 하네스 단위시험 15개 독립 통과.
- 분석기는 observer boundary 시간, 완료 이벤트, 각 상황의 메모리 표본, GPU 텔레메트리, 실제 상수 기상·배출 행과 마지막 추가 행을 검사하도록 수정되었다. 양의 분자/0과 0/0 bootstrap 결과도 분리되었다. 최신 코드의 최종 분석 회귀시험은 진행 중이다.
- 새 observer v2는 stop 확인 후 상황 시작 이벤트를 추가한다. 상황별 값은 시작 이벤트부터 출력 drain 전 종료 이벤트까지이며, warmup 뒤 전체 경계 시간은 별도 기록한다. 이전 observer 자료와 혼합하지 않는다.
- `functional_matrix.py`의 review_required 상태도 종료코드 0을 반환하므로 호출자는 summary 상태를 검사해야 한다. 종료코드 수정 요청을 전달했다.
- 미검증 항목: 실제 offset 0 observer/bare CPU 결과 일치, 6개 seed의 실제 쌍 비교·차이, padding과 GPU receptor의 실제 실행, 22회 본시험 및 결과 분석. 이 기록은 검증 보류 상태다.

최종 코드 재확인: `functional_matrix.py`는 pass=0, review_required=2, fail=1로 종료하도록 수정되었다. 분석 단위시험 11개를 별도 임시 경로에서 독립 실행해 통과했다. 실제 모델 결과 및 새 observer의 offset 0 일치 검증은 별도 실행 증거가 필요하다.

추가 HIGH: 실제 GRZ sparse `-1` 좌표는 셀 인덱스가 아니라 물리적 셀 중심이다. 기존 분석기는 범위 검사에서 안전하게 거부했으나, 대조기의 dense/sparse 혼합 정렬은 같은 좌표계를 사용하지 않았다. `Write2DConcentrations.cs`의 origin과 spacing에 따라 수정 중이며 실제 GRZ와 인코딩 혼합 회귀시험 전까지 분석 결과를 승인할 수 없다.

좌표 수정 재검토: `compare.py`는 dense와 sparse를 물리 셀 중심 좌표로 통일하고, `analyze_study.py`는 두 형식에 동일한 격자 인덱스 변환을 적용한다. dense 원점·간격·크기도 확인한다. 수정 후 하네스 17개, 분석 13개 단위시험을 독립 실행해 통과했다. 실제 4시간 CPU/GPU 출력의 24개 그룹·시간 필드 복원 합계 검사 기록은 `analysis/actual_grz_parser_integration.json`에 있다. 독립 물리 검증이나 본 코호트 분석은 아니다.

2026-11-02 본시험 직전 추가 검토: `run_study.py`는 사전 22회 순서, 각 쌍의 입력 해시, 전체 16개 기능 사례와 bare CPU 대조, 288개 실제 생성자 시드 probe, 실행 중 매 시간의 seed 공식·CPU/GPU 일치, GPU cache hit, JSON/MD 프로토콜 및 소스·바이너리 해시를 확인하도록 보강되었다. 실패 시 결과를 별도 기록하고 자동 재시도하지 않는다. `functional_matrix.py`는 실패와 검토 필요를 0이 아닌 종료코드로 구분한다. 최신 하네스 단위시험 19개 독립 통과. 기존 `qa/harness_study_preflight.json`은 MD 해시 항목이 없는 이전 스크립트의 결과이므로 최종 스크립트 실행 전 고유 사전점검 기록 또는 실제 freeze 기록으로 양쪽 프로토콜 해시를 확인해야 한다. 본 검토에서 모델 실행은 하지 않았다.
