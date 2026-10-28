#!/usr/bin/env python3
"""Snapshot the HCR-only handoff, dependencies and evidence into a verified ZIP."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "outputs/sorting_station/hcr_sim"
EXCLUDED = {"__pycache__", ".pytest_cache", ".git", "build", "install", "log"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="HCR3A_SIM_TEAM_20261008")
    parser.add_argument("--isaac-python", default=os.environ.get("ISAAC_PYTHON", "/home/bhc/isaac/env_isaaclab/bin/python"))
    args = parser.parse_args()
    if Path(args.name).name != args.name or not args.name:
        parser.error("name must be one directory name")
    target = SIM / "delivery" / args.name
    if target.exists() or target.with_suffix(".zip").exists():
        parser.error("Delivery already exists; choose a new --name to preserve it")
    target.mkdir(parents=True)
    entries = {}

    def add(source, destination=None, category="source"):
        source = Path(source).resolve()
        if destination is None:
            destination = Path("workspace") / source.relative_to(ROOT)
        destination = Path(destination)
        if destination.is_absolute() or ".." in destination.parts:
            raise ValueError(destination)
        if source.is_dir():
            for child in sorted(source.rglob("*")):
                relative = child.relative_to(source)
                if child.is_file() and not any(part in EXCLUDED for part in relative.parts) and child.suffix not in (".pyc", ".pyo"):
                    add(child, destination / relative, category)
            return
        if not source.is_file():
            raise FileNotFoundError(source)
        out = target / destination
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, out)
        entries[destination.as_posix()] = dict(origin=str(source), category=category)

    def write(relative, value, category="delivery"):
        out = target / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(value, encoding="utf-8")
        entries[relative] = dict(origin="generated", category=category)

    # The validated recipe supplies all 98 original transport resources and
    # HCR runtime inputs; separate import helpers and ROS packages are explicit.
    validated = json.loads((SIM / "validation/random8_seed43_sort1/metadata.json").read_text())
    mismatches = []
    for relative, expected in validated["source_sha256"].items():
        if not relative.startswith(("src/sorting_station/", "src/smartfarm_description/")):
            raise ValueError("Unexpected runtime dependency: " + relative)
        p = ROOT / relative
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            mismatches.append(relative)
        add(p)
    if mismatches:
        raise ValueError("Validated HCR runtime inputs changed: " + str(mismatches))
    originals = json.loads((SIM / "validation/existing_transport_sources.json").read_text())["source_sha256"]
    for relative, expected in originals.items():
        p = ROOT / relative
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError("Original transport resource changed: " + relative)
        add(p)
    explicit = [
        "src/sorting_station/hcr_sim", "src/sorting_station/run_hcr_sim.sh",
        "src/sorting_station/sorting_sim/__init__.py", "src/sorting_station/sorting_sim/settings.py",
        "src/sorting_station/sorting_sim/assets.py", "src/sorting_station/hcr/zone_preview.py",
        "src/sorting_station/hcr_sorting", "src/smartfarm_interfaces",
        "src/smartfarm_description/config/hcr3a_station.json",
        "src/smartfarm_description/config/hcr3a_random8_validation.json",
        "src/smartfarm_description/urdf/hcr3a_functional.urdf",
        "src/smartfarm_description/scripts/fetch_hcr3a_cad.py",
        "docs/sorting/HCR3A_SIM_TEAM_HANDOFF_KR.md", "docs/sorting/HCR3A_SIM_TEAM_REQUEST_KR.md",
        "docs/INTERFACES.md", "scripts/package_hcr_sim_handoff.py", "scripts/verify_hcr_sim_delivery.py",
    ]
    for relative in explicit:
        add(ROOT / relative)
    add(ROOT / "scripts/verify_hcr_sim_delivery.py", "verify_delivery.py", "delivery")
    add(SIM / "validation/random8_seed43_sort1/zones.json", "workspace/outputs/sorting_station/hcr_sim/zones.json", "sample_roi")

    cases = ["random8_seed43_sort1", "random8_seed43_unload", "random8_seed43_sort2_error",
             "random8_seed42_spatial_only", "height75_manual", "existing_transport_ros"]
    for name in cases:
        add(SIM / "validation" / name, Path("reference/validation") / name, "evidence")
    evidence_files = ["random8_seed43_sort1.log", "random8_seed43.log", "random8_seed43_sort2.log",
                      "random8_seed42.log", "random_payload_unit.log", "existing_transport_sources.json"]
    for name in evidence_files:
        add(SIM / "validation" / name, Path("reference/validation") / name, "evidence")
    # Keep the original independent geometry audit and the exact derived hull
    # meshes as evidence; these meshes contain old absolute visual references
    # and are not used as the receiving PC's runtime cache.
    add(SIM / "validation/audit_random_payload.py", "reference/validation/audit_random_payload.py", "evidence")
    for p in (SIM / "assets/peppers").glob("*.usda"):
        add(p, Path("reference/validation/derived_peppers") / p.name, "evidence")
    for name in ("hcr3a.zip", "controller.zip", "manifest.json"):
        add(SIM / "source_cad" / name, Path("reference/source_cad") / name, "reference_cad")
    photo_labels = {
        "20261007_125554 (1).jpg": "투입 미끄럼틀과 과실",
        "20261007_125600 (1).jpg": "컨트롤러 위 보관부",
        "20261007_125556 (1).jpg": "협동로봇과 투입부 상대 배치",
        "20261007_125548 (1).jpg": "보관부–협동로봇–투입부 전체 배치",
        "20261007_125550 (1).jpg": "4레인 투입부",
        "20261007_125545 (1).jpg": "보관부 경사 통로",
        "Screenshot_20261007_135734_Samsung Notes.jpg": "설치판/컨트롤러 평면 치수 노트",
        "Screenshot_20261007_135726_Samsung Notes.jpg": "4레인 미끄럼틀 평면·측면 치수 노트",
        "Screenshot_20261007_135740_Samsung Notes.jpg": "세 부분 측면 배치 노트",
        "20261007_140441.jpg": "JRT 그리퍼 모델 라벨",
        "20261007_140422.jpg": "그리퍼 손가락과 고마찰 패드",
    }
    for name in photo_labels:
        add(Path("/home/bhc/Downloads") / name, Path("reference/photos") / name, "user_reference_photo")
    write("reference/photos/README.md", "# 사용자 제공 실물 사진·치수 노트\n\n" +
          "\n".join(f"- [{label}](<{name}>)" for name, label in photo_labels.items()) + "\n")

    # Preserve only the HCR sections from the large shared decision history.
    decisions = (ROOT / "docs/DECISIONS.md").read_text().split("\n## ")
    hcr = ["## " + section for section in decisions[1:] if "HCR" in section.splitlines()[0] or "75 mm 과실 8개" in section.splitlines()[0]]
    write("reference/HCR_DECISIONS.md", "# HCR 관련 결정 발췌\n\n" + "\n\n".join(hcr) + "\n", "reference")

    package_probe = """import importlib.metadata as m,json,sys
