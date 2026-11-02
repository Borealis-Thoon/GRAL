# 배포 묶음 코드 검토

검토 상태: 수정 필요. 읽기 전용 코드 검토이며 패키징 스크립트 실행·모델 실행·출력 변경은 수행하지 않았다.

[HIGH] 검토 확인서가 분석 결과에 결속되지 않음
- 파일: publication/package_evidence.py:70
- 상태가 pass인 다른 분석의 확인서도 허용한다. 확인서에 실제 analysis_summary, artifact_sha256, study receipt 해시를 넣고 현재 파일과 대조한다.

[HIGH] 분석 결과와 실행 원본의 해시 연계 누락
- 파일: publication/package_evidence.py:66, 111, 142
- 분석의 artifact_sha256 목록과 파일 해시를 검사하지 않고 GRZ는 개수만 확인한다. 결과 JSON도 최종 실행 receipt의 동일 run 결과와 대조하지 않는다. 분석에 사용한 run별 GRZ·결과 해시를 저장하고 패키징 시 대조하며 00001..N의 정확한 시간 파일 집합을 검사한다.

[HIGH] 허용 목록이 아닌 qa·docs 폴더 전체 수집
- 파일: publication/package_evidence.py:103, 109
- 해당 확장자의 추가 로컬 문서·합성 시험 기록이나 민감 파일도 포함될 수 있다. 목적에 필요한 파일의 명시적 목록과 경로별 허용 검사를 사용한다.

[MEDIUM] 목적지 상위 링크 및 복사 중 변경
- 파일: publication/package_evidence.py:154
- 목적지 상위 경로의 해석 결과가 허용된 작업 폴더인지 확인하고, 원본은 복사 전·후 해시 및 복사본 해시를 비교한다. 상위 경로 junction과 링크도 검사한다.

확인한 점: 새 목적지만 생성하고, 입력 해시와 실행 수·순서·통과 상태 및 source HEAD를 검사한다. 원본 manifest를 보존하고 별도 사본에서 runs[].path만 갱신한다. 제외 확장자와 cache 경로 검사가 있으며 observer 원본 해시는 overlay 기록과 대조한다. 실행 전 스크립트 수정과 최종 근거 확인이 필요하다.

## 보강본 정적 재검토

이전에 지적한 검토 확인서 해시 결속, 분석 산출물 목록 대조, 원본 실행·GRZ 입력 스냅샷 확인, 정확한 시간별 GRZ 집합, QA·문서 허용 목록, 경로 링크 검사, 복사 전후 해시 검사가 코드에 반영되었다. 현재 추가 차단 사항은 발견하지 못했다. 진행 중인 코호트에 영향을 주지 않도록 패키징·시험은 실행하지 않았다.

필수 확인서: `status`, `source_head`, `study_manifest_sha256`, `study_results_sha256`, `analysis_summary_sha256`, `artifact_manifest_sha256`, `analysis_inputs_manifest_sha256`, `claims`, `scope`, `analysis_inputs_manifest_before_after_equal`, `formal_equivalence_not_tested`, `inference_inconclusive`, `analysis_source_sha256`. 세 boolean 항목은 true여야 하며 분석 전후 입력 목록의 실제 일치 확인이 선행되어야 한다. 배포 후 manifest·해시와 별도 portable analysis 재실행은 미검증 상태다.
