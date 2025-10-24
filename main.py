import sys
import os
import subprocess
import shutil
import logging
import hashlib
import json
import uuid
from datetime import datetime
from collections import deque
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
                             QMessageBox, QProgressBar, QGraphicsDropShadowEffect, QPushButton,
                             QFileDialog, QDialog, QTextEdit, QTabWidget, QListWidget, QListWidgetItem,
                             QSplitter, QGroupBox, QCheckBox, QComboBox, QSpinBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QTextBrowser, QStatusBar, QMenuBar, QMenu,
                             QAction, QSystemTrayIcon, QStyle, QFormLayout, QLineEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings, QUrl
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QFont, QIcon, QPixmap, QDesktopServices

def global_exception_handler(exctype, value, traceback):
    """Global exception handler to catch unhandled exceptions"""
    error_msg = f"Uncaught exception: {exctype.__name__}: {value}"
    logging.error(error_msg, exc_info=(exctype, value, traceback))
    try:
        QMessageBox.critical(None, "Unexpected Error", f"An unexpected error occurred:\n{error_msg}\n\nPlease check the logs for more details.")
    except:
        pass
    sys.__excepthook__(exctype, value, traceback)

sys.excepthook = global_exception_handler

class InstallationTask:
    """Represents a single installation task"""
    def __init__(self, file_path, task_id=None):
        self.file_path = file_path
        self.task_id = task_id or hashlib.md5(file_path.encode()).hexdigest()[:8]
        self.status = "queued"  # queued, installing, completed, failed
        self.progress = 0
        self.message = ""
        self.start_time = None
        self.end_time = None
        self.file_hash = self.calculate_hash()
        self.file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    def calculate_hash(self):
        """Calculate SHA256 hash of the file"""
        try:
            with open(self.file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except:
            return "unknown"

    def get_file_type(self):
        """Get the file type/extension"""
        if self.file_path.endswith('.tar.gz'):
            return 'tar.gz'
        elif self.file_path.endswith('.tar.xz'):
            return 'tar.xz'
        _, ext = os.path.splitext(self.file_path)
        return ext.lower().lstrip('.')

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'file_path': self.file_path,
            'task_id': self.task_id,
            'status': self.status,
            'progress': self.progress,
            'message': self.message,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'file_hash': self.file_hash,
            'file_size': self.file_size
        }

    @classmethod
    def from_dict(cls, data):
        """Create instance from dictionary"""
        task = cls(data['file_path'], data.get('task_id'))
        task.status = data.get('status', 'queued')
        task.progress = data.get('progress', 0)
        task.message = data.get('message', '')
        task.start_time = datetime.fromisoformat(data['start_time']) if data.get('start_time') else None
        task.end_time = datetime.fromisoformat(data['end_time']) if data.get('end_time') else None
        task.file_hash = data.get('file_hash', 'unknown')
        task.file_size = data.get('file_size', 0)
        return task

class BatchInstaller(QThread):
    """Handles batch installation of multiple files"""
    progress_updated = pyqtSignal(str, int, str)  # task_id, progress, message
    task_completed = pyqtSignal(str, bool, str)   # task_id, success, message
    batch_finished = pyqtSignal()

    def __init__(self, tasks):
        super().__init__()
        self.tasks = deque(tasks)
        self.running = True

    def run(self):
        while self.tasks and self.running:
            task = self.tasks.popleft()
            task.status = "installing"
            task.start_time = datetime.now()

            try:
                self.progress_updated.emit(task.task_id, 10, f"Starting installation of {os.path.basename(task.file_path)}")

                # Determine file type and install
                ext = self.get_file_type(task.file_path)
                install_func = getattr(self, f"install_{ext.replace('.', '_')}", None)

                if not install_func:
                    raise Exception(f"Unsupported file type: {ext}")

                self.progress_updated.emit(task.task_id, 50, "Installing...")
                result = install_func(task.file_path)

                task.status = "completed"
                task.message = result
                self.progress_updated.emit(task.task_id, 100, result)
                self.task_completed.emit(task.task_id, True, result)

            except Exception as e:
                task.status = "failed"
                task.message = str(e)
                logging.error(f"Installation failed for {task.file_path}: {e}")
                self.progress_updated.emit(task.task_id, 100, f"Failed: {e}")
                self.task_completed.emit(task.task_id, False, str(e))

            task.end_time = datetime.now()

        self.batch_finished.emit()

    def get_file_type(self, file_path):
        if file_path.endswith('.tar.gz'):
            return 'tar.gz'
        elif file_path.endswith('.tar.xz'):
            return 'tar.xz'
        _, ext = os.path.splitext(file_path)
        return ext.lower().lstrip('.')

    def install_deb(self, file_path):
        if not shutil.which('dpkg'):
            raise Exception("dpkg not found. Please install dpkg.")
        self.run_command(['pkexec', 'dpkg', '-i', file_path])
        self.run_command(['pkexec', 'apt-get', 'install', '-f'])
        return f"Successfully installed {os.path.basename(file_path)}"

    def install_appimage(self, file_path):
        app_dir = os.path.expanduser("~/Applications")
        os.makedirs(app_dir, exist_ok=True)
        dest = os.path.join(app_dir, os.path.basename(file_path))
        if os.path.exists(dest):
            base, ext = os.path.splitext(dest)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            dest = f"{base}_{counter}{ext}"
        shutil.move(file_path, dest)
        os.chmod(dest, 0o755)
        return f"AppImage installed to {dest}"

    def install_tar_gz(self, file_path):
        return self.install_tar(file_path)

    def install_tar_xz(self, file_path):
        return self.install_tar(file_path)

    def install_tgz(self, file_path):
        return self.install_tar(file_path)

    def install_tar(self, file_path):
        app_dir = os.path.expanduser("~/Applications")
        os.makedirs(app_dir, exist_ok=True)
        extract_dir = os.path.join(app_dir, os.path.splitext(os.path.basename(file_path))[0])
        os.makedirs(extract_dir, exist_ok=True)
        self.run_command(['tar', '-xf', file_path, '-C', extract_dir])
        install_script = os.path.join(extract_dir, 'install.sh')
        if os.path.exists(install_script):
            os.chmod(install_script, 0o755)
            self.run_command(['pkexec', 'bash', install_script])
        return f"Extracted to {extract_dir}"

    def install_snap(self, file_path):
        if not shutil.which('snap'):
            raise Exception("snap not found. Please install snapd.")
        self.run_command(['pkexec', 'snap', 'install', file_path, '--dangerous'])
        return f"Successfully installed {os.path.basename(file_path)}"

    def install_flatpak(self, file_path):
        if not shutil.which('flatpak'):
            raise Exception("flatpak not found. Please install flatpak.")
        self.run_command(['flatpak', 'install', '--user', file_path])
        return f"Successfully installed {os.path.basename(file_path)}"

    def install_run(self, file_path):
        return self.install_executable(file_path)

    def install_bin(self, file_path):
        return self.install_executable(file_path)

    def install_executable(self, file_path):
        os.chmod(file_path, 0o755)
        self.run_command(['pkexec', 'bash', file_path])
        return f"Executed {os.path.basename(file_path)}"

    def run_command(self, cmd):
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or result.stdout.strip())

