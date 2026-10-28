"""Geometric harvest-task planner; all lengths are in metres.

The robot faces world +X or -X. ``direction=-1`` reverses task selection order,
independently of robot heading. Its straight route is parallel to X, and rigid
local arm/work offsets locate the work box relative to its base. The algorithm
checks a box, not inverse kinematics, approach paths, collisions, or perception
uncertainty. Observations must already have stable fruit IDs across views.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import math
from numbers import Real
from typing import Any, Iterable, Literal


EPSILON = 1e-9


@dataclass(frozen=True)
class Config:
    width: float = 0.35
    margin: float = 0.03
    mount_x: float = 0.08
    mount_y: float = 0.10
    mount_z: float = 0.40
    work_distance: float = 0.25
    depth: float = 0.10
    z_min: float = -0.10
    z_max: float = 0.35
    bed_y: float = 0.0
    route_start: float = 0.0
    route_end: float = 1.5
    direction: int = 1
    base_yaw: float = 0.0
    work_side: int = 1
    range_tolerance: float = 0.0
    membership_margin: float = 0.03
    depth_tolerance: float = 0.0  # 깊이(Y) 측정 오차 여유(m). 실제 작업 상자는 유지한다.

    @property
    def mount_world_xy(self) -> tuple[float, float]:
        """Rotate the local mount offset for the supported 0/π route headings."""
        sign = 1 if math.cos(self.base_yaw) > 0 else -1
        return sign * self.mount_x, sign * self.mount_y

    @property
    def work_world_xy(self) -> tuple[float, float]:
        """Work-box offset from the mount; local -Y is the robot's right."""
        sign = 1 if math.cos(self.base_yaw) > 0 else -1
        return 0.0, sign * self.work_side * self.work_distance

    @property
    def route_y(self) -> float:
        """Base route offset that keeps the work-box centre at ``bed_y``."""
        return self.bed_y - self.mount_world_xy[1] - self.work_world_xy[1]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        for name, value in asdict(self).items():
            _require_finite(name, value)
        if self.direction not in (-1, 1):
            raise ValueError("direction must be +1 or -1")
        if self.work_side not in (-1, 1):
            raise ValueError("work_side must be +1 (left) or -1 (right)")
        yaw = math.remainder(self.base_yaw, 2 * math.pi)
        if min(abs(yaw), abs(abs(yaw) - math.pi)) > EPSILON:
            raise ValueError("base_yaw must be 0 or pi for the straight X route")
        if self.width <= 0:
            raise ValueError("width must be positive")
        if self.margin < 0 or 2 * self.margin >= self.width:
            raise ValueError("margin must be nonnegative and less than width / 2")
        if self.membership_margin < 0 or 2 * self.membership_margin >= self.width:
            raise ValueError("membership_margin must be nonnegative and less than width / 2")
        if self.range_tolerance < 0:
            raise ValueError("range_tolerance must be nonnegative")
        if self.depth_tolerance < 0:
            raise ValueError("depth_tolerance must be nonnegative")
        if self.depth <= 0:
            raise ValueError("depth must be positive")
        if self.work_distance <= 0:
            raise ValueError("work_distance must be positive")
        if self.z_min >= self.z_max:
            raise ValueError("z_min must be less than z_max")
        if self.route_start >= self.route_end:
            raise ValueError("route_start must be less than route_end")


@dataclass(frozen=True)
class Fruit:
    id: str
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Task:
    task_id: int
    anchor_id: str
    member_ids: tuple[str, ...]
    observed_ids: tuple[str, ...]
    base_x: float
    base_y: float
    arm_x: float
    arm_y: float
    arm_z: float
    window_x_min: float
    window_x_max: float
    window_y_min: float
    window_y_max: float
    window_z_min: float
    window_z_max: float
    safe_x_min: float
    safe_x_max: float
    base_yaw: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["member_ids"] = list(self.member_ids)
        result["observed_ids"] = list(self.observed_ids)
        return result


