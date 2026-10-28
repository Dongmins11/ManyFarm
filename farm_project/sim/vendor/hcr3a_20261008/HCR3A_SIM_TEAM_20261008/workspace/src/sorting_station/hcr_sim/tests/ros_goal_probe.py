"""Integration probe: real ROS goal + Modbus + RGB/physics simulator.

Start this under a sourced ROS environment, then launch run_hcr_sim.py
--modbus --auto-roi --pepper-per-lane 1. No synthetic camera states.
"""

import json
import argparse
import time
from pathlib import Path

import rclpy
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from smartfarm_interfaces.action import SortBatch
from hcr_sorting.node import SorterNode


def main():
    root = Path.cwd() / "outputs/sorting_station/hcr_sim"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "validation/ros")
    parser.add_argument("--wait-for-steps", type=int, default=24000)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    task = "sim_" + str(time.time_ns())
    rclpy.init(args=["--ros-args", "-p", "robot_id:=sorter_sim",
                    "-p", "modbus_host:=127.0.0.1", "-p", "modbus_port:=1502",
                    "-p", "modbus_peer:=127.0.0.1",
                    "-p", f"camera_state:={root / 'state.json'}",
                    "-p", f"runtime_state:={out / 'runtime.json'}",
                    "-p", f"journal:={out / (task + '.sqlite3')}",
                    "-p", "camera_timeout:=3.0", "-p", "scene_timeout:=120.0"])
    server = SorterNode()
    node = Node("hcr_sim_goal_probe")
    executor = SingleThreadedExecutor()
    executor.add_node(server)
    executor.add_node(node)
    action = ActionClient(node, SortBatch, "/sorter_sim/sort_batch")
    feedback = []

    def until(predicate, seconds):
        deadline = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() > deadline:
                raise TimeoutError(server.engine.view(time.monotonic()))
            executor.spin_once(timeout_sec=.05)

    def on_feedback(msg):
        f = msg.feedback
        feedback.append(dict(phase=f.phase, red=f.red_count, yellow=f.yellow_count))

    try:
        print("WAITING FOR SIM CAMERA + HCR READY", flush=True)
        until(lambda: server.engine.ready(time.monotonic()) and action.server_is_ready(), 300)
        goal = SortBatch.Goal(robot_id="sorter_sim", task_id=task,
                             batch_id="sim_validation", timestamp="2026-10-07T00:00:00Z")
        future = action.send_goal_async(goal, feedback_callback=on_feedback)
        until(future.done, 10)
        handle = future.result()
        assert handle.accepted, "Goal rejected"
        print("GOAL ACCEPTED", flush=True)
        result_future = handle.get_result_async()
        until(result_future.done, 600)
        result = result_future.result().result
        report = dict(result_code=result.result_code, red_count=result.red_count,
                      yellow_count=result.yellow_count, error_code=result.error_code,
                      feedback=feedback, task_id=task)
        (out / "goal_result.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({k: v for k, v in report.items() if k != "feedback"}), flush=True)
        assert (result.result_code, result.red_count, result.yellow_count) == ("SUCCESS", 2, 2)
        assert any(f["phase"] == "BUSY" for f in feedback)
        # Keep the PC heartbeat alive until the finite simulator saves its
        # own physical positions and events (run it with --steps 24000).
        def simulator_saved():
            try:
                data = json.loads((root / "report.json").read_text())
                return data["counts"] == [2, 2] and data["steps"] >= args.wait_for_steps
            except (OSError, ValueError, KeyError):
                return False
        until(simulator_saved, 120)
    finally:
        action.destroy()
        executor.remove_node(server)
        executor.remove_node(node)
        server.close()
        node.destroy_node()
        executor.shutdown()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
