#!/usr/bin/env python3
"""Isaac Sim 5.1: label map and capture bed-scoped YOLO segmentation images."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def parse(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=ROOT/"sim/config/scout_dataset.json")
    p.add_argument("--scene", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--camera-prim")
    p.add_argument("--sections", nargs="+", help="BED_01..BED_16 survey-side IDs, or all")
    p.add_argument("--physical-beds", nargs="+", type=int, help="USD Bed_01..08 numbers; captures selected sides")
    p.add_argument("--frames-per-section", type=int)
    p.add_argument("--seed", type=int)
    p.add_argument("--headless", action="store_true")
    p.add_argument("--label-only", action="store_true")
    p.add_argument("--no-postprocess", action="store_true")
    return p.parse_args(argv)


def main():
    args = parse()
    cfg = json.loads(args.config.expanduser().resolve().read_text(encoding="utf-8"))
    def absolute(path):
        path = Path(path).expanduser()
        return path.resolve() if path.is_absolute() else (ROOT/path).resolve()
    scene = absolute(args.scene or cfg["scene"])
    if not scene.is_file():
        raise FileNotFoundError(f"Scene not found: {scene}; supply --scene /absolute/path/to/current.usd")
    cfg["scene"] = str(scene)
    cfg["output_dir"] = str(absolute(args.output or cfg["output_dir"]))
    for name in ("sections", "frames_per_section", "seed"):
        value = getattr(args, name)
        if value is not None:
            cfg[name] = value
    if args.camera_prim:
        cfg["camera"]["source_prim"] = args.camera_prim
    if args.no_postprocess:
        cfg["postprocess"]["enabled"] = False
    graph = json.loads(absolute(cfg["graph"]).read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT/"sim/tools"))
    # Kit/omni imports must come after SimulationApp. Do not use ROS Python here.
    from isaacsim import SimulationApp
    sys.argv = [sys.argv[0]]
    app = SimulationApp({"headless": args.headless, "renderer": "RayTracedLighting"})
    task = None
    try:
        import omni.usd
        from scout_dataset.capture import generate
        async def run():
            context = omni.usd.get_context()
            result = await context.open_stage_async(str(scene))
            if isinstance(result, tuple) and not result[0]:
                raise RuntimeError(f"Could not open stage: {result}")
            stage = context.get_stage()
            if stage is None:
                raise RuntimeError("No stage after open")
            return await generate(stage, cfg, graph, label_only=args.label_only,
                                  physical_beds=args.physical_beds)
        task = asyncio.ensure_future(run())
        while app.is_running() and not task.done():
            app.update()
        if not task.done():
            task.cancel()
            # Let finally blocks flush manifests and destroy render products.
            for _ in range(8):
                app.update()
                if task.done():
                    break
            raise RuntimeError("Isaac Sim closed before generation finished")
        print(json.dumps(task.result(), ensure_ascii=False, indent=2), flush=True)
    finally:
        if task and not task.done():
            task.cancel()
        app.close()


if __name__ == "__main__":
    main()