# Set the global exception handler
sys.excepthook = global_exception_handler

class InstallationTask:
    """Represents a single installation task"""
    def __init__(self, file_path, task_id=None):
        self.file_path = file_path
        self.task_id = task_id or hashlib.md5(file_path.encode()).hexdigest()[:8]
        self.status = "queued"  # queued, installing, completed, failed
        self.progress = 0
        self.message = ""
        self.start_time = None
        self.end_time = None
        self.file_hash = self.calculate_hash()
        self.file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    def calculate_hash(self):
        """Calculate SHA256 hash of the file"""
        try:
            with open(self.file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except:
            return "unknown"

    def get_file_type(self):
        """Get the file type/extension"""
        if self.file_path.endswith('.tar.gz'):
            return 'tar.gz'
        elif self.file_path.endswith('.tar.xz'):
            return 'tar.xz'
        _, ext = os.path.splitext(self.file_path)
        return ext.lower().lstrip('.')

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'file_path': self.file_path,
            'task_id': self.task_id,
            'status': self.status,
            'progress': self.progress,
            'message': self.message,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'file_hash': self.file_hash,
            'file_size': self.file_size
        }

    @classmethod
    def from_dict(cls, data):
        """Create instance from dictionary"""
        task = cls(data['file_path'], data.get('task_id'))
        task.status = data.get('status', 'queued')
        task.progress = data.get('progress', 0)
        task.message = data.get('message', '')
        task.start_time = datetime.fromisoformat(data['start_time']) if data.get('start_time') else None
        task.end_time = datetime.fromisoformat(data['end_time']) if data.get('end_time') else None
        task.file_hash = data.get('file_hash', 'unknown')
        task.file_size = data.get('file_size', 0)
        return task

class BatchInstaller(QThread):
    """Handles batch installation of multiple files"""
    progress_updated = pyqtSignal(str, int, str)  # task_id, progress, message
    task_completed = pyqtSignal(str, bool, str)   # task_id, success, message
    batch_finished = pyqtSignal()

    def __init__(self, tasks):
        super().__init__()
        self.tasks = deque(tasks)
        self.running = True

    def run(self):
        while self.tasks and self.running:
            task = self.tasks.popleft()
            task.status = "installing"
            task.start_time = datetime.now()

            try:
                self.progress_updated.emit(task.task_id, 10, f"Starting installation of {os.path.basename(task.file_path)}")

                # Determine file type and install
                ext = self.get_file_type(task.file_path)
                install_func = getattr(self, f"install_{ext.replace('.', '_')}", None)

                if not install_func:
                    raise Exception(f"Unsupported file type: {ext}")

                self.progress_updated.emit(task.task_id, 50, "Installing...")
                result = install_func(task.file_path)

                task.status = "completed"
                task.message = result
                self.progress_updated.emit(task.task_id, 100, result)
                self.task_completed.emit(task.task_id, True, result)

            except Exception as e:
                task.status = "failed"
                task.message = str(e)
                logging.error(f"Installation failed for {task.file_path}: {e}")
                self.progress_updated.emit(task.task_id, 100, f"Failed: {e}")
                self.task_completed.emit(task.task_id, False, str(e))

            task.end_time = datetime.now()

        self.batch_finished.emit()

    def get_file_type(self, file_path):
        if file_path.endswith('.tar.gz'):
            return 'tar.gz'
        elif file_path.endswith('.tar.xz'):
            return 'tar.xz'
        _, ext = os.path.splitext(file_path)
        return ext.lower().lstrip('.')

    def install_deb(self, file_path):
        if not shutil.which('dpkg'):
            raise Exception("dpkg not found. Please install dpkg.")
        self.run_command(['pkexec', 'dpkg', '-i', file_path])
        self.run_command(['pkexec', 'apt-get', 'install', '-f'])
        return f"Successfully installed {os.path.basename(file_path)}"

    def install_appimage(self, file_path):
        app_dir = os.path.expanduser("~/Applications")
        os.makedirs(app_dir, exist_ok=True)
        dest = os.path.join(app_dir, os.path.basename(file_path))
        if os.path.exists(dest):
            base, ext = os.path.splitext(dest)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            dest = f"{base}_{counter}{ext}"
        shutil.move(file_path, dest)
        os.chmod(dest, 0o755)
        return f"AppImage installed to {dest}"

    def install_tar_gz(self, file_path):
        return self.install_tar(file_path)

    def install_tar_xz(self, file_path):
        return self.install_tar(file_path)

    def install_tgz(self, file_path):
        return self.install_tar(file_path)

    def install_tar(self, file_path):
        app_dir = os.path.expanduser("~/Applications")
        os.makedirs(app_dir, exist_ok=True)
        extract_dir = os.path.join(app_dir, os.path.splitext(os.path.basename(file_path))[0])
        os.makedirs(extract_dir, exist_ok=True)
        self.run_command(['tar', '-xf', file_path, '-C', extract_dir])
        install_script = os.path.join(extract_dir, 'install.sh')
        if os.path.exists(install_script):
            os.chmod(install_script, 0o755)
            self.run_command(['pkexec', 'bash', install_script])
        return f"Extracted to {extract_dir}"

    def install_snap(self, file_path):
        if not shutil.which('snap'):
            raise Exception("snap not found. Please install snapd.")
        self.run_command(['pkexec', 'snap', 'install', file_path, '--dangerous'])
        return f"Successfully installed {os.path.basename(file_path)}"

    def install_flatpak(self, file_path):
        if not shutil.which('flatpak'):
            raise Exception("flatpak not found. Please install flatpak.")
        self.run_command(['flatpak', 'install', '--user', file_path])
        return f"Successfully installed {os.path.basename(file_path)}"

    def install_run(self, file_path):
        return self.install_executable(file_path)

    def install_bin(self, file_path):
        return self.install_executable(file_path)

    def install_executable(self, file_path):
        os.chmod(file_path, 0o755)
        self.run_command(['pkexec', 'bash', file_path])
        return f"Executed {os.path.basename(file_path)}"

    def run_command(self, cmd):
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or result.stdout.strip())

class InstallWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, install_func, file_path):
        super().__init__()
        self.install_func = install_func
        self.file_path = file_path

    def run(self):
        try:
            result = self.install_func(self.file_path)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class LinuxAppInstaller(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("LinuxAppInstaller", "Settings")
        logging.basicConfig(filename='installer.log', level=logging.INFO,
                          format='%(asctime)s - %(levelname)s - %(message)s')

        self.installation_queue = []
        self.installation_history = []
        self.current_batch_installer = None
        self.current_worker = None
        self.installing = False

        self.init_ui()
        self.check_dependencies()
        self.setup_system_tray()
        self.load_settings()
        self.load_history()

    def init_ui(self):
        self.setWindowTitle("Linux Universal App Installer")
        self.setGeometry(100, 100, 900, 700)
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        # Create central widget with tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create tabs
        self.create_install_tab()
        self.create_queue_tab()
        self.create_history_tab()
        self.create_settings_tab()
        self.create_help_tab()

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Menu bar
        self.create_menu_bar()

    def create_install_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Title
        title = QLabel("Linux Universal App Installer")
        title.setFont(QFont("Helvetica Neue", 20, QFont.Light))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Drop zone
        self.drop_widget = QWidget()
        self.drop_widget.setAcceptDrops(True)
        drop_layout = QVBoxLayout(self.drop_widget)
        drop_layout.setContentsMargins(20, 20, 20, 20)

        self.drop_label = QLabel("Drop application files here\n\nor use the Browse button below\n\nSupported: .deb, .appimage, .tar.gz, .tar.xz, .tgz, .snap, .flatpak, .run, .bin")
        self.drop_label.setFont(QFont("Helvetica Neue", 14, QFont.Light))
        self.drop_label.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(self.drop_label)

        self.drop_widget.setStyleSheet("""
            QWidget {
                background-color: #ecf0f1;
                border: 2px dashed #bdc3c7;
                border-radius: 15px;
                padding: 20px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 8)
        shadow.setColor(Qt.gray)
        self.drop_widget.setGraphicsEffect(shadow)

        layout.addWidget(self.drop_widget)

        # Buttons
        button_layout = QHBoxLayout()
        self.browse_button = QPushButton("Browse Files")
        self.browse_button.setFont(QFont("Helvetica Neue", 12))
        self.browse_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #21618c; }
        """)
        self.browse_button.clicked.connect(self.browse_files)
        button_layout.addWidget(self.browse_button)

        self.install_button = QPushButton("Install Selected")
        self.install_button.setFont(QFont("Helvetica Neue", 12))
        self.install_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
        """)
        self.install_button.clicked.connect(self.start_installation)
        self.install_button.setEnabled(False)
        button_layout.addWidget(self.install_button)

        layout.addLayout(button_layout)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.tabs.addTab(tab, "Install")

    def create_queue_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Title
        title = QLabel("Installation Queue")
        title.setFont(QFont("Helvetica Neue", 18, QFont.Light))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Queue list
        self.queue_list = QListWidget()
        self.queue_list.setFont(QFont("Helvetica Neue", 12))
        self.queue_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                padding: 5px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        layout.addWidget(self.queue_list)

        # Queue controls
        controls_layout = QHBoxLayout()

        self.add_to_queue_button = QPushButton("Add to Queue")
        self.add_to_queue_button.setFont(QFont("Helvetica Neue", 12))
        self.add_to_queue_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #21618c; }
        """)
        self.add_to_queue_button.clicked.connect(self.add_to_queue)
        controls_layout.addWidget(self.add_to_queue_button)

        self.remove_from_queue_button = QPushButton("Remove")
        self.remove_from_queue_button.setFont(QFont("Helvetica Neue", 12))
        self.remove_from_queue_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:pressed { background-color: #a93226; }
        """)
        self.remove_from_queue_button.clicked.connect(self.remove_from_queue)
        controls_layout.addWidget(self.remove_from_queue_button)

        self.clear_queue_button = QPushButton("Clear All")
        self.clear_queue_button.setFont(QFont("Helvetica Neue", 12))
        self.clear_queue_button.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #e67e22; }
            QPushButton:pressed { background-color: #d35400; }
        """)
        self.clear_queue_button.clicked.connect(self.clear_queue)
        controls_layout.addWidget(self.clear_queue_button)

        layout.addLayout(controls_layout)

        # Batch install button
        self.batch_install_button = QPushButton("Install All in Queue")
        self.batch_install_button.setFont(QFont("Helvetica Neue", 14, QFont.Bold))
        self.batch_install_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 24px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
        """)
        self.batch_install_button.clicked.connect(self.start_batch_installation)
        layout.addWidget(self.batch_install_button)

        self.tabs.addTab(tab, "Queue")

    def create_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Title
        title = QLabel("Installation History")
        title.setFont(QFont("Helvetica Neue", 18, QFont.Light))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["File", "Type", "Status", "Timestamp"])
        self.history_table.setFont(QFont("Helvetica Neue", 11))
        self.history_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                background-color: white;
                gridline-color: #ecf0f1;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 8px;
                border: none;
                font-weight: 600;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setAlternatingRowColors(True)
        layout.addWidget(self.history_table)

        # History controls
        controls_layout = QHBoxLayout()

        self.refresh_history_button = QPushButton("Refresh")
        self.refresh_history_button.setFont(QFont("Helvetica Neue", 12))
        self.refresh_history_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #21618c; }
        """)
        self.refresh_history_button.clicked.connect(self.load_history)
        controls_layout.addWidget(self.refresh_history_button)

        self.clear_history_button = QPushButton("Clear History")
        self.clear_history_button.setFont(QFont("Helvetica Neue", 12))
        self.clear_history_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:pressed { background-color: #a93226; }
        """)
        self.clear_history_button.clicked.connect(self.clear_history)
        controls_layout.addWidget(self.clear_history_button)

        layout.addLayout(controls_layout)

        self.tabs.addTab(tab, "History")

    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Helvetica Neue", 18, QFont.Light))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Settings form
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setFormAlignment(Qt.AlignLeft)

        # Auto-start queue
        self.auto_start_queue_checkbox = QCheckBox("Auto-start installation queue")
        self.auto_start_queue_checkbox.setFont(QFont("Helvetica Neue", 12))
        auto_start_value = self.settings.value("auto_start_queue", False)
        self.auto_start_queue_checkbox.setChecked(bool(auto_start_value) if auto_start_value is not None else False)
        self.auto_start_queue_checkbox.stateChanged.connect(self.save_settings)
        form_layout.addRow(self.auto_start_queue_checkbox)

        # Show notifications
        self.show_notifications_checkbox = QCheckBox("Show desktop notifications")
        self.show_notifications_checkbox.setFont(QFont("Helvetica Neue", 12))
        notifications_value = self.settings.value("show_notifications", True)
        self.show_notifications_checkbox.setChecked(bool(notifications_value) if notifications_value is not None else True)
        self.show_notifications_checkbox.stateChanged.connect(self.save_settings)
        form_layout.addRow(self.show_notifications_checkbox)

        # Verbose logging
        self.verbose_logging_checkbox = QCheckBox("Enable verbose logging")
        self.verbose_logging_checkbox.setFont(QFont("Helvetica Neue", 12))
        logging_value = self.settings.value("verbose_logging", False)
        self.verbose_logging_checkbox.setChecked(bool(logging_value) if logging_value is not None else False)
        self.verbose_logging_checkbox.stateChanged.connect(self.save_settings)
        form_layout.addRow(self.verbose_logging_checkbox)

        # Default installation directory
        self.install_dir_label = QLabel("Default installation directory:")
        self.install_dir_label.setFont(QFont("Helvetica Neue", 12))
        self.install_dir_edit = QLineEdit(self.settings.value("install_dir", "/opt"))
        self.install_dir_edit.setFont(QFont("Helvetica Neue", 12))
        self.install_dir_edit.textChanged.connect(self.save_settings)
        form_layout.addRow(self.install_dir_label, self.install_dir_edit)

        # Browse button for install dir
        browse_layout = QHBoxLayout()
        browse_layout.addWidget(self.install_dir_edit)
        self.browse_install_dir_button = QPushButton("Browse...")
        self.browse_install_dir_button.setFont(QFont("Helvetica Neue", 10))
        self.browse_install_dir_button.clicked.connect(self.browse_install_dir)
        browse_layout.addWidget(self.browse_install_dir_button)
        form_layout.addRow(browse_layout)

        layout.addLayout(form_layout)

        # Save button
        self.save_settings_button = QPushButton("Save Settings")
        self.save_settings_button.setFont(QFont("Helvetica Neue", 14, QFont.Bold))
        self.save_settings_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 24px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
        """)
        self.save_settings_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_settings_button)

        layout.addStretch()

        self.tabs.addTab(tab, "Settings")

    def create_help_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Title
        title = QLabel("Help & Documentation")
        title.setFont(QFont("Helvetica Neue", 18, QFont.Light))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Help content
        help_browser = QTextBrowser()
        help_browser.setFont(QFont("Helvetica Neue", 12))
        help_browser.setOpenExternalLinks(True)
        help_content = """
        <h2>Linux Universal App Installer</h2>
        <p>A professional drag-and-drop application installer for Linux supporting multiple package formats.</p>

        <h3>Supported Formats</h3>
        <ul>
        <li><b>.deb</b> - Debian packages (requires dpkg and apt)</li>
        <li><b>.appimage</b> - AppImage portable applications</li>
        <li><b>.tar.gz, .tar.xz, .tgz</b> - Compressed archives</li>
        <li><b>.snap</b> - Snap packages (requires snapd)</li>
        <li><b>.flatpak</b> - Flatpak packages (requires flatpak)</li>
        <li><b>.run, .bin</b> - Executable installers</li>
        </ul>

        <h3>How to Use</h3>
        <ol>
        <li>Drag and drop application files onto the drop zone</li>
        <li>Or click "Browse Files" to select files manually</li>
        <li>The installer will automatically detect the file type and install it</li>
        <li>Check the installation history for completed installations</li>
        </ol>

        <h3>Batch Installation</h3>
        <p>Use the Queue tab to add multiple files and install them all at once.</p>

        <h3>Settings</h3>
        <p>Configure auto-start queue, notifications, logging, and installation directory in the Settings tab.</p>

        <h3>Troubleshooting</h3>
        <ul>
        <li>Check the error logs via the Logs menu if installations fail</li>
        <li>Ensure you have the necessary package managers installed (dpkg, snap, flatpak)</li>
        <li>Some installations require administrator privileges</li>
        </ul>

        <h3>About</h3>
        <p>Version 2.0 - Enterprise-grade Linux application installer with professional UI and robust error handling.</p>
        """
        help_browser.setHtml(help_content)
        layout.addWidget(help_browser)

        self.tabs.addTab(tab, "Help")

    def create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu('View')
        logs_action = QAction('View Logs', self)
        logs_action.triggered.connect(self.view_logs)
        view_menu.addAction(logs_action)

        # Help menu
        help_menu = menubar.addMenu('Help')
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray_icon.setToolTip("Linux Universal App Installer")

        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        hide_action = QAction("Hide", self)
        hide_action.triggered.connect(self.hide)
        tray_menu.addAction(hide_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def load_settings(self):
        # Load settings from QSettings
        pass

    def save_settings(self):
        # Save settings to QSettings
        settings = {
            "auto_start_queue": self.auto_start_queue_checkbox.isChecked(),
            "show_notifications": self.show_notifications_checkbox.isChecked(),
            "verbose_logging": self.verbose_logging_checkbox.isChecked(),
            "install_dir": self.install_dir_edit.text()
        }
        for key, value in settings.items():
            self.settings.setValue(key, value)
        QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")

    def browse_install_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Installation Directory", self.install_dir_edit.text())
        if dir_path:
            self.install_dir_edit.setText(dir_path)

    def add_to_queue(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Files to Queue",
            "",
            "All Supported Files (*.deb *.appimage *.tar.gz *.tar.xz *.tgz *.snap *.flatpak *.run *.bin);;All Files (*)"
        )
        for file_path in files:
            if os.path.isfile(file_path):
                task = InstallationTask(file_path)
                self.installation_queue.append(task)
                self.update_queue_display()

    def remove_from_queue(self):
        current_item = self.queue_list.currentItem()
        if current_item:
            task_id = current_item.data(Qt.UserRole)
            self.installation_queue = [task for task in self.installation_queue if task.task_id != task_id]
            self.update_queue_display()

    def clear_queue(self):
        self.installation_queue.clear()
        self.update_queue_display()

    def update_queue_display(self):
        self.queue_list.clear()
        for task in self.installation_queue:
            item = QListWidgetItem(f"{os.path.basename(task.file_path)} ({task.get_file_type()})")
            item.setData(Qt.UserRole, task.task_id)
            self.queue_list.addItem(item)

    def start_batch_installation(self):
        if not self.installation_queue:
            QMessageBox.information(self, "No Files", "Please add files to the queue first.")
            return

        if self.current_batch_installer and self.current_batch_installer.isRunning():
            QMessageBox.warning(self, "Installation in Progress", "Batch installation is already running.")
            return

        self.current_batch_installer = BatchInstaller(self.installation_queue.copy())
        self.current_batch_installer.set_installer(self)  # Pass reference to main window
        self.current_batch_installer.progress_updated.connect(self.on_batch_progress)
        self.current_batch_installer.task_completed.connect(self.on_batch_task_completed)
        self.current_batch_installer.batch_finished.connect(self.on_batch_finished)
        self.current_batch_installer.start()

        self.batch_install_button.setEnabled(False)
        self.status_bar.showMessage("Batch installation started...")

    def on_batch_progress(self, task_id, progress, message):
        # Update progress for specific task
        pass

    def on_batch_task_completed(self, task_id, success, message):
        # Handle task completion
        task = next((t for t in self.installation_queue if t.task_id == task_id), None)
        if task:
            task.status = "completed" if success else "failed"
            task.message = message
            self.save_history_entry(task)
            self.update_queue_display()
            self.load_history()

    def on_batch_finished(self):
        self.current_batch_installer = None
        self.batch_install_button.setEnabled(True)
        self.status_bar.showMessage("Batch installation completed.")
        QMessageBox.information(self, "Batch Complete", "All files in the queue have been processed.")

    def start_installation(self):
        # Get selected files from install tab
        # For now, just browse for files
        self.browse_files()

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)

    def load_history(self):
        try:
            if os.path.exists('history.json'):
                with open('history.json', 'r') as f:
                    history_data = json.load(f)
                    self.installation_history = [InstallationTask.from_dict(item) for item in history_data]
            else:
                self.installation_history = []
        except Exception as e:
            logging.error(f"Failed to load history: {e}")
            self.installation_history = []

        self.update_history_display()

    def update_history_display(self):
        self.history_table.setRowCount(len(self.installation_history))
        for row, task in enumerate(reversed(self.installation_history[-100:])):  # Show last 100 entries
            self.history_table.setItem(row, 0, QTableWidgetItem(os.path.basename(task.file_path)))
            self.history_table.setItem(row, 1, QTableWidgetItem(task.get_file_type()))
            self.history_table.setItem(row, 2, QTableWidgetItem(task.status.capitalize()))
            timestamp = task.end_time.strftime("%Y-%m-%d %H:%M:%S") if task.end_time else "N/A"
            self.history_table.setItem(row, 3, QTableWidgetItem(timestamp))

    def save_history_entry(self, task):
        self.installation_history.append(task)
        try:
            history_data = [task.to_dict() for task in self.installation_history[-1000:]]  # Keep last 1000 entries
            with open('history.json', 'w') as f:
                json.dump(history_data, f, indent=2, default=str)
        except Exception as e:
            logging.error(f"Failed to save history: {e}")

    def clear_history(self):
        reply = QMessageBox.question(self, "Clear History", 
                                   "Are you sure you want to clear all installation history?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.installation_history.clear()
            try:
                if os.path.exists('history.json'):
                    os.remove('history.json')
            except Exception as e:
                logging.error(f"Failed to delete history file: {e}")
            self.update_history_display()

    def show_about(self):
        QMessageBox.about(self, "About Linux Universal App Installer",
                         "Version 2.0\n\nA professional drag-and-drop application installer for Linux.\n\nSupports: .deb, .appimage, .tar.gz, .tar.xz, .tgz, .snap, .flatpak, .run, .bin")

    def check_dependencies(self):
        required_cmds = ['pkexec', 'tar']
        for cmd in required_cmds:
            if not shutil.which(cmd):
                error_msg = f"Required command '{cmd}' not found. Please install it."
                logging.error(error_msg)
                QMessageBox.critical(None, "Missing Dependency", error_msg)
                sys.exit(1)

    def create_menu(self):
        menu_bar = self.menuBar()
        logs_menu = menu_bar.addMenu("Logs")
        view_logs_action = logs_menu.addAction("View Error Logs")
        view_logs_action.triggered.connect(self.view_logs)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            self.drop_widget.setStyleSheet("""
                QWidget {
                    background-color: #d5f4e6;
                    border: 2px dashed #27ae60;
                    border-radius: 15px;
                    padding: 20px;
                }
            """)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.reset_drop_style()

    def dropEvent(self, event: QDropEvent):
        self.reset_drop_style()
        if self.installing:
            self.status_label.setText("Installation already in progress. Please wait.")
            return
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for file_path in files:
            if os.path.isfile(file_path):
                self.install_file(file_path)

    def reset_drop_style(self):
        self.drop_widget.setStyleSheet("""
            QWidget {
                background-color: #ecf0f1;
                border: 2px dashed #bdc3c7;
                border-radius: 15px;
                padding: 20px;
            }
        """)

    def browse_files(self):
        if self.installing:
            self.status_label.setText("Installation already in progress. Please wait.")
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Install",
            "",
            "All Supported Files (*.deb *.appimage *.tar.gz *.tar.xz *.tgz *.snap *.flatpak *.run *.bin);;All Files (*)"
        )
        for file_path in files:
            if os.path.isfile(file_path):
                self.install_file(file_path)

    def install_file(self, file_path):
        if self.installing:
            self.status_label.setText("Installation already in progress. Please wait.")
            return

        if self.current_worker and self.current_worker.isRunning():
            self.status_label.setText("Installation already in progress. Please wait.")
            return

        try:
            if not os.path.exists(file_path):
                error_msg = f"File does not exist: {file_path}"
                logging.error(error_msg)
                raise Exception(error_msg)
            if not os.access(file_path, os.R_OK):
                error_msg = f"File is not readable: {file_path}"
                logging.error(error_msg)
                raise Exception(error_msg)
            if os.path.getsize(file_path) == 0:
                error_msg = f"File is empty: {file_path}"
                logging.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            self.show_error(str(e))
            return

        ext = self.get_file_type(file_path)
        if ext not in ['deb', 'appimage', 'tar.gz', 'tar.xz', 'tgz', 'snap', 'flatpak', 'run', 'bin']:
            error_msg = f"Unsupported file type: {ext}"
            logging.error(error_msg)
            self.show_error(error_msg)
            return

        self.installing = True
        self.drop_widget.setAcceptDrops(False)
        self.browse_button.setEnabled(False)
        self.status_label.setText(f"Installing {os.path.basename(file_path)}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

        install_func = getattr(self, f"install_{ext.replace('.', '_')}")
        self.current_worker = InstallWorker(install_func, file_path)
        self.current_worker.finished.connect(self.on_install_finished)
        self.current_worker.error.connect(self.on_install_error)
        self.current_worker.start()

    def get_file_type(self, file_path):
        if file_path.endswith('.tar.gz'):
            return 'tar.gz'
        elif file_path.endswith('.tar.xz'):
            return 'tar.xz'
        _, ext = os.path.splitext(file_path)
        return ext.lower().lstrip('.')

    def install_deb(self, file_path):
        if not shutil.which('dpkg'):
            raise Exception("dpkg not found. Please install dpkg.")
        self.run_command(['pkexec', 'dpkg', '-i', file_path])
        self.run_command(['pkexec', 'apt-get', 'install', '-f'])
        return f"Successfully installed {os.path.basename(file_path)}"

    def install_appimage(self, file_path):
        app_dir = os.path.expanduser("~/Applications")
        try:
            os.makedirs(app_dir, exist_ok=True)
            dest = os.path.join(app_dir, os.path.basename(file_path))
            if os.path.exists(dest):
                base, ext = os.path.splitext(dest)
                counter = 1
                while os.path.exists(f"{base}_{counter}{ext}"):
                    counter += 1
                dest = f"{base}_{counter}{ext}"
            shutil.move(file_path, dest)
            os.chmod(dest, 0o755)

            # Create desktop integration
            self.create_appimage_desktop_entry(dest)

            # Post-installation setup
            completion_msg = self.post_install_setup(os.path.splitext(os.path.basename(dest))[0], dest, 'appimage')

        except Exception as e:
            raise Exception(f"Failed to install AppImage: {e}")
        return f"AppImage installed to {dest} with desktop integration"

    def install_tar_gz(self, file_path):
        return self.install_tar(file_path)

    def install_tar_xz(self, file_path):
        return self.install_tar(file_path)

    def install_tgz(self, file_path):
        return self.install_tar(file_path)

    def install_tar(self, file_path):
        app_dir = os.path.expanduser("~/Applications")
        try:
            os.makedirs(app_dir, exist_ok=True)
            extract_dir = os.path.join(app_dir, os.path.splitext(os.path.basename(file_path))[0])
            os.makedirs(extract_dir, exist_ok=True)
            self.run_command(['tar', '-xf', file_path, '-C', extract_dir])

            # Look for executable files and create desktop entries
            self.create_tar_desktop_entries(extract_dir)

            install_script = os.path.join(extract_dir, 'install.sh')
            if os.path.exists(install_script):
                os.chmod(install_script, 0o755)
                self.run_command(['pkexec', 'bash', install_script])

            # Post-installation setup
            app_name = os.path.basename(extract_dir)
            completion_msg = self.post_install_setup(app_name, extract_dir, 'tar')

        except Exception as e:
            raise Exception(f"Failed to extract archive: {e}")
        return f"Extracted to {extract_dir} with desktop integration"

    def install_snap(self, file_path):
        if not shutil.which('snap'):
            raise Exception("snap not found. Please install snapd.")
        self.run_command(['pkexec', 'snap', 'install', file_path, '--dangerous'])
        return f"Successfully installed {os.path.basename(file_path)}"

    def install_flatpak(self, file_path):
        if not shutil.which('flatpak'):
            raise Exception("flatpak not found. Please install flatpak.")
        self.run_command(['flatpak', 'install', '--user', file_path])
        return f"Successfully installed {os.path.basename(file_path)}"

    def install_run(self, file_path):
        return self.install_executable(file_path)

    def install_bin(self, file_path):
        return self.install_executable(file_path)

    def install_executable(self, file_path):
        try:
            os.chmod(file_path, 0o755)

            # Try to run the installer
            result = self.run_command(['pkexec', 'bash', file_path])

            # Create desktop entry for the installed application if it's not a generic installer
            exe_name = os.path.basename(file_path)
            if not exe_name.lower().startswith(('install', 'setup', 'configure')):
                self.create_executable_desktop_entry(file_path)

            # Post-installation setup
            app_name = os.path.splitext(exe_name)[0]
            completion_msg = self.post_install_setup(app_name, file_path, 'executable')

        except Exception as e:
            raise Exception(f"Failed to execute installer: {e}")
        return f"Executed {os.path.basename(file_path)} with desktop integration"

    def create_appimage_desktop_entry(self, appimage_path):
        """Create desktop shortcut and menu entry for AppImage"""
        try:
            app_name = os.path.splitext(os.path.basename(appimage_path))[0]
            desktop_file = os.path.expanduser(f"~/.local/share/applications/{app_name}.desktop")

            # Try to extract icon from AppImage if possible
            icon_path = self.extract_appimage_icon(appimage_path, app_name)

            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={app_name}
Comment=Application installed by Linux Universal App Installer
Exec="{appimage_path}"
Icon={icon_path or 'application-x-executable'}
Terminal=false
StartupWMClass={app_name}
Categories=Utility;Application;
"""

            # Write desktop file for menu
            os.makedirs(os.path.dirname(desktop_file), exist_ok=True)
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)

            # Create desktop shortcut
            desktop_shortcut = os.path.expanduser(f"~/Desktop/{app_name}.desktop")
            with open(desktop_shortcut, 'w') as f:
                f.write(desktop_content)

            os.chmod(desktop_file, 0o755)
            os.chmod(desktop_shortcut, 0o755)

            # Update desktop database
            self.run_command(['update-desktop-database', os.path.expanduser('~/.local/share/applications')])

        except Exception as e:
            logging.warning(f"Failed to create desktop entry for {appimage_path}: {e}")

    def extract_appimage_icon(self, appimage_path, app_name):
        """Try to extract icon from AppImage"""
        try:
            # Mount the AppImage temporarily to extract icon
            mount_point = f"/tmp/{app_name}_mount"
            os.makedirs(mount_point, exist_ok=True)

            # Try to mount AppImage (this might not work on all systems)
            result = subprocess.run([appimage_path, '--appimage-mount'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                actual_mount = result.stdout.strip()
                icon_dir = os.path.join(actual_mount, '.DirIcon')
                if os.path.exists(icon_dir):
                    # Copy icon to local icons directory
                    icons_dir = os.path.expanduser('~/.local/share/icons')
                    os.makedirs(icons_dir, exist_ok=True)
                    icon_dest = os.path.join(icons_dir, f"{app_name}.png")
                    shutil.copy2(icon_dir, icon_dest)
                    return icon_dest

            # Fallback: look for common icon names in the mount point
            if 'actual_mount' in locals():
                for icon_name in ['.DirIcon', 'icon.png', 'Icon.png', f"{app_name}.png"]:
                    icon_path = os.path.join(actual_mount, icon_name)
                    if os.path.exists(icon_path):
                        icons_dir = os.path.expanduser('~/.local/share/icons')
                        os.makedirs(icons_dir, exist_ok=True)
                        icon_dest = os.path.join(icons_dir, f"{app_name}.png")
                        shutil.copy2(icon_path, icon_dest)
                        return icon_dest

        except Exception as e:
            logging.debug(f"Could not extract icon from AppImage {appimage_path}: {e}")

        return None

    def create_tar_desktop_entries(self, extract_dir):
        """Create desktop entries for executables found in extracted tar archive"""
        try:
            # Find executable files
            executables = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.access(file_path, os.X_OK) and not file.endswith(('.so', '.dll', '.dylib')):
                        # Check if it's a binary executable (not script)
                        try:
                            with open(file_path, 'rb') as f:
                                header = f.read(4)
                                if header.startswith(b'\x7fELF') or header.startswith(b'#!/'):  # ELF binary or script
                                    executables.append(file_path)
                        except:
                            continue

            # Create desktop entries for found executables
            for exe_path in executables[:3]:  # Limit to 3 executables to avoid spam
                exe_name = os.path.basename(exe_path)
                if exe_name in ['install.sh', 'uninstall.sh', 'configure']:
                    continue  # Skip common installer scripts

                app_name = exe_name
                desktop_file = os.path.expanduser(f"~/.local/share/applications/{app_name}.desktop")

                desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={app_name}
Comment=Application installed by Linux Universal App Installer
Exec="{exe_path}"
Icon=application-x-executable
Terminal=false
Categories=Utility;Application;
"""

                # Write desktop file for menu
                os.makedirs(os.path.dirname(desktop_file), exist_ok=True)
                with open(desktop_file, 'w') as f:
                    f.write(desktop_content)

                # Create desktop shortcut
                desktop_shortcut = os.path.expanduser(f"~/Desktop/{app_name}.desktop")
                with open(desktop_shortcut, 'w') as f:
                    f.write(desktop_content)

                os.chmod(desktop_file, 0o755)
                os.chmod(desktop_shortcut, 0o755)

            # Update desktop database
            if executables:
                self.run_command(['update-desktop-database', os.path.expanduser('~/.local/share/applications')])

        except Exception as e:
            logging.warning(f"Failed to create desktop entries for {extract_dir}: {e}")

    def create_executable_desktop_entry(self, exe_path):
        """Create desktop entry for executable installer"""
        try:
            exe_name = os.path.basename(exe_path)
            app_name = os.path.splitext(exe_name)[0]
            desktop_file = os.path.expanduser(f"~/.local/share/applications/{app_name}.desktop")

            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={app_name}
Comment=Application installed by Linux Universal App Installer
Exec={exe_path}
Icon=application-x-executable
Terminal=false
Categories=Utility;Application;
"""

            # Write desktop file for menu
            os.makedirs(os.path.dirname(desktop_file), exist_ok=True)
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)

            # Create desktop shortcut
            desktop_shortcut = os.path.expanduser(f"~/Desktop/{app_name}.desktop")
            with open(desktop_shortcut, 'w') as f:
                f.write(desktop_content)

            os.chmod(desktop_file, 0o755)
            os.chmod(desktop_shortcut, 0o755)

            # Update desktop database
            self.run_command(['update-desktop-database', os.path.expanduser('~/.local/share/applications')])

        except Exception as e:
            logging.warning(f"Failed to create desktop entry for {exe_path}: {e}")

    def setup_application_directories(self, app_name):
        """Create standard application directories like Windows installer does"""
        try:
            # Create application data directory
            app_data_dir = os.path.expanduser(f"~/.local/share/{app_name}")
            os.makedirs(app_data_dir, exist_ok=True)

            # Create config directory
            config_dir = os.path.expanduser(f"~/.config/{app_name}")
            os.makedirs(config_dir, exist_ok=True)

            # Create cache directory
            cache_dir = os.path.expanduser(f"~/.cache/{app_name}")
            os.makedirs(cache_dir, exist_ok=True)

            return {
                'data': app_data_dir,
                'config': config_dir,
                'cache': cache_dir
            }
        except Exception as e:
            logging.warning(f"Failed to create application directories for {app_name}: {e}")
            return {}

    def create_uninstall_entry(self, app_name, install_path, uninstall_command=None):
        """Create uninstall entry for the application"""
        try:
            # Create desktop uninstaller
            uninstall_desktop = os.path.expanduser(f"~/.local/share/applications/{app_name}-uninstall.desktop")

            if uninstall_command:
                exec_cmd = uninstall_command
            else:
                # Default uninstall command (could be enhanced)
                exec_cmd = f"rm -rf {install_path}"

            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Uninstall {app_name}
Comment=Uninstall {app_name}
Exec={exec_cmd}
Icon=edit-delete
Terminal=true
Categories=Utility;System;
"""

            with open(uninstall_desktop, 'w') as f:
                f.write(desktop_content)
            os.chmod(uninstall_desktop, 0o755)

        except Exception as e:
            logging.warning(f"Failed to create uninstall entry for {app_name}: {e}")

    def setup_file_associations(self, app_name, file_extensions=None):
        """Set up file associations for the application"""
        if not file_extensions:
            return

        try:
            for ext in file_extensions:
                mime_type = f"application/x-{app_name}-{ext.lstrip('.')}"

                # Create mime type file
                mime_dir = os.path.expanduser("~/.local/share/mime/packages")
                os.makedirs(mime_dir, exist_ok=True)

                mime_file = os.path.join(mime_dir, f"{app_name}-{ext.lstrip('.')}.xml")
                mime_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="{mime_type}">
    <comment>{app_name} {ext} file</comment>
    <glob pattern="*{ext}"/>
  </mime-type>
</mime-info>"""

                with open(mime_file, 'w') as f:
                    f.write(mime_content)

                # Update mime database
                self.run_command(['update-mime-database', os.path.expanduser('~/.local/share/mime')])

                # Create application association
                apps_dir = os.path.expanduser("~/.local/share/applications")
                defaults_file = os.path.join(apps_dir, f"defaults.list")
                os.makedirs(apps_dir, exist_ok=True)

                # Read existing defaults
                defaults = {}
                if os.path.exists(defaults_file):
                    with open(defaults_file, 'r') as f:
                        for line in f:
                            if '=' in line:
                                key, value = line.strip().split('=', 1)
                                defaults[key] = value

                # Add our association
                defaults[mime_type] = f"{app_name}.desktop"

                # Write back
                with open(defaults_file, 'w') as f:
                    for key, value in defaults.items():
                        f.write(f"{key}={value}\n")

        except Exception as e:
            logging.warning(f"Failed to setup file associations for {app_name}: {e}")

    def post_install_setup(self, app_name, install_path, file_type):
        """Perform post-installation setup like Windows installers do"""
        try:
            # Create application directories
            dirs = self.setup_application_directories(app_name)

            # Create uninstall entry
            self.create_uninstall_entry(app_name, install_path)

            # Setup file associations based on file type
            file_associations = {
                'appimage': ['.appimage'],
                'tar.gz': ['.tar.gz', '.tgz'],
                'tar.xz': ['.tar.xz'],
                'run': ['.run'],
                'bin': ['.bin']
            }

            if file_type in file_associations:
                self.setup_file_associations(app_name, file_associations[file_type])

            # Show completion message with details
            completion_msg = f"""
Application '{app_name}' has been successfully installed!

Installation Details:
• Application Location: {install_path}
• Desktop Shortcut: ~/Desktop/{app_name}.desktop
• Menu Entry: ~/.local/share/applications/{app_name}.desktop
• Data Directory: {dirs.get('data', 'N/A')}
• Config Directory: {dirs.get('config', 'N/A')}

The application is now ready to use. You can find it in your applications menu or on your desktop.
"""

            logging.info(f"Post-installation setup completed for {app_name}")
            return completion_msg

        except Exception as e:
            logging.warning(f"Post-installation setup failed for {app_name}: {e}")
            return f"Application '{app_name}' installed successfully, but some integration features may not be available."

    def run_command(self, cmd):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 min timeout
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logging.error(f"Command failed: {' '.join(cmd)} - {error_msg}")
                raise Exception(error_msg)
        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out: {' '.join(cmd)}"
            logging.error(error_msg)
            raise Exception(error_msg)

    def on_install_finished(self, message):
        try:
            self.installing = False
            self.current_worker = None
            self.drop_widget.setAcceptDrops(True)
            self.browse_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
            QMessageBox.information(self, "Success", message)
        except Exception as e:
            logging.error(f"Error in on_install_finished: {e}")

    def on_install_error(self, error_msg):
        try:
            self.installing = False
            self.current_worker = None
            self.drop_widget.setAcceptDrops(True)
            self.browse_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
            logging.error(f"Installation failed: {error_msg}")
            QMessageBox.critical(self, "Installation Failed", error_msg)
        except Exception as e:
            logging.error(f"Error in on_install_error: {e}")

    def view_logs(self):
        try:
            with open('installer.log', 'r') as f:
                log_content = f.read()
        except FileNotFoundError:
            log_content = "No error logs available yet."
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Error Logs")
        dialog.setFixedSize(600, 400)
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setPlainText(log_content)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        
        dialog.exec_()


def main():
    """Main entry point for the Linux Universal App Installer"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern style
    try:
        window = LinuxAppInstaller()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        error_msg = f"Application failed to start: {e}"
        logging.error(error_msg)
        QMessageBox.critical(None, "Error", error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()