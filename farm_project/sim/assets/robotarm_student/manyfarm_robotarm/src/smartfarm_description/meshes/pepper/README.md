# 공통 파프리카 형상

기존 src/Pepper_RL_Demo/assets의 Pepper_Red.usdc와 Pepper_Yellow.usdc를 바이트 변경 없이 공통 자산 위치에 복사했다. manifest는 해당 두 형상의 기존 metadata만 포함한다. 형상 재모델링이나 수확 코드/캐시 재사용은 없다. HCR 기능 환경의 visual과 convex hull 생성 원본으로 사용한다. 기존 원본과 그 출처·라이선스 정보는 보존한다.

USD의 상대 텍스처 참조를 유지하기 위해 기존 assets/textures/fruit_* 파일도 같은 상대 경로에 바이트 변경 없이 복사했다. 이 파일이 없으면 GUI 렌더에서 과실이 회색으로 표시될 수 있다.
