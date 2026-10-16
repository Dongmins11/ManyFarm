"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import xml.etree.ElementTree as ET

import numpy as np

from scipy.spatial.transform import Rotation

from .settings import URDF, JOINTS

def origin(node):
    t = np.eye(4)
    if node is not None:
        t[:3, 3] = np.fromstring(node.get("xyz", "0 0 0"), sep=" ")
        t[:3, :3] = Rotation.from_euler("xyz", np.fromstring(node.get("rpy", "0 0 0"), sep=" ")).as_matrix()
    return t

class ArmKinematics:
    def __init__(self, path=URDF):
        self.root = ET.parse(path).getroot()
        self.by_child = {j.find("child").get("link"): j for j in self.root.findall("joint")}
        self.names = ["arm_2/" + n for n in JOINTS]
        joints = {j.get("name"): j for j in self.root.findall("joint")}
        self.lower = np.array([float(joints[n].find("limit").get("lower")) for n in self.names])
        self.upper = np.array([float(joints[n].find("limit").get("upper")) for n in self.names])

    def fk(self, q, link="arm_2/tool0"):
        chain = []
        while link in self.by_child:
            j = self.by_child[link]
            chain.append(j)
            link = j.find("parent").get("link")
        t = np.eye(4)
        angles = dict(zip(self.names, q))
        for j in reversed(chain):
            t = t @ origin(j.find("origin"))
            if j.get("name") in angles:
                r = np.eye(4)
                axis = np.fromstring(j.find("axis").get("xyz"), sep=" ")
                r[:3, :3] = Rotation.from_rotvec(axis * angles[j.get("name")]).as_matrix()
                t = t @ r
        return t

    def grasp_fk(self, q, diameter=.070):
        # Original tool0 lies on the fixed finger surface, NOT midway between fingers.
        t = self.fk(q, "arm_2/gripper_link")
        offset = np.eye(4)
        offset[:3, 3] = [-.0079 + diameter/2, -.000218121, -.085]
        offset[:3, :3] = Rotation.from_euler("y", np.pi).as_matrix()
        return t @ offset

    def candidates(self, cfg, count=512, seed=42):
        rng = np.random.default_rng(seed)
        lo = np.array(cfg.region_origin) + cfg.region_min
        hi = np.array(cfg.region_origin) + cfg.region_max
        radius = cfg.diameter / 2 + 0.015
        qs, points = [], []
        # FK sampling avoids promising unreachable Cartesian box corners.
        for _ in range(150000):
            q = rng.uniform(self.lower + 0.08, self.upper - 0.08)
            q[5] = 1.1
            tcp = self.grasp_fk(q, cfg.diameter)
            p = tcp[:3, 3]
            if not np.all((p >= lo) & (p <= hi)):
                continue
            # Keep fruit clear of deck/frame and box. Conservative bounding boxes.
            if p[0] < 0.30 + radius and p[2] < 0.74 + cfg.length / 2:
                continue
            if (0.30-radius < p[0] < 0.50+radius and abs(p[1]) < .10+radius
                    and p[2] < .701+cfg.length/2+.025):
                continue
            # Tool approach (+Z) must have a forward component, not approach through tree.
            if tcp[0, 2] < 0.25:
                continue
            # Coarse link centre check against deck and box.
            safe = True
            for link in ("upper_arm_link", "lower_arm_link", "wrist_link", "gripper_link"):
                b = self.fk(q, "arm_2/" + link)[:3, 3]
                if b[2] < .74 and b[0] < .325:
                    safe = False
                if .275 < b[0] < .525 and abs(b[1]) < .125 and .475 < b[2] < .73:
                    safe = False
            if safe:
                qs.append(q)
                points.append(p)
                if len(qs) >= count:
                    break
        if len(qs) < min(64, count):
            raise RuntimeError(f"Only {len(qs)} feasible FK seeds. Inspect assembly and region.")
        return np.array(qs), np.array(points)
