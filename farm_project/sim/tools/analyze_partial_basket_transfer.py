"""낙하 시험 원시 기록에서 위치/자세별 집계와 경로 그림을 만든다."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);args=parser.parse_args()
    result=json.loads((args.directory/'result.json').read_text())
    trajectories={r['id']:r['samples'] for r in map(json.loads,(args.directory/'trajectories.jsonl').read_text().splitlines())}
    rows=[];fig,axes=plt.subplots(2,3,figsize=(12,7),layout='constrained')
    colors={'captured':'#218c49','floor_loss':'#cb3b3b','not_settled_or_retained':'#e59a21'}
    for i,condition in enumerate(('overlap72','centered_control')):
        for j,orientation in enumerate(('upright','side_x','side_y')):
            cases=[c for c in result['cases'] if c['condition']==condition and c['orientation']==orientation]
            captured=sum(c['captured'] for c in cases)
            rows.append(dict(condition=condition,orientation=orientation,total=len(cases),captured=captured,
                floor_loss=sum(c['outcome']=='floor_loss' for c in cases),retained=sum(c['outcome']=='not_settled_or_retained' for c in cases)))
            ax=axes[i,j]
            for c in cases:
                x,y=c['release_xy_m'];ax.scatter(x*1000,y*1000,c=colors[c['outcome']],s=100)
            ax.set(xlim=(-70,70),ylim=(-70,70),aspect='equal',xlabel='Release X in harvest frame (mm)',ylabel='Release Y (mm)',
                title=f'{condition} / {orientation}: {captured}/{len(cases)} captured')
            ax.grid(alpha=.2)
    fig.suptitle('Independent single-pepper drops: green=captured, red=floor loss, orange=retained near rim')
    fig.savefig(args.directory/'release_map.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,6),layout='constrained')
    ax.add_patch(Rectangle((-.3,0),.3,.003,color='#555'))
    ax.add_patch(Rectangle((-.3,0),.003,.19,color='#555'))
    ax.add_patch(Rectangle((-.003,0),.003,.19,color='#555'))
    ax.plot([-.14,.05],[.2465,.2465],color='#496db5',lw=3,label='Harvest outlet (approx. projected span)')
    for case_id,label in [(12,'Centre release: captured'),(0,'Exposed edge, upright: retained'),(27,'Exposed edge, sideways: lost')]:
        case=result['cases'][case_id];xyz=np.array([s['center_in_receiver_m'] for s in trajectories[case_id]])
        ax.plot(xyz[:,0],xyz[:,2],color=colors[case['outcome']],label=label)
        ax.scatter(*xyz[0,[0,2]],color=colors[case['outcome']],marker='o')
        ax.scatter(*xyz[-1,[0,2]],color=colors[case['outcome']],marker='x')
    ax.set(xlim=(-.32,.2),ylim=(-.28,.36),aspect='equal',xlabel='Receiver local X (m; front rim at 0)',ylabel='Receiver local Z (m)',
           title='72.1% overlap: actual fruit-centre trajectories, side projection')
    ax.legend(loc='lower left',fontsize=8);ax.grid(alpha=.2)
    fig.savefig(args.directory/'drop_paths.png',dpi=150);plt.close(fig)
    (args.directory/'counts.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(rows))


if __name__=='__main__':main()