r={'python':sys.version.split()[0]}
for p in ('isaacsim','isaacsim-kernel','isaaclab','torch','numpy','scipy','opencv-python-headless','opencv-python'):
 try:r[p]=m.version(p)
 except m.PackageNotFoundError:r[p]=None
print(json.dumps(r))
"""
    environment = json.loads(subprocess.check_output([args.isaac_python, "-c", package_probe], text=True))
    environment["recorded_at"] = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    environment["physics_device"] = "cpu"
    environment["render_device"] = "NVIDIA GPU"
    environment["physics_dt_seconds"] = 1 / 240
    environment["gui"] = json.loads(subprocess.check_output(["/usr/bin/python3", "-c",
        "import cv2,sys,json;print(json.dumps({'python':sys.version.split()[0],'opencv':cv2.__version__,'backend':[s.strip() for s in cv2.getBuildInformation().splitlines() if 'GUI:' in s]}))"], text=True))
    environment["ros_distributions_present"] = [p.name for p in Path("/opt/ros").iterdir() if p.is_dir()]
    write("ENVIRONMENT.json", json.dumps(environment, indent=2, ensure_ascii=False) + "\n")
    git = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    write("SOURCE_SNAPSHOT.json", json.dumps(dict(
        git_head=git, archive_is_local_file_snapshot=True,
        git_head_alone_does_not_include_untracked_hcr_files=True,
        validated_runtime_inputs_count=len(validated["source_sha256"]),
        validated_runtime_inputs_changed=mismatches, original_transport_resource_count=len(originals),
        scope="HCR-3A simulation and dependencies; no harvest policy/cache or OMX runtime"), indent=2) + "\n")

    # Run the actual delivered imports/tests, not tests against the parent repo.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(target / "workspace/src/sorting_station")
    result = subprocess.run([args.isaac_python, "-m", "unittest", "discover", "-s",
        "src/sorting_station/hcr_sim/tests", "-v"], cwd=target / "workspace", env=env,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    write("DELIVERY_UNIT_TESTS.log", result.stdout, "verification")
    if result.returncode:
        raise RuntimeError("Delivered unit tests failed; see DELIVERY_UNIT_TESTS.log")
    profile = target / "workspace/src/smartfarm_description/config/hcr3a_random8_validation.json"
    if profile.read_bytes() != (SIM / "validation/random8_seed43_sort1/configuration.json").read_bytes():
        raise ValueError("Reproduction profile differs from validated configuration")

    write("README.md", """# HCR-3A 선별장 시뮬레이션팀 전달 묶음

