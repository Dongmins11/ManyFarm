#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dock.py  —  운송로봇 wmany 정밀 도킹 · 하나의 코드로 여러 장소 (10-01 통합)
            harvest(수확로봇) · sorter(선별장) · parking(주차장)
            (harvest_dock.py · sorter_dock_v2.py 를 합쳤다. 두 파일은 ~/wmany/old/ 에 보관)

  ■ 구조
    · 동작(접근 · 정렬 · 마지막 직진)은 이 파일 하나
    · 장소마다 다른 값(마커 ID · 크기 · 정지 거리 · 라이다 목표 · 대기점)은 ~/wmany/dock/sites.yaml
      → START 할 때마다 다시 읽으므로 값만 바꿀 땐 sites.yaml 만 고치고 재시작 없이 다시 START
    · 여기 아래 파라미터는 "기본값". sites.yaml 의 장소 항목에 같은 이름이 있으면 그 값이 이긴다
    · 티칭 파일도 장소별: ~/wmany/dock/teach_<장소>.yaml (카메라) · lidar_<장소>.yaml (라이다)

  ■ 명령  (토픽 /dock/cmd · 상태는 /dock/state 에 "장소:상태" 로 나간다. 예 harvest:DONE)
    START <장소>     도킹 시작               예) "{data: START harvest}"
    UNDOCK           ### (10-06) 도킹 자리에서 도킹을 시작했던 곳(3번 노드 등)까지 똑바로 후진 → "<장소>:UNDOCKED"
    START <장소> turn=<도>   ### (10-02) 먼저 그 자리에서 <도> 만큼 돌고(+ 왼쪽) 대기점 없이 바로 도킹
                             라우트서버(wf dock parking)가 3번 노드에 데려다 놓고 이걸 보낸다
    STOP             정지
    LTEACH <장소>    라이다 목표 각도 티칭    로봇을 자로 맞춘 도킹 자세에 두고 (주변 비우고)
    LRESET <장소>    라이다 티칭값 치우고 sites.yaml 값으로
    TEACH <장소>     카메라(마커) 목표 티칭  — 지금은 안 씀 (기본값으로 멈춘다)
    SITES            sites.yaml 에 있는 장소 목록 출력
    ※ ros2 topic pub 는 --once 대신 -t 3 -r 2 로 보낸다 (한 번만 쏘면 사라질 때가 있다)

  ■ 장소 하나의 마커 배치 (로봇에서 볼 때)
    먼 마커 (far, 큰 것)   · 오른쪽 : 멀리서 방향 · 좌우를 대략 잡는다
    가까운 마커 (near, 작은 것) · 왼쪽 : 정확한 도킹 기준. switch_dist 안쪽부터 끝까지 보면서 들어간다
    off_x = 가까운 마커 중심 - 먼 마커 중심 (가로) [m]. 가까운 것이 왼쪽이면 -

  ■ 도킹
  ① NAV     Nav2 로 대기점까지 (staging_x 를 안 주면 건너뜀)
  ② SEARCH  제자리에서 천천히 돌며 먼 마커 또는 가까운 마커 찾기
  ③ TRACK   먼 마커 기준으로 "가까운 마커 정면선" 을 따라 접근 (off_x 로 가까운 마커 위치 환산)
             가까운 마커가 연속 잡히고 switch_dist 안쪽이면 → FINE
  ④ FINE    가까운 마커만 보고 따라가기. 거리 ≤ final_dist → 정지
             · 가까이서(near_lost_dist 안) 놓치면: final_dist + lost_margin 안이면 DONE(정렬로), 아니면 FAILED 정지
               (눈감고 가지 않는다 · 수확로봇 옆에서 제자리 회전도 하지 않는다)
             · 멀리서 놓치면 먼 마커로 복귀 → 없으면 REACQ (제자리 재탐색)
  ⑤ ALIGN   제자리 회전으로 몸체 각도를 맞춤
             · 라이다 정렬 — 라이다로 정면 면(수확로봇 옆면 · 벽) 각도를 재고, 오도메트리로 돌고, 멈춰서 다시 잰다.
               라이다 각도가 lidar_target_deg(자로 맞춘 자세에서 읽은 값 · 장소마다 다름) 와 같아질 때까지 반복
             · 라이다 목표가 없거나(LTEACH 전) 면을 못 찾으면 예전 방식(카메라 마커 각도 + final_yaw_deg 를 오도메트리로 회전)
  ⑥ PUSH    각도까지 맞춘 뒤 오도메트리로 push_dist 만 똑바로 더 전진 (0 이면 안 함)
             · 마커가 너무 가까워 흐려 못 읽는 구간이라 "눈감고" 가되, 거리를 바퀴 이동량으로 잰다
             · ALIGN 이 제대로 끝난 경우만 한다 (각도 맞추기 시간 초과 · /odom 없음 · FAILED 면 안 한다)
  ⑦ DONE    정지 → 목표값과의 차이 출력 (PUSH 전, 마지막으로 본 마커 기준)

실행 (로봇에서. bringup · cam 켜져 있어야 함)
  python3 ~/wmany/dock/dock.py --ros-args -p dry_run:=false     # 실제 주행 대기 (alias: dock)
  python3 ~/wmany/dock/dock.py                                  # dry_run (계산만 · 안 움직임)
  그다음 PC 에서:  ros2 topic pub -t 3 -r 2 /dock/cmd std_msgs/msg/String "{data: START harvest}"
