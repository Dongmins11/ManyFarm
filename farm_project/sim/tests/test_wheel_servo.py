"""실측 바퀴 제어의 제동 방향·적분 제한·측정 오류 처리 검사."""
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_devices'))
from farm_sim_devices.wheel_servo import WheelVelocityServo


class WheelServoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.servo=WheelVelocityServo(dict(kp=1.,ki=4.,max_correction_rad_s=2.))

    def test_stop_resets_integral_and_brakes_measured_motion(self) -> None:
        for _ in range(60):self.servo.command(np.array([.5,-.5]),np.zeros(2))
        result=self.servo.command(np.zeros(2),np.array([.5,-.5]))
        self.assertLess(result[0],0);self.assertGreater(result[1],0)
        np.testing.assert_array_equal(self.servo.integral,np.zeros(2))

    def test_stationary_command_integrates_persistent_disturbance(self) -> None:
        measured=np.array([.05,-.05])
        first=self.servo.command(np.zeros(2),measured)
        for _ in range(60):result=self.servo.command(np.zeros(2),measured)
        self.assertLess(result[0],first[0])
        self.assertGreater(result[1],first[1])
        self.assertLess(self.servo.integral[0],0.)
        self.assertGreater(self.servo.integral[1],0.)

    def test_stalled_wheel_correction_is_bounded(self) -> None:
        for _ in range(1000):result=self.servo.command(np.array([.1,-.1]),np.zeros(2))
        self.assertTrue(np.all(np.abs(result)<=2.1))

    def test_nonfinite_sensor_is_rejected(self) -> None:
        with self.assertRaises(ValueError):self.servo.command(np.zeros(2),np.array([float('nan'),0]))

    def test_zero_motion_has_zero_output(self) -> None:
        np.testing.assert_array_equal(self.servo.command(np.zeros(2),np.zeros(2)),np.zeros(2))


if __name__=='__main__':unittest.main()
