"""Small Script Editor panel for the currently open farm scene."""
import asyncio
import json
from pathlib import Path
import traceback

_panel = None


class CapturePanel:
    def __init__(self, project_root):
        import omni.ui as ui
        self.root = Path(project_root)
        self.job = None
        self.window = ui.Window("Scout training dataset", width=540, height=350)
        with self.window.frame:
            with ui.VStack(spacing=8):
                ui.Label("Current scene | optical centre 1.14 m from Bed_Edge")
                ui.Label("Sections: all or BED_01,BED_02 ... (survey-side IDs)")
                self.sections = ui.SimpleStringModel("all")
                ui.StringField(model=self.sections)
                with ui.HStack():
                    ui.Label("Images per section")
                    self.count = ui.SimpleIntModel(100)
                    ui.IntField(model=self.count)
                ui.Button("0. Random XYZ rotation (config) and SAVE", clicked_fn=self.rotate)
                ui.Button("1. Label Red/Yellow and SAVE current map", clicked_fn=self.label)
                ui.Button("2. Generate dataset from current scene", clicked_fn=self.start)
                ui.Button("Stop generation", clicked_fn=self.stop)
                self.status = ui.Label("Ready. Detailed progress appears in the terminal.", word_wrap=True)

    def rotate(self):
        from .stage import load_fruit_rotation_settings, randomize_current_stage_and_save
        if self.job and not self.job.done():
            self.status.text = "Stop capture before changing fruit rotations."
            return
        try:
            settings = load_fruit_rotation_settings(self.root)
            rotations = randomize_current_stage_and_save(**settings)
            self.status.text = f"Saved: {len(rotations)} peppers, XYZ offsets within +/-{settings['max_degrees']:g} deg."
        except Exception as exc:
            traceback.print_exc()
            self.status.text = str(exc)

    def label(self):
        from .stage import label_current_stage_and_save
        if self.job and not self.job.done():
            self.status.text = "Capture is running. Stop it before saving the map."
            return
        try:
            cfg = json.loads((self.root/"sim/config/scout_dataset.json").read_text(encoding="utf-8"))
            graph = json.loads((self.root/cfg["graph"]).read_text(encoding="utf-8"))
            fruits = label_current_stage_and_save(graph)
            self.status.text = f"Saved current map: {len(fruits)} Red/Yellow fruit labels."
        except Exception as exc:
            traceback.print_exc()
            self.status.text = str(exc)

    def start(self):
        if self.job and not self.job.done():
            return
        import omni.usd
        from .capture import generate
        try:
            cfg = json.loads((self.root/"sim/config/scout_dataset.json").read_text(encoding="utf-8"))
            cfg["sections"] = self.sections.as_string.replace(",", " ").split()
            cfg["frames_per_section"] = self.count.as_int
            cfg["output_dir"] = str((self.root/cfg["output_dir"]).resolve())
            graph = json.loads((self.root/cfg["graph"]).read_text(encoding="utf-8"))
            stage = omni.usd.get_context().get_stage()
            if stage is None:
                raise RuntimeError("Open the farm scene first")
        except Exception as exc:
            self.status.text = str(exc)
            return

        async def task():
            self.status.text = "Capturing. See terminal for per-section progress."
            try:
                result = await generate(stage, cfg, graph)
                self.status.text = f"Done: {result['images']} images\n{result['dataset']}"
            except asyncio.CancelledError:
                self.status.text = "Stopped. Completed frames and failure/stop summary were retained."
            except Exception as exc:
                traceback.print_exc()
                self.status.text = str(exc)
        self.job = asyncio.ensure_future(task())

    def stop(self):
        if self.job and not self.job.done():
            self.job.cancel()


def show_panel(project_root):
    global _panel
    if _panel and _panel.job and not _panel.job.done():
        raise RuntimeError("Stop the existing capture before reloading this panel")
    _panel = CapturePanel(project_root)
    return _panel
