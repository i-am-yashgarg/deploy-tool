#!/usr/bin/env python3

import os
import sys
import signal
import shlex
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import yaml
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QCheckBox, QSpinBox, QWidget
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "deployment.yaml"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def expand_path(path_text: str) -> str:
    return os.path.abspath(os.path.expanduser(path_text or "~"))


def terminal_executable():
    for name in ("x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"):
        path = shutil.which(name)
        if path:
            return path
    return None


def process_alive(pid):
    """Return True only while the PID represents a live, non-zombie process."""
    if not pid:
        return False

    try:
        stat_path = Path(f"/proc/{pid}/stat")
        if stat_path.exists():
            data = stat_path.read_text(encoding="utf-8", errors="ignore")
            close_paren = data.rfind(")")
            if close_paren != -1:
                state = data[close_paren + 2:close_paren + 3]
                if state == "Z":
                    return False
    except Exception:
        pass

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class StepEditor(QDialog):
    def __init__(self, step=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add / Edit Command")
        self.resize(700, 430)

        step = step or {}

        self.id_edit = QLineEdit(str(step.get("id", "")))
        self.name_edit = QLineEdit(str(step.get("name", "")))
        self.command_edit = QTextEdit(str(step.get("command", "")))
        self.workdir_edit = QLineEdit(str(step.get("working_directory", "~")))

        self.terminal_check = QCheckBox("Open command in a separate terminal")
        self.terminal_check.setChecked(bool(step.get("terminal", False)))

        self.wait_check = QCheckBox("Wait for this command before continuing")
        self.wait_check.setChecked(bool(step.get("wait", True)))

        form = QFormLayout()
        form.addRow("ID:", self.id_edit)
        form.addRow("Name:", self.name_edit)
        form.addRow("Command:", self.command_edit)
        form.addRow("Working Directory:", self.workdir_edit)
        form.addRow("", self.terminal_check)
        form.addRow("", self.wait_check)

        buttons = QHBoxLayout()
        save_btn = QPushButton("SAVE")
        cancel_btn = QPushButton("CANCEL")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def get_step(self):
        return {
            "id": self.id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "command": self.command_edit.toPlainText().strip(),
            "working_directory": self.workdir_edit.text().strip() or "~",
            "terminal": self.terminal_check.isChecked(),
            "wait": self.wait_check.isChecked(),
        }


class CommandManager(QDialog):
    def __init__(self, config_file, parent=None):
        super().__init__(parent)
        self.config_file = Path(config_file)
        self.steps = []
        self.setWindowTitle("Manage Deployment Commands")
        self.resize(1050, 560)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Name", "Command", "Working Directory", "Terminal", "Wait"]
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)

        add_btn = QPushButton("ADD")
        edit_btn = QPushButton("EDIT")
        delete_btn = QPushButton("DELETE")
        up_btn = QPushButton("MOVE UP")
        down_btn = QPushButton("MOVE DOWN")
        save_btn = QPushButton("SAVE")
        close_btn = QPushButton("CLOSE")

        add_btn.clicked.connect(self.add_step)
        edit_btn.clicked.connect(self.edit_step)
        delete_btn.clicked.connect(self.delete_step)
        up_btn.clicked.connect(self.move_up)
        down_btn.clicked.connect(self.move_down)
        save_btn.clicked.connect(self.save_config)
        close_btn.clicked.connect(self.close)

        buttons = QHBoxLayout()
        for b in (add_btn, edit_btn, delete_btn, up_btn, down_btn, save_btn, close_btn):
            buttons.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.steps = data.get("steps", []) or []
            self.refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "Config Error", str(e))

    def refresh_table(self):
        self.table.setRowCount(0)
        for step in self.steps:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                step.get("id", ""),
                step.get("name", ""),
                step.get("command", ""),
                step.get("working_directory", "~"),
                "YES" if step.get("terminal", False) else "NO",
                "YES" if step.get("wait", True) else "NO",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def selected_row(self):
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def add_step(self):
        dialog = StepEditor(parent=self)
        if dialog.exec() == QDialog.Accepted:
            step = dialog.get_step()
            if not self.validate_step(step, None):
                return
            self.steps.append(step)
            self.refresh_table()

    def edit_step(self):
        row = self.selected_row()
        if row < 0:
            QMessageBox.warning(self, "Select Command", "Please select a command first.")
            return

        dialog = StepEditor(self.steps[row], self)
        if dialog.exec() == QDialog.Accepted:
            step = dialog.get_step()
            if not self.validate_step(step, row):
                return
            self.steps[row] = step
            self.refresh_table()

    def delete_step(self):
        row = self.selected_row()
        if row < 0:
            return
        if QMessageBox.question(
            self, "Delete Command",
            f"Delete '{self.steps[row].get('name', self.steps[row].get('id', ''))}'?"
        ) == QMessageBox.Yes:
            self.steps.pop(row)
            self.refresh_table()

    def move_up(self):
        row = self.selected_row()
        if row > 0:
            self.steps[row - 1], self.steps[row] = self.steps[row], self.steps[row - 1]
            self.refresh_table()
            self.table.selectRow(row - 1)

    def move_down(self):
        row = self.selected_row()
        if 0 <= row < len(self.steps) - 1:
            self.steps[row + 1], self.steps[row] = self.steps[row], self.steps[row + 1]
            self.refresh_table()
            self.table.selectRow(row + 1)

    def validate_step(self, step, current_row):
        if not step["id"] or not step["name"] or not step["command"]:
            QMessageBox.warning(self, "Invalid Command", "ID, Name and Command are required.")
            return False

        ids = [s.get("id") for i, s in enumerate(self.steps) if i != current_row]
        if step["id"] in ids:
            QMessageBox.warning(self, "Duplicate ID", f"ID '{step['id']}' already exists.")
            return False

        wd = expand_path(step["working_directory"])
        if not os.path.isdir(wd):
            answer = QMessageBox.question(
                self, "Working Directory",
                f"This directory does not currently exist:\n{wd}\n\nSave anyway?"
            )
            if answer != QMessageBox.Yes:
                return False

        return True

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                yaml.safe_dump({"steps": self.steps}, f, sort_keys=False, allow_unicode=True)
            QMessageBox.information(self, "Saved", "Deployment configuration saved.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))


class DeploymentThread(QThread):
    log_signal = Signal(str)
    status_signal = Signal(str)
    active_count_signal = Signal(int)
    finished_signal = Signal(str)

    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self.steps = steps
        self.stop_requested = False
        self.lock = threading.Lock()

        # Every entry is an ACTUAL command process, not a terminal emulator process.
        # key = step id, value = {"pid": pid, "name": name, "terminal": bool}
        self.active_processes = {}

        self.log_file_path = None

    def write_log(self, message):
        self.log_signal.emit(message)
        if self.log_file_path:
            try:
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(message + "\n")
                    f.flush()
            except Exception:
                pass

    def update_active_count(self):
        with self.lock:
            count = len(self.active_processes)
        self.active_count_signal.emit(count)

    def register_process(self, step_id, pid, name, terminal=False):
        with self.lock:
            self.active_processes[step_id] = {
                "pid": pid,
                "name": name,
                "terminal": terminal,
            }
        self.update_active_count()

    def unregister_process(self, step_id):
        with self.lock:
            self.active_processes.pop(step_id, None)
        self.update_active_count()

    def get_active_processes(self):
        with self.lock:
            return dict(self.active_processes)

    def wait_for_pid(self, step_id, pid, timeout=None):
        start = time.time()

        while process_alive(pid):
            if self.stop_requested:
                return False

            if timeout is not None and time.time() - start >= timeout:
                return False

            time.sleep(0.25)

        return True

    def start_normal(self, step):
        step_id = step["id"]
        command = step["command"]
        cwd = expand_path(step.get("working_directory", "~"))

        self.write_log(f"$ {command}")

        proc = subprocess.Popen(
            ["bash", "-lc", command],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )

        self.register_process(step_id, proc.pid, step["name"], False)

        def reader():
            try:
                for line in iter(proc.stdout.readline, ""):
                    if line:
                        self.write_log(f"[{step_id}] {line.rstrip()}")
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass

        threading.Thread(target=reader, daemon=True).start()

        if step.get("wait", True):
            while proc.poll() is None:
                if self.stop_requested:
                    self.stop_pid(step_id, proc.pid)
                    break
                time.sleep(0.1)

            proc.wait()
            self.unregister_process(step_id)

            if self.stop_requested:
                return False

            self.write_log(
                f"✓ Step {step_id}: {'SUCCESS' if proc.returncode == 0 else 'FAILED'}"
            )
            return proc.returncode == 0

        # Background process: DO NOT unregister here.
        self.write_log(f"Step {step_id} is a long-running process.")
        self.write_log("It will remain active until it exits or STOP is pressed.")
        return True

    def start_terminal(self, step):
        """
        Open the command in a visible terminal and track the terminal launcher
        process itself. GNOME Terminal's --wait makes that process stay alive
        until the command/terminal exits, so even very fast commands are handled
        correctly. The process group is owned by this deployment tool, allowing
        STOP to terminate the command and close the terminal it opened.
        """
        terminal = terminal_executable()
        if not terminal:
            self.write_log("ERROR: No supported terminal emulator found.")
            return False

        step_id = step["id"]
        command = step["command"]
        cwd = expand_path(step.get("working_directory", "~"))

        self.write_log(f"$ {command}")

        term_name = os.path.basename(terminal)

        # Keep the terminal process tied to this deployment process group.
        # --disable-factory prevents an existing GNOME Terminal server from
        # swallowing our process into another process tree.
        shell_command = f"cd {shlex.quote(cwd)} && exec bash -lc {shlex.quote(command)}"

        if term_name == "gnome-terminal":
            launch = [
                terminal,
                "--disable-factory",
                "--wait",
                "--",
                "bash",
                "-lc",
                shell_command,
            ]
        elif term_name == "konsole":
            launch = [
                terminal,
                "--nofork",
                "-e",
                "bash",
                "-lc",
                shell_command,
            ]
        elif term_name == "xfce4-terminal":
            launch = [
                terminal,
                "--disable-server",
                "--command",
                f"bash -lc {shlex.quote(shell_command)}",
            ]
        elif term_name == "xterm":
            launch = [
                terminal,
                "-e",
                "bash",
                "-lc",
                shell_command,
            ]
        else:
            # x-terminal-emulator generally supports -e.
            launch = [
                terminal,
                "-e",
                "bash",
                "-lc",
                shell_command,
            ]

        try:
            proc = subprocess.Popen(
                launch,
                cwd=cwd,
                start_new_session=True,
            )
        except Exception as e:
            self.write_log(f"ERROR launching terminal: {e}")
            return False

        # Track the Popen process immediately. Do NOT wait for a PID file.
        # This fixes the fast-command race that caused:
        # "Could not track actual process for step1."
        self.register_process(step_id, proc.pid, step["name"], True)

        self.write_log(f"Terminal opened for: {step['name']}")
        self.write_log(f"Terminal process PID: {proc.pid}")

        if step.get("wait", True):
            # Wait for the terminal/command to finish. STOP is checked by the
            # worker loop, so the GUI remains responsive.
            while proc.poll() is None:
                if self.stop_requested:
                    self.stop_pid(step_id, proc.pid)
                    break
                time.sleep(0.1)

            return_code = proc.poll()
            if return_code is None:
                try:
                    return_code = proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    return_code = -1

            self.unregister_process(step_id)

            if self.stop_requested:
                return False

            if return_code == 0:
                self.write_log(f"✓ Step {step_id}: SUCCESS")
                return True

            self.write_log(
                f"✗ Step {step_id}: FAILED (exit code {return_code})"
            )
            return False

        # wait:false: keep the terminal process registered until it naturally
        # exits or STOP is pressed. The main deployment sequence can continue.
        self.write_log(f"Step {step_id} is a long-running terminal process.")
        self.write_log("STOP remains available while this terminal is active.")
        return True

    def start_step(self, step):
        self.write_log("")
        self.write_log(f"========== {step['id'].upper()} ==========")
        self.write_log(f"Starting: {step['name']}")

        if not os.path.isdir(expand_path(step.get("working_directory", "~"))):
            self.write_log(
                f"ERROR: Working directory does not exist: "
                f"{expand_path(step.get('working_directory', '~'))}"
            )
            return False

        if step.get("terminal", False):
            return self.start_terminal(step)

        return self.start_normal(step)

    def stop_pid(self, step_id, pid):
        if not pid:
            return

        self.write_log(f"Stopping [{step_id}] PID {pid}...")

        try:
            pgid = os.getpgid(pid)
        except ProcessLookupError:
            return
        except Exception:
            pgid = None

        # Graceful stop.
        try:
            if pgid:
                os.killpg(pgid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except Exception as e:
            self.write_log(f"SIGTERM failed for [{step_id}]: {e}")

        # Never wait forever.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if not process_alive(pid):
                return
            time.sleep(0.05)

        # Force stop.
        try:
            if pgid:
                os.killpg(pgid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except Exception as e:
            self.write_log(f"SIGKILL failed for [{step_id}]: {e}")

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if not process_alive(pid):
                return
            time.sleep(0.05)

        self.write_log(
            f"WARNING: PID {pid} did not disappear immediately; continuing cleanup."
        )

    def stop_all_processes(self):
        active = self.get_active_processes()

        if not active:
            self.update_active_count()
            return

        self.write_log("")
        self.write_log("========================================")
        self.write_log("STOPPING ACTIVE PROCESSES")
        self.write_log("========================================")

        for step_id, info in active.items():
            self.stop_pid(step_id, info["pid"])
            self.unregister_process(step_id)

        self.update_active_count()
        self.write_log("✓ All active processes stopped.")

    def run(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_file_path = LOG_DIR / f"deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        self.write_log("========================================")
        self.write_log("NEXTUP ROBOTICS DEPLOYMENT")
        self.write_log(f"Started: {timestamp}")
        self.write_log("========================================")

        failed = False

        for index, step in enumerate(self.steps, start=1):
            if self.stop_requested:
                break

            self.status_signal.emit(f"RUNNING: {step.get('name', step.get('id', 'Step'))}")

            self.write_log(f"● Step {index}: RUNNING")

            ok = self.start_step(step)

            if not ok and not self.stop_requested:
                failed = True
                self.write_log(f"✗ Step {step['id']} failed.")
                break

            if ok:
                self.write_log(f"✓ {step['name']} started/completed successfully")

        # Sequence has ended, but background processes may still be alive.
        if self.stop_requested:
            self.stop_all_processes()
            self.status_signal.emit("STOPPED")
            self.finished_signal.emit("STOPPED")
            self.write_log("")
            self.write_log("========================================")
            self.write_log("■ DEPLOYMENT STOPPED")
            self.write_log("All active processes were terminated.")
            self.write_log("========================================")
            return

        if failed:
            self.status_signal.emit("FAILED")
            self.finished_signal.emit("FAILED")
            self.write_log("")
            self.write_log("========================================")
            self.write_log("✗ DEPLOYMENT FAILED")
            self.write_log("========================================")
            return

        self.write_log("")
        self.write_log("========================================")
        self.write_log("✓ DEPLOYMENT SEQUENCE COMPLETED")
        self.write_log("All configured steps have been started.")
        self.write_log("========================================")

        # IMPORTANT:
        # Keep the QThread alive while wait:false processes remain active.
        # This guarantees STOP stays available.
        while True:
            if self.stop_requested:
                self.stop_all_processes()
                self.status_signal.emit("STOPPED")
                self.finished_signal.emit("STOPPED")
                self.write_log("")
                self.write_log("========================================")
                self.write_log("■ DEPLOYMENT STOPPED")
                self.write_log("All active processes were terminated.")
                self.write_log("========================================")
                return

            active = self.get_active_processes()

            # Remove processes that naturally exited.
            for step_id, info in list(active.items()):
                if not process_alive(info["pid"]):
                    self.unregister_process(step_id)
                    self.write_log(f"✓ Background process finished: {step_id}")

            if not self.get_active_processes():
                self.status_signal.emit("COMPLETED")
                self.finished_signal.emit("COMPLETED")
                return

            # Sequence is completed, but processes are still active.
            self.status_signal.emit("COMPLETED - PROCESSES ACTIVE")
            time.sleep(0.25)

    def stop(self):
        # Only request the stop here. The worker thread performs cleanup.
        # This prevents the GUI from freezing on STOPPING.
        self.stop_requested = True


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nextup Robotics Deployment Tool")
        self.resize(1150, 760)

        self.steps = []
        self.thread = None
        self.current_log_file = None

        title = QLabel("NEXTUP ROBOTICS\nDEPLOYMENT TOOL")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 27px; font-weight: bold;")

        self.status_label = QLabel("READY")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 21px; font-weight: bold;")

        self.active_label = QLabel("Active Processes: 0")
        self.active_label.setAlignment(Qt.AlignCenter)
        self.active_label.setStyleSheet("font-size: 16px;")

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("font-family: monospace; font-size: 13px;")

        self.start_btn = QPushButton("START DEPLOYMENT")
        self.stop_btn = QPushButton("STOP")
        self.manage_btn = QPushButton("MANAGE COMMANDS")
        self.clear_btn = QPushButton("CLEAR LOG")
        self.reload_btn = QPushButton("RELOAD CONFIG")

        self.start_btn.clicked.connect(self.start_deployment)
        self.stop_btn.clicked.connect(self.stop_deployment)
        self.manage_btn.clicked.connect(self.manage_commands)
        self.clear_btn.clicked.connect(self.log_box.clear)
        self.reload_btn.clicked.connect(self.load_config)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(self.start_btn)
        top_buttons.addWidget(self.stop_btn)
        top_buttons.addWidget(self.manage_btn)

        bottom_buttons = QHBoxLayout()
        bottom_buttons.addWidget(self.clear_btn)
        bottom_buttons.addWidget(self.reload_btn)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.active_label)
        layout.addWidget(self.log_box)
        layout.addLayout(top_buttons)
        layout.addLayout(bottom_buttons)
        self.setCentralWidget(central)

        self.stop_btn.setEnabled(False)
        self.load_config()

        # Safety refresh: button state follows REAL active process count.
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.refresh_button_state)
        self.state_timer.start(250)

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.steps = data.get("steps", []) or []
            self.status_label.setText("READY")
        except Exception as e:
            self.steps = []
            QMessageBox.critical(self, "Config Error", str(e))

    def manage_commands(self):
        if self.has_active_processes():
            QMessageBox.warning(
                self,
                "Deployment Active",
                "Stop all active deployment processes before editing commands."
            )
            return

        dialog = CommandManager(CONFIG_FILE, self)
        if dialog.exec() == QDialog.Accepted:
            self.load_config()

    def has_active_processes(self):
        return bool(
            self.thread
            and self.thread.get_active_processes()
        )

    def refresh_button_state(self):
        active = self.has_active_processes()

        self.active_label.setText(
            f"Active Processes: {len(self.thread.get_active_processes()) if self.thread else 0}"
        )

        # STOP is controlled ONLY by actual active processes.
        self.stop_btn.setEnabled(active)

        # Never allow a second deployment while any process is active.
        self.start_btn.setEnabled(not active)

    def start_deployment(self):
        if self.has_active_processes():
            QMessageBox.warning(
                self,
                "Deployment Already Active",
                "Active deployment processes are already running.\n\n"
                "Stop them before starting another deployment."
            )
            return

        self.load_config()

        if not self.steps:
            QMessageBox.warning(self, "No Commands", "No deployment commands are configured.")
            return

        self.log_box.clear()

        self.thread = DeploymentThread(self.steps)
        self.thread.log_signal.connect(self.log_box.append)
        self.thread.status_signal.connect(self.status_label.setText)
        self.thread.active_count_signal.connect(
            lambda count: self.active_label.setText(f"Active Processes: {count}")
        )
        self.thread.finished_signal.connect(self.deployment_finished)

        self.status_label.setText("STARTING")
        self.thread.start()

        self.refresh_button_state()

    def deployment_finished(self, status):
        self.status_label.setText(status)

        # The worker has completed cleanup. STOP is now definitely finished.
        self.stop_btn.setEnabled(False)
        self.active_label.setText("Active Processes: 0")
        self.start_btn.setEnabled(True)

    def stop_deployment(self):
        # STOP is valid whenever an actual process exists.
        if not self.thread:
            return

        active = self.thread.get_active_processes()

        if not active:
            self.stop_btn.setEnabled(False)
            return

        self.log_box.append("")
        self.log_box.append("■ STOP REQUESTED")
        self.status_label.setText("STOPPING...")
        self.thread.stop()

    def closeEvent(self, event):
        if self.has_active_processes():
            answer = QMessageBox.question(
                self,
                "Active Processes",
                "Deployment processes are still running.\n\n"
                "Stop them and close the application?"
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return

            self.thread.stop()
            self.thread.wait(5000)

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
