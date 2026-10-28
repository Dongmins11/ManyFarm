"""Camera-driven single-job sequence; explicit assisted grasp for functional tests."""

import numpy as np
from .model import Arm, teach, storage_points, lane_centers


class Sorter:
    def __init__(self, cfg, robot, fruits):
        self.cfg = cfg
        self.robot = robot
        self.fruits = fruits
        self.arm = Arm(cfg)
        self.poses = teach(cfg)
        self.phase = "IDLE"
        self.active = False
        self.canceled = False
        self.counts = [0, 0]
        self.error = ""
        self.completed = []
        self.q = np.array(self.poses["HOME"]["q"])
        self.target = self.q.copy()
        self.held = None
        self.sequence = []
        self.index = 0
        self.step_start = 0
        self.duration = 1
        self.from_q = self.q.copy()
        self.grasp_path = None
        self.filtered_fruit = None
        self.empty_since = None
        self.current = None
        self.open_jaw = (cfg["gripper"]["open_gap"] - cfg["gripper"]["closed_gap"]) / 2
        self.jaw = self.open_jaw
        self.events = []
        self.job = 0
        self.motion_start = 0
        self.paths = {}
        self.lane_map = {n: n for n in "ABCD"}
        self.command_lane = None

    def recover(self):
        """Only ROI faults before motion are recoverable without scene reset."""
        if self.phase == "ERROR" and self.error in (
            "VISION_PICK_COLOR_MISMATCH", "VISION_TARGET_WITHOUT_PICKUP_OBJECT"
        ) and self.current is None and self.held is None:
            self.phase = "IDLE"
            self.error = ""
            self.empty_since = None
            return True
        return False

    def start(self):
        if self.phase not in ("IDLE", "SUCCESS", "CANCELED"):
            return
        self.active = True
        self.canceled = False
        self.error = ""
        self.counts = [0, 0]
        self.phase = "SCANNING"
        self.empty_since = None

    def cancel(self):
        self.canceled = True
        if self.phase == "SCANNING":
            self.active = False
            self.phase = "CANCELED"

    def fail(self, message):
        if self.phase == "ERROR":
            return
        self.error = message
        self.phase = "ERROR"
        self.active = False
        self.events.append({"event": "ERROR", "message": message})

    def choose(self, lane, color, now, job=None):
        if self.phase not in ("SCANNING", "IDLE"):
            return False
        centers = [
            (np.asarray(f["object"].data.root_pos_w[0].cpu()), f)
            for f in self.fruits
            if not f["sorted"]
        ]
        y = lane_centers(self.cfg)[self.lane_map[lane]]
        candidates = [
            (p, f)
            for p, f in centers
            if abs(p[1] - y) < 0.05
            and self.cfg["intake"]["low_x"] - 0.03
            < p[0]
            < self.cfg["intake"]["low_x"] + 0.14
        ]
        if not candidates:
            self.fail("VISION_TARGET_WITHOUT_PICKUP_OBJECT")
            return False
        p, f = min(candidates, key=lambda item: item[0][0])
        if f["color"] != color:
            self.fail("VISION_PICK_COLOR_MISMATCH")
            return False
        # Center the jaw assembly between the measured lane walls. The fruit
        # may settle off-center; the assisted grasp retains its actual pose.
        p = p.copy()
        p[1] = y
        # Dumped peppers can rest lower than the upright preloaded fixture.
        # Keep the approximate hand clear of the bottom stop; attachment still
        # checks the actual TCP distance and retains the real fruit pose.
        p[2] += self.cfg['physics'].get('assisted_grasp_clearance', 0.)
        try:
            pick = self.arm.ik(p, self.q)
            up = self.arm.ik(p + [0, 0, 0.12], pick)
            knots = [up]
            for fraction in np.linspace(0, 1, 17)[1:]:
                knots.append(self.arm.ik(p + [0, 0, 0.12 * (1 - fraction)], knots[-1]))
            self.paths = {"DESCEND": np.asarray(knots), "LIFT": np.asarray(knots[::-1])}
            end = np.array(self.poses[color]["xyz"])
            start = np.array(self.poses[color + "_CLEAR"]["xyz"])
            orientation = self.arm.fk(self.poses[color]["q"])[:3, :3]
            knots = [np.array(self.poses[color + "_CLEAR"]["q"])]
            for fraction in np.linspace(0, 1, 17)[1:]:
                knots.append(
                    self.arm.ik(
                        start + fraction * (end - start), knots[-1], orientation
                    )
                )
            self.paths["PLACE_" + color] = np.asarray(knots)
            self.paths["RETURN_CLEAR"] = np.asarray(knots[::-1])
        except ValueError as exc:
            self.fail(str(exc))
            return False
        self.current = f
        self.command_lane = lane
        self.exclude_robot_contacts()
        self.job = job or self.job + 1
        self.motion_start = now
        self.empty_since = None
        self.sequence = [
            ("APPROACH", up, 1.2),
            ("DESCEND", pick, 1.4),
            ("CLOSE", None, 0.5),
            ("LIFT", up, 1.1),
            ("HOME", self.poses["HOME"]["q"], 1.0),
            ("TRANSFER", self.poses["TRANSFER"]["q"], 1.5),
            ("STORAGE_CLEAR", self.poses[color + "_CLEAR"]["q"], 1.5),
            ("PLACE_" + color, self.poses[color]["q"], 1.8),
            ("OPEN", None, 0.5),
            ("RETURN_CLEAR", self.poses[color + "_CLEAR"]["q"], 1.8),
            ("TRANSFER", self.poses["TRANSFER"]["q"], 1.5),
            ("RETURN_HOME", self.poses["HOME"]["q"], 1.5),
            ("VERIFY_BIN", None, 2.0),
        ]
        self.index = 0
        self.enter(now)
        self.events.append(
            {"event": "BUSY", "job": self.job, "lane": lane, "color": color}
        )
        return True

    def enter(self, now):
        self.phase, self.target, self.duration = self.sequence[self.index]
        self.step_start = now
        self.from_q = self.q.copy()
        if self.target is None:
            self.target = self.q.copy()
        else:
            self.target = np.asarray(self.target)
        if self.phase == "CLOSE":
            self.jaw = 0
        if self.phase == "OPEN":
            self.jaw = self.open_jaw
            self.release()
        if self.phase == "TRANSFER" and self.held is None:
            self.restore_collisions()

    def attach(self):
        from pxr import UsdPhysics, Gf, UsdGeom
        import isaaclab.sim as sim
        from scipy.spatial.transform import Rotation

        stage = sim.get_current_stage()
        tool_id = self.robot.body_names.index("link6")
        actual = self.robot.data.body_pos_w[0, tool_id].cpu().numpy()
        quat = self.robot.data.body_quat_w[0, tool_id].cpu().numpy()
        R = Rotation.from_quat(quat[[1, 2, 3, 0]])
        fruit = self.current["object"]
        p = fruit.data.root_pos_w[0].cpu().numpy()
        q = fruit.data.root_quat_w[0].cpu().numpy()
        tcp = actual + R.apply(self.arm.tcp)
        if np.linalg.norm(p - tcp) > 0.045:
            self.fail(f"GRASP_TOO_FAR distance={np.linalg.norm(p-tcp):.3f}")
            return
        # Fixed grasp is a declared functional approximation, not proof of pad force.
        bodies = [
            prim
            for prim in stage.Traverse()
            if prim.GetName() == "link6"
            and str(prim.GetPath()).startswith("/World/HCRRobot")
            and prim.HasAPI(UsdPhysics.RigidBodyAPI)
        ]
        if len(bodies) != 1:
            self.fail("TOOL_BODY_NOT_FOUND")
            return
        self.grasp_path = "/World/AssistedGrasp"
        j = UsdPhysics.FixedJoint.Define(stage, self.grasp_path)
        j.CreateExcludeFromArticulationAttr(True)
        j.CreateBody0Rel().SetTargets([bodies[0].GetPath()])
        j.CreateBody1Rel().SetTargets([self.current["path"]])
        j.CreateLocalPos0Attr(Gf.Vec3f(*map(float, R.inv().apply(p - actual))))
        qr = (R.inv() * Rotation.from_quat(q[[1, 2, 3, 0]])).as_quat()
        j.CreateLocalRot0Attr(Gf.Quatf(float(qr[3]), Gf.Vec3f(*map(float, qr[:3]))))
        j.CreateLocalPos1Attr(Gf.Vec3f(0))
        j.CreateLocalRot1Attr(Gf.Quatf(1))
        self.held = self.current
        self.events.append({"event": "ASSISTED_GRASP", "job": self.job})

    def release(self):
        if self.grasp_path:
            import isaaclab.sim as sim

            sim.get_current_stage().RemovePrim(self.grasp_path)
            self.grasp_path = None
        self.held = None

    def restore_collisions(self):
        if self.filtered_fruit:
            import isaaclab.sim as sim
            from pxr import UsdPhysics

            prim = sim.get_current_stage().GetPrimAtPath(self.filtered_fruit)
            UsdPhysics.FilteredPairsAPI(prim).GetFilteredPairsRel().ClearTargets(True)
            self.filtered_fruit = None

    def exclude_robot_contacts(self):
        # Functional assisted grasp: exclude approximate hand/arm contact
        # during approach and wrist rotation. All lane/bin/fruit contacts stay.
        import isaaclab.sim as sim
        from pxr import UsdPhysics

        stage = sim.get_current_stage()
        fruit_prim = stage.GetPrimAtPath(self.current["path"])
        bodies = [
            prim.GetPath()
            for prim in stage.Traverse()
            if str(prim.GetPath()).startswith("/World/HCRRobot")
            and prim.HasAPI(UsdPhysics.RigidBodyAPI)
        ]
        UsdPhysics.FilteredPairsAPI.Apply(
            fruit_prim
        ).CreateFilteredPairsRel().SetTargets(bodies)
        self.filtered_fruit = self.current["path"]

    def in_bin(self, f):
        p = f["object"].data.root_pos_w[0].cpu().numpy()
        s = self.cfg["storage"]
        run = (s["ramp_length"] ** 2 - s["ramp_rise"] ** 2) ** 0.5
        edge = s["drop_x"] - run
        sign = 1 if f["color"] == "RED" else -1
        zlow = s["drop_z"] - s["ramp_rise"]
        # Storage includes both the receiving chute and its flat tray. Later
        # fruit may queue on the chute behind fruit already in the tray.
        surface = zlow + max(0, min(run, p[0] - edge)) * s["ramp_rise"] / run
        return (
            edge - s["bin_length"] + 0.015 < p[0] < s["drop_x"] - 0.01
            and 0.005 < sign * p[1] < s["width"] / 2 - 0.008
            and surface - 0.005 < p[2] < surface + self.cfg["physics"]["pepper_length"] + 0.02
        )

    def tick(self, now, ready, states, allow_select=True):
        if self.phase == "SCANNING":
            if self.canceled:
                self.phase = "CANCELED"
                self.active = False
                return
            if not ready:
                self.empty_since = None
                return
            chosen = next(
                ((n, states[n]) for n in "ABCD" if states.get(n) in ("RED", "YELLOW")),
                None,
            )
            if chosen and allow_select:
                self.choose(*chosen, now)
            elif allow_select and all(states.get(n) == "NO_COLOR" for n in "ABCD"):
                if self.empty_since is None:
                    self.empty_since = now
                if now - self.empty_since >= 3:
                    self.phase = "SUCCESS"
                    self.active = False
            else:
                self.empty_since = None
            return
        if self.phase in ("IDLE", "SUCCESS", "CANCELED", "ERROR", "DONE"):
            return
        t = min(1, (now - self.step_start) / self.duration)
        blend = t * t * (3 - 2 * t)
        self.q = self.from_q + blend * (self.target - self.from_q)
        if self.phase in self.paths:
            knots = self.paths[self.phase]
            v = blend * (len(knots) - 1)
            i = min(int(v), len(knots) - 2)
            self.q = knots[i] + (v - i) * (knots[i + 1] - knots[i])
        if t < 1:
            return
        # Wait for measured tracking, not only the commanded trajectory time.
        measured = self.robot.data.joint_pos[0, self.arm_ids].cpu().numpy()
        if np.max(np.abs(measured - self.q)) > 0.04:
            if now - self.step_start > self.duration + 3:
                self.events.append(
                    {
                        "event": "TRACKING_ERROR",
                        "phase": self.phase,
                        "target": self.q.tolist(),
                        "measured": measured.tolist(),
                    }
                )
                self.fail("JOINT_TRACKING_TIMEOUT")
            return
        if self.phase == "CLOSE" and self.held is None:
            self.attach()
            if self.phase == "ERROR":
                return
        if self.phase == "VERIFY_BIN":
            if not self.in_bin(self.current):
                self.fail("RELEASE_NOT_IN_CORRECT_BIN")
                return
            self.current["sorted"] = True
            self.counts[0 if self.current["color"] == "RED" else 1] += 1
            self.completed.append(self.job)
            self.events.append(
                {"event": "DONE", "job": self.job, "counts": self.counts.copy()}
            )
            self.phase = "DONE"
            return
        self.index += 1
        self.enter(now)

    def ready_again(self, now):
        if self.phase == "DONE":
            self.phase = "CANCELED" if self.canceled else "SCANNING"
            self.active = not self.canceled
            self.empty_since = None
            self.scan_after = now + 0.5
