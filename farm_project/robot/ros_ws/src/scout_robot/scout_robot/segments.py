"""Bed-specific capture segments; distances follow the ordered bed route."""
import math


def plan_segments(bed, section_id, K, mount, width, height, preprocess, default_overlap):
    settings=bed.cfg.get('segmentation',{'mode':'auto'})
    if not isinstance(settings,dict):raise ValueError(f'{section_id}: segmentation must be an object')
    mode=settings.get('mode','auto')
    overlap=settings.get('overlap_fraction',default_overlap)
    if isinstance(overlap,bool) or not isinstance(overlap,(int,float)) or not math.isfinite(overlap) or not 0<=overlap<1:
        raise ValueError(f'{section_id}: invalid segmentation overlap_fraction')
    finish=bed.cfg.get('finish_at','route_end')
    if finish not in ('last_segment','route_end'):
        raise ValueError(f'{section_id}: finish_at must be last_segment or route_end')
    design=bed.viewpoints(K,mount,width,height,preprocess,overlap)
    if mode=='auto':
        prefix=settings.get('id_prefix',section_id+'_S')
        if not isinstance(prefix,str) or not prefix.strip():raise ValueError('Empty segment ID prefix')
        items=[{'segment_id':f'{prefix}{i+1:03d}','offset_m':s}
               for i,s in enumerate(design['stops_s_m'])]
    elif mode=='manual':
        items=settings.get('segments')
        if not isinstance(items,list) or not items:raise ValueError(f'{section_id}: manual segments are empty')
    else:raise ValueError(f'{section_id}: segmentation mode must be auto or manual')
    segments=[];seen=set();previous=-math.inf
    lo,hi=design['relative_coverage_m'];max_step=design['usable_width_m']*(1-overlap)
    for item in items:
        if not isinstance(item,dict):raise ValueError('Each segment must be an object')
        sid=item.get('segment_id');s=item.get('offset_m')
        if not isinstance(sid,str) or not sid.strip() or sid in seen:
            raise ValueError(f'{section_id}: segment IDs must be nonempty and unique')
        if isinstance(s,bool) or not isinstance(s,(int,float)) or not math.isfinite(s) or not 0<=s<=bed.length:
            raise ValueError(f'{sid}: offset_m must be inside the bed route')
        if s<=previous:raise ValueError(f'{sid}: segment offsets must be strictly increasing')
        if segments and s-previous>max_step+1e-6:
            raise ValueError(f'{sid}: camera coverage/required overlap has a gap; add or move a segment')
        segments.append({'segment_id':sid,'offset_m':float(s),
                         'coverage_start_m':max(0.,s+lo),'coverage_end_m':min(bed.length,s+hi)})
        seen.add(sid);previous=s
    if segments[0]['offset_m']+lo>1e-6 or segments[-1]['offset_m']+hi<bed.length-1e-6:
        raise ValueError(f'{section_id}: configured segments do not cover both bed route ends')
    design.update(segments=segments,stops_s_m=[v['offset_m'] for v in segments],
                  segmentation_mode=mode,finish_at=finish)
    return design
