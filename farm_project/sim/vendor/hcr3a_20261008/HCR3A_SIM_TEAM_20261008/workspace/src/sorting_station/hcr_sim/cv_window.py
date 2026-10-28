"""OpenCV GUI in a separate Python process, isolated from Isaac's headless cv2.

Only display frames and mouse/key events cross the boundary. Classification,
ROI persistence, robot commands and camera state stay in the simulator.
"""

import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import uuid


class CameraWindow:
    def __init__(self, cv, output_root, title="HCR SIM camera"):
        self.cv = cv
        self.folder = Path(output_root) / "gui" / uuid.uuid4().hex
        self.folder.mkdir(parents=True, exist_ok=True)
        self.frame = self.folder / "frame.png"
        self.events = queue.Queue()
        self.log_path = self.folder / "stderr.log"
        self.log = self.log_path.open("w")
        env = os.environ.copy()
        # Isaac's Python/Qt/library paths must not leak into system Python.
        for name in ("PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH",
                     "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_FONTDIR"):
            env.pop(name, None)
        python = env.get("HCR_GUI_PYTHON", "/usr/bin/python3")
        try:
            self.process = subprocess.Popen(
                [python, "-u", str(Path(__file__).resolve()), str(self.folder), title],
                env=env, stdout=subprocess.PIPE, stderr=self.log, text=True,
            )
        except OSError as exc:
            self.log.close()
            raise RuntimeError(f"Cannot start camera GUI Python: {python}") from exc
        self.reader = threading.Thread(target=self._read_events, daemon=True)
        self.reader.start()
        try:
            event = self.events.get(timeout=10)
            if event.get("kind") != "ready":
                raise RuntimeError("Camera GUI did not initialize")
        except (queue.Empty, RuntimeError) as exc:
            self.close()
            detail = self.log_path.read_text().strip()
            raise RuntimeError(
                "Camera GUI could not open. HCR_GUI_PYTHON must point to Python "
                "with GUI-capable OpenCV and desktop display access. "
                f"GUI log: {self.log_path}\n{detail[-2000:]}"
            ) from exc

    def _read_events(self):
        try:
            for line in self.process.stdout:
                try:
                    self.events.put(json.loads(line))
                except ValueError:
                    continue
        finally:
            self.events.put(dict(kind="closed", returncode=self.process.wait()))

    def show(self, frame):
        ok, encoded = self.cv.imencode(".png", frame)
        if not ok:
            raise RuntimeError("Cannot encode camera GUI frame")
        temporary = self.frame.with_suffix(".tmp")
        temporary.write_bytes(encoded.tobytes())
        os.replace(temporary, self.frame)

    def poll(self):
        events = []
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                return events
            if event.get("kind") == "closed" and event.get("returncode"):
                raise RuntimeError(f"Camera GUI exited unexpectedly; see {self.log_path}")
            events.append(event)

    def close(self):
        (self.folder / "close").touch()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.reader.join(timeout=1)
        self.process.stdout.close()
        self.log.close()


def run_window(folder, title):
    import cv2

    folder = Path(folder)
    frame = folder / "frame.png"

    def send(**event):
        print(json.dumps(event), flush=True)

    def mouse(event, x, y, flags, _):
        if event in (cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP):
            send(kind="mouse", event=event, x=x, y=y, flags=flags)

    cv2.namedWindow(title, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(title, mouse)
    # Qt HighGUI waitKey can return lowercase even for Shift+C. Preserve the
    # actual typed character with Qt events when this backend is available.
    key_filter = None
    try:
        from PyQt5 import QtCore, QtWidgets

        qt_app = QtWidgets.QApplication.instance()
        if qt_app is not None:
            class KeyFilter(QtCore.QObject):
                def eventFilter(self, obj, event):
                    if event.type() == QtCore.QEvent.KeyPress:
                        text = event.text()
                        if event.key() == QtCore.Qt.Key_Escape:
                            send(kind="key", key=27)
                            return True
                        if len(text) == 1 and text in "abcdABCDgsqrtCx":
                            send(kind="key", key=ord(text))
                            return True
                    return False

            key_filter = KeyFilter()
            qt_app.installEventFilter(key_filter)
    except ImportError:
        pass
    send(kind="ready")
    previous = None
    try:
        while not (folder / "close").exists():
            try:
                stamp = frame.stat().st_mtime_ns
            except FileNotFoundError:
                stamp = None
            if stamp is not None and stamp != previous:
                image = cv2.imread(str(frame))
                if image is not None:
                    cv2.imshow(title, image)
                    previous = stamp
            key = cv2.waitKey(10) & 255
            if key != 255 and key_filter is None:
                send(kind="key", key=key)
            if previous is not None and cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                send(kind="key", key=ord("q"))
                break
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    import sys

    run_window(sys.argv[1], sys.argv[2])