2026-10-08 로컬 파일 스냅샷. HCR 선별장 대상이며 OMX/수확 RL 배포본이 아니다.

1. `python3 verify_delivery.py`로 전달 파일을 검사한다.
2. [팀 요청문](workspace/docs/sorting/HCR3A_SIM_TEAM_REQUEST_KR.md)을 읽는다.
3. [전달서](workspace/docs/sorting/HCR3A_SIM_TEAM_HANDOFF_KR.md)의 단독 재현 → 농장 통합 순서를 따른다.
4. `cd workspace`하고 본인 Isaac Lab Python 경로를 `ISAAC_PYTHON`에 설정한다.

```bash
export ISAAC_PYTHON=/본인/IsaacLab환경/bin/python
export HCR_GUI_PYTHON=/usr/bin/python3
bash src/sorting_station/run_hcr_sim.sh \\
  --config src/smartfarm_description/config/hcr3a_random8_validation.json \\
  --pepper-per-lane 2 --payload-layout random --payload-seed 43 \\
  --auto-start --stop-after-sorted 1
```

새 workspace에는 성공 시험의 수동 ROI가 포함된다. 기존 농장 ROI를 덮어쓰지 않는다.
위 설정에서 기존 기록은 8개 배출/1회 선별·복귀 DONE이며 전체 배치 완료는 아니다.
다른 카메라 및 연속 선별에서는 몸통을 포함하도록 수동 ROI를 다시 확인한다.

## 첨부 자료

- [실물 사진·치수 노트](reference/photos/README.md), [HCR 결정 발췌](reference/HCR_DECISIONS.md)
- [최신 성공 검증](reference/validation/random8_seed43_sort1/report.json), [독립 감사](reference/validation/random8_seed43_unload/audit.json)
- [두 번째 영상 오판 실패](reference/validation/random8_seed43_sort2_error/report.json)
- [전체 검증 기록](workspace/src/sorting_station/hcr_sim/VALIDATION.md)
- ENVIRONMENT.json: 전달 시점 환경 실측값. SOURCE_SNAPSHOT.json: 소스 기준과 Git 스냅샷 범위.
- MANIFEST.json: 경로/크기/SHA256/출처. DELIVERY_UNIT_TESTS.log: 복사한 workspace의 회귀 검사.
- reference/source_cad: 기존 제조사 STEP ZIP과 출처 URL/해시. 동작 로봇의 URDF가 아니다.

![중력으로 불규칙하게 적재된 과실](reference/validation/random8_seed43_sort1/transport_approach.png)

![8개 투입 후 선별장](reference/validation/random8_seed43_sort1/transport_ready.png)

## 전달 기준

원본 운반 자산과 현재 HCR 런타임을 그대로 복사했다. USD 변환 캐시는 수신 PC에서 재생성한다.
`reference/validation/derived_peppers`는 과거 감사의 충돌점 참고 파일이며, 절대 visual 참조를 포함할 수 있어 실행 캐시로 쓰지 않는다.
옛 audit_random_payload.py는 원래 outputs 디렉터리 구조를 전제로 한 기록용 스크립트다. 수신본의 검사 진입점은 verify_delivery.py다.
경로/좌표 변환·농장 공통 실행 루프 어댑터는 통합 작업으로 남아 있다.
보조 고정 파지/지정 차량 경로의 기능 모델이며 실물 동역학이나 여러 seed의 일반 성능 보증이 아니다.
""")
    write("INVENTORY.md", "# 전달 파일 목록\n\n| 분류 | 파일 | bytes |\n|---|---|---:|\n" +
          "\n".join(f"| {info['category']} | `{name}` | {(target/name).stat().st_size} |" for name, info in sorted(entries.items())) + "\n")
    manifest = dict(schema=1, created_at=environment["recorded_at"], scope="HCR-3A simulation handoff", files=[])
    for relative, info in sorted(entries.items()):
        p = target / relative
        manifest["files"].append(dict(path=relative, bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(), **info))
    (target / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    subprocess.run([sys.executable, str(target / "verify_delivery.py")], check=True)
    archive = target.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for relative in [*sorted(entries), "MANIFEST.json"]:
            z.write(target / relative, target.name + "/" + relative)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("ZIP integrity failure")
        for entry in manifest["files"]:
            if hashlib.sha256(z.read(target.name + "/" + entry["path"])).hexdigest() != entry["sha256"]:
                raise RuntimeError("ZIP entry mismatch: " + entry["path"])
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n")
    print(json.dumps(dict(archive=str(archive), files=len(entries), bytes=archive.stat().st_size,
        sha256=digest, unit_tests_passed=True, validated_runtime_sources_unchanged=True), indent=2))


if __name__ == "__main__":
    main()
