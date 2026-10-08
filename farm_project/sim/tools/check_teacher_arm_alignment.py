"""독립 학습 환경과 농장 실행의 실제 PhysX readback을 이름 기준으로 대조한다."""
import argparse
import json
from pathlib import Path
import numpy as np


def compare(reference_path: Path, farm_directory: Path) -> dict:
    """허용 오차를 넘는 팔 물성 차이 또는 접촉 구성 차이를 실패로 반환한다."""
    reference = json.loads(reference_path.read_text())
    farm = json.loads((farm_directory/'arm_physx_readback.json').read_text())
    contract = json.loads((farm_directory/'runtime_contract.json').read_text())
    checks = {}
    def close(name: str, actual: object, expected: object, atol: float = 1e-7) -> None:
        a, b = np.asarray(actual, float), np.asarray(expected, float)
        checks[name] = dict(pass_check=bool(a.shape == b.shape and np.allclose(a,b,atol=atol,rtol=1e-6)),
                           actual=a.tolist(), expected=b.tolist())
    for i, name in enumerate(reference['body_names']):
        if not name.startswith('arm_2_'):
            continue
        j = farm['body_names'].index(name)
        for key in ('masses','inertias'):
            close(name+'/'+key, farm[key][0][j], reference[key][0][i])
        close(name+'/com_position', farm['coms'][0][0][j], reference['coms'][0][i][:3])
        q = np.array(farm['coms'][1][0][j])[[1,2,3,0]]
        expected = np.array(reference['coms'][0][i][3:])
        if q @ expected < 0:
            q = -q
        close(name+'/com_orientation_xyzw', q, expected)
    for i, name in enumerate(reference['joint_names']):
        if not name.startswith('arm_2_'):
            continue
        j = farm['joint_names'].index(name)
        close(name+'/limits', farm['dof_limits'][0][j], reference['dof_limits'][0][i])
        for key in ('stiffness','damping'):
            close(name+'/'+key, np.asarray(farm[key]).reshape(-1)[j], reference[key][0][i])
        close(name+'/effort', np.asarray(farm['effort_limits']).reshape(-1)[j], .5 if name=='arm_2_gripper' else 2.)
        close(name+'/velocity', np.asarray(farm['velocity_limits']).reshape(-1)[j], 1.5 if name=='arm_2_gripper' else 1.2)
    ref_scene = next(r for r in reference['usd'] if r['type']=='PhysicsScene')['resolved_usd_attributes']
    farm_scene = contract['physics_scene_usd'][0]['resolved_usd_attributes']
    # 쿼리는 농장 lidar가 사용하며, collision group filter는 IsaacLab env 복제 구조 차이다.
    excluded = {'physxScene:enableSceneQuerySupport','physxScene:invertCollisionGroupFilter'}
    for key, expected in ref_scene.items():
        if key not in excluded:
            if key == 'physxScene:gpuFoundLostPairsCapacity':
                # 농장 요구량 4,048,988개 때문에 학습 장면보다 메모리 버퍼만 늘린다.
                expected = 4194304
            actual = farm_scene.get(key)
            checks['scene/'+key] = dict(pass_check=actual==expected,actual=actual,expected=expected)
    articulation = next(r for r in contract['robot_usd']
                        if any('ArticulationRoot' in s for s in r['applied_schemas']))
    for key, expected in [('enabledSelfCollisions',True),('solverPositionIterationCount',12),
                          ('solverVelocityIterationCount',4)]:
        actual = articulation['resolved_usd_attributes']['physxArticulation:'+key]
        checks['articulation/'+key] = dict(pass_check=actual==expected,actual=actual,expected=expected)
    expected_contacts = ['arm_2_shoulder_link','arm_2_upper_arm_link','arm_2_lower_arm_link','arm_2_wrist_link']
    actual_contacts = [p.rsplit('/',1)[-1] for p in contract['arm_contact_paths']]
    checks['contact_sensor_links'] = dict(pass_check=sorted(actual_contacts)==sorted(expected_contacts),
                                         actual=actual_contacts,expected=expected_contacts)
    source_colliders = [r for r in reference['usd'] if '/collisions/' in r['path'] and
                        any('CollisionAPI'==s or s=='PhysicsCollisionAPI' for s in r['applied_schemas'])]
    for row in source_colliders:
        suffix = row['path'].split('/Robot/',1)[1].replace('/collisions/','/TeacherCollisions/')
        actual = next(r for r in contract['robot_usd'] if r['path'].endswith('/'+suffix))
        for key in ('mesh_local_bounds_m','mesh_vertex_count','material_resolved_attributes'):
            if key in row:
                expected = row[key]
                value = actual.get(key)
                checks[suffix+'/'+key] = dict(pass_check=value==expected,actual=value,expected=expected)
        expected = row['resolved_usd_attributes'].get('physics:approximation')
        value = actual['resolved_usd_attributes'].get('physics:approximation')
        checks[suffix+'/approximation'] = dict(pass_check=value==expected,actual=value,expected=expected)
    if len(source_colliders)!=15:
        raise ValueError('학습 팔 충돌체 15개를 찾지 못했습니다.')
    return dict(reference=str(reference_path),farm_directory=str(farm_directory),
        passed=all(c['pass_check'] for c in checks.values()),checks=checks,
        intentional_environment_differences=['농장 이동 차체 대 학습 고정 베이스',
            '농장 장애물/다른 과실/적재함 배치', '농장 lidar scene query 및 env collision group 구성',
            '농장 GPU found/lost 충돌쌍 버퍼 4,194,304개(학습 2,097,152개)',
            '농장 대기60Hz, 수확480Hz; 정책20Hz'])


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',required=True,type=Path)
    parser.add_argument('--farm-directory',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    report=compare(args.reference,args.farm_directory)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PASS' if report['passed'] else 'FAIL',len(report['checks']),
          [k for k,v in report['checks'].items() if not v['pass_check']])
    raise SystemExit(not report['passed'])
