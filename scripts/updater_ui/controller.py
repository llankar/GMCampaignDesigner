from __future__ import annotations

import traceback
from pathlib import Path
import queue
import tempfile
import threading
from tkinter import messagebox

from apply_update import apply_update, parse_args
from updater_ui.window import UpdaterWindow


_LOG_PATH = Path(tempfile.gettempdir()) / "gmcampaign_updater.log"


class UpdaterController:
    def __init__(self, args) -> None:
        self.args = args
        self.window = UpdaterWindow()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.exit_code = 1

    def run(self) -> int:
        worker = threading.Thread(target=self._run_update, args=(self.args,), daemon=True)
        worker.start()
        self.window.root.after(100, self._pump_events)
        self.window.run()
        return self.exit_code

    def _run_update(self, args: object) -> None:
        try:
            apply_update(args, progress_cb=self._progress_callback)
        except Exception as exc:
            self._write_error_log(exc)
            self.events.put(("error", exc))
            return
        self.events.put(("done", None))

    def _progress_callback(self, message: str, fraction: float) -> None:
        self.events.put(("progress", (message, fraction)))

    def _pump_events(self) -> None:
        keep_running = True
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if event == "progress":
                message, fraction = payload  # type: ignore[misc]
                self.window.set_progress(message, fraction)
            elif event == "done":
                self.exit_code = 0
                self.window.show_success()
                self.window.root.after(1200, self.window.root.destroy)
                keep_running = False
            elif event == "error":
                self.exit_code = 1
                error = payload
                clear_message = (
                    f"The update could not be completed.\n\n"
                    f"Error: {error}\n\n"
                    f"A detailed log has been written to:\n{_LOG_PATH}"
                )
                self.window.show_error(f"Error details logged to: {_LOG_PATH}")
                messagebox.showerror("Updater error", clear_message, parent=self.window.root)
                self.window.root.after(150, self.window.root.destroy)
                keep_running = False

        if keep_running:
            self.window.root.after(100, self._pump_events)

    def _write_error_log(self, exc: Exception) -> None:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write("\n=== GMCampaignDesigner updater failure ===\n")
            handle.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def run_updater_app() -> int:
    args = parse_args()
    controller = UpdaterController(args)
    return controller.run()


if __name__ == "__main__":
    raise SystemExit(run_updater_app())
