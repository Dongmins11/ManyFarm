"""60Hz 전달본에서 scene 생성 없는 추론 계산만 재현 가능하게 가져온다.

정책/단계 메서드는 원문을 보존한다. scene/reset/reward는 농장 실행에 포함하지
않으며 초기 측정·구동기 출력 연결은 TeacherState가 담당한다.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import textwrap

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT/'sim/ros_ws/src/farm_sim_devices/farm_sim_devices/_teacher_vendor'
METHODS = {'__init__', '_pre_physics_step', '_update_task', '_get_observations',
           '_get_dones', '_target_elapsed_steps', '_transport_observations', '_write_gain',
           '_potential', '_grasp_center', '_grasp_orientation', '_native_recovery_enabled', 'proprio'}


def build(bundle: Path) -> None:
    source = bundle/'src/harvest_robot/harvest_rl'
    requested: dict[str, set[str]] = {}
    generated: dict[str, str] = {}
    audit = []

    def export(module: str, names: set[str]) -> None:
        previous = requested.setdefault(module, set())
        if names <= previous:
            return
        previous.update(names)
        path = source/(module+'.py')
        content = path.read_text()
        tree = ast.parse(content)
        nodes = []
        imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        for n in tree.body:
            if isinstance(n, ast.ClassDef) and (module.endswith('_env') or module == 'env'):
                if n.name == 'HarvestEnvCfg':
                    continue
                n.body = [m for m in n.body if isinstance(m, ast.FunctionDef) and m.name in METHODS]
                if module == 'env':
                    n.bases = []
                    n.body = [m for m in n.body if m.name != '__init__']
                    n.body.insert(0, ast.parse('def __init__(self, *args, **kwargs):\n    self._initialize_sample(*args, **kwargs)').body[0])
                if module == 'teacher_domain_env':
                    n.body = [m for m in n.body if m.name != '__init__']
                    n.body.insert(0, ast.parse('def __init__(self, *args, domain, **kwargs):\n    self.domain = domain\n    self.domain_ready = True\n    super().__init__(*args, **kwargs)').body[0])
                if module == 'teacher_contact_margin_env':
                    n.body = [ast.Pass()]
                if module == 'teacher_pressure_compare_env':
                    # 전달 선택은 goal_N=0: 원본 pressure_step도 즉시 identity를 반환한다.
                    # 학습 reward 전용 접촉점 진단을 운용 센서로 위장하지 않는다.
                    n.body = [m for m in n.body if m.name != '_pre_physics_step']
                    n.body.append(ast.parse('def _pre_physics_step(self, proposed):\n    if self.pressure_spec.goal_N != 0:\n        raise ValueError("배포에서 제외한 추가 압력 제어입니다.")\n    super()._pre_physics_step(proposed)').body[0])
                if not n.body:
                    n.body = [ast.Pass()]
            nodes.append(n)
        # scene 의존성이 없는 참조 심볼만 재귀적으로 가져온다.
        selected = []
        needed = set(previous)
        while True:
            old = len(needed)
            selected = []
            for n in nodes:
                defined = ({n.name} if isinstance(n, (ast.ClassDef, ast.FunctionDef)) else
                           {v.id for v in ast.walk(n) if isinstance(v, ast.Name) and isinstance(v.ctx, ast.Store)}
                           if isinstance(n, (ast.Assign, ast.AnnAssign)) else set())
                if defined & needed:
                    selected.append(n)
                    needed.update(v.id for v in ast.walk(n) if isinstance(v, ast.Name) and isinstance(v.ctx, ast.Load))
            if len(needed) == old:
                break
        lines = ['"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""']
        for n in imports:
            aliases = [a for a in n.names if (a.asname or a.name.split('.')[0]) in needed]
            if not aliases:
                continue
            if isinstance(n, ast.ImportFrom):
                if n.module == 'isaaclab.utils.math':
                    n = ast.ImportFrom(module='quaternion', names=aliases, level=1)
                else:
                    n.names = aliases
                    if n.level:
                        export(n.module, {a.name for a in aliases})
            else:
                n.names = aliases
            lines.append(ast.unparse(n))
        for n in selected:
            if isinstance(n, ast.ClassDef) and (module.endswith('_env') or module == 'env'):
                bases = '('+', '.join(ast.unparse(b) for b in n.bases)+')' if n.bases else ''
                lines.append('\nclass '+n.name+bases+':')
                for method in n.body:
                    if isinstance(method, ast.Pass):
                        lines.append('    pass')
                        continue
                    original = next((c for c in ast.parse(content).body if isinstance(c, ast.ClassDef) and c.name == n.name), None)
                    original_method = next((m for m in original.body if isinstance(m, ast.FunctionDef) and m.name == method.name), None)
                    same = original_method is not None and ast.dump(method) == ast.dump(original_method)
                    code = textwrap.dedent('\n'.join(content.splitlines()[original_method.lineno-1:original_method.end_lineno])) if same else ast.unparse(method)
                    if module == 'teacher_bridge_pull_risk_env' and method.name == '__init__':
                        code = code.replace("CACHE/'harvest_training.urdf'", 'self.kinematics_path')
                        same = False
                    lines.append(textwrap.indent(code, '    '))
                    audit.append(dict(module=module, method=n.name+'.'+method.name, original_body=same))
            else:
                if isinstance(n, (ast.ClassDef, ast.FunctionDef)):
                    lines.extend('@'+ast.unparse(d) for d in n.decorator_list)
                lines.append(ast.get_source_segment(content, n))
        result = '\n\n'.join(lines)+'\n'
        # 함수 내부의 상대 import도 동일한 심볼 단위로 가져온다.
        for n in ast.walk(ast.parse(result)):
            if isinstance(n, ast.ImportFrom) and n.level and n.module != 'quaternion':
                export(n.module, {a.name for a in n.names})
        generated[module] = result

    export('teacher_friction_progress_env', {'TeacherFrictionProgressEnv'})
    export('attachment_60hz', {'coupled_wrench'})
    export('settings', {'TaskSettings', 'JOINTS', 'CACHE', 'URDF'})
    export('logic', {'captured_break_candidate', 'mesh_settled_in_box', 'valid_pull', 'bilateral_contact', 'qualified_grasp'})
    export('friction_followup', {'FollowupSpec'})
    export('pressure_compare', {'PressureSpec'})
    export('bridge_pull_risk', {'RiskPullSpec'})
    # response6는 원본 전달본의 명시적 validate wrapper와 같은 제약으로 한정한다.
    generated['settings'] = generated['settings'].replace('ROOT = Path(__file__).resolve().parents[3]', 'ROOT = Path(__file__).resolve().parent')
    generated['settings'] = generated['settings'].replace('self.stem_response_version not in (1, 2, 3, 4, 5)', 'self.stem_response_version != 6')
    generated['settings'] = generated['settings'].replace('def validate(self):', '''def validate(self):
        if (self.attachment_version != 4 or self.contact_substeps != 1
                or abs(self.physics_dt-1/60)>1e-12 or self.decimation != 3):
            raise ValueError('60Hz / 20Hz / response6만 지원합니다.')''')
    DEST.mkdir(parents=True, exist_ok=True)
    for name, content in generated.items():
        (DEST/(name+'.py')).write_text(content)
    for name in ('kernel.py', 'staged_teacher.py'):
        (DEST/name).unlink(missing_ok=True)
    assets = ROOT/'sim/assets/robotarm_teacher'
    for folder in ('entry', 'pull', 'transport', 'place'):
        if (assets/folder).exists():
            shutil.rmtree(assets/folder)
    shutil.copytree(bundle/'handoff/actors', assets/'actors', dirs_exist_ok=True)
    shutil.copy2(bundle/'handoff/DEPLOYMENT.json', assets/'DEPLOYMENT.json')
    shutil.copy2(bundle/'outputs/harvest_rl/assets/harvest_training.urdf', assets/'harvest_training.urdf')
    (DEST/'PROVENANCE.json').write_text(json.dumps(dict(delivery='harvest_teacher_60hz_20261013_r2',
        source_files={name+'.py': hashlib.sha256((source/(name+'.py')).read_bytes()).hexdigest() for name in generated},
        methods=audit, note='scene/reset/reward 제외; 초기화는 농장 측정값. 정책 단계 계산 원문 보존.'), indent=2)+'\n')
    print('Imported', len(generated), 'calculation modules')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    build(parser.parse_args().bundle)
