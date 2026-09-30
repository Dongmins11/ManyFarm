"""Synchronized Replicator RGB and instance segmentation capture."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import traceback
import numpy as np

from .core import (usd_camera_matrix, select_target_instances, make_labels,
                   postprocess_rgb, label_overlay)
from .stage import (label_stage, save_labeled_copy, inspect_beds,
                    validate_render_geometry, source_camera, configure_camera,
                    assign_section_membership)


def write_json(path, data):
    path = Path(path)
    def encode(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, Path):
            return str(value)
        raise TypeError(type(value).__name__)
    temporary = path.with_name(path.name+".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                    allow_nan=False, default=encode)+"\n", encoding="utf-8")
    temporary.replace(path)


def resolve_sections(graph, fruits, beds, requested="all", physical_beds=None):
    sections = graph.get("survey_sections", {})
    if not sections:
        raise ValueError("graph.geojson has no survey_sections; use the 16-side graph or explicit mapping")
    wanted = list(sections) if requested == "all" or requested == ["all"] else list(requested)
    unknown = set(wanted)-set(sections)
    if unknown:
        raise ValueError(f"Unknown section IDs: {sorted(unknown)}")
    by_path = {bed.bed_path: bed for bed in beds.values()}
    result = []
    for section_id in wanted:
        section = sections[section_id]
        path = section["evaluation_bed_prim"].rstrip("/")
        if path not in by_path:
            raise ValueError(f"{section_id}: physical bed prim not found: {path}")
        bed = by_path[path]
        if physical_beds and bed.physical_bed not in physical_beds:
            continue
        side = section["survey_side"]
        if side not in ("west", "east"):
            raise ValueError(f"Unknown side for {section_id}: {side}")
        result.append((section_id, side, bed))
    if not result:
        raise ValueError("Selected section/physical-bed filters contain no capture views")
    return result


class DatasetWriter:
    def __init__(self, run, config):
        self.run, self.config = Path(run), config
        self.run.mkdir(parents=True, exist_ok=False)
        self.counts = Counter()
        self.class_counts = Counter()
        for folder in ("images", "labels", "raw_rgb", "gt_masks"):
            for split in ("train", "val"):
                (self.run/folder/split).mkdir(parents=True)
        (self.run/"previews").mkdir()
        (self.run/"metadata").mkdir()
        self.manifest = (self.run/"manifest.jsonl").open("w", encoding="utf-8")

    def save(self, name, rgb, processed, lines, objects, masks, meta):
        from PIL import Image
        split = "val" if meta["physical_bed"] in self.config["capture"]["validation_physical_beds"] else "train"
        stem = Path(split)/name
        Image.fromarray(processed).save(self.run/"images"/(str(stem)+".png"))
        if self.config["capture"]["save_raw_rgb"]:
            Image.fromarray(rgb).save(self.run/"raw_rgb"/(str(stem)+".png"))
        (self.run/"labels"/(str(stem)+".txt")).write_text("\n".join(lines)+("\n" if lines else ""), encoding="utf-8")
        if self.config["capture"]["save_gt_masks"]:
            mask_image = np.zeros(rgb.shape[:2], np.uint16)
            for obj, mask in zip(objects, masks):
                mask_image[mask] = obj["gt_mask_value"]
            Image.fromarray(mask_image).save(self.run/"gt_masks"/(str(stem)+".png"))
        every = self.config["capture"]["overlay_every"]
        if every > 0 and self.counts["total"] % every == 0:
            Image.fromarray(label_overlay(processed, objects, masks)).save(self.run/"previews"/(name+".png"))
        meta = {**meta, "split": split, "image": "images/"+str(stem)+".png", "objects": objects}
        write_json(self.run/"metadata"/(name+".json"), meta)
        self.manifest.write(json.dumps({"image": meta["image"], "metadata": "metadata/"+name+".json",
                                       "section_id": meta["section_id"], "physical_bed": meta["physical_bed"],
                                       "split": split, "instances": len(lines)}, ensure_ascii=False)+"\n")
        self.manifest.flush()
        self.counts[split] += 1
        self.counts["total"] += 1
        for obj in objects:
            self.class_counts[obj["class_name"]] += 1

    def close(self, status, error=None):
        self.manifest.close()
        complete_splits = bool(self.counts["train"] and self.counts["val"])
        # Explicit absolute dataset path works regardless of ultralytics datasets_dir.
        yaml = "path: "+json.dumps(str(self.run.resolve()), ensure_ascii=False)+"\ntrain: images/train\nval: images/val\nnames:\n  0: Red\n  1: Yellow\n"
        (self.run/"data.yaml").write_text(yaml, encoding="utf-8")
        write_json(self.run/"summary.json", {"status": status, "error": error,
                   "images": dict(self.counts), "instances": dict(self.class_counts),
                   "train_and_val_present": complete_splits,
                   "validation_group": "physical USD bed; both sides stay in the same split",
                   "label_scope": "visible Red/Yellow instances on the target survey section (physical bed AND side) only",
                   "non_target_peppers": "remain visible in RGB; have no positive labels",
                   "postprocess": "visual reference preset; not a calibrated D435 noise model"})
        if not complete_splits:
            print("[scout_dataset] Preview/subset run: train and val are not both populated. Generate all sections or set validation_physical_beds before training.", flush=True)


async def generate(stage, config, graph, *, label_only=False, physical_beds=None):
    """Run inside Kit's event loop, either standalone or from Script Editor."""
    import omni.kit.app
    import omni.replicator.core as rep
    import omni.timeline
    from pxr import Gf, Usd, UsdGeom

    cfg = config
    if cfg.get("class_names") != ["Red", "Yellow"]:
        raise ValueError("This package preserves existing model classes: 0 Red, 1 Yellow")
    fruits = label_stage(stage)
    beds = inspect_beds(stage, fruits)
    membership = assign_section_membership(stage, fruits, beds, graph)
    labeled_map = save_labeled_copy(stage)
    print(f"[scout_dataset] Labelled map: {labeled_map}", flush=True)
    print(f"[scout_dataset] Labels: {dict(Counter(f.color for f in fruits.values()))}", flush=True)
    if label_only:
        return {"labeled_map": str(labeled_map), "fruit_count": len(fruits)}

    validate_render_geometry(stage, fruits)
    sections = resolve_sections(graph, fruits, beds, cfg["sections"], physical_beds)
    source = source_camera(stage, cfg["camera"])
    height = cfg["camera"]["world_height_m"]
    height = source["world_height_m"] if height is None else float(height)
    n = int(cfg["frames_per_section"])
    if n < 1:
        raise ValueError("frames_per_section must be positive")
    seed = int(cfg["seed"])
    pose_rng, image_rng = [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(2)]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")+f"_s{seed}"
    run = Path(cfg["output_dir"])/run_id
    writer = DatasetWriter(run, cfg)
    capture_path = "/World/ScoutDatasetCamera_"+run_id
    rp = None
    annotators = []
    status, error = "failed", None
    timeline = omni.timeline.get_timeline_interface()
    was_playing = timeline.is_playing()
    previous_edit = stage.GetEditTarget()
    print(f"[scout_dataset] Output: {run}", flush=True)
    try:
        timeline.pause()
        rep.orchestrator.set_capture_on_play(False)
        stage.SetEditTarget(stage.GetSessionLayer())
        cam = UsdGeom.Camera.Define(stage, capture_path)
        optics = configure_camera(cam, source, cfg["camera"])
        xform = UsdGeom.Xformable(cam.GetPrim())
        op = xform.MakeMatrixXform()
        xform.SetResetXformStack(True)
        w, h = map(int, cfg["camera"]["resolution"])
        rp = rep.create.render_product(capture_path, (w, h))
        rgb_annot = rep.AnnotatorRegistry.get_annotator("rgb")
        instance_annot = rep.AnnotatorRegistry.get_annotator("instance_segmentation",
                                                          init_params={"colorize": False})
        for annot in (rgb_annot, instance_annot):
            annot.attach(rp)
            annotators.append(annot)
        for _ in range(int(cfg["capture"]["warmup_frames"])):
            await omni.kit.app.get_app().next_update_async()
        write_json(run/"session.json", {"run_id": run_id, "timestamp_timezone": "UTC", "config": cfg, "labelled_map": labeled_map,
            "source_scene": stage.GetRootLayer().realPath, "optics": optics,
            "camera_height_world_m": height, "beds": {k: asdict(v) for k, v in beds.items()},
            "sections": [{"section_id": sid, "side": side, "physical_bed": bed.physical_bed,
                          "bed_prim": bed.bed_path} for sid, side, bed in sections],
            "fruit_inventory": [{**asdict(f), **membership[f.path]} for f in fruits.values()],
            "capture_mode": "static scene, continuous uniform along-bed camera positions; no segment snapping"})
        for section_id, side, bed in sections:
            saved, attempts = 0, 0
            limit = n*int(cfg["capture"]["max_attempts_per_image"])
            while saved < n and attempts < limit:
                attempts += 1
                cc = cfg["camera"]
                pitch = source["pitch_deg"]+float(pose_rng.uniform(-cc["pitch_jitter_deg"], cc["pitch_jitter_deg"]))
                z = height+float(pose_rng.uniform(-cc["height_jitter_m"], cc["height_jitter_m"]))
                pose = bed.sample_pose(side, pose_rng, cc["distance_from_outer_edge_m"], z,
                                       pitch, cc["yaw_jitter_deg"], cc["end_margin_m"])
                matrix = usd_camera_matrix(pose["position_world_m"], pose["forward_world"])
                op.Set(Gf.Matrix4d(matrix.T.tolist()))
                # RGB and instance map are read from the same render product,
                # after the same synchronized capture; no physics/time advances.
                await rep.orchestrator.step_async(rt_subframes=int(cfg["capture"]["rt_subframes"]),
                                                  delta_time=0.0, pause_timeline=True)
                raw = rgb_annot.get_data()
                if isinstance(raw, dict):
                    raw = raw["data"]
                raw = np.asarray(raw)
                if raw.ndim != 3 or raw.shape[:2] != (h, w) or raw.shape[2] < 3 or raw.dtype != np.uint8:
                    raise RuntimeError(f"Unexpected RGB output: {raw.shape}, {raw.dtype}")
                rgb = raw[..., :3].copy()
                payload = instance_annot.get_data()
                selected, exclusion = select_target_instances(payload, fruits, bed.bed_path, side, membership)
                if np.asarray(payload["data"]).shape[:2] != (h, w):
                    raise RuntimeError("RGB/mask resolution mismatch")
                lines, objects, masks, dropped = make_labels(selected,
                    cfg["capture"]["min_visible_pixels"], cfg["capture"]["polygon_epsilon_px"])
                for obj in objects:
                    obj.update(survey_side=side, section_id=membership[obj["prim_path"]]["section_id"])
                    if obj["section_id"] != section_id:
                        raise RuntimeError("Object section does not match capture section")
                if not lines and cfg["capture"]["skip_empty"]:
                    continue
                processed, effects = postprocess_rgb(rgb, cfg["postprocess"], image_rng)
                name = f"{run_id}_{section_id}_P{bed.physical_bed:02d}_{saved:05d}"
                metadata = {"run_id": run_id, "section_id": section_id, "physical_bed": bed.physical_bed,
                    "target_bed_prim": bed.bed_path, "target_side": side, "seed": seed, "attempt": attempts,
                    "camera": pose, "postprocess": effects,
                    "filter": exclusion, "dropped_tiny_instances": dropped,
                    "label_basis": "visible unblurred GT mask; RGB-only photometric postprocessing"}
                writer.save(name, rgb, processed, lines, objects, masks, metadata)
                saved += 1
                if saved == 1 or saved % 10 == 0 or saved == n:
                    print(f"[scout_dataset] {section_id} / physical Bed_{bed.physical_bed:02d} {side}: {saved}/{n}, target={len(lines)}, other-bed excluded={exclusion['excluded_other_bed_fruits']}, opposite-side excluded={exclusion['excluded_opposite_side_fruits']}", flush=True)
            if saved < n:
                raise RuntimeError(f"{section_id}: only {saved}/{n} valid images in {attempts} attempts. Check camera view, frame geometry, semantics and referenced assets.")
        status = "completed"
    except BaseException:
        error = traceback.format_exc()
        raise
    finally:
        for annot in annotators:
            try:
                annot.detach(rp)
            except Exception:
                pass
        if rp is not None:
            try:
                rp.destroy()
            except Exception:
                pass
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            stage.RemovePrim(capture_path)
        stage.SetEditTarget(previous_edit)
        if was_playing:
            timeline.play()
        writer.close(status, error)
    print(f"[scout_dataset] Complete: {writer.counts['total']} images -> {run}", flush=True)
    return {"labeled_map": str(labeled_map), "dataset": str(run), "images": writer.counts["total"]}