"""

import csv
import math
import os
import random                                   ### 수정 (10-01) 라이다 직선 찾기(RANSAC)
import signal                                   ### 수정 (10-02) 카메라 프로세스 끄기
import subprocess                               ### 수정 (10-02) 카메라 프로세스 켜기
import threading                                ### 수정 (10-02) 카메라 끄기를 기다리는 동안 멈추지 않게
import time
from collections import deque                   ### 수정 (10-01) 라이다 측정값 버퍼

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CameraInfo, LaserScan   ### 수정 (10-01) LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TwistStamped, PoseStamped
from std_msgs.msg import String
from nav2_msgs.action import NavigateToPose
import yaml

NEW_API = hasattr(cv2.aruco, "ArucoDetector")

IDLE, NAV, SEARCH, TRACK, FINE, REACQ, ALIGN, PUSH, DONE, FAILED = (
    "IDLE", "NAV", "SEARCH", "TRACK", "FINE", "REACQ", "ALIGN", "PUSH", "DONE", "FAILED")
FACE = "FACE"
UNDOCK = "UNDOCK"   ### 수정 (10-06) 도킹 자리에서 똑바로 후진해 빠져나오기
### 수정 (10-02) 도킹할 때만 켜는 카메라 — 로봇 alias cam 과 같은 명령
CAM_CMD = ["ros2", "run", "camera_ros", "camera_node", "--ros-args",
           "-p", "format:=RGB888", "-p", "width:=1280", "-p", "height:=720"]   ### 수정 (10-02) 도킹 전에 제자리에서 정해진 각도만큼 돌기 (START <장소> turn=<도>)   ### 수정 (09-30) PUSH 추가

# camera_info 가 안 올 때 쓰는 캘리브레이션 (imx219 1280x720 백업 yaml 값)
K_DEFAULT = [1760.09461, 0.0, 608.60175, 0.0, 1762.77619, 321.59117, 0.0, 0.0, 1.0]
D_DEFAULT = [0.15413, 0.299465, -0.024481, -0.009309, 0.0]


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


### 수정 (10-01) 라이다로 정면 면 찾기 — lidar_face_check.py 와 같은 계산
def fit_face(pts, tol, min_inliers, iters):
    """pts: 로봇 기준 (x 앞, y 왼쪽) [m] 점 목록 → 정면 면 직선을 찾아 (phi_deg, dist_m, inliers) 반환. 못 찾으면 None

    직선을 x = a·y + b 꼴로 둔다 (정면 벽은 y 가 변해도 x 가 거의 그대로라 이 꼴이 안정적).
      phi = atan(a) : + 면 로봇이 면에 대해 왼쪽(반시계)으로 틀어진 것   ← 반시계로 돌면 phi 가 커진다
      dist = b·cos(phi) : 라이다 중심 → 면 수직 거리
    ① RANSAC: 두 점을 골라 직선을 긋고, 1cm 안에 드는 점이 가장 많은 직선을 고른다 → 로봇 기둥 같은 튀는 점은 빠진다
    ② 그 점들로 최소제곱을 다시 해 기울기를 다듬는다"""
    if len(pts) < min_inliers:
        return None
    best = []
    for _ in range(iters):
        (x1, y1), (x2, y2) = random.sample(pts, 2)
        if abs(y2 - y1) < 0.01:                  # 두 점이 좌우로 너무 붙어 있으면 기울기가 불안정 → 건너뜀
            continue
        a = (x2 - x1) / (y2 - y1)
        b = x1 - a * y1
        k = math.sqrt(1.0 + a * a)               # 점-직선 수직거리 = |x - a·y - b| / sqrt(1+a²)
        inl = [(x, y) for (x, y) in pts if abs(x - a * y - b) / k <= tol]
        if len(inl) > len(best):
            best = inl
    if len(best) < min_inliers:
        return None
    m = len(best)
    sy = sum(y for _, y in best); sx = sum(x for x, _ in best)
    syy = sum(y * y for _, y in best); sxy = sum(x * y for x, y in best)
    den = m * syy - sy * sy
    if abs(den) < 1e-9:
        return None
    a = (m * sxy - sx * sy) / den
    b = (sx - a * sy) / m
    phi = math.atan(a)
    return math.degrees(phi), b * math.cos(phi), m


class Dock(Node):
    def __init__(self):
        super().__init__("dock")

        # ───────── 기본값 — 장소별 값은 sites.yaml 이 이긴다 (--ros-args -p 이름:=값 으로 기본값을 바꿀 수 있다) ─────────
        P = self.declare_parameter
        P("sites_file", "~/wmany/dock/sites.yaml")   # 장소별 값 파일 (START 때마다 다시 읽는다)
        P("site", "")                   # 켤 때 미리 고를 장소 (비우면 START <장소> 때 고른다)
        # ① 대기점
        P("staging_x", float("nan"))    # nan 이면 Nav2 건너뜀 (도킹만 시험)
        P("staging_y", float("nan"))
        P("staging_qz", 0.0)
        P("staging_qw", 1.0)
        P("nav_timeout", 120.0)
        P("skip_staging", False)        ### 수정 (10-02) True 면 sites.yaml 에 대기점이 있어도 Nav2 로 안 간다 (라우트서버가 데려다 줄 때)
        P("face_tol_deg", 1.0)          ### 수정 (10-02) FACE 회전 허용오차 [deg]
        P("face_timeout", 20.0)
        P("cam_auto", True)             ### 수정 (10-02) True 면 START 때 카메라를 켜고 끝나면 끈다 (이미 켜진 카메라는 그대로 쓴다)
        P("cam_wait_s", 10.0)           ### 수정 (10-02) START 후 이 시간 안에 첫 영상이 안 오면 FAILED         ### 수정 (10-02) FACE 회전 제한 시간 [s] — 넘으면 멈추고 그냥 SEARCH
        # 마커  (아래 마커 · 거리 값들의 기본값은 harvest 기준. 장소별 값은 sites.yaml)
        P("far_id", 21)
        P("far_size", 0.10)             # ID 21 한 변 [m]
        P("near_id", 22)
        P("near_size", 0.02)            # ID 22 한 변 [m]   ### 수정 (09-30) 0.03 → 0.02 (2cm 마커로 교체)
        P("off_x", -0.09)               # ID 22 중심 - ID 21 중심, 가로 [m]  (22 가 21 왼쪽 9cm)
                                        #   로봇에서 볼 때 22 가 오른쪽이면 +, 왼쪽이면 -
        # 티칭
        P("teach_file", "~/wmany/dock/teach_{site}.yaml")   # 카메라 티칭 파일 ({site} 는 장소 이름으로 바뀐다)
        P("teach_frames", 20)           # 티칭할 때 평균낼 프레임 수
        # 티칭 파일이 없을 때 쓰는 목표 (거리 · 좌우 · 각도) — 전부 "카메라 렌즈 ~ ID 22" 기준
        P("final_dist", 0.08)           # [m]  렌즈~마커 정지 거리   ### 수정 (09-30) 0.12 → 0.08 (2cm 실측 성공값)
        P("final_lat", 0.0)             # [m]
        P("final_yaw_deg", 8.0)         # [deg] + 면 오른쪽(시계방향)으로 튼 자세
                                        ### 수정 (10-01) 0.0 → 8.0 : 카메라가 개조 장착으로 약 8° 틀어져 달려 있다.
                                        ###   마커를 정면(0°)으로 맞추면 몸체가 8° 틀어져 한쪽 바퀴가 약 4cm 앞선다.
                                        ###   선별장(sorter_dock_v2) 과 같은 값 · 장착을 바로잡으면 0 으로 되돌린다.
        P("stop_lead_s", 0.3)           # 영상 지연 보정 [s] — 목표 + (현재 속도 × 이 값) 에서 미리 멈춘다
        P("near_lost_dist", 0.25)       # 이 안에서 22 를 놓치면 재탐색 없이 정지
        P("lost_margin", 0.02)          #   그때 마지막 거리가 목표 + 이 값 안이면 DONE, 아니면 FAILED
        P("far_min_dist", 0.25)         # 21 만 보이는데 이보다 가까우면 FAILED (22 를 못 찾음)   ### 수정 (09-30) 0.30 → 0.25
        P("switch_frames", 5)           # 22 가 연속 이만큼 잡히고
        P("switch_dist", 0.33)          #   22 거리가 이 안쪽이면 FINE 으로 전환   ### 수정 (09-30) 0.40 → 0.33 (2cm 인식 거리)
                                        #   (3cm 는 멀면 좌우 잡음이 커서 0.4m 안에서만 믿는다)
        P("smooth", 0.4)                # 좌우·각도 지수평균 계수 (1.0 이면 평균 안 함)
        # 정면선 따라가기
        P("cam_offset", 0.10)           # 카메라가 바퀴 축보다 앞에 나온 거리 [m]
        P("look_min", 0.15)             # lookahead 최소 [m]  (작을수록 급하게 꺾는다)
        P("look_max", 0.30)             # lookahead 최대 [m]  (크면 선에 늦게 붙어 비스듬히 도착)
        P("look_gain", 0.5)             # lookahead = look_gain × 남은거리 (look_min ~ look_max)
        P("turn_only_deg", 25.0)        # 목표 방향이 이보다 틀어지면 제자리 회전
        ### 수정 (10-01) 근접 구간 — 마커가 가까우면 카메라 각도가 ±5° 넘게 튄다 (2cm 마커 0.1m 에서 -0.4 ~ -16.8°)
        ###   튀는 값 하나에 제자리로 크게 돌다 마커를 잃는 일을 막는다. 각도는 뒤의 라이다 정렬(ALIGN)이 맞춘다
        P("close_dist", 0.15)           # 가까운 마커까지 이보다 가까우면 "근접 구간" [m]
        P("close_w_max", 0.06)          # 근접 구간 최대 회전 속도 [rad/s] — 제자리 회전 · 화면 붙잡기 회전도 이 안으로
                                        #   (전진은 멈추지 않는다: 근접 구간에선 v_min 이상으로 계속 천천히 들어간다)
        P("bearing_max_deg", 12.0)      # 마커가 화면 중앙에서 이보다 벗어나면 전진 멈추고 먼저 돌린다 (ID 22)
        P("bearing_max_far_deg", 17.0)  # ID 21 을 볼 때 한계 (22 정면선으로 가면 21 은 옆으로 치우치므로 넓게)
                                        #   (카메라 좌우 화각 ±20°)
        P("reacq_timeout", 3.0)         # 멀리서 놓쳤을 때 제자리에서 다시 찾는 시간 [s]
        P("w_reacq", 0.20)
        # 속도 (쏠림 때문에 0.13 이하)
        P("v_max", 0.06)
        P("v_min", 0.02)                # 움직일 때 최소 속도 (멈칫 방지)
        P("k_v", 0.25)                  # v = k_v × 남은거리  (목표 근처에서 느려진다)
        P("w_max", 0.35)
        P("w_search", 0.25)
        P("k_w", 1.5)                   # 제자리 회전 게인
        # 최종 판정 (정지 후 로그용)
        P("tol_lat", 0.015)
        P("tol_yaw_deg", 3.0)
        # 도착 후 제자리 회전 (오도메트리 기준) — 목표 각도는 티칭값
        P("align_tol_deg", 0.7)         # 회전 허용오차
        P("align_timeout", 5.0)
        ### 수정 (10-06) UNDOCK — 도킹 시작점(SEARCH 들어간 자리)까지 후진. 그 자리를 모르면 undock_dist 만큼
        P("undock_dist", 0.35)          # 도킹 시작점을 모를 때 (dock 을 재시작했을 때) 후진 거리 [m]
        P("undock_max", 0.80)           # 아무리 멀어도 이 이상은 후진하지 않는다 [m]
        P("undock_speed", 0.05)         # 후진 속도 [m/s]
        P("undock_rear_stop", 0.25)     # 뒤쪽 라이다에 이 거리 안 장애물이 잡히면 멈춤 [m] (0.20 안쪽은 몸체라 무시)
        # ─── ### 수정 (09-30) 정렬 후 마지막 직진 (PUSH) ────────────────────────────────
        #  ALIGN 으로 각도까지 맞춘 다음, 마커를 보지 않고 바퀴 이동량(/odom)만으로 조금 더 붙는다.
        #  final_dist(0.08m) 보다 가까우면 2cm 마커가 흐려 못 읽기 때문에 "보면서" 갈 수 없는 구간이다.
        P("push_dist", 0.0)             # 마지막 직진 거리 [m]. /odom 위치로 잰 직선거리가 이 값이 되면 정지
                                        #   ### 통합 (10-01) 기본 0 (안전) — 직진할 장소만 sites.yaml 에 넣는다 (harvest 0.02)
                                        #   0 이면 PUSH 단계를 통째로 건너뛰고 ALIGN 뒤 바로 DONE (예전 동작)
        P("push_speed", 0.02)           # 직진 속도 [m/s]. 0.02 면 2cm 에 약 1초
                                        #   회전(w)은 0 으로 고정 — ALIGN 에서 맞춘 방향 그대로 직진만 한다
        ### 수정 (10-01) 라이다 거리로 멈추는 마지막 직진
        P("push_to_dist", float("nan")) # 라이다로 잰 "라이다 중심 → 정면 면" 거리가 이 값이 되면 멈춘다 [m]
                                        #   nan = 안 씀 (push_dist 만큼 오도메트리로). 값이 있으면 push_dist 대신 이걸 쓴다
                                        #   → 어디서 멈췄든(0.08m 든 0.12m 든) 최종 간격이 항상 같아진다
                                        #   라이다가 면을 못 보고 있으면 push_dist(오도메트리) 로 대체
        P("push_max", 0.08)             # push_to_dist 를 쓸 때 최대 직진 거리 [m] — 라이다가 엉뚱한 걸 봐도 이 이상은 안 간다
        P("push_timeout", 3.0)          # 이 시간 [s] 안에 push_dist 를 못 가면 멈추고 그대로 DONE
                                        #   바퀴가 턱에 걸리거나 무언가에 닿아 못 나갈 때 계속 밀지 않기 위한 안전장치
                                        #   (2cm ÷ 0.02m/s = 1초 이므로 3초면 넉넉하다)
        # ─── ### 수정 (10-01) 라이다 정렬 (ALIGN 을 라이다로) ──────────────────────────────
        #  카메라가 개조 장착으로 틀어져 있어 마커 각도만으로는 몸체가 똑바로 서지 않는다.
        #  라이다는 몸체에 고정돼 있으니, 라이다로 수확로봇 면의 기울기를 직접 재서 맞춘다.
        #  방식 = "재고 → 돌고 → 멈춰서 다시 잰다" 반복
        #    · 잴 때는 멈춘 상태에서 여러 장 평균 (돌면서 재면 스캔이 늦게 와서 지나쳐 버린다)
        #    · 돌 때는 오도메트리로 정확히 그 각도만큼 (짧은 회전은 오도메트리가 정확하다)
        P("lidar_align", True)          # True = 라이다 정렬 사용 · False = 예전 방식(카메라 각도 + 오도메트리)만
        P("lidar_target_deg", float("nan"))   # 목표 라이다 각도 [deg] = 로봇을 자로 "똑바로" 맞춘 자세에서 라이다가 읽은 값
                                        #   기본 nan = 목표 없음 → 라이다 정렬 안 함. sites.yaml 이나 LTEACH 로 장소마다 정한다 (harvest 8.2)
                                        #   0 이 아닌 이유: 라이다 장착 각도 · 라이다 높이의 면 기울기 때문 (10-01 실측 +8.2°)
                                        #   LTEACH 명령으로 다시 재면 lidar_teach_file 값이 이 값보다 우선한다
        P("lidar_teach_file", "~/wmany/dock/lidar_{site}.yaml")   # LTEACH 결과 저장 파일 ({site} → 장소 이름)
        P("lidar_topic", "/scan")       # 원본 스캔 (필터 전). /scan_filtered 는 0.20m 안쪽을 지워 도킹 거리에서 면도 사라진다
        P("lidar_front_deg", 0.0)       # 라이다 기준 "정면" 방향 [deg]
        P("lidar_sector_deg", 30.0)     # 정면 ± 이 각도 안의 점만 쓴다 [deg]
        P("lidar_min_r", 0.08)          # 이보다 가까운 점은 버린다 [m]
        P("lidar_max_r", 0.60)          # 이보다 먼 점은 버린다 [m]
        P("lidar_inlier_tol", 0.01)     # 직선 위의 점으로 칠 거리 [m]
        P("lidar_min_inliers", 10)      # 직선 위 점이 이보다 적으면 그 스캔은 "면 못 찾음"
        P("lidar_avg_n", 5)             # 한 번 잴 때 평균 낼 스캔 수 (멈춘 상태에서 새로 들어온 것만)
        P("lidar_settle_s", 0.3)        # 회전을 멈춘 뒤 이 시간 [s] 지난 스캔부터 쓴다 (흔들림 · 늦게 온 스캔 제외)
        P("lidar_wait_s", 2.0)          # 이 시간 [s] 안에 lidar_avg_n 장을 못 모으면 "라이다 못 씀"
        P("lidar_tol_deg", 0.7)         # 목표와의 차이가 이 안이면 정렬 완료 [deg] (바퀴 차이 약 0.35cm)
        P("lidar_max_iter", 4)          # 재고-돌기 최대 반복 횟수. 넘으면 PUSH 없이 DONE (남은 각도 출력)
        P("lidar_turn_tol_deg", 0.3)    # 한 번 돌 때 오도메트리 목표 허용오차 [deg]
        P("lidar_turn_timeout", 3.0)    # 한 번 돌기 제한 시간 [s] — 넘으면 멈추고 그냥 다시 잰다
        P("lidar_teach_frames", 20)     # LTEACH 때 평균 낼 스캔 수
        P("lidar_teach_max_sd", 1.0)    # LTEACH 흔들림(표준편차)이 이 값 [deg] 을 넘으면 저장하지 않는다
        # 안전
        P("dock_timeout", 90.0)
        P("lost_timeout", 1.0)          ### 수정 (09-30) 0.5 → 1.0 (근접 흐림으로 가끔 못 읽어도 1초 대기)
        P("dry_run", True)              # 기본 True — 계산만 하고 안 움직인다
        P("autostart", False)
        P("image_topic", "/camera/image_raw")
        P("info_topic", "/camera/camera_info")
        P("dictionary", "DICT_4X4_50")
        # ─────────────────────────────────────────────────────────────────────

        names = ["sites_file", "site", "staging_x", "staging_y", "staging_qz", "staging_qw", "nav_timeout",
                 "skip_staging", "face_tol_deg", "face_timeout", "cam_auto", "cam_wait_s",   ### 수정 (10-02)
                 "far_id", "far_size", "near_id", "near_size", "off_x",
                 "teach_file", "teach_frames", "final_dist", "final_lat",
                 "stop_lead_s", "near_lost_dist", "lost_margin", "far_min_dist", "switch_frames", "switch_dist", "smooth",
                 "cam_offset", "look_min", "look_max", "look_gain", "turn_only_deg",
                 "bearing_max_deg", "bearing_max_far_deg", "reacq_timeout", "w_reacq",
                 "v_max", "v_min", "k_v", "w_max", "w_search", "k_w",
                 "tol_lat", "tol_yaw_deg", "final_yaw_deg", "align_tol_deg", "align_timeout", "dock_timeout", "lost_timeout",
                 "push_dist", "push_speed", "push_timeout",                  ### 수정 (09-30) PUSH 파라미터
                 "undock_dist", "undock_max", "undock_speed", "undock_rear_stop",   ### 수정 (10-06) UNDOCK
                 "close_dist", "close_w_max", "push_to_dist", "push_max",   ### 수정 (10-01) 근접 구간 · 라이다 거리 직진
                 "lidar_align", "lidar_target_deg", "lidar_teach_file", "lidar_topic", "lidar_front_deg",   ### 수정 (10-01)
                 "lidar_sector_deg", "lidar_min_r", "lidar_max_r", "lidar_inlier_tol", "lidar_min_inliers",
                 "lidar_avg_n", "lidar_settle_s", "lidar_wait_s", "lidar_tol_deg", "lidar_max_iter",
                 "lidar_turn_tol_deg", "lidar_turn_timeout", "lidar_teach_frames", "lidar_teach_max_sd",
                 "dry_run", "autostart", "image_topic", "info_topic", "dictionary"]
        self.c = {n: self.get_parameter(n).value for n in names}
        self.base = dict(self.c)        ### 통합 (10-01) 기본값 보관 — 장소를 고를 때마다 여기에 sites.yaml 값을 덮어 self.c 를 만든다
        self.site = None                # 지금 고른 장소 이름
        self.site_desc = ""
        c = self.c
        self.use_nav = False
        self.teach_path = ""
        self.teach_buf = None           # 티칭 중이면 측정값을 모으는 리스트
        self.t_teach = 0.0
        self.dist_ref, self.lat_ref = c["final_dist"], c["final_lat"]
        self.yaw_ref = math.radians(c["final_yaw_deg"])
        self.target_src = "기본값"
        ### 수정 (10-01) 라이다 정렬용 상태값
        self.lidar_buf = deque(maxlen=60)   # 최근 라이다 측정 (시각 monotonic, phi_deg, dist_m)
        self.lidar_teach_path = ""
        self.lidar_target = float("nan")    # 실제로 쓸 목표 (장소를 고르면 sites.yaml / LTEACH 파일 값)
        self.lidar_src = "없음"
        self.lteach_t0 = None               # LTEACH 중이면 시작 시각
        self.align_mode = "odom"            # ALIGN 방식: "odom"(예전) · "l_meas"(라이다로 재는 중) · "l_turn"(오도메트리로 도는 중)
        self.l_iter = 0                     # 라이다 재고-돌기 반복 횟수
        self.l_meas_t0 = 0.0                # 이번 측정 시작 시각 (회전 멈춘 시각)
        self.l_turn_t0 = 0.0                # 이번 회전 시작 시각
        self.l_first = None                 # 처음 잰 라이다 각도 (결과 출력용)
        self.align_why = ""                 # 정렬 시작 이유 (DONE 메시지에 붙인다)
        self.aligned_by = ""                # 마지막 정렬 방식 "lidar" · "odom" (최종 판정 출력용)

        # ArUco
        d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, c["dictionary"]))
        if NEW_API:
            prm = cv2.aruco.DetectorParameters()
            prm.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
            self.detector = cv2.aruco.ArucoDetector(d, prm)
        else:
            self.dict = d
            self.params = cv2.aruco.DetectorParameters_create()
            self.params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.obj = {c["far_id"]: self.square(c["far_size"]),
                    c["near_id"]: self.square(c["near_size"])}

        self.bridge = CvBridge()
        self.K = None
        self.D = None
        self.t_start_node = time.monotonic()
        # 마커별 최신 측정 {id: (meas, t)}
        self.meas = {}
        self.near_streak = 0            # 12 연속 검출 횟수
        self.last_near = None           # 12 마지막 측정
        self.n_det = 0
        self.stale = 0
        self.hz = 0.0
        self.hz_t = time.monotonic()

        self.create_subscription(CameraInfo, c["info_topic"], self.on_info, 10)
        ### 수정 (10-02) 카메라 영상은 도킹 · TEACH 하는 동안에만 받는다 (cam_on / cam_off)
        #   대기 중에도 1280x720 영상(초당 30장 · 장당 약 2.7MB)을 받아 버리느라 CPU 를 40% 넘게 써서
        #   라우트서버 주행 중 위치추정이 끊기고 Nav2 가 내려갔다
        self.img_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                                  history=HistoryPolicy.KEEP_LAST)
        self.img_sub = None
        self.cam_proc = None            ### 수정 (10-02) dock 이 직접 켠 카메라 프로세스 (None 이면 안 켬)
        self.cam_log = None
        self.first_img = None           ### 수정 (10-02) START 후 첫 영상이 온 시각
        self.create_subscription(Odometry, "/odom", self.on_odom, qos_profile_sensor_data, callback_group=getattr(self, "_sensor_group", None))
        # ### 수정 (10-01) 라이다 (BEST_EFFORT 로 오므로 sensor_data QoS)
        self.create_subscription(LaserScan, c["lidar_topic"], self.on_scan, qos_profile_sensor_data, callback_group=getattr(self, "_sensor_group", None))   # 장소마다 켜고 끄므로 항상 받는다
        self.create_subscription(String, "/dock/cmd", self.on_cmd, 10)          ### 통합 (10-01) 토픽 이름
        self.pub = self.create_publisher(TwistStamped, "/cmd_vel", 10)
        self.pub_state = self.create_publisher(String, "/dock/state", 10)      ### 통합 (10-01) "장소:상태"
        self.nav = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self.nav_goal = None
        self.nav_done = None

        # 로그 CSV 는 START 마다 새로 연다 → ~/wmany/logs/dock_<장소>_<날짜_시간>.csv
        self.log_path = None
        self.log_f = None
        self.log = None

        self.state = IDLE
        self.t0 = self.t_dock = 0.0
        self.last_print = 0.0
        self._v = self._w = 0.0
        self.reacq_dir = 1.0
        self.t_reacq = 0.0
        self.t_align = 0.0
        self.odom_yaw = None
        self.align_goal = None
        self.align_psi0 = 0.0
        self.face_deg = None            ### 수정 (10-02) START ... turn=<도> 로 받은 회전량 (None 이면 안 돔)
        self.face_goal = None
        self.t_face = 0.0
        ### 수정 (09-30) PUSH 용 상태값
        self.odom_xy = None             # /odom 의 현재 위치 (x, y) [m] — PUSH 거리 재는 데 쓴다
        self.push_xy0 = None            # PUSH 를 시작한 순간의 위치 (x, y)
        self.dock_start_xy = None       ### 수정 (10-06) 이번 도킹을 시작한 자리 (SEARCH 들어간 순간 /odom 위치) — UNDOCK 목표
        self.undock_xy0 = None          ### 수정 (10-06) UNDOCK 시작 위치 · 방향 · 목표 거리
        self.undock_yaw0 = None
        self.undock_target = 0.0
        self.t_undock = 0.0
        self.rear_block = 0             ### 수정 (10-06) 뒤쪽 장애물 점 개수 (UNDOCK 중에만 셈)
        self.t_push = 0.0               # PUSH 를 시작한 시각 (push_timeout 판정용)
        self.push_why = ""              # PUSH 전에 DONE 이 될 이유 (ALIGN 결과) — 끝나면 같이 출력
        self.push_lidar = False         # (10-01) 이번 PUSH 를 라이다 면 거리로 멈추는지

        self.create_timer(0.1, self.loop)
        L = self.get_logger()
        L.info(f"dock 준비 | 장소 파일 {os.path.expanduser(c['sites_file'])} · 명령 /dock/cmd · 상태 /dock/state")
        if c["dry_run"]:
            L.info("  DRY RUN — 계산만 하고 안 움직인다  (실제 주행: -p dry_run:=false)")
        else:
            L.warn("  ★ 실제 주행 ★  멈출 때: Ctrl+C 또는 STOP 신호")
        self.list_sites()
        if c["site"]:
            self.select_site(c["site"])
        if c["autostart"] and self.site:
            self.start()
        else:
            L.info('  시작: ros2 topic pub -t 3 -r 2 /dock/cmd std_msgs/msg/String "{data: START harvest}"')

    # ───────────── 통합 (10-01) 장소 고르기 ─────────────
    def read_sites(self):
        """sites.yaml 을 읽어 {장소: {값}} 반환. 못 읽으면 None"""
        path = os.path.expanduser(self.base["sites_file"])
        try:
            with open(path) as f:
                d = yaml.safe_load(f) or {}
            return {str(k): (v or {}) for k, v in d.items()}
        except FileNotFoundError:
            self.get_logger().error(f"장소 파일 없음: {path}")
        except Exception as e:
            self.get_logger().error(f"장소 파일 읽기 실패: {path} — {e}")
        return None

    def list_sites(self):
        sites = self.read_sites()
        if sites is None:
            return
        for k, v in sites.items():
            self.get_logger().info(f"  장소 {k:8s} {'사용' if v.get('enabled', True) else '미설정'} · {v.get('desc', '')}")

    def select_site(self, name):
        """장소를 골라 self.c = 기본값 + sites.yaml[장소] 로 만든다. 성공하면 True
        (도킹 중에는 부르지 않는다 — on_cmd 에서 막는다)"""
        L = self.get_logger()
        sites = self.read_sites()
        if sites is None:
            return False
        if name not in sites:
            L.error(f"장소 '{name}' 없음 — sites.yaml 에 있는 장소: {', '.join(sites) or '없음'}")
            return False
        sv = sites[name]
        if not sv.get("enabled", True):
            L.error(f"장소 '{name}' 는 아직 미설정(enabled: false) — sites.yaml 을 채우고 enabled: true 로")
            return False
        c = dict(self.base)
        for k, v in sv.items():
            if k in ("enabled", "desc"):
                continue
            if k not in c:
                L.warn(f"  sites.yaml [{name}] 의 '{k}' 는 모르는 이름 — 무시 (오타 확인)")
                continue
            if v is None:                                  # null → nan (대기점 없음 · 라이다 목표 없음)
                v = float("nan")
            try:
                base_v = self.base[k]
                if isinstance(base_v, bool):
                    v = bool(v)
                elif isinstance(base_v, int):
                    v = int(v)
                elif isinstance(base_v, float):
                    v = float(v)
                else:
                    v = str(v)
            except (TypeError, ValueError):
                L.warn(f"  sites.yaml [{name}] 의 '{k}: {v}' 값 형식이 이상함 — 기본값 {self.base[k]} 사용")
                continue
            c[k] = v
        self.c = c
        self.site = name
        self.site_desc = sv.get("desc", "")
        # 장소에 따라 달라지는 것들 다시 계산
        self.obj = {c["far_id"]: self.square(c["far_size"]), c["near_id"]: self.square(c["near_size"])}
        self.use_nav = not (math.isnan(c["staging_x"]) or math.isnan(c["staging_y"]) or c["skip_staging"])
        self.teach_path = os.path.expanduser(c["teach_file"].replace("{site}", name))
        self.lidar_teach_path = os.path.expanduser(c["lidar_teach_file"].replace("{site}", name))
        self.load_teach(quiet=True)
        self.load_lidar_teach()
        L.info(f"■ 장소 [{name}] {self.site_desc}")
        L.info(f"  마커 : 먼 ID {c['far_id']} {c['far_size']*100:.0f}cm · 가까운 ID {c['near_id']} {c['near_size']*100:.0f}cm · "
               f"off_x {c['off_x']*100:+.1f}cm")
        L.info("  대기점 : " + (f"x {c['staging_x']:.3f}  y {c['staging_y']:.3f}" if self.use_nav
                                 else ("건너뜀 (skip_staging · 라우트서버가 데려다 줌)" if c["skip_staging"]
                                       else "없음 → Nav2 건너뛰고 지금 자리에서 도킹")))
        L.info(f"  목표 ({self.target_src}) : 거리 {self.dist_ref:.3f}m · 좌우 {self.lat_ref*100:+.1f}cm · "
               f"각도 {math.degrees(self.yaw_ref):+.1f}°")
        if not c["lidar_align"]:
            L.info("  정렬 : 카메라 마커 각도 + 오도메트리 (라이다 정렬 꺼짐)")
        elif math.isfinite(self.lidar_target):
            L.info(f"  정렬 : 라이다 · 목표 {self.lidar_target:+.1f}° ({self.lidar_src}) · 못 찾으면 카메라+오도메트리로 대체")
        else:
            L.warn("  정렬 : 라이다 목표 없음 → 카메라+오도메트리로 정렬 (라이다를 쓰려면 자로 맞춘 자세에서 LTEACH)")
        L.info(f"  마지막 직진 : {c['push_dist']*100:.1f}cm" if c["push_dist"] > 0 else "  마지막 직진 : 안 함")
        return True

    def open_log(self):
        """START 마다 새 로그 CSV"""
        try:
            if self.log_f:
                self.log_f.close()
        except Exception:
            pass
        log_dir = os.path.expanduser("~/wmany/logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, f"dock_{self.site}_{time.strftime('%m%d_%H%M%S')}.csv")
        self.log_f = open(self.log_path, "w", newline="")
        self.log = csv.writer(self.log_f)
        self.log.writerow(["t", "state", "src", "dist", "lat", "psi_deg", "alpha_deg", "v", "w"])
        self.get_logger().info(f"  로그 : {self.log_path}")

    @staticmethod
    def square(size):
        s = size / 2.0
        return np.array([[-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0]], np.float64)

    # ───────────── 입력 ─────────────
    def on_info(self, m):
        if self.K is None and m.k[0] > 0:
            self.K = np.array(m.k, np.float64).reshape(3, 3)
            self.D = np.array(m.d, np.float64)
            self.get_logger().info(f"camera_info 수신 fx={self.K[0,0]:.1f}")

    def on_odom(self, m):
        p = m.pose.pose.position
        self.odom_xy = (p.x, p.y)       ### 수정 (09-30) PUSH 거리 계산용 위치 저장
        q = m.pose.pose.orientation
        self.odom_yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))

    def ensure_K(self):
        if self.K is None and time.monotonic() - self.t_start_node > 3.0:
            self.K = np.array(K_DEFAULT, np.float64).reshape(3, 3)
            self.D = np.array(D_DEFAULT, np.float64)
            self.get_logger().warn("camera_info 없음 → 백업 캘리브레이션 값 사용 (fx 1760)")

    # ───────────── 티칭 ─────────────
    def load_teach(self, quiet=False):
        c = self.c
        self.dist_ref, self.lat_ref = c["final_dist"], c["final_lat"]
        self.yaw_ref = math.radians(c["final_yaw_deg"])
        self.target_src = "sites.yaml"
        try:
            with open(self.teach_path) as f:
                t = yaml.safe_load(f)
            self.dist_ref = float(t["dist"])
            self.lat_ref = float(t["lat"])
            self.yaw_ref = math.radians(float(t["yaw_deg"]))
            self.target_src = f"카메라 티칭 {t.get('time', '')}"
        except FileNotFoundError:
            if not quiet:
                self.get_logger().warn(f"티칭 파일 없음 ({self.teach_path}) → 기본 목표 사용")
        except Exception as e:
            self.get_logger().error(f"티칭 파일 읽기 실패: {e} → 파라미터 목표 사용")

    # ───────────── ### 수정 (10-02) 카메라 구독 켜고 끄기 ─────────────
    def cam_on(self):
        if self.img_sub is None:
            self.img_sub = self.create_subscription(Image, self.base["image_topic"], self.on_image, self.img_qos)
            self.get_logger().info("  카메라 영상 받기 시작")

    def cam_off(self):
        if self.img_sub is not None and self.teach_buf is None:
            self.destroy_subscription(self.img_sub)
            self.img_sub = None
            self.meas = {}
            self.get_logger().info("  카메라 영상 받기 끔 (대기 중 CPU 절약)")

    # ───────────── ### 수정 (10-06) UNDOCK — 도킹 자리에서 똑바로 후진 ─────────────
    def start_undock(self):
        c = self.c
        if self.odom_xy is None or self.odom_yaw is None:
            self.get_logger().error("UNDOCK 불가 — /odom 이 안 들어온다")
            self.pub_state.publish(String(data=f"{self.site or 'dock'}:FAILED"))
            return
        if self.dock_start_xy is not None:
            d = math.hypot(self.odom_xy[0] - self.dock_start_xy[0], self.odom_xy[1] - self.dock_start_xy[1])
            src = "도킹 시작점까지"
        else:
            d = c["undock_dist"]
            src = "시작점 모름 (dock 재시작) → 기본"
        self.undock_target = min(d, c["undock_max"])
        self.undock_xy0 = self.odom_xy
        self.undock_yaw0 = self.odom_yaw
        self.rear_block = 0
        self.t0 = self.t_undock = time.monotonic()
        self.get_logger().info(f"UNDOCK — {src} {self.undock_target:.2f}m 후진 ({c['undock_speed']:.2f}m/s · 방향 유지)")
        self.enter(UNDOCK)

    # ───────────── ### 수정 (10-02) 카메라 프로세스 켜고 끄기 ─────────────
    def cam_start(self):
        """START · TEACH 때 카메라를 켠다. 이미 누가 켜 둔 카메라가 있으면 그걸 쓰고 손대지 않는다"""
        if not self.base["cam_auto"]:
            return
        if self.cam_proc is not None and self.cam_proc.poll() is None:
            return
        if subprocess.run(["pgrep", "-f", "[c]amera_ros camera_node|[c]amera_node --ros-args"],
                          stdout=subprocess.DEVNULL).returncode == 0:
            self.get_logger().info("  카메라가 이미 켜져 있음 — 그대로 쓴다 (끝나도 안 끈다)")
            return
        log_dir = os.path.expanduser("~/wmany/logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, f"cam_{time.strftime('%m%d_%H%M%S')}.log")
        self.cam_log = open(path, "w")
        self.cam_proc = subprocess.Popen(CAM_CMD, stdout=self.cam_log, stderr=subprocess.STDOUT,
                                         start_new_session=True)
        self.get_logger().info(f"  카메라 켬 (로그 {path})")

    def cam_stop(self, wait=False):
        """dock 이 켠 카메라만 끈다. Ctrl+C 로 잘 안 꺼지므로 2초 뒤에도 살아 있으면 강제 종료"""
        proc, log = self.cam_proc, self.cam_log
        self.cam_proc = self.cam_log = None
        if proc is None:
            return

        def _kill():
            try:
                os.killpg(proc.pid, signal.SIGINT)
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            except ProcessLookupError:
                pass
            try:
                log.close()
            except Exception:
                pass
        if wait:
            _kill()
        else:
            threading.Thread(target=_kill, daemon=True).start()   # 기다리는 2초 동안 dock 이 멈추지 않게
        self.get_logger().info("  카메라 끔")

    def start_teach(self):
        if self.state not in (IDLE, DONE, FAILED):
            self.get_logger().warn("도킹 중에는 TEACH 불가 — STOP 후 다시")
            return
        self.teach_buf = []
        self.t_teach = time.monotonic()
        self.cam_start()                ### 수정 (10-02) 카메라 프로세스
        self.cam_on()                   ### 수정 (10-02)
        self.get_logger().info(f"TEACH — ID {self.c['near_id']} 를 {self.c['teach_frames']} 프레임 모읍니다. 로봇을 움직이지 마십시오")

    def check_teach(self):
        c = self.c
        buf = self.teach_buf
        if len(buf) >= c["teach_frames"]:
            n = len(buf)
            d = sum(b["dist"] for b in buf) / n
            la = sum(b["lat"] for b in buf) / n
            ps = sum(b["psi"] for b in buf) / n
            sd = math.sqrt(sum((b["lat"] - la) ** 2 for b in buf) / n)
            data = {"dist": round(d, 4), "lat": round(la, 4), "yaw_deg": round(math.degrees(ps), 2),
                    "lat_sd": round(sd, 4), "frames": n, "near_id": c["near_id"],
                    "near_size": c["near_size"], "time": time.strftime("%Y-%m-%d %H:%M:%S")}
            with open(self.teach_path, "w") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            self.teach_buf = None
            self.load_teach()
            if self.state in (IDLE, DONE, FAILED):
                self.cam_off()          ### 수정 (10-02)
                self.cam_stop()
            self.get_logger().info(
                f"■ TEACH 저장 → {self.teach_path} | 거리 {d:.3f}m · 좌우 {la*100:+.1f}cm · "
                f"각도 {math.degrees(ps):+.1f}° · 좌우 흔들림 ±{sd*100:.1f}cm")
            if sd > 0.005:
                self.get_logger().warn("  좌우 흔들림이 0.5cm 를 넘는다 — 마커가 화면 가장자리이거나 너무 가깝다. 다시 TEACH 권장")
        elif time.monotonic() - self.t_teach > 5.0:
            self.teach_buf = None
            if self.state in (IDLE, DONE, FAILED):
                self.cam_off()          ### 수정 (10-02)
                self.cam_stop()
            self.get_logger().error(
                f"TEACH 실패 — 5초 동안 ID {c['near_id']} 를 {len(buf)} 프레임밖에 못 봄 "
                "(너무 가깝거나 높이가 안 맞음). 조금 물러나서 다시")

    def on_cmd(self, m):
        """### 통합 (10-01) "명령 장소" 형식. 예) START harvest · LTEACH sorter · STOP · SITES"""
        parts = m.data.strip().split()
        if not parts:
            return
        cmd = parts[0].upper()
        arg = parts[1].lower() if len(parts) > 1 else ""
        ### 수정 (10-02) START <장소> turn=<도> — 도킹 전에 제자리 회전 (+ 왼쪽 · 반시계)
        turn = None
        for extra in parts[2:]:
            if extra.lower().startswith("turn="):
                try:
                    turn = float(extra.split("=", 1)[1])
                except ValueError:
                    self.get_logger().warn(f"turn 값이 숫자가 아님 '{extra}' — 회전 없이 진행")
        busy = self.state not in (IDLE, DONE, FAILED)
        if cmd == "STOP":
            self.cancel_nav()
            self.finish(IDLE, "수동 정지")
            return
        if cmd == "SITES":
            self.list_sites()
            return
        if cmd == "UNDOCK":
            ### 수정 (10-06) 장소와 무관 — 지금 자리에서 똑바로 후진
            if self.state == UNDOCK:
                return                                  # -t 3 으로 여러 번 와도 한 번만
            if busy:
                self.get_logger().warn(f"[{self.site}] {self.state} 진행 중 — UNDOCK 무시 (먼저 STOP)")
                return
            self.start_undock()
            return
        if cmd not in ("START", "TEACH", "LTEACH", "LRESET"):
            self.get_logger().warn(f"모르는 명령 '{m.data}' — START <장소> · STOP · UNDOCK · LTEACH <장소> · LRESET <장소> · TEACH <장소> · SITES")
            return
        if busy:
            # START 를 -t 3 으로 여러 번 보내므로, 같은 장소 START 가 또 오면 조용히 무시한다
            if not (cmd == "START" and arg in ("", self.site)):
                self.get_logger().warn(f"[{self.site}] {self.state} 진행 중 — '{m.data}' 무시 (먼저 STOP)")
            return
        if not arg:
            if self.site is None:
                self.get_logger().warn(f"장소를 붙여 주십시오 — 예) {cmd} harvest")
                return
            arg = self.site
        if arg != self.site or cmd == "START":       # START 때는 sites.yaml 을 다시 읽는다 (값 고친 것 반영)
            if not self.select_site(arg):
                self.pub_state.publish(String(data=f"{arg}:REJECTED"))
                return
        if cmd == "START":
            self.face_deg = turn
            self.start()
        elif cmd == "TEACH":
            self.start_teach()
        elif cmd == "LTEACH":
            self.start_lteach()
        elif cmd == "LRESET":
            self.reset_lteach()

    def on_image(self, m):
        age = (self.get_clock().now() - rclpy.time.Time.from_msg(m.header.stamp)).nanoseconds * 1e-9
        if not 0 <= age <= 0.3:
            self.stale += 1
            return
        self.process_image(self.bridge.imgmsg_to_cv2(m, desired_encoding="mono8"))

    def process_image(self, img):
        if self.first_img is None:
            self.first_img = time.monotonic()   ### 수정 (10-02) 카메라가 켜졌다는 표시
        if self.K is None:
            return
        if self.state in (IDLE, NAV, FACE, DONE, FAILED) and self.teach_buf is None:
            return
        if NEW_API:
            corners, ids, _ = self.detector.detectMarkers(img)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(img, self.dict, parameters=self.params)

        near_seen = False
        now = time.monotonic()
        if ids is not None:
            for cn, i in zip(corners, ids.flatten()):
                i = int(i)
                if i not in self.obj:
                    continue
                raw = self.solve(self.obj[i], cn.reshape(4, 2).astype(np.float64), marker_id=i)
                if raw is None:
                    continue
                meas = self.smooth(i, raw, now)
                self.meas[i] = (meas, now)
                self.n_det += 1
                if i == self.c["near_id"]:
                    near_seen = True
                    self.last_near = dict(meas)
                    if self.teach_buf is not None:
                        self.teach_buf.append(raw)
        self.near_streak = self.near_streak + 1 if near_seen else 0

    # ───────────── 자세 계산 ─────────────
    def solve(self, obj, img, marker_id=None):
        """IPPE 두 해를 모두 구해 LM 으로 다듬고, 물리적으로 맞는 것 중 오차 작은 해를 쓴다.
        (정면에 가까울 때 IPPE 가 '마커가 기울어진 해' 를 고르는 모호성 대비)"""
        try:
            _, rvs, tvs, _ = cv2.solvePnPGeneric(obj, img, self.K, self.D,
                                                 flags=cv2.SOLVEPNP_IPPE_SQUARE)
        except cv2.error:
            return None
        best = None
        for rv, tv in zip(rvs, tvs):
            try:
                rv, tv = cv2.solvePnPRefineLM(obj, img, self.K, self.D, rv.copy(), tv.copy())
            except cv2.error:
                pass
            R, _ = cv2.Rodrigues(rv)
            t = tv.flatten()
            p = -R.T @ t                # 마커 좌표계에서 카메라 위치 (x 오른쪽, z 마커 앞)
            if t[2] <= 0 or p[2] <= 0:
                continue
            pr, _ = cv2.projectPoints(obj, rv, tv, self.K, self.D)
            err = float(np.sqrt(((pr.reshape(4, 2) - img) ** 2).sum(1).mean()))
            fwd = R[2, :]               # 카메라 광축 방향 (마커 좌표계)
            m = {"dist": float(p[2]),
                 "lat": float(p[0]),                      # + 면 로봇이 정면선 오른쪽
                 "psi": math.atan2(fwd[0], -fwd[2])}      # + 면 로봇이 오른쪽을 보고 있음
            if best is None or err < best[0]:
                best = (err, m)
        return None if best is None else best[1]

    def smooth(self, mid, raw, now):
        """좌우·각도 잡음 줄이기 (지수평균). 끊겼다 다시 잡히면 새로 시작"""
        a = self.c["smooth"]
        prev = self.meas.get(mid)
        if prev is None or now - prev[1] > self.c["lost_timeout"] or a >= 1.0:
            return dict(raw)
        pm = prev[0]
        return {"dist": raw["dist"],
                "lat": pm["lat"] + a * (raw["lat"] - pm["lat"]),
                "psi": pm["psi"] + a * (raw["psi"] - pm["psi"])}

    # ───────────── Nav2 ─────────────
    def send_nav(self):
        c = self.c
        if not self.nav.wait_for_server(timeout_sec=3.0):
            self.finish(FAILED, "Nav2 가 안 떠 있다 (PC 에서 nav2_farm 확인)")
            return
        g = NavigateToPose.Goal()
        g.pose = PoseStamped()
        g.pose.header.frame_id = "map"
        g.pose.header.stamp = self.get_clock().now().to_msg()
        g.pose.pose.position.x = float(c["staging_x"])
        g.pose.pose.position.y = float(c["staging_y"])
        g.pose.pose.orientation.z = float(c["staging_qz"])
        g.pose.pose.orientation.w = float(c["staging_qw"])
        self.nav_done = None
        self.nav.send_goal_async(g).add_done_callback(self.on_nav_accepted)
        self.get_logger().info(f"Nav2 → 대기점 x {c['staging_x']:.2f} y {c['staging_y']:.2f}")

    def on_nav_accepted(self, fut):
        h = fut.result()
        if not h.accepted:
            self.nav_done = "rejected"
            return
        self.nav_goal = h
        h.get_result_async().add_done_callback(self.on_nav_result)

    def on_nav_result(self, fut):
        st = fut.result().status
        self.nav_done = "ok" if st == 4 else f"status {st}"
        self.nav_goal = None

    def cancel_nav(self):
        if self.nav_goal is not None:
            self.nav_goal.cancel_goal_async()
            self.nav_goal = None

    # ───────────── 상태 ─────────────
    def start(self):
        self.first_img = None
        self.dock_start_xy = None       ### 수정 (10-06) SEARCH 들어갈 때 다시 기록
        self.cam_start()                ### 수정 (10-02) 카메라 켜기 (FACE 회전과 동시에 켜진다)
        self.cam_on()                   ### 수정 (10-02) 도킹 시작할 때만 영상을 받는다
        self.open_log()                 ### 통합 (10-01) 도킹마다 새 로그
        self.aligned_by = ""
        self.t0 = time.monotonic()
        self.meas = {}
        self.near_streak = 0
        self.last_near = None
        ### 수정 (10-02) turn= 이 있으면 대기점 이동 없이 그 자리에서 돌고 → SEARCH
        if self.face_deg is not None and abs(self.face_deg) > self.c["face_tol_deg"]:
            if self.odom_yaw is None:
                self.get_logger().warn("/odom 이 아직 없음 — 회전 없이 SEARCH")
            else:
                self.face_goal = self.odom_yaw + math.radians(self.face_deg)
                self.t_face = time.monotonic()
                self.get_logger().info(f"제자리 회전 {self.face_deg:+.1f}° ({'왼' if self.face_deg > 0 else '오른'}쪽) 후 도킹")
                self.enter(FACE)
                return
        if self.face_deg is not None:
            self.get_logger().info(f"회전량 {self.face_deg:+.1f}° — 이미 맞음, 바로 도킹")
        if self.use_nav and self.face_deg is None:
            self.enter(NAV)
            self.send_nav()
        else:
            self.t_dock = time.monotonic()
            self.enter(SEARCH)

    def enter(self, s):
        if s == SEARCH and self.dock_start_xy is None and self.odom_xy is not None:
            self.dock_start_xy = self.odom_xy       ### 수정 (10-06) 도킹 시작점 = UNDOCK 으로 돌아올 자리
        self.state = s
        self.get_logger().info(f"── {s}")
        self.pub_state.publish(String(data=f"{self.site}:{s}"))

    def finish(self, s, why):
        self.drive(0.0, 0.0, force=True)
        self.state = s
        self.pub_state.publish(String(data=f"{self.site}:{s}"))
        self.cam_off()                  ### 수정 (10-02) DONE · FAILED · STOP 이면 영상 끊기
        if self.teach_buf is None:
            self.cam_stop()             ### 수정 (10-02) 카메라도 끈다
        el = time.monotonic() - self.t0 if self.t0 else 0.0
        self.get_logger().info(f"■ [{self.site}] {s} — {why}  ({el:.1f}s)")
        if s == DONE and self.last_near:
            m = self.last_near
            ok_lat = abs(m["lat"] - self.lat_ref) <= self.c["tol_lat"]
            # 라이다로 정렬했으면 각도 판정은 라이다가 이미 했다 → 카메라 각도로는 좌우만 본다
            ok = ok_lat if self.aligned_by == "lidar" else (
                ok_lat and abs(math.degrees(m["psi"] - self.yaw_ref)) <= self.c["tol_yaw_deg"])
            self.get_logger().info(
                f"  최종: 거리 {m['dist']:.3f}m ({(m['dist']-self.dist_ref)*100:+.1f}cm)  "
                f"좌우 {m['lat']*100:+.1f}cm ({(m['lat']-self.lat_ref)*100:+.1f}cm)  "
                f"각도 {math.degrees(m['psi']):+.1f}° ({math.degrees(m['psi']-self.yaw_ref):+.1f}°)  → "
                f"{'정렬 OK' if ok else '허용오차 밖'}"
                + ("  (각도는 라이다로 맞춤 — 카메라 각도는 참고만)" if self.aligned_by == "lidar" else "")
                + "  ※ 괄호 = 목표와의 차이 · 정렬·직진 전 마지막으로 본 마커 기준")

    # ───────────── ### 수정 (10-01) 라이다 ─────────────
    def on_scan(self, m):
        """스캔 1장 → 정면 면 각도를 계산해 lidar_buf 에 쌓는다 (면을 못 찾은 스캔은 안 쌓는다)"""
        if self.state == UNDOCK:
            ### 수정 (10-06) 후진 중 뒤쪽 ±25° 에 0.20 ~ undock_rear_stop 사이 점이 몇 개인지
            cu = self.c
            rear = math.radians(cu["lidar_front_deg"]) + math.pi
            n = 0
            for i, r in enumerate(m.ranges):
                if not math.isfinite(r) or r < 0.20 or r > cu["undock_rear_stop"]:
                    continue
                a = m.angle_min + i * m.angle_increment
                if abs(math.atan2(math.sin(a - rear), math.cos(a - rear))) <= math.radians(25):
                    n += 1
            self.rear_block = n
            return
        ### 수정 (10-02) 도킹 접근~정렬~직진 · LTEACH 때만 계산한다 (대기 중 RANSAC 이 CPU 를 먹었다)
        if self.state not in (TRACK, FINE, REACQ, ALIGN, PUSH) and self.lteach_t0 is None:
            return
        c = self.c
        front = math.radians(c["lidar_front_deg"])
        half = math.radians(c["lidar_sector_deg"])
        pts = []
        for i, r in enumerate(m.ranges):
            if not math.isfinite(r) or r < c["lidar_min_r"] or r > c["lidar_max_r"]:
                continue
            a = m.angle_min + i * m.angle_increment
            d = math.atan2(math.sin(a - front), math.cos(a - front))   # 정면 기준 -180~180
            if abs(d) <= half:
                pts.append((r * math.cos(d), r * math.sin(d)))
        res = fit_face(pts, c["lidar_inlier_tol"], c["lidar_min_inliers"], 150)
        if res:
            self.lidar_buf.append((time.monotonic(), res[0], res[1]))

    def lidar_mean_since(self, t0, n):
        """t0 이후 들어온 측정 중 마지막 n 개의 (평균 각도, 표준편차, 평균 거리). 모자라면 None"""
        v = [(phi, dist) for (t, phi, dist) in self.lidar_buf if t >= t0]
        if len(v) < n:
            return None
        v = v[-n:]
        mu = sum(p for p, _ in v) / n
        sd = math.sqrt(sum((p - mu) ** 2 for p, _ in v) / n)
        return mu, sd, sum(d for _, d in v) / n

    def lidar_fresh(self, max_age=1.0):
        """최근 max_age 초 안에 면을 찾은 스캔이 있나"""
        return bool(self.lidar_buf) and time.monotonic() - self.lidar_buf[-1][0] <= max_age

    def load_lidar_teach(self):
        """LTEACH 파일이 있으면 그 목표 각도를 쓴다 (없으면 파라미터 lidar_target_deg)"""
        try:
            with open(self.lidar_teach_path) as f:
                t = yaml.safe_load(f)
            self.lidar_target = float(t["target_deg"])
            self.lidar_src = f"LTEACH {t.get('time', '')}"
        except FileNotFoundError:
            self.lidar_target = self.c["lidar_target_deg"]
            self.lidar_src = "sites.yaml"
        except Exception as e:
            self.lidar_target = self.c["lidar_target_deg"]
            self.lidar_src = "sites.yaml"
            self.get_logger().error(f"라이다 티칭 파일 읽기 실패: {e} → 기본값 {self.lidar_target:+.1f}°")

    def start_lteach(self):
        if self.state not in (IDLE, DONE, FAILED):
            self.get_logger().warn("도킹 중에는 LTEACH 불가 — STOP 후 다시")
            return
        if not self.lidar_fresh(2.0):
            self.get_logger().warn("최근 2초 동안 라이다로 면을 못 찾음 — 로봇 정면 0.6m 안에 면이 있는지 · bringup 확인")
            return
        self.lteach_t0 = time.monotonic()
        self.get_logger().info(f"[{self.site}] LTEACH — 라이다 {self.c['lidar_teach_frames']}장을 모읍니다. 로봇을 움직이지 마십시오 "
                               "(로봇 정면 ±30° · 0.6m 안에 사람이 없어야 한다)")

    def check_lteach(self):
        c = self.c
        r = self.lidar_mean_since(self.lteach_t0, c["lidar_teach_frames"])
        if r is None:
            if time.monotonic() - self.lteach_t0 > 10.0:
                got = len([1 for (t, _, _) in self.lidar_buf if t >= self.lteach_t0])
                self.lteach_t0 = None
                self.get_logger().error(f"LTEACH 실패 — 10초 동안 면을 {got}장밖에 못 찾음 (라이다 높이에 면이 있는지 · bringup 확인)")
            return
        mu, sd, dist = r
        self.lteach_t0 = None
        if sd > c["lidar_teach_max_sd"]:
            self.get_logger().error(f"LTEACH 저장 안 함 — 흔들림 ±{sd:.1f}° 가 {c['lidar_teach_max_sd']:.1f}° 보다 큼 "
                                    "(주변 사람 · 면이 너무 좁음). 비키고 다시")
            return
        data = {"target_deg": round(mu, 2), "sd_deg": round(sd, 2), "dist_m": round(dist, 4),
                "frames": c["lidar_teach_frames"], "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        os.makedirs(os.path.dirname(self.lidar_teach_path), exist_ok=True)
        with open(self.lidar_teach_path, "w") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        old = self.lidar_target
        old_s = f"{old:+.1f}°" if math.isfinite(old) else "없음"
        self.load_lidar_teach()
        self.get_logger().info(f"■ [{self.site}] LTEACH 저장 → {self.lidar_teach_path} | 목표 {old_s} → {mu:+.2f}° "
                               f"(흔들림 ±{sd:.2f}° · 면까지 {dist:.3f}m)")

    def reset_lteach(self):
        if os.path.exists(self.lidar_teach_path):
            bak = self.lidar_teach_path + time.strftime(".bak_%m%d_%H%M%S")
            os.rename(self.lidar_teach_path, bak)          # 지우지 않고 이름만 바꿔 둔다
            self.get_logger().info(f"LRESET — 티칭 파일을 {bak} 로 치움")
        self.load_lidar_teach()
        self.get_logger().info(f"[{self.site}] LRESET — 라이다 목표 {self.lidar_target:+.1f}° ({self.lidar_src})"
                               + ("" if math.isfinite(self.lidar_target) else " → 라이다 정렬 안 함 (카메라+오도메트리)"))

    def start_align(self, psi_now, why, allow_lidar=True):
        """도착 자세에서 제자리 회전 시작.  allow_lidar=False 면 라이다를 건너뛰고 바로 예전 방식
        (10-01) 라이다를 쓸 수 있으면 라이다 정렬(l_meas → l_turn 반복), 아니면 아래 예전 방식(카메라 각도 + 오도메트리)"""
        c = self.c
        ### 수정 (10-01) 라이다 정렬 먼저
        if (allow_lidar and c["lidar_align"] and math.isfinite(self.lidar_target)
                and self.odom_yaw is not None and self.lidar_fresh()):
            self.drive(0.0, 0.0, force=True)
            self.align_mode = "l_meas"
            self.aligned_by = "lidar"
            self.l_iter = 0
            self.l_first = None
            self.l_meas_t0 = time.monotonic()
            self.align_why = why
            self.t_align = time.monotonic()
            self.get_logger().info(f"{why} · 라이다 정렬 시작 (목표 {self.lidar_target:+.1f}° · {self.lidar_src})")
            self.enter(ALIGN)
            return
        if allow_lidar and c["lidar_align"]:
            self.get_logger().warn("라이다 목표 없음 (LTEACH 전) → 카메라 각도 + 오도메트리로 정렬"
                                   if not math.isfinite(self.lidar_target) else
                                   "라이다로 면을 못 찾음 (최근 1초 스캔 없음) → 카메라 각도 + 오도메트리로 대체")
        self.align_mode = "odom"
        self.aligned_by = "odom"
        delta = self.yaw_ref - psi_now                              # + 면 오른쪽(시계방향)으로 더 돌아야 함
        if abs(math.degrees(delta)) <= c["align_tol_deg"]:
            self.done_or_push(f"{why} · 각도 이미 맞음")      ### 수정 (09-30) 바로 DONE → PUSH 거쳐 DONE
            return
        if self.odom_yaw is None:
            self.finish(DONE, f"DOCK_STABLE ({why} · /odom 없음 → 각도 맞추기 생략)")
            return
        # 마커 각도 psi 는 시계방향 +, 오도메트리 yaw 는 반시계방향 + → 부호 반대
        self.align_goal = self.odom_yaw - delta
        self.align_psi0 = psi_now
        self.t_align = time.monotonic()
        self.get_logger().info(
            f"{why} · 현재 각도 {math.degrees(psi_now):+.1f}° → 목표 {math.degrees(self.yaw_ref):+.1f}° "
            f"({'오른' if delta > 0 else '왼'}쪽으로 {abs(math.degrees(delta)):.1f}° 회전)")
        self.enter(ALIGN)

    # ───────────── ### 수정 (09-30) 정렬 후 마지막 직진 (PUSH) ─────────────
    def done_or_push(self, why):
        """ALIGN 이 '제대로' 끝났을 때 부른다 → PUSH 할 수 있으면 PUSH 시작, 아니면 바로 DONE.

        이 함수를 부르는 곳 (= PUSH 하는 경우) 은 딱 두 군데:
          ① start_align() — 도착했을 때 각도가 이미 허용오차 안
          ② loop() 의 ALIGN — 오도메트리 회전이 목표 각도에 도달
          (FINE 에서 목표 근처(+2cm)에서 마커를 놓친 경우도 결국 start_align 을 거치므로 여기로 온다)
        PUSH 하지 않는 경우 (이 함수를 안 부르고 바로 finish):
          · 각도 맞추기 시간 초과 — 각도가 덜 맞은 채 앞으로 가면 비스듬히 부딪힐 수 있다
          · /odom 없음            — 거리를 잴 수 없다
          · FAILED 전부           — 위치가 확실하지 않다
        """
        c = self.c
        ### 수정 (10-01) push_to_dist(라이다 거리) 가 있으면 그걸로, 없으면 push_dist(오도메트리) 로
        self.push_lidar = False
        if math.isfinite(c["push_to_dist"]) and self.lidar_fresh(0.5):
            now_d = self.lidar_buf[-1][2]
            if now_d <= c["push_to_dist"]:
                self.finish(DONE, f"DOCK_STABLE ({why} · 면까지 {now_d:.3f}m ≤ 목표 {c['push_to_dist']:.3f}m → 직진 불필요)")
                return
            self.push_lidar = True
        elif math.isfinite(c["push_to_dist"]):
            self.get_logger().warn("라이다로 면 거리를 못 읽음 → 마지막 직진은 push_dist(오도메트리)로")
        if not self.push_lidar and c["push_dist"] <= 0.0:   # 0 이면 기능 끔 → 예전과 똑같이 DONE
            self.finish(DONE, f"DOCK_STABLE ({why})")
            return
        if self.odom_xy is None:                      # /odom 위치가 한 번도 안 들어옴 → 잴 수 없으니 생략
            self.finish(DONE, f"DOCK_STABLE ({why} · /odom 위치 없음 → 마지막 직진 생략)")
            return
        if c["dry_run"]:                              # dry_run 은 바퀴가 안 도니 거리가 안 늘어난다 → 생략
            self.finish(DONE, f"DOCK_STABLE ({why} · DRY RUN → 마지막 직진 생략)")
            return
        self.drive(0.0, 0.0, force=True)              # 회전 끝난 직후 잔여 회전을 확실히 끊고 시작
        self.push_xy0 = self.odom_xy                  # 출발점 기억 — 여기서부터 직선거리를 잰다
        self.t_push = time.monotonic()
        self.push_why = why
        if self.push_lidar:
            self.get_logger().info(
                f"{why} · 마지막 직진 시작 — 라이다 면 거리 {self.lidar_buf[-1][2]:.3f}m → {c['push_to_dist']:.3f}m 까지 "
                f"(최대 {c['push_max']*100:.0f}cm · 속도 {c['push_speed']:.3f} m/s)")
        else:
            self.get_logger().info(
                f"{why} · 마지막 직진 {c['push_dist']*100:.1f}cm 시작 (속도 {c['push_speed']:.3f} m/s · 마커 안 봄)")
        self.enter(PUSH)

    def push_moved(self):
        """PUSH 시작점에서 지금까지 움직인 직선거리 [m] (/odom 기준)"""
        if self.odom_xy is None or self.push_xy0 is None:
            return 0.0
        return math.hypot(self.odom_xy[0] - self.push_xy0[0], self.odom_xy[1] - self.push_xy0[1])

    def get(self, mid):
        """lost_timeout 안의 측정만 돌려준다"""
        e = self.meas.get(mid)
        if e is None or time.monotonic() - e[1] > self.c["lost_timeout"]:
            return None
        return e[0]

    # ───────────── 정면선 따라가기 ─────────────
    @staticmethod
    def bearing(lat_m, dist, psi):
        """카메라 화면에서 마커 중심 방향 [rad] (+ 면 화면 오른쪽)"""
        return math.atan2(-lat_m, dist) - psi

    def pursuit(self, lat, dist, psi, lat_m=None, bmax=None, close=False):
        """정면선 따라가기 → (v, w, alpha)
        lat, dist, psi : 카메라 기준 (lat 은 도킹 정면선 기준)
        lat_m          : 보고 있는 마커 자체 기준 좌우 (화면 유지 판단용)
        close          : (10-01) 근접 구간 — 제자리 회전 없이 천천히 전진, 회전은 close_w_max 안으로만"""
        c = self.c
        if close:
            v, w, alpha = self.pursuit(lat, dist, psi, lat_m, bmax, close=False)
            v = max(v, c["v_min"])                          # 제자리 회전(v=0) 대신 계속 천천히 전진
            w = clamp(w, -c["close_w_max"], c["close_w_max"])   # 튀는 각도에 크게 돌지 않게
            return v, w, alpha
        if lat_m is None:
            lat_m = lat
        # ① 마커를 화면 안에 붙잡아 둔다
        b = self.bearing(lat_m, dist, psi)
        if bmax is None:
            bmax = c["bearing_max_deg"]
        if abs(math.degrees(b)) > bmax:
            return 0.0, -c["k_w"] * b, b                    # 마커 쪽으로 제자리 회전
        # ② 바퀴 축 중심 위치로 환산 (카메라는 축보다 cam_offset 앞)
        d = c["cam_offset"]
        # 티칭한 자세에서의 바퀴 축 좌우 위치를 기준선으로 쓴다
        #   (도착 후 ALIGN 으로 yaw_ref 만큼 돌면 카메라 좌우가 lat_ref 가 되도록)
        xc_ref = self.lat_ref - d * math.sin(self.yaw_ref)
        xc = lat - d * math.sin(psi) - xc_ref
        remain = max(0.0, dist - self.dist_ref)
        L = clamp(c["look_gain"] * remain, c["look_min"], c["look_max"])
        target = math.atan2(-xc, L)                         # 정면선 위 L 앞의 점
        alpha = math.atan2(math.sin(target - psi), math.cos(target - psi))   # + 면 목표가 오른쪽
        if abs(math.degrees(alpha)) > c["turn_only_deg"]:
            return 0.0, -c["k_w"] * alpha, alpha            # 제자리 회전
        v = clamp(c["k_v"] * remain, c["v_min"], c["v_max"])
        Ld = math.hypot(xc, L)
        w = -v * 2.0 * math.sin(alpha) / Ld                 # 오른쪽 목표 → 시계방향(-)
        return v, w, alpha

    # ───────────── 제어 루프 10 Hz ─────────────
    def loop(self):
        c = self.c
        s = self.state
        self.ensure_K()
        if self.teach_buf is not None:
            self.check_teach()
        if self.lteach_t0 is not None:          ### 수정 (10-01) 라이다 티칭 중
            self.check_lteach()
        if s in (IDLE, DONE, FAILED):
            return

        if s == NAV:
            if time.monotonic() - self.t0 > c["nav_timeout"]:
                self.cancel_nav()
                self.finish(FAILED, f"대기점 이동 시간 초과 {c['nav_timeout']:.0f}s")
            elif self.nav_done == "ok":
                self.get_logger().info("대기점 도착")
                self.t_dock = time.monotonic()
                self.meas = {}
                self.enter(SEARCH)
            elif self.nav_done is not None:
                self.finish(FAILED, f"Nav2 실패 ({self.nav_done})")
            return

        if s == UNDOCK:
            ### 수정 (10-06) 방향을 유지하며 똑바로 후진 → 목표 거리 도달하면 "<장소>:UNDOCKED"
            moved = math.hypot(self.odom_xy[0] - self.undock_xy0[0], self.odom_xy[1] - self.undock_xy0[1])
            if moved >= self.undock_target - 0.01:
                self.drive(0.0, 0.0, force=True)
                self.state = IDLE
                self.dock_start_xy = None
                self.pub_state.publish(String(data=f"{self.site or 'dock'}:UNDOCKED"))
                self.get_logger().info(f"■ UNDOCKED — {moved:.2f}m 후진 완료 ({time.monotonic() - self.t_undock:.1f}s)")
                return
            if self.rear_block >= 3:
                self.finish(FAILED, f"UNDOCK 정지 — 뒤쪽 {c['undock_rear_stop']:.2f}m 안에 장애물 ({moved:.2f}/{self.undock_target:.2f}m)")
                return
            if time.monotonic() - self.t_undock > self.undock_target / max(c["undock_speed"], 0.01) + 8.0:
                self.finish(FAILED, f"UNDOCK 시간 초과 ({moved:.2f}/{self.undock_target:.2f}m)")
                return
            err = math.atan2(math.sin(self.undock_yaw0 - self.odom_yaw), math.cos(self.undock_yaw0 - self.odom_yaw))
            self.drive(-abs(c["undock_speed"]), clamp(c["k_w"] * err, -0.1, 0.1))
            return

        if s == FACE:
            ### 수정 (10-02) 오도메트리로 정해진 각도만큼 제자리 회전 → 끝나면 SEARCH
            err = math.atan2(math.sin(self.face_goal - self.odom_yaw),
                             math.cos(self.face_goal - self.odom_yaw))    # + 면 반시계(왼쪽)로 더
            timeout = time.monotonic() - self.t_face > c["face_timeout"]
            if abs(math.degrees(err)) <= c["face_tol_deg"] or timeout:
                self.drive(0.0, 0.0, force=True)
                if timeout:
                    self.get_logger().warn(f"회전 시간 초과 (남은 {math.degrees(err):+.1f}°) — 그대로 SEARCH")
                else:
                    self.get_logger().info("회전 완료")
                self.t_dock = time.monotonic()
                self.meas = {}
                self.enter(SEARCH)
                return
            w = clamp(c["k_w"] * err, -c["w_max"], c["w_max"])
            if abs(w) < 0.08:
                w = math.copysign(0.08, w)
            self.drive(0.0, w)
            return

        if time.monotonic() - self.t_dock > c["dock_timeout"]:
            self.finish(FAILED, f"도킹 시간 초과 {c['dock_timeout']:.0f}s")
            return

        far = self.get(c["far_id"])
        near = self.get(c["near_id"])
        v = w = 0.0
        src, info = "-", None

        if s == SEARCH:
            if near or far:
                self.enter(TRACK)
                return
            if self.first_img is None:
                ### 수정 (10-02) 카메라가 아직 안 켜졌으면 돌지 않고 기다린다
                if time.monotonic() - self.t0 > c["cam_wait_s"]:
                    self.finish(FAILED, f"카메라 영상이 {c['cam_wait_s']:.0f}초 안에 안 옴 (로그 ~/wmany/logs/cam_*.log)")
                    return
                w = 0.0
            else:
                w = c["w_search"]

        elif s == TRACK:
            if near and self.near_streak >= c["switch_frames"] and near["dist"] <= c["switch_dist"]:
                self.get_logger().info(
                    f"ID {c['near_id']} 연속 {self.near_streak}프레임 · {near['dist']:.2f}m → 작은 마커로 전환")
                self.enter(FINE)
                return
            if far:
                if far["dist"] < c["far_min_dist"] and not near:
                    self.finish(FAILED, f"ID {c['near_id']} 를 못 찾은 채 {far['dist']:.2f}m 까지 옴")
                    return
                src, info = str(c["far_id"]), (far["lat"] - c["off_x"], far["dist"], far["psi"])
                v, w, alpha = self.pursuit(*info, lat_m=far["lat"], bmax=c["bearing_max_far_deg"])
            elif near:                                  # 11 이 안 보이면 12 로라도 접근
                src, info = str(c["near_id"]), (near["lat"], near["dist"], near["psi"])
                v, w, alpha = self.pursuit(*info)
            else:
                self.enter(SEARCH)
                return

        elif s == FINE:
            if near:
                if near["dist"] <= self.dist_ref + abs(self._v) * c["stop_lead_s"]:
                    self.drive(0.0, 0.0, force=True)
                    self.start_align(near["psi"], f"거리 {near['dist']:.3f}m 도달")
                    return
                src, info = str(c["near_id"]), (near["lat"], near["dist"], near["psi"])
                v, w, alpha = self.pursuit(*info, close=near["dist"] < c["close_dist"])   ### 수정 (10-01) 근접 구간
            else:
                ln = self.last_near
                if ln and ln["dist"] <= c["near_lost_dist"]:
                    # 수확로봇 바로 앞 — 눈감고 가지도, 돌며 찾지도 않는다
                    if ln["dist"] <= self.dist_ref + c["lost_margin"]:
                        self.drive(0.0, 0.0, force=True)
                        self.start_align(ln["psi"], f"마지막 {ln['dist']:.3f}m 에서 놓침 (목표 {self.dist_ref:.3f}m 근처)")
                    else:
                        self.finish(FAILED, f"가까이서 ID {c['near_id']} 놓침 (마지막 {ln['dist']:.3f}m · "
                                            f"목표 {self.dist_ref:.3f}m) — 높이·조명 확인")
                    return
                if far:
                    self.get_logger().warn("작은 마커 놓침 → 큰 마커로 복귀")
                    self.near_streak = 0
                    self.enter(TRACK)
                    return
                # 멀리서 놓침 → 마지막으로 본 방향으로 돌며 다시 찾기
                self.reacq_dir = 1.0
                if ln:
                    self.reacq_dir = 1.0 if self.bearing(ln["lat"], ln["dist"], ln["psi"]) >= 0 else -1.0
                self.get_logger().warn(
                    f"작은 마커 놓침 ({ln['dist']:.3f}m) → {'오른' if self.reacq_dir > 0 else '왼'}쪽으로 돌며 다시 찾기"
                    if ln else "작은 마커 놓침 → 다시 찾기")
                self.t_reacq = time.monotonic()
                self.enter(REACQ)
                return

        elif s == ALIGN and self.align_mode == "l_meas":
            # ### 수정 (10-01) 라이다 정렬 ① 멈춘 상태에서 라이다 각도를 잰다
            w = 0.0
            r = self.lidar_mean_since(self.l_meas_t0 + c["lidar_settle_s"], c["lidar_avg_n"])
            if r is None:
                if time.monotonic() - self.l_meas_t0 > c["lidar_wait_s"] + c["lidar_settle_s"]:
                    if self.l_iter == 0:                     # 처음부터 못 잼 → 예전 방식으로 대체
                        self.get_logger().warn("라이다 측정 실패 → 카메라 각도 + 오도메트리로 대체")
                        ln = self.last_near                   # 마지막으로 본 2cm 마커 각도로 예전 방식 회전
                        self.start_align(ln["psi"] if ln else self.yaw_ref, self.align_why + " · 라이다 실패",
                                         allow_lidar=False)
                    else:                                     # 돌다가 끊김 → 더 돌지 않고 끝 (PUSH 없음)
                        self.finish(DONE, f"DOCK_STABLE ({self.align_why} · 라이다 끊김 · PUSH 생략)")
                    return
            else:
                mu, sd, dist = r
                err = self.lidar_target - mu                 # + 면 반시계(왼쪽)로 더 돌아야 함
                if self.l_first is None:
                    self.l_first = mu
                self.get_logger().info(
                    f"[라이다 {self.l_iter + 1}] 면 각도 {mu:+.1f}° (±{sd:.1f}) · 목표 {self.lidar_target:+.1f}° · "
                    f"차이 {err:+.1f}° · 면까지 {dist:.3f}m")
                if abs(err) <= c["lidar_tol_deg"]:
                    self.done_or_push(f"{self.align_why} · 라이다 정렬 {self.l_first:+.1f}° → {mu:+.1f}° "
                                      f"(목표 {self.lidar_target:+.1f}°)")
                    return
                if c["dry_run"]:
                    self.finish(DONE, f"DOCK_STABLE (DRY RUN · 라이다 {mu:+.1f}° → "
                                      f"{'왼' if err > 0 else '오른'}쪽으로 {abs(err):.1f}° 돌아야 함)")
                    return
                if self.l_iter >= c["lidar_max_iter"]:
                    self.finish(DONE, f"DOCK_STABLE ({self.align_why} · 라이다 정렬 {c['lidar_max_iter']}회 초과 · "
                                      f"남은 {err:+.1f}° · PUSH 생략)")
                    return
                # ② 그 차이만큼 오도메트리로 돈다
                self.align_goal = self.odom_yaw + math.radians(err)
                self.l_iter += 1
                self.l_turn_t0 = time.monotonic()
                self.align_mode = "l_turn"
                self.get_logger().info(f"  → {'왼' if err > 0 else '오른'}쪽으로 {abs(err):.1f}° 회전")

        elif s == ALIGN and self.align_mode == "l_turn":
            # ### 수정 (10-01) 라이다 정렬 ② 오도메트리로 정해진 각도만큼 돌고, 멈추면 ① 로 돌아가 다시 잰다
            err = math.atan2(math.sin(self.align_goal - self.odom_yaw),
                             math.cos(self.align_goal - self.odom_yaw))    # + 면 반시계(왼쪽)로 더
            if (abs(math.degrees(err)) <= c["lidar_turn_tol_deg"]
                    or time.monotonic() - self.l_turn_t0 > c["lidar_turn_timeout"]):
                self.drive(0.0, 0.0, force=True)
                self.align_mode = "l_meas"
                self.l_meas_t0 = time.monotonic()            # 지금부터 settle 지난 스캔만 쓴다
                return
            w = clamp(c["k_w"] * err, -0.15, 0.15)
            if abs(w) < 0.05:
                w = math.copysign(0.05, w)
            alpha = err

        elif s == ALIGN:
            # 오도메트리로 제자리 회전 (마커를 놓쳐도 계속 된다)
            err = math.atan2(math.sin(self.align_goal - self.odom_yaw),
                             math.cos(self.align_goal - self.odom_yaw))    # + 면 반시계(왼쪽)로 더
            if abs(math.degrees(err)) <= c["align_tol_deg"]:
                turned = math.degrees(self.yaw_ref - self.align_psi0)
                self.done_or_push(f"각도 {turned:+.1f}° 회전 완료")   ### 수정 (09-30) 바로 DONE → PUSH 거쳐 DONE
                return
            if time.monotonic() - self.t_align > c["align_timeout"]:
                self.finish(DONE, f"DOCK_STABLE (각도 맞추기 시간 초과 · 남은 {math.degrees(err):+.1f}°)")
                return
            w = clamp(c["k_w"] * err, -0.15, 0.15)
            if abs(w) < 0.05:
                w = math.copysign(0.05, w)
            alpha = err
            if near:
                src, info = str(c["near_id"]), (near["lat"], near["dist"], near["psi"])

        elif s == PUSH:
            # ### 수정 (09-30) 마지막 직진 — 마커는 보지 않고 /odom 이동거리로만 판단
            moved = self.push_moved()
            if self.push_lidar:
                # ### 수정 (10-01) 라이다 면 거리로 멈춤. 스캔이 약 0.2초 늦으니 그만큼(속도×0.2) 미리 멈춘다
                if self.lidar_fresh(0.5):
                    d_now = self.lidar_buf[-1][2]
                    if d_now <= c["push_to_dist"] + c["push_speed"] * 0.2:
                        self.finish(DONE, f"DOCK_STABLE ({self.push_why} · 라이다 면 거리 {d_now:.3f}m 에서 정지 "
                                          f"(목표 {c['push_to_dist']:.3f}m · 직진 {moved*100:.1f}cm))")
                        return
                else:                                            # 라이다가 끊김 → 더 가지 않는다
                    self.finish(DONE, f"DOCK_STABLE ({self.push_why} · 직진 중 라이다 끊김 · {moved*100:.1f}cm 에서 멈춤)")
                    return
                if moved >= c["push_max"]:                       # 안전 상한
                    self.finish(DONE, f"DOCK_STABLE ({self.push_why} · 직진 상한 {c['push_max']*100:.0f}cm 도달 · "
                                      f"라이다 면 거리 {self.lidar_buf[-1][2]:.3f}m)")
                    return
            elif moved >= c["push_dist"]:                        # 목표 거리만큼 갔다 → 정지 · DONE
                self.finish(DONE, f"DOCK_STABLE ({self.push_why} · 마지막 직진 {moved*100:.1f}cm 완료)")
                return
            # 라이다 직진은 최대 push_max 만큼 가므로 제한 시간도 그만큼 늘린다 (8cm ÷ 0.02m/s = 4초 + 1초)
            t_lim = (max(c["push_timeout"], c["push_max"] / max(c["push_speed"], 1e-3) + 1.0)
                     if self.push_lidar else c["push_timeout"])
            if time.monotonic() - self.t_push > t_lim:           # 제시간에 못 감 → 더 밀지 않고 정지
                self.finish(DONE, f"DOCK_STABLE ({self.push_why} · 마지막 직진 시간 초과 · "
                                  f"{moved*100:.1f}cm 에서 멈춤 — 걸림 확인)")
                return
            v = c["push_speed"]                                  # 일정 속도로 직진
            w = 0.0                                              # 방향은 ALIGN 에서 맞춘 그대로 (회전 없음)
            alpha = 0.0
            if near:                                             # 마커가 읽히면 로그에만 남긴다 (제어엔 안 씀)
                src, info = str(c["near_id"]), (near["lat"], near["dist"], near["psi"])

        elif s == REACQ:
            if near:
                self.enter(FINE)
                return
            if far:
                self.near_streak = 0
                self.enter(TRACK)
                return
            if time.monotonic() - self.t_reacq > c["reacq_timeout"]:
                ln = self.last_near
                self.finish(FAILED, "두 마커 모두 놓침"
                            + (f" (마지막 12 거리 {ln['dist']:.3f}m)" if ln else ""))
                return
            w = -self.reacq_dir * c["w_reacq"]           # 마커가 오른쪽(+)이었으면 시계방향(-)

        self.drive(v, w)
        self.status(src, info, v, w, alpha if info else 0.0)

    # ───────────── 출력 ─────────────
    def drive(self, v, w, force=False):
        c = self.c
        v = clamp(v, -c["v_max"], c["v_max"])
        w = clamp(w, -c["w_max"], c["w_max"])
        self._v, self._w = v, w
        if c["dry_run"] and not force:
            return
        t = TwistStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = "base_link"
        t.twist.linear.x = float(v)
        t.twist.angular.z = float(w)
        self.pub.publish(t)

    def status(self, src, info, v, w, alpha):
        now = time.monotonic()
        v, w = self._v, self._w
        row = [f"{now - self.t0:.2f}", self.state, src]
        row += ([f"{info[1]:.4f}", f"{info[0]:.4f}", f"{math.degrees(info[2]):.2f}",
                 f"{math.degrees(alpha):.2f}"] if info else ["", "", "", ""])
        row += [f"{v:.3f}", f"{w:.3f}"]
        if self.log:
            self.log.writerow(row)
        if now - self.hz_t >= 1.0:
            self.hz = self.n_det / (now - self.hz_t)
            self.n_det = 0
            self.hz_t = now
        if now - self.last_print > 0.5:
            self.last_print = now
            if info:
                self.get_logger().info(
                    f"[{self.state:6s}|ID{src}] 거리 {info[1]:.3f}m  좌우 {info[0]*100:+5.1f}cm  "
                    f"각도 {math.degrees(info[2]):+5.1f}°  목표방향 {math.degrees(alpha):+5.1f}°  "
                    f"| v {v:+.3f} w {w:+.3f}  검출 {self.hz:.0f}Hz"
                    + (f"  늦은사진 {self.stale}" if self.stale else ""))
            else:
                self.get_logger().info(f"[{self.state:6s}] 마커 안 보임  | v {v:+.3f} w {w:+.3f}")

    def stop_robot(self):
        t = TwistStamped()
        t.header.frame_id = "base_link"
        for _ in range(10):
            try:
                t.header.stamp = self.get_clock().now().to_msg()
                self.pub.publish(t)
            except Exception:
                break
            time.sleep(0.03)

    def destroy_node(self):
        self.cam_stop(wait=True)        ### 수정 (10-02) dock 을 끄면 dock 이 켠 카메라도 끈다
        try:
            self.log_f.close()
        except Exception:
            pass
        super().destroy_node()


def main():
    from rclpy.signals import SignalHandlerOptions
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    n = Dock()
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        n.get_logger().info("Ctrl+C — Nav2 취소 · 정지 명령 전송")
    finally:
        n.cancel_nav()
        n.stop_robot()
        if n.log_path:
            n.get_logger().info(f"로그 저장: {n.log_path}")
        n.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