@dataclass(frozen=True)
class Hold:
    anchor_id: str
    reason: str


@dataclass(frozen=True)
class Event:
    kind: Literal["task", "hold"]
    anchor_id: str
    task: Task | None = None
    reason: str = ""


@dataclass
class PlanResult:
    tasks: list[Task] = field(default_factory=list)
    holds: list[Hold] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": [task.to_dict() for task in self.tasks],
            "holds": [asdict(hold) for hold in self.holds],
            "events": [
                {
                    "kind": event.kind,
                    "anchor_id": event.anchor_id,
                    "task": event.task.to_dict() if event.task else None,
                    "reason": event.reason,
                }
                for event in self.events
            ],
        }


def _require_finite(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def validate_fruits(fruits: Iterable[Fruit]) -> list[Fruit]:
    """Materialize and validate observations without changing their coordinates."""
    result = list(fruits)
    ids: set[str] = set()
    for fruit in result:
        if not isinstance(fruit, Fruit):
            raise ValueError("each observation must be a Fruit")
        if not isinstance(fruit.id, str) or not fruit.id.strip():
            raise ValueError("fruit IDs must be nonempty strings")
        if fruit.id in ids:
            raise ValueError(f"duplicate fruit ID: {fruit.id}")
        ids.add(fruit.id)
        for axis in ("x", "y", "z"):
            _require_finite(f"fruit {fruit.id}.{axis}", getattr(fruit, axis))
    return result


def _inside(value: float, lower: float, upper: float, tolerance: float = 0.0) -> bool:
    return lower - tolerance - EPSILON <= value <= upper + tolerance + EPSILON


def plan_harvest(fruits: Iterable[Fruit], config: Config | None = None) -> PlanResult:
    """Anchor each group at the first remaining fruit in traversal order.

    A held anchor is removed from the current planning pass, never silently
    discarded or retried indefinitely. A route-bound hold means this *strict
    anchor rule* cannot produce an allowed stop; it does not establish that the
    fruit is unreachable under every possible alternative grouping policy.

    ``observed_ids`` contains all input fruit points in the full outer 3-D box,
    including previously assigned/held points. It describes geometric inclusion,
    not camera visibility. ``member_ids`` owns only still-pending points in the
    membership-inset box plus per-axis range_tolerance. Placement margin only
    positions the anchor; membership_margin defines the independent X inset.
    """
    config = Config() if config is None else config
    if not isinstance(config, Config):
        raise ValueError("config must be a Config")
    config.validate()
    observations = sorted(
        validate_fruits(fruits), key=lambda fruit: (config.direction * fruit.x, fruit.id)
    )
    pending = list(observations)
    result = PlanResult()
    y_min = config.bed_y - config.depth / 2
    y_max = config.bed_y + config.depth / 2
    z_min = config.mount_z + config.z_min
    z_max = config.mount_z + config.z_max

    def hold(anchor: Fruit, reason: str) -> None:
        result.holds.append(Hold(anchor.id, reason))
        result.events.append(Event("hold", anchor.id, reason=reason))
        pending.pop(0)

    for name, value in (("route_y", config.route_y), ("window_y_min", y_min),
                        ("window_y_max", y_max), ("window_z_min", z_min),
                        ("window_z_max", z_max)):
        _require_finite(name, value)

    while pending:
        anchor = pending[0]
        if not _inside(anchor.y, y_min, y_max, config.range_tolerance + config.depth_tolerance):
            hold(anchor, "depth_out_of_range")
            continue
        if not _inside(anchor.z, z_min, z_max, config.range_tolerance):
            hold(anchor, "height_out_of_range")
            continue

        left = (anchor.x - config.margin if config.direction == 1
                else anchor.x + config.margin - config.width)
        right = left + config.width
        arm_x = (left + right) / 2 - config.work_world_xy[0]
        base_x = arm_x - config.mount_world_xy[0]
        # Placement margin and membership inset are independent policies.
        safe_left, safe_right = left + config.membership_margin, right - config.membership_margin
        for name, value in (("window_x_min", left), ("window_x_max", right),
                            ("arm_x", arm_x), ("base_x", base_x)):
            _require_finite(name, value)
        if not _inside(base_x, config.route_start, config.route_end):
            hold(anchor, "route_out_of_range")
            continue

        def fits(fruit: Fruit, x_min: float, x_max: float) -> bool:
            return (_inside(fruit.x, x_min, x_max, config.range_tolerance)
                    and _inside(fruit.y, y_min, y_max, config.range_tolerance + config.depth_tolerance)
                    and _inside(fruit.z, z_min, z_max, config.range_tolerance))

        members = tuple(fruit.id for fruit in pending if fits(fruit, safe_left, safe_right))
        if anchor.id not in members:
            raise ValueError("coordinate scale cannot preserve the configured anchor margin")
        observed = tuple(fruit.id for fruit in observations if fits(fruit, left, right))
        task = Task(
            task_id=len(result.tasks) + 1,
            anchor_id=anchor.id,
            member_ids=members,
            observed_ids=observed,
            base_x=base_x,
            base_y=config.route_y,
            arm_x=arm_x,
            arm_y=config.route_y + config.mount_world_xy[1],
            arm_z=config.mount_z,
            window_x_min=left,
            window_x_max=right,
            window_y_min=y_min,
            window_y_max=y_max,
            window_z_min=z_min,
            window_z_max=z_max,
            safe_x_min=safe_left,
            safe_x_max=safe_right,
            base_yaw=config.base_yaw,
        )
        result.tasks.append(task)
        result.events.append(Event("task", anchor.id, task=task))
        assigned = set(members)
        pending = [fruit for fruit in pending if fruit.id not in assigned]

    return result


def _fits_task(fruit: Fruit, task: Task, *, safe: bool, tolerance: float = 0.0,
               depth_tolerance: float = 0.0) -> bool:
    return (_inside(fruit.x, task.safe_x_min if safe else task.window_x_min,
                    task.safe_x_max if safe else task.window_x_max, tolerance)
            and _inside(fruit.y, task.window_y_min, task.window_y_max, tolerance + depth_tolerance)
            and _inside(fruit.z, task.window_z_min, task.window_z_max, tolerance))


def extend_plan(previous: PlanResult, observed: Iterable[Fruit],
                config: Config | None = None, *, revalidate: bool = False,
                overlap_trigger_ratio: float | None = None) -> PlanResult:
    """Accumulate one observation without moving or replacing existing windows.

    With revalidate=True, updated points are checked against their existing
    window; out-of-range members are released and reconsidered. Unobserved
    points retain membership. Empty windows stay reserved internally so IDs
    and geometry are never reused; callers omit empty tasks from dispatch.
    With revalidate=False, existing membership is permanent. Newly visible
    IDs first join an existing task whose safe 3-D box contains them; if several
    do, the oldest task wins. Only the remaining IDs can anchor new windows.
    A held fruit is retried when it is observed again, while unseen holds remain.
    No matching is attempted here: stable IDs are a prerequisite supplied by the
    observation source (simulated body IDs in this demo).

    The result is a new object. Existing task IDs, anchors, and geometry stay
    fixed; member/observed tuples can shrink when revalidating corrected points.
    Events describe the
    current accumulated plan, with one event per task or unresolved held ID.
    """
    if not isinstance(previous, PlanResult):
        raise ValueError("previous must be a PlanResult")
    config = Config() if config is None else config
    if not isinstance(config, Config):
        raise ValueError("config must be a Config")
    config.validate()
    observations = sorted(validate_fruits(observed),
                          key=lambda fruit: (config.direction * fruit.x, fruit.id))
    owners: set[str] = set()
    task_ids: set[int] = set()
    by_id = {fruit.id: fruit for fruit in observations}
    prepared = []
    for task in previous.tasks:
        if task.task_id in task_ids:
            raise ValueError("previous plan has duplicate task IDs")
        task_ids.add(task.task_id)
        for member in task.member_ids:
            if member in owners:
                raise ValueError(f"previous plan assigns fruit {member} more than once")
            owners.add(member)

        if revalidate:
            members = tuple(fid for fid in task.member_ids
                            if fid not in by_id or _fits_task(by_id[fid], task, safe=True,
                                                             tolerance=config.range_tolerance, depth_tolerance=config.depth_tolerance))
            seen = tuple(fid for fid in task.observed_ids
                         if fid not in by_id or _fits_task(by_id[fid], task, safe=False,
                                                          tolerance=config.range_tolerance, depth_tolerance=config.depth_tolerance))
            task = replace(task, member_ids=members, observed_ids=seen)
        prepared.append(task)

    owners = {fid for task in prepared for fid in task.member_ids}

    pending = [fruit for fruit in observations if fruit.id not in owners]
    tasks: list[Task] = []
    for task in prepared:
        additions = tuple(fruit.id for fruit in pending if _fits_task(fruit, task, safe=True, tolerance=config.range_tolerance, depth_tolerance=config.depth_tolerance))
        seen_ids = list(task.observed_ids)
        seen = set(seen_ids)
        for fruit in observations:
            if fruit.id not in seen and _fits_task(fruit, task, safe=False, tolerance=config.range_tolerance, depth_tolerance=config.depth_tolerance):
                seen_ids.append(fruit.id)
                seen.add(fruit.id)
        updated = replace(task, member_ids=task.member_ids + additions,
                          observed_ids=tuple(seen_ids))
        tasks.append(updated)
        owners.update(additions)
        pending = [fruit for fruit in pending if fruit.id not in owners]

    extension = plan_harvest(pending, config)
    next_task_id = max(task_ids, default=0) + 1
    appended_events: list[Event] = []
    for event in extension.events:
        if event.kind == "task" and event.task is not None:
            if overlap_trigger_ratio is not None:
                from .window_overlap import reduce_overlap
                event = replace(event, task=reduce_overlap(
                    event.task, tasks, by_id, config, overlap_trigger_ratio))
            task = replace(event.task, task_id=next_task_id,
                           observed_ids=tuple(fruit.id for fruit in observations
                                              if _fits_task(fruit, event.task, safe=False, tolerance=config.range_tolerance, depth_tolerance=config.depth_tolerance)))
            tasks.append(task)
            owners.update(task.member_ids)
            appended_events.append(Event("task", task.anchor_id, task=task))
            next_task_id += 1
        elif event.kind == "hold":
            appended_events.append(event)

    hold_by_id = {hold.anchor_id: hold for hold in previous.holds
                  if hold.anchor_id not in owners}
    for hold in extension.holds:
        if hold.anchor_id not in owners:
            hold_by_id[hold.anchor_id] = hold

    tasks_by_id = {task.task_id: task for task in tasks}
    events: list[Event] = []
    emitted_tasks: set[int] = set()
    emitted_holds: set[str] = set()
    # Preserve event order where possible while replacing stale task/hold values.
    source_events = previous.events + appended_events
    source_events += [Event("task", task.anchor_id, task=task) for task in tasks]
    source_events += [Event("hold", hold.anchor_id, reason=hold.reason)
                      for hold in hold_by_id.values()]
    for event in source_events:
        if event.kind == "task" and event.task is not None:
            task_id = event.task.task_id
            if task_id in tasks_by_id and task_id not in emitted_tasks:
                task = tasks_by_id[task_id]
                events.append(Event("task", task.anchor_id, task=task))
                emitted_tasks.add(task_id)
        elif event.kind == "hold" and event.anchor_id in hold_by_id:
            if event.anchor_id not in emitted_holds:
                hold = hold_by_id[event.anchor_id]
                events.append(Event("hold", hold.anchor_id, reason=hold.reason))
                emitted_holds.add(hold.anchor_id)

    return PlanResult(tasks=tasks, holds=list(hold_by_id.values()), events=events)
