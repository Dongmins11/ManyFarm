"""SEC01 복귀/출발 간섭 로그를 좌표가 보존된 지도에 표시한다. 시험 제어 없음."""
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/tmp/farm-map-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon, Rectangle
import numpy as np
from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'sim/docs/test_results/20261028_sec01_single_cycle'
MAPS = ROOT/'sim/ros_ws/src/farm_sim_config/maps'
OUT = ROOT/'sim/docs/test_results/20261030_sec01_conflict_map'
BLUE, ORANGE, RED = '#0878b5', '#cc6700', '#c72736'


def main() -> None:
    """전체 지도·북쪽 경로·최근접 표본을 한 PNG에 저장한다."""
    OUT.mkdir(parents=True, exist_ok=True)
    font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    plt.rcParams.update({'font.family': 'Noto Sans CJK JP', 'font.size': 11,
                         'axes.unicode_minus': False, 'savefig.facecolor': 'white'})
    info = yaml.safe_load((MAPS/'hcr_farm_map.yaml').read_text())
    raster = np.asarray(Image.open(MAPS/info['image']))
    ox, oy, yaw = info['origin']
    assert yaw == 0
    res = info['resolution']
    extent = [ox, ox+raster.shape[1]*res, oy, oy+raster.shape[0]*res]
    closest = json.loads((SOURCE/'failure_analysis.json').read_text())['closest']
    rows = [json.loads(s) for s in (SOURCE/'close_approach.jsonl').read_text().splitlines()]
    rows = [r for r in rows if r['sim_time_s'] <= closest['sim_time_s']]
    scout, harvest = np.array(closest['scout_xy']), np.array(closest['harvest_xy'])
    center = (scout+harvest)/2
    # 전체 계획 로그가 아닌 현재 그래프 좌표에 따른 설명용 경로 재구성.
    # 작업선·station·공유 통로 좌표와 당시 첫 윈도우를 데이터에서 읽는다.
    def nodes(filename: str) -> dict:
        return {f['properties']['id']: f['geometry']['coordinates'][:2]
                for f in json.loads((MAPS/filename).read_text())['features']
                if f['geometry']['type'] == 'Point'}
    sn, hn = nodes('graph.geojson'), nodes('harvest_graph.geojson')
    task = yaml.safe_load((ROOT/'sim/ros_ws/src/farm_sim_config/config/task.yaml').read_text())['sections']['SEC01']
    tasks = json.loads((SOURCE/'scout_result.json').read_text())['scout_result']['result']['harvest_tasks']
    first = tasks[0]['goal_pose']['position']
    scout_path = np.array([task['survey_geometry']['end_xy_m'], sn[10100], sn[9001], sn[9002], sn[9003], sn[8001]])
    harvest_path = np.array([hn[8002], hn[9008], hn[9007], hn[9006], hn[9005], hn[9004], hn[9003], hn[9002], hn[20102], [first['x'], first['y']]])
    fig = plt.figure(figsize=(16, 12), layout=None)
    grid = fig.add_gridspec(2, 2, width_ratios=[.85, 1.55], height_ratios=[1.2, 1],
                           left=.045, right=.97, bottom=.17, top=.88, wspace=.19, hspace=.32)
    whole, route, detail = fig.add_subplot(grid[:, 0]), fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[1, 1])
    for ax in (whole, route, detail):
        ax.imshow(raster, cmap='gray', vmin=0, vmax=255, extent=extent, origin='upper', interpolation='nearest', alpha=.7)
        ax.set_aspect('equal')
        ax.grid(alpha=.15)
        ax.set_xlabel('맵 X (m)  /  오른쪽 = +X')
        ax.set_ylabel('맵 Y (m)')
        ax.plot(scout_path[:, 0], scout_path[:, 1], '--', color=BLUE, lw=2, zorder=3)
        ax.plot(harvest_path[:, 0], harvest_path[:, 1], '--', color=ORANGE, lw=2, zorder=3)
        for key, color in [('scout_xy', BLUE), ('harvest_xy', ORANGE)]:
            points = np.array([r[key] for r in rows])
            ax.plot(points[:, 0], points[:, 1], color=color, lw=2.7, zorder=4)
        ax.scatter(*center, marker='x', color=RED, s=100, lw=3, zorder=8)
    whole.set(xlim=(extent[0], extent[1]), ylim=(extent[2], extent[3]), title='① 농장 전체 — 위쪽이 +Y')
    whole.add_patch(Rectangle((-7.1, 8.9), 5.9, 5., fill=False, ec=RED, lw=2))
    whole.annotate('북쪽 = +Y\n지도 위쪽을 뜻함', xy=(3.6, 13.9), xytext=(3.6, 8.8), ha='center',
                   arrowprops=dict(arrowstyle='-|>', lw=2, color='#243746'), fontsize=12, weight='bold')
    whole.text(-4.9, 6., 'SEC01\n대상 베드', ha='center', va='center', fontsize=10,
               bbox=dict(fc='white', ec='none', alpha=.9))
    whole.text(0, -12.5, '※ 실제 지리상의 북쪽이 아닌\n맵 +Y 방향을 북쪽으로 표기', ha='center', fontsize=10)
    route.set(xlim=(-7.1, -1.2), ylim=(8.9, 13.9), title='② 북쪽 가로 통로 — Y = 11.5m')
    route.axhspan(11.35, 11.7, color=RED, alpha=.08)
    for xy, label, color, offset in [(sn[8001], '예찰 스테이션', BLUE, (0, 10)), (hn[8002], '수확 스테이션', ORANGE, (0, 10))]:
        route.scatter(*xy, marker='s', s=75, c=color, zorder=5)
        route.annotate(label, xy=xy, xytext=offset, textcoords='offset points', color=color, ha='center')
    for a, b, color in [((-6.4, 11.62), (-6.05, 11.62), BLUE), ((-4.1, 11.55), (-4.8, 11.55), ORANGE)]:
        route.annotate('', xy=b, xytext=a, arrowprops=dict(arrowstyle='-|>', color=color, lw=2.4))
    route.text(-4.2, 12.05, '수확 출발: 서쪽(−X)으로 전진', color=ORANGE, ha='center', fontsize=10)
    route.annotate('예찰 복귀: +Y로 후진한 뒤\n가로 통로에서 +X로 이동', xy=(-6.65, 10.3), xytext=(-4.9, 10.2),
                   color=BLUE, fontsize=10, arrowprops=dict(arrowstyle='->', color=BLUE))
    route.annotate('충돌/간섭 관측 구간', xy=center, xytext=(-6.8, 12.55), color=RED,
                   arrowprops=dict(arrowstyle='->', color=RED), weight='bold')
    route.text(-6.65, 9.1, '예찰선', color=BLUE, ha='center')
    route.text(-6.01, 9.1, '수확선', color=ORANGE, ha='center')
    detail.set(xlim=(-6.45, -4.95), ylim=(11.04, 12.15), title='③ 당시 최근접 위치 — 두 로봇이 같은 가로 통로에 있음')
    theta = closest['harvest_yaw']
    rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    footprint = np.array([[.32, .27], [.32, -.27], [-.32, -.27], [-.32, .27]]) @ rot.T + harvest
    detail.add_patch(Polygon(footprint, fc=ORANGE, ec=ORANGE, alpha=.35, zorder=5))
    detail.add_patch(Circle(scout, .1, fc=BLUE, ec=BLUE, alpha=.45, zorder=5))
    detail.scatter(*scout, c=BLUE, s=30, zorder=8)
    detail.scatter(*harvest, c=ORANGE, s=30, zorder=8)
    detail.annotate('예찰 중심\n(−5.911, 11.600)', xy=scout, xytext=(-6.36, 11.94), color=BLUE, fontsize=10,
                    arrowprops=dict(arrowstyle='->', color=BLUE))
    detail.annotate('수확 중심\n(−5.528, 11.555)', xy=harvest, xytext=(-5.56, 11.94), color=ORANGE, fontsize=10,
                    arrowprops=dict(arrowstyle='->', color=ORANGE))
    detail.annotate('', xy=(scout[0], 11.25), xytext=(harvest[0], 11.25), arrowprops=dict(arrowstyle='<->', color='#243746'))
    detail.text(center[0], 11.14, '중심 간 거리 약 38.6cm', ha='center', fontsize=11)
    fig.suptitle('SEC01 예찰 복귀 × 수확 출발 — 경로와 간섭 위치', fontsize=22, y=.97, weight='bold')
    fig.text(.5, .923, '베드 옆의 평행 주행선 구간이 아니라, 베드 위쪽 가로 통로에서 만난 기록입니다.', ha='center', fontsize=13)
    handles = [Line2D([], [], color=BLUE, lw=3, label='예찰'), Line2D([], [], color=ORANGE, lw=3, label='수확'),
               Line2D([], [], color='#555', ls='--', lw=2, label='설정 경로 재구성'),
               Line2D([], [], color='#555', lw=3, label='당시 실제 위치 기록'),
               Line2D([], [], color=RED, marker='x', ls='', label='최근접 중심의 중간점')]
    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5, .081), ncol=5, frameon=False, fontsize=11)
    fig.text(.5, .045, '근거: 2026-10-28 시험 / sim 197.167s 표본 · 두 위치의 시각차 약 0.2s · 외곽 도형은 Nav2 설정 기준', ha='center', fontsize=10)
    fig.text(.5, .023, '×는 실제 접촉점이 아닙니다. 접촉력 미기록. 점선은 현재 그래프 좌표로 재구성했고, 실선만 당시 저장된 실제 궤적입니다.', ha='center', fontsize=10, color='#555')
    fig.savefig(OUT/'sec01_routes_conflict_map.png', dpi=170)
    # 원시 근거와 지도 해석을 이미지 옆에 남긴다.
    (OUT/'sources.json').write_text(json.dumps(dict(map=str(MAPS/'hcr_farm_map.yaml'),
        coordinate_convention='north means map +Y; not geographic north', sources=str(SOURCE),
        closest=closest, marker_is_contact_point=False, planned_route_is_reconstructed=True,
        scout_path=scout_path.tolist(), harvest_path=harvest_path.tolist()), ensure_ascii=False, indent=2)+'\n')
    print(OUT/'sec01_routes_conflict_map.png')


if __name__ == '__main__':
    main()
