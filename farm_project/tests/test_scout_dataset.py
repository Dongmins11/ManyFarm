"""CPU verification of geometry, bed filtering, polygons, labels and saved output.

Run: python -m unittest discover -s tests -p test_scout_dataset.py -v
Requires the dataset requirements and usd-core for the USD tests.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"sim/tools"))
from scout_dataset.core import (Fruit, bed_geometry_from_points, usd_camera_matrix,
    select_target_instances, make_labels, mask_to_polygon, postprocess_rgb, classify_fruit_side)
from scout_dataset.capture import DatasetWriter, resolve_sections

CFG = json.loads((ROOT/"sim/config/scout_dataset.json").read_text())


class GeometryTests(unittest.TestCase):
    def test_continuous_sampling_distance_direction_and_bounds(self):
        points = [[x, y] for x in (-5.5, -4.5) for y in (2., 10.)]
        bed = bed_geometry_from_points(2, "/World/Vegetation/Bed_02", points, ["edge"])
        rng = np.random.default_rng(12)
        offsets = []
        for side, expected_x, sign in (("west", -6.64, 1), ("east", -3.36, -1)):
            for _ in range(100):
                p = bed.sample_pose(side, rng, 1.14, .6)
                x, y, z = p["position_world_m"]
                self.assertAlmostEqual(x, expected_x)
                self.assertTrue(2 <= y <= 10)
                self.assertEqual(z, .6)
                np.testing.assert_allclose(p["forward_world"], [sign, 0, 0], atol=1e-12)
                offsets.append(p["along_m"])
        self.assertEqual(len(set(offsets)), 200)
        self.assertTrue(any(abs(v-round(v)) > .1 for v in offsets))

    def test_rotated_bed_and_usd_camera_axes(self):
        theta = np.deg2rad(28)
        rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        points = np.array([[x, y] for x in (-.5, .5) for y in (-4, 4)]) @ rotation.T
        bed = bed_geometry_from_points(1, "/Bed_01", points, ["edge"])
        self.assertAlmostEqual(bed.half_width_m, .5)
        self.assertAlmostEqual(bed.half_length_m, 4)
        for side in ("west", "east"):
            p = bed.sample_pose(side, np.random.default_rng(2), 1.14, .6, 4, 2)
            self.assertAlmostEqual(p["edge_distance_m"], 1.14)
            m = usd_camera_matrix(p["position_world_m"], p["forward_world"])
            np.testing.assert_allclose(m[:3, :3].T@m[:3, :3], np.eye(3), atol=1e-12)
            np.testing.assert_allclose(-m[:3, 2], p["forward_world"], atol=1e-12)
            self.assertAlmostEqual(np.linalg.det(m[:3, :3]), 1.)


class LabelTests(unittest.TestCase):
    def setUp(self):
        self.target = "/World/Vegetation/Bed_02"
        p = self.target+"/Fruits/Pepper_0001_red"
        q = "/World/Vegetation/Bed_03/Fruits/Pepper_0001_yellow"
        self.fruits = {p: Fruit(p, self.target, 2, "red"),
                       q: Fruit(q, "/World/Vegetation/Bed_03", 3, "yellow")}
        self.p, self.q = p, q
        self.membership = {p: {"side": "west"}, q: {"side": "west"}}

    def test_only_target_bed_and_union_submeshes(self):
        image = np.zeros((60, 90), np.uint32)
        image[5:20, 5:15] = 30
        image[25:40, 6:20] = 31
        image[5:40, 40:65] = 88
        labels = {"0": "BACKGROUND", "30": self.p+"/Model/body",
                  "31": self.p+"/Model/stem", "88": self.q+"/Model"}
        selected, excluded = select_target_instances({"data": image, "info": {"idToLabels": labels}},
                                                     self.fruits, self.target, "west", self.membership)
        self.assertEqual(len(selected), 1)
        self.assertEqual(int(selected[0][1].sum()), 150+210)
        self.assertFalse(selected[0][1][10, 50])
        self.assertEqual(excluded["excluded_other_bed_fruits"], 1)
        rows, objects, masks, _ = make_labels(selected)
        self.assertEqual(len(rows), 1)
        self.assertEqual(objects[0]["physical_bed"], 2)
        numbers = list(map(float, rows[0].split()))
        self.assertEqual(numbers[0], 0)
        self.assertTrue(all(0 <= v <= 1 for v in numbers[1:]))
        self.assertEqual((len(numbers)-1) % 2, 0)

    def test_mapping_is_per_frame_not_cached_ids(self):
        image = np.full((8, 8), 30, np.uint32)
        for path, expected in [(self.p, 1), (self.q, 0)]:
            payload = {"data": image, "info": {"idToLabels": {30: path}}}
            selected, _ = select_target_instances(payload, self.fruits, self.target, "west", self.membership)
            self.assertEqual(len(selected), expected)

    def test_missing_paths_fail_instead_of_silent_incorrect_labels(self):
        payload = {"data": np.full((8, 8), 30, np.uint32), "info": {"idToLabels": {
            30: "/World/Vegetation/Bed_020/Fruits/Pepper_0001_red/Model"}}}
        with self.assertRaises(RuntimeError):
            select_target_instances(payload, self.fruits, self.target, "west", self.membership)

    def test_same_bed_opposite_side_is_excluded_in_both_directions(self):
        opposite_path = self.target+"/Fruits/Pepper_0002_yellow"
        self.fruits[opposite_path] = Fruit(opposite_path, self.target, 2, "yellow")
        self.membership[opposite_path] = {"side": "east"}
        pixels = np.zeros((50, 80), np.uint32)
        pixels[2:15, 2:15] = 3  # west, current bed
        pixels[20:35, 20:35] = 4  # east, SAME bed, visibly present
        pixels[2:15, 55:70] = 5  # another bed
        payload = {"data": pixels, "info": {"idToLabels": {
            3: self.p+"/Model", 4: opposite_path+"/Model", 5: self.q+"/Model"}}}
        for side, wanted in [("west", self.p), ("east", opposite_path)]:
            selected, excluded = select_target_instances(payload, self.fruits, self.target,
                                                         side, self.membership)
            self.assertEqual([x[0].path for x in selected], [wanted])
            self.assertEqual(excluded["excluded_opposite_side_fruits"], 1)
            self.assertEqual(excluded["excluded_other_bed_fruits"], 1)
            rows, objects, masks, _ = make_labels(selected)
            self.assertEqual(len(rows), 1)
            self.assertEqual(objects[0]["prim_path"], wanted)

    def test_side_assignment_uses_bed_frame_and_rejects_centreline(self):
        theta = np.deg2rad(30.)
        rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        center = np.array([-5., 6.])
        points = np.array([[x, y] for x in (-.5, .5) for y in (-4., 4.)]) @ rotation.T + center
        bed = bed_geometry_from_points(2, self.target, points, ["edge"])
        for offset, wanted in [(-.49, "west"), (.49, "east")]:
            position = np.r_[center+offset*bed.normal_xy+2.5*bed.tangent_xy, .8]
            self.assertEqual(classify_fruit_side(position, bed), wanted)
        with self.assertRaises(ValueError):
            classify_fruit_side([*center, .8], bed)

    def test_polygon_preserves_holes_and_disconnected_instances(self):
        import cv2
        mask = np.zeros((160, 200), np.uint8)
        cv2.circle(mask, (70, 80), 40, 1, -1)
        cv2.circle(mask, (70, 80), 15, 0, -1)
        cv2.circle(mask, (150, 40), 12, 1, -1)
        polygon = mask_to_polygon(mask)
        rendered = np.zeros_like(mask)
        cv2.fillPoly(rendered, [np.rint(polygon).astype(np.int32)], 1)
        self.assertEqual(rendered[80, 70], 0)
        self.assertEqual(rendered[40, 150], 1)
        self.assertGreater(np.sum(mask & rendered)/np.sum(mask | rendered), .98)


class ImagingTests(unittest.TestCase):
    def test_postprocess_determinism_shape_and_labels_unchanged(self):
        rng = np.random.default_rng(5)
        rgb = rng.integers(0, 256, (160, 240, 3), dtype=np.uint8)
        original = rgb.copy()
        first, effect = postprocess_rgb(rgb, CFG["postprocess"], np.random.default_rng(8))
        second, _ = postprocess_rgb(rgb, CFG["postprocess"], np.random.default_rng(8))
        np.testing.assert_array_equal(first, second)
        np.testing.assert_array_equal(rgb, original)
        self.assertEqual(first.shape, original.shape)
        self.assertEqual(first.dtype, np.uint8)
        self.assertTrue(effect["enabled"])
        self.assertFalse(np.array_equal(first, rgb))

    def test_file_bundle_mask_and_physical_bed_split(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            writer = DatasetWriter(Path(tmp)/"run", CFG)
            rgb = np.full((30, 40, 3), 120, np.uint8)
            mask = np.zeros((30, 40), bool);mask[4:20, 5:25] = True
            fruit = Fruit("/Bed_07/Fruits/Pepper_0001_yellow", "/Bed_07", 7, "yellow")
            lines, objects, masks, _ = make_labels([(fruit, mask, [22])])
            for sid in ("BED_15", "BED_16"):
                writer.save(sid, rgb, rgb, lines, objects, masks,
                            {"physical_bed": 7, "section_id": sid})
            writer.close("completed")
            run = Path(tmp)/"run"
            self.assertEqual(len(list((run/"images/val").glob("*.png"))), 2)
            self.assertEqual(len(list((run/"images/train").glob("*.png"))), 0)
            saved = np.asarray(Image.open(run/"gt_masks/val/BED_15.png"))
            np.testing.assert_array_equal(saved > 0, mask)
            self.assertTrue((run/"data.yaml").exists())


class USDTests(unittest.TestCase):
    def test_label_save_roundtrip_and_non_target_preservation(self):
        try:
            from pxr import Usd, UsdGeom, Sdf, UsdSemantics
        except ImportError:
            self.skipTest("usd-core unavailable")
        from scout_dataset.stage import label_stage, save_labeled_copy, inspect_fruits
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp)/"farm.usda"
            stage = Usd.Stage.CreateNew(str(original))
            for color in ("red", "yellow", "green"):
                path = f"/World/Vegetation/Bed_02/Fruits/Pepper_0001_{color}"
                prim = UsdGeom.Xform.Define(stage, path).GetPrim()
                prim.CreateAttribute("crop:color", Sdf.ValueTypeNames.String).Set(color)
                prim.CreateAttribute("crop:bedId", Sdf.ValueTypeNames.Int).Set(2)
            stage.GetRootLayer().Save()
            before = original.read_bytes()
            label_stage(stage)
            output = save_labeled_copy(stage)
            self.assertEqual(original.read_bytes(), before)
            restored = Usd.Stage.Open(str(output))
            self.assertEqual(len(inspect_fruits(restored)), 2)
            for color in ("red", "yellow"):
                p = restored.GetPrimAtPath(f"/World/Vegetation/Bed_02/Fruits/Pepper_0001_{color}")
                self.assertEqual(list(UsdSemantics.LabelsAPI(p, "class").GetLabelsAttr().Get()), ["pepper_"+color])
            p = restored.GetPrimAtPath("/World/Vegetation/Bed_02/Fruits/Pepper_0001_green")
            self.assertFalse(p.HasAPI(UsdSemantics.LabelsAPI, "class"))

    def test_camera_intrinsics_and_usd_transform_roundtrip(self):
        try:
            from pxr import Usd, UsdGeom, Gf
        except ImportError:
            self.skipTest("usd-core unavailable")
        from scout_dataset.stage import configure_camera
        stage = Usd.Stage.CreateInMemory()
        camera = UsdGeom.Camera.Define(stage, "/Camera")
        source = {"focalLength": 1.88, "horizontalAperture": 3.5,
                  "verticalAperture": 2.1, "horizontalApertureOffset": 0.,
                  "verticalApertureOffset": 0., "clippingRange": [.01, 100.]}
        cfg = dict(CFG["camera"])
        cfg.update(intrinsics_mode="calibrated_K", K=[[900., 0, 627.], [0, 905., 356.], [0, 0, 1.]])
        optics = configure_camera(camera, source, cfg)
        np.testing.assert_allclose(optics["K"], cfg["K"])
        # Check USD's actual projection, not just the K value returned by our helper.
        projection = np.asarray(camera.GetCamera().frustum.ComputeProjectionMatrix())
        for point, expected in [([0, 0, -1, 1], [627, 356]),
                                ([.1, 0, -1, 1], [717, 356]),
                                ([0, .1, -1, 1], [627, 265.5])]:
            clip = np.asarray(point) @ projection
            ndc = clip[:3]/clip[3]
            pixels = [(ndc[0]+1)*640, (1-ndc[1])*360]
            np.testing.assert_allclose(pixels, expected, atol=1e-4)
        m = usd_camera_matrix([-6.64, 5, .6], [1, 0, 0])
        UsdGeom.Xformable(camera.GetPrim()).MakeMatrixXform().Set(Gf.Matrix4d(m.T.tolist()))
        actual = np.asarray(UsdGeom.XformCache().GetLocalToWorldTransform(camera.GetPrim())).T
        np.testing.assert_allclose(actual, m)


if __name__ == "__main__":
    unittest.main()
