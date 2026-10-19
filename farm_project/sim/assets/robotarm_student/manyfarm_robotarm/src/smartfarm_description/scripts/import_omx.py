#!/usr/bin/env python3
"""Vendor and prefix the official ROBOTIS OMX-F follower model.

Source is pinned to the ROBOTIS open_manipulator 5.1.2 release. The untouched
official URDF is kept under urdf/upstream/omx_f.urdf and the official STL files
under meshes/omx_f. A prefixed derivative is written to
urdf/generated/omx_f.urdf so it can be embedded safely in the ManyFarm station.
"""
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as E

P = Path(__file__).resolve().parents[1]
REF = "5.1.2"
RAW = f"https://raw.githubusercontent.com/ROBOTIS-GIT/open_manipulator/{REF}/open_manipulator_description"
UPSTREAM = P / "urdf" / "upstream" / "omx_f.urdf"
MESH_DIR = P / "meshes" / "omx_f"
GENERATED = P / "urdf" / "generated" / "omx_f.urdf"

MESHES = (
    "follower_01_base.stl",
    "follower_02_base_tilt_Revised.stl",
    "follower_03_middle_verticle.stl",
    "follower_04_middle_horizontal.stl",
    "follower_05_tip.stl",
    "follower_06_pan_Revised.stl",
    "follower_07_gripper_motorized.stl",
    "follower_08_gripper_gear.stl",
)


def download(url: str, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    urllib.request.urlretrieve(url, temporary)
    temporary.replace(destination)


def ensure_official_assets(force: bool = False):
    if force or not UPSTREAM.is_file():
        download(f"{RAW}/urdf/omx_f/omx_f.urdf", UPSTREAM)
    MESH_DIR.mkdir(parents=True, exist_ok=True)
    for name in MESHES:
        path = MESH_DIR / name
        if force or not path.is_file():
            download(f"{RAW}/meshes/omx_f/{name}", path)


def prefixed(name: str) -> str:
    if name == "world":
        return name
    return "omx_" + name


def build_generated_urdf():
    ensure_official_assets()
    root = E.parse(UPSTREAM).getroot()

    # The station provides its own world/mount. Drop the upstream world anchor.
    world = root.find("link[@name='world']")
    if world is not None:
        root.remove(world)
    world_fixed = root.find("joint[@name='world_fixed']")
    if world_fixed is not None:
        root.remove(world_fixed)

    for link in root.findall("link"):
        link.set("name", prefixed(link.get("name")))

    for joint in root.findall("joint"):
        joint.set("name", prefixed(joint.get("name")))
        parent = joint.find("parent")
        child = joint.find("child")
        if parent is not None:
            parent.set("link", prefixed(parent.get("link")))
        if child is not None:
            child.set("link", prefixed(child.get("link")))
        mimic = joint.find("mimic")
        if mimic is not None:
            mimic.set("joint", prefixed(mimic.get("joint")))

    for mesh in root.iter("mesh"):
        mesh.set(
            "filename",
            "package://smartfarm_description/meshes/omx_f/"
            + Path(mesh.get("filename")).name,
        )

    # The physical follower used for data collection is black. Keep the official
    # mesh geometry but override only visual colors in the generated derivative.
    for visual in root.findall("./link/visual"):
        color = visual.find("./material/color")
        if color is not None:
            color.set("rgba", "0.025 0.025 0.025 1")

    # The official endpoint cube is a visual marker, not physical OMX-F geometry.
    endpoint = root.find("link[@name='omx_end_effector_link']")
    if endpoint is not None:
        for visual in list(endpoint.findall("visual")):
            endpoint.remove(visual)

    root.set("name", "robotis_omx_f_prefixed")
    GENERATED.parent.mkdir(parents=True, exist_ok=True)
    E.indent(root)
    GENERATED.write_text(
        '<?xml version="1.0"?>\n' + E.tostring(root, encoding="unicode") + "\n",
        encoding="utf-8",
    )
    return GENERATED


if __name__ == "__main__":
    generated = build_generated_urdf()
    print(f"Official OMX-F {REF} ready: {generated}")
