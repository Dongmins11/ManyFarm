"""Photo-derived HCR station geometry, called after Isaac Sim startup. SI units."""

import math


def create_station(cfg):
    import isaaclab.sim as sim
    from pxr import UsdGeom, UsdPhysics, Gf, UsdShade, PhysxSchema

    stage = sim.get_current_stage()
    root = UsdGeom.Xform.Define(stage, "/World/HCRStation").GetPrim()
    root.SetCustomDataByKey("model_status", "photo-derived functional approximation")

    def material(name, static, dynamic):
        path = "/World/HCRMaterials/" + name
        mat = UsdShade.Material.Define(stage, path)
        p = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
        p.CreateStaticFrictionAttr(static)
        p.CreateDynamicFrictionAttr(dynamic)
        p.CreateRestitutionAttr(cfg["physics"]["restitution"])
        PhysxSchema.PhysxMaterialAPI.Apply(mat.GetPrim()).CreateFrictionCombineModeAttr(
            "min" if name == "FoamBoard" else "max"
        )
        return mat

    foam = material(
        "FoamBoard",
        cfg["physics"]["foam_static_friction"],
        cfg["physics"]["foam_dynamic_friction"],
    )
    pad = material(
        "GripPad",
        cfg["physics"]["pad_static_friction"],
        cfg["physics"]["pad_dynamic_friction"],
    )

    def box(name, size, center, rot_y=0, color=(0.91, 0.92, 0.90), mat=foam):
        obj = UsdGeom.Cube.Define(stage, "/World/HCRStation/" + name)
        obj.CreateSizeAttr(1)
        x = UsdGeom.Xformable(obj)
        x.AddTranslateOp().Set(Gf.Vec3d(*map(float, center)))
        if rot_y:
            x.AddRotateYOp().Set(float(rot_y))
        x.AddScaleOp().Set(Gf.Vec3f(*map(float, size)))
        obj.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        UsdPhysics.CollisionAPI.Apply(obj.GetPrim())
        collision = PhysxSchema.PhysxCollisionAPI.Apply(obj.GetPrim())
        collision.CreateContactOffsetAttr(0.001)
        collision.CreateRestOffsetAttr(0)
        UsdShade.MaterialBindingAPI.Apply(obj.GetPrim()).Bind(
            mat, UsdShade.Tokens.weakerThanDescendants, "physics"
        )
        return obj.GetPrim()

    panel = cfg["panel_size"]
    box("RobotMountPlate", panel, [0, 0, panel[2] / 2], color=(0.48, 0.52, 0.56))
    # Grooves are visual only, avoiding thousands of thin contact colliders.
    for i in range(19):
        obj = UsdGeom.Cube.Define(stage, f"/World/HCRStation/PlateGroove{i}")
        obj.CreateSizeAttr(1)
        x = UsdGeom.Xformable(obj)
        x.AddTranslateOp().Set(Gf.Vec3d(0, -0.285 + i * 0.03, panel[2] + 0.0003))
        x.AddScaleOp().Set(Gf.Vec3f(0.49, 0.004, 0.0005))
        obj.CreateDisplayColorAttr([Gf.Vec3f(0.28, 0.30, 0.32)])
    control = cfg["controller_size"]
    cx = -panel[0] / 2 - cfg["controller_gap"] - control[0] / 2
    box("Controller", control, [cx, 0, control[2] / 2], color=(0.10, 0.12, 0.14))
    box(
        "ControllerFrontPanel",
        [0.004, 0.39, 0.37],
        [cx - control[0] / 2 - 0.002, 0, control[2] / 2],
        color=(0.07, 0.08, 0.09),
    )
    r = cfg["intake"]
    run = math.sqrt(r["slope_length"] ** 2 - r["rise"] ** 2)
    angle = math.degrees(math.asin(r["rise"] / r["slope_length"]))
    mid = [r["low_x"] + run / 2, 0, cfg["base_z"] + r["rise"] / 2 - r["board"] / 2]
    box("IntakeSlope", [r["slope_length"], r["width"], r["board"]], mid, -angle)
    for i in range(5):
        h = r["outer_wall_height"] if i in (0, 4) else r["divider_height"]
        y = -r["width"] / 2 + r["board"] / 2 + i * (r["lane_clear_width"] + r["board"])
        # Walls follow the slope with no gap below them.
        box(
            f"IntakeWall{i}",
            [r["slope_length"], r["board"], h],
            [
                mid[0] - math.sin(math.radians(angle)) * h / 2,
                y,
                mid[2] + math.cos(math.radians(angle)) * h / 2,
            ],
            -angle,
        )
    box(
        "IntakeLowLip",
        [0.005, r["width"], r["lip_height"]],
        [r["low_x"] - 0.0025, 0, cfg["base_z"] + r["lip_height"] / 2],
    )
    for x in [r["low_x"] + 0.10, r["low_x"] + run - 0.02]:
        h = max(0.015, cfg["base_z"] + (x - r["low_x"]) * r["rise"] / run - 0.003)
        box("IntakeSupport" + str(int(x * 1000)), [0.025, 0.48, h], [x, 0, h / 2])
    s = cfg["storage"]
    run_s = math.sqrt(s["ramp_length"] ** 2 - s["ramp_rise"] ** 2)
    a = math.degrees(math.asin(s["ramp_rise"] / s["ramp_length"]))
    xhigh = s["drop_x"]
    xlow = xhigh - run_s
    zlow = s["drop_z"] - s["ramp_rise"]
    for color, sign in [("Red", 1), ("Yellow", -1)]:
        y = sign * s["width"] / 4
        width = s["width"] / 2
        box(
            color + "StorageSlope",
            [s["ramp_length"], width, 0.005],
            [(xhigh + xlow) / 2, y, (s["drop_z"] + zlow) / 2 - 0.0025],
            -a,
        )
        for side in [-1, 1]:
            box(
                color + "SlopeSide" + ("L" if side > 0 else "R"),
                [s["ramp_length"], 0.005, s["wall_height"]],
                [
                    (xhigh + xlow) / 2 - 0.025,
                    y + side * (width - 0.005) / 2,
                    (s["drop_z"] + zlow) / 2 + 0.04,
                ],
                -a,
            )
        box(
            color + "StorageInletBack",
            [0.005, width, 0.15],
            [xhigh + 0.012, y, s["drop_z"] + 0.07],
        )
        bx = xlow - s["bin_length"] / 2
        box(color + "BinFloor", [s["bin_length"], width, 0.005], [bx, y, zlow - 0.0025])
        box(
            color + "BinEnd",
            [0.005, width, s["wall_height"]],
            [xlow - s["bin_length"], y, zlow + s["wall_height"] / 2],
        )
        for side in [-1, 1]:
            box(
                color + "BinSide" + ("L" if side > 0 else "R"),
                [s["bin_length"], 0.005, s["wall_height"]],
                [bx, y + side * (width - 0.005) / 2, zlow + s["wall_height"] / 2],
            )
    # Visual foamboard perimeter from photos; front opening keeps view unobstructed.
    box("RearFoamWall", [1.65, 0.005, 0.85], [-0.05, 0.38, 0.425])
    box("LeftFoamWall", [0.005, 0.65, 0.60], [-0.89, 0.055, 0.30])
    return foam, pad
