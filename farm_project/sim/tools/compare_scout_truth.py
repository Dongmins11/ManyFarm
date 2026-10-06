#!/usr/bin/env python3
"""TEMP offline coverage/identity/window check. Ground truth never feeds the robot."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/scout_robot'))
from scout_robot.survey_core import StraightBed,transform_points
from scout_robot.route import load_route


def maximum_matching(candidates):
    # Maximum-cardinality bipartite matching; nearest candidates tried first.
    owner={}
    def visit(i,seen):
        for _,j in candidates[i]:
            if j in seen:continue
            seen.add(j)
            if j not in owner or visit(owner[j],seen):owner[j]=i;return True
        return False
    for i in sorted(range(len(candidates)),key=lambda i:len(candidates[i])):visit(i,set())
    return {i:j for j,i in owner.items()}


def compare(report,truth,root,tolerance):
    results={};T=np.array(report['config']['evaluation']['T_map_world'],float)
    if T.shape!=(4,4) or not np.allclose(T[3],[0,0,0,1]) or not np.isfinite(T).all():raise ValueError('Invalid world->map matrix')
    if not np.allclose(T[:3,:3].T@T[:3,:3],np.eye(3),atol=1e-6):raise ValueError('world->map must be rigid')
    for section,record in report['sections'].items():
        cfg=report['config']['sections'][section]
        bed=StraightBed(load_route(root/cfg['route_file'],cfg['node_ids']),cfg)
        range_tolerance=bed.plan_cfg.range_tolerance
        height_min=bed.plan_cfg.mount_z+bed.plan_cfg.z_min-range_tolerance
        height_max=bed.plan_cfg.mount_z+bed.plan_cfg.z_max+range_tolerance
        targets=[];excluded=[]
        for fruit in truth['fruits']:
            if fruit['bed_prim']!=cfg['evaluation_bed_prim']:continue
            q=transform_points(T,[fruit['center_world_m']])[0];s,n,z=bed.local(q)
            reason=None
            if fruit['class_name'] not in ('Red','Yellow'):reason='class_not_in_model'
            elif not 0<=s<=bed.length:reason='outside_route_extent'
            elif abs(n-bed.bed_n)>report['config']['association_band_half_depth_m']:reason='other_side_or_depth_band'
            elif not height_min<=z<=height_max:reason='outside_work_height'
            if reason:excluded.append({'gt_id':fruit['gt_id'],'reason':reason});continue
            targets.append(fruit)
        all_predictions=record['survey']['fruits']
        predictions=[];excluded_predictions=[]
        for f in all_predictions:
            s,n,z=bed.local(f['position_map_m'])
            if (0<=s<=bed.length and abs(n-bed.bed_n)<=report['config']['association_band_half_depth_m']
                and height_min<=z<=height_max):
                predictions.append(f)
            else:excluded_predictions.append(f['id'])
        inv=np.linalg.inv(T);candidates=[];errors={} 
        for i,fruit in enumerate(predictions):
            point=transform_points(inv,[fruit['position_map_m']])[0];options=[]
            for j,gt in enumerate(targets):
                lo,hi=np.array(gt['aabb_world_m']);delta=np.maximum(np.maximum(lo-point,point-hi),0)
                residual=float(np.linalg.norm(delta))
                # Geometry-only association allows a separate color confusion count.
                if residual<=tolerance:
                    center=float(np.linalg.norm(point-np.array(gt['center_world_m'])))
                    options.append((residual+center*1e-3,j));errors[i,j]=(residual,center)
            candidates.append(sorted(options))
        matching=maximum_matching(candidates);pairs=[]
        for i,j in matching.items():
            pairs.append({'fruit_id':predictions[i]['id'],'gt_id':targets[j]['gt_id'],
                'point_to_aabb_m':errors[i,j][0],'surface_to_bbox_center_m':errors[i,j][1],
                'class_correct':predictions[i]['class_name']==targets[j]['class_name']})
        duplicates=[predictions[i]['id'] for i in range(len(predictions)) if i not in matching and candidates[i]]
        misses=[gt['gt_id'] for j,gt in enumerate(targets) if j not in matching.values()]
        byid={p['fruit_id']:p['gt_id'] for p in pairs};window_checks=[];owners={}
        for w in record['survey']['windows']:
            gt_ids=[byid[x] for x in w['member_ids'] if x in byid]
            for gt in gt_ids:owners.setdefault(gt,[]).append(w['window_id'])
            window_checks.append({'window_id':w['window_id'],'expected_count':w['expected_count'],
                'matched_unique_gt_count':len(set(gt_ids)),'matched_gt_ids':gt_ids,
                'unmatched_member_ids':[x for x in w['member_ids'] if x not in byid]})
        hits=len(pairs)
        results[section]={'section_status':record['status'],'placed_target_count':len(targets),
            'work_range_tolerance_m':range_tolerance,'evaluation_height_limits_m':[height_min,height_max],
            'detected_id_count':len(all_predictions),'evaluated_id_count':len(predictions),
            'excluded_prediction_ids':excluded_predictions,'matched_count':hits,
            'precision_in_evaluation_scope':hits/len(predictions) if predictions else None,
            'placed_target_recall':hits/len(targets) if targets else None,
            'correct_color_count':sum(p['class_correct'] for p in pairs),'possible_duplicate_ids':duplicates,
            'unmatched_ids':[predictions[i]['id'] for i in range(len(predictions)) if i not in matching],
            'missed_gt_ids':misses,'matches':pairs,'excluded_gt':excluded,'window_checks':window_checks,
            'duplicate_window_gt_owners':{k:v for k,v in owners.items() if len(v)>1},
            'task_count':len(window_checks)}
    return {'mission_status':report['status'],'method':'maximum-cardinality distance-ordered point-to-USD-AABB matching',
        'tolerance_m':tolerance,'limitations':['Placed-target recall includes occluded fruit; not visible-only detector recall.',
          'RGB-D points are surface samples. Center distance is not localization RMSE.',
          'AABB matching is approximate; adjacent or overlapping fruit can be ambiguous.',
          'Context detections outside work height are reported in excluded_prediction_ids, not scored.',
          'Static USD must match the running scene. T_map_world is an independent calibration, not AMCL fit.'],
        'sections':results}


def main():
    p=argparse.ArgumentParser();p.add_argument('--survey',default='latest');p.add_argument('--truth',required=True)
    p.add_argument('--tolerance',type=float,default=.03);a=p.parse_args()
    if not 0<a.tolerance<.5:raise ValueError('Invalid tolerance')
    if a.survey=='latest':
        files=list((ROOT/'sim/runs/scout_survey').glob('*/survey.json'))
        if not files:raise SystemExit('sim/runs/scout_survey에 결과가 없습니다. 이전 결과는 --survey로 파일 경로를 지정하세요.')
        path=max(files,key=lambda p:p.stat().st_mtime)
    else:path=Path(a.survey)
    report=json.loads(path.read_text());truth=json.loads(Path(a.truth).read_text())
    result=compare(report,truth,ROOT,a.tolerance);out=path.parent/'truth_comparison.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    for key,s in result['sections'].items():
        print(f'{key}: placed targets={s["placed_target_count"]}, IDs={s["detected_id_count"]}, matched={s["matched_count"]}, tasks={s["task_count"]}, possible duplicates={len(s["possible_duplicate_ids"])}')
    print(out)
if __name__=='__main__':main()
