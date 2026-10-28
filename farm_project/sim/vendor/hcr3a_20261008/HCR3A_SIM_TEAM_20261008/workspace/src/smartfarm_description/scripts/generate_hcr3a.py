#!/usr/bin/env python3
"""Generate separate approximate HCR/JRT URDF; preserve the legacy OMX asset."""

import sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/sorting_station"))
from hcr_sim.model import Arm, load_config


def generate(cfg=None, destination=None):
    c = cfg if cfg is not None else load_config()
    arm = Arm(c)
    root = ET.Element("robot", name="hcr3a_functional")

    def link(name, size, xyz=(0, 0, 0), rgba="0.94 0.32 0.025 1", mass=1):
        l = ET.SubElement(root, "link", name=name)
        i = ET.SubElement(l, "inertial")
        ET.SubElement(i, "origin", xyz=" ".join(map(str, xyz)))
        ET.SubElement(i, "mass", value=str(mass))
        ET.SubElement(
            i, "inertia", ixx=".01", iyy=".01", izz=".01", ixy="0", ixz="0", iyz="0"
        )
        for kind in ["visual", "collision"]:
            item = ET.SubElement(l, kind)
            ET.SubElement(item, "origin", xyz=" ".join(map(str, xyz)))
            geom = ET.SubElement(item, "geometry")
            ET.SubElement(geom, "box", size=" ".join(map(str, size)))
            if kind == "visual":
                mat = ET.SubElement(item, "material", name=name + "_color")
                ET.SubElement(mat, "color", rgba=rgba)

    def joint(
        name, parent, child, kind, origin, axis=(0, 0, 1), lower=-6.28, upper=6.28
    ):
        j = ET.SubElement(root, "joint", name=name, type=kind)
        ET.SubElement(j, "parent", link=parent)
        ET.SubElement(j, "child", link=child)
        ET.SubElement(j, "origin", xyz=" ".join(map(str, origin)))
        ET.SubElement(j, "axis", xyz=" ".join(map(str, axis)))
        ET.SubElement(
            j, "limit", lower=str(lower), upper=str(upper), effort="150", velocity="2"
        )
        ET.SubElement(j, "dynamics", damping=".5", friction=".01")

    height = c["robot"]["shoulder_z"]
    link(
        "base",
        (0.128, 0.128, height),
        xyz=(0, 0, height / 2),
        rgba=".07 .075 .085 1",
        mass=3,
    )
    u = c["robot"]["upper_length"]
    f = c["robot"]["fore_length"]
    sizes = [
        (0.10, 0.10, 0.08),
        (u, 0.065, 0.065),
        (f, 0.055, 0.055),
        (0.065, 0.065, 0.065),
        (0.07, 0.05, 0.05),
        (0.035, 0.055, 0.055),
    ]
    centers = [
        (0, 0, 0),
        (u / 2, 0, 0),
        (f / 2, 0, 0),
        (0, 0, 0),
        (0.02, 0, 0),
        (0, 0, 0),
    ]
    parent = "base"
    for i in range(6):
        child = f"link{i+1}"
        link(
            child,
            sizes[i],
            centers[i],
            rgba=".07 .075 .085 1" if i == 0 else "0.94 0.32 0.025 1",
        )
        joint(
            f"joint{i+1}",
            parent,
            child,
            "revolute",
            arm.origins[i],
            arm.axes[i],
            float(arm.lower[i]),
            float(arm.upper[i]),
        )
        parent = child
    bw, bd, bl = c["gripper"]["body_size"]
    link(
        "tool",
        (bl, bw, bd),
        xyz=(bl / 2 + 0.007, 0, 0),
        rgba=".035 .035 .04 1",
        mass=0.98,
    )
    joint("tool_mount", "link6", "tool", "fixed", (0.02, 0, 0))
    for sign, label in [(1, "left"), (-1, "right")]:
        link(
            label + "_finger",
            (c["gripper"]["finger_length"], 0.010, 0.030),
            xyz=(0.15, 0, 0),
            rgba=".08 .08 .085 1",
            mass=0.05,
        )
        closed = c["gripper"]["closed_gap"] / 2 + 0.009
        travel = (c["gripper"]["open_gap"] - c["gripper"]["closed_gap"]) / 2
        joint(
            label + "_jaw",
            "tool",
            label + "_finger",
            "prismatic",
            (0, sign * closed, 0),
            (0, sign, 0),
            0,
            travel,
        )
        link(
            label + "_pad",
            (0.045, 0.004, 0.027),
            xyz=(0.17, -sign * 0.007, 0),
            rgba=".95 .15 .45 1",
            mass=0.01,
        )
        joint(
            label + "_pad_mount", label + "_finger", label + "_pad", "fixed", (0, 0, 0)
        )
    link("tcp", (0.002, 0.002, 0.002), mass=0.001)
    # TCP is a coordinate frame inside the grasped object, not a solid probe.
    tcp = root.find("link[@name='tcp']")
    tcp.remove(tcp.find("collision"))
    joint("tcp_mount", "link6", "tcp", "fixed", tuple(arm.tcp))
    p = (
        Path(destination)
        if destination
        else ROOT / "src/smartfarm_description/urdf/hcr3a_functional.urdf"
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root)
    ET.ElementTree(root).write(p, encoding="utf-8", xml_declaration=True)
    return p


if __name__ == "__main__":
    print(generate())
