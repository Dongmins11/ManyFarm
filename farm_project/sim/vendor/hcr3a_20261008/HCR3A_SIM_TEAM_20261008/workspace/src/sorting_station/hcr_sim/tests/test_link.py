"""Local socket test: status heartbeat must survive a blocked render/control loop."""

import sys
import threading
import time
import unittest
from hcr_sim.model import ROOT
from hcr_sim.link import SimHCRLink

sys.path.insert(0, str(ROOT / "src/sorting_station/hcr_sorting"))
from hcr_sorting.modbus import ModbusServer, RegisterBank


class LinkTests(unittest.TestCase):
    def test_heartbeat_is_independent_of_control_tick(self):
        bank = RegisterBank()
        bank.update([11, 7, 1, 1, 2])
        server = ModbusServer(("127.0.0.1", 0), bank, "127.0.0.1")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        link = None
        try:
            link = SimHCRLink(server.server_address[1])
            link.status(2, 7, 0)
            # Deliberately do not tick the simulator or update link state.
            time.sleep(0.45)
            events, overflow = bank.drain()
            self.assertFalse(overflow)
            self.assertGreaterEqual(len(events), 3)
            self.assertEqual(events[-1][1:], (2, 7, 0, 0))
            self.assertEqual(link.latest, (11, 7, 1, 1, 2))
            self.assertEqual(link.error, "")
        finally:
            if link:
                link.close()
            server.shutdown()
            server.server_close()
            thread.join(2)


if __name__ == "__main__":
    unittest.main()
