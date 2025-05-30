import sys
import os
import json
import ctypes
import webbrowser
import random
import hashlib
import requests
import zipfile
import io
import shutil
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QProgressBar, QFrame, QScrollArea, QGridLayout, 
    QMessageBox, QLineEdit, QDialog
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize,
    QThread, Signal, QObject, QPoint, QRectF, Property
)
from PySide6.QtGui import (
    QMovie, QPixmap, QIcon, QPainter, QPen, QConicalGradient, 
    QColor, QBrush, QLinearGradient, QRadialGradient, QFont
)
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

APP_VERSION = "v1.3.0"
RECENT_FILE = "recent_cursors.json"
FAV_FILE = "favorites.json"
CURSOR_LIB_PATH = "CursorsLib"
ANIME_PATH = os.path.join(CURSOR_LIB_PATH, "CursorsLib", "Anime")
CLASSIC_PATH = os.path.join(CURSOR_LIB_PATH, "CursorsLib", "Classic")
GITHUB_CURSORS_URL = "https://github.com/ShustovCarleone/Cursor-Galaxy/releases/download/v1.2.0/CursorsLib.zip"

CURSOR_KEYS = {
    "pointer": "Arrow",
    "help": "Help",
    "busy": "Busy",
    "link": "AppStarting",
    "cross": "Crosshair",
    "text": "IBeam",
    "move": "SizeAll",
    "dgn1": "SizeNESW",
    "dgn2": "SizeNWSE",
    "horz": "SizeWE",
    "vert": "SizeNS",
    "alternate": "AlternateSelect",
    "unavailable": "No",
    "work": "WorkingInBackground",
    "hand": "Hand",
    "normal": "Arrow",
    "alternate2": "AlternateSelect",
    "diagonal1": "SizeNESW",
    "diagonal2": "SizeNWSE",
    "handwriting": "Handwriting",
    "horizontal": "SizeWE",
    "vertical": "SizeNS",
    "person": "Person",
    "pin": "Pin",
    "precision": "PrecisionSelect",
    "working": "WorkingInBackground"
}

# Классы для интерфейса
class AnimatedBackground(QLabel):
    def __init__(self, parent, gif_path):
        super().__init__(parent)
        self.movie = QMovie(gif_path)
        self.movie.setScaledSize(parent.size())
        self.setMovie(self.movie)
        self.movie.start()
        self.setScaledContents(True)
        
    def resizeEvent(self, event):
        self.movie.setScaledSize(event.size())
        super().resizeEvent(event)

class Notification(QWidget):
    def __init__(self, message, duration=3000):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.duration = duration

        layout = QVBoxLayout(self)
        frame = QFrame()
        frame.setStyleSheet("background-color: #333333; border-radius: 10px;")
        frame_layout = QVBoxLayout(frame)
        label = QLabel(message)
        label.setStyleSheet("color: white; font-size: 14px;")
        label.setWordWrap(True)
        frame_layout.addWidget(label)
        layout.addWidget(frame)

        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(300)
        self.opacity_anim.setStartValue(0)
        self.opacity_anim.setEndValue(1)
        self.opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.opacity_anim.start()

        QTimer.singleShot(self.duration, self.fade_out)

    def fade_out(self):
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(300)
        self.opacity_anim.setStartValue(1)
        self.opacity_anim.setEndValue(0)
        self.opacity_anim.finished.connect(self.close)
        self.opacity_anim.start()

class AnimatedGIF(QLabel):
    def __init__(self, gif_path, width=195, height=150):
        super().__init__()
        self._size = QSize(width, height)
        self.base_size = QSize(width, height)
        self.hover_size = QSize(int(width * 1.1), int(height * 1.1))

        self.setFixedSize(self.base_size)
        self.movie = QMovie(gif_path)
        self.movie.setScaledSize(self.base_size)
        
        self.movie.jumpToFrame(0)
        self.static_pixmap = QPixmap(self.movie.currentPixmap())
        self.setPixmap(self.static_pixmap)
        
        self.movie.frameChanged.connect(self.update_pixmap)
        self.movie.stop()

        self.anim = QPropertyAnimation(self, b"animatedSize")
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

    def update_pixmap(self):
        if self.movie.state() == QMovie.Running:
            self.setPixmap(self.movie.currentPixmap())

    def start_animation(self):
        self.movie.start()

    def stop_animation(self):
        self.movie.stop()
        self.setPixmap(self.static_pixmap)

    def enterEvent(self, event):
        self.animate_resize(self.hover_size)
        self.movie.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate_resize(self.base_size)
        self.movie.stop()
        super().leaveEvent(event)

    def animate_resize(self, target_size):
        self.anim.stop()
        self.anim.setStartValue(self.size())
        self.anim.setEndValue(target_size)
        self.anim.start()

    def get_animated_size(self):
        return self.size()

    def set_animated_size(self, size):
        self.setFixedSize(size)
        self.movie.setScaledSize(size)

    animatedSize = Property(QSize, get_animated_size, set_animated_size)

class Worker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, category):
        super().__init__()
        self.category = category

    def run(self):
        try:
            cursors = self.load_cursors()
            self.finished.emit(cursors)
        except Exception as e:
            self.error.emit(str(e))

    def load_cursors(self):
        # Теперь ищем курсоры в CursorLib/CursorsLib/Anime и CursorLib/CursorsLib/Classic
        base_path = os.path.join(CURSOR_LIB_PATH, "CursorsLib")
        path = os.path.join(base_path, "Anime") if self.category == "anime" else os.path.join(base_path, "Classic")
        cursors = {}
        # Не создаём папки, если их нет
        if not os.path.exists(path):
            return cursors
        for folder in os.listdir(path):
            full_path = os.path.join(path, folder)
            if os.path.isdir(full_path):
                files = os.listdir(full_path)
                cursor_files = {
                    name.lower().split(".")[0]: os.path.abspath(os.path.join(full_path, name))
                    for name in files if name.lower().endswith((".cur", ".ani"))
                }
                if cursor_files:
                    cursors[folder] = cursor_files
        return cursors

class StarryBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stars = []
        self.init_stars(150)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stars)
        self.timer.start(100)

    def init_stars(self, count):
        for _ in range(count):
            self.stars.append((random.randint(0, self.width()), random.randint(0, self.height()), random.randint(1, 3), random.randint(50, 255)))

    def update_stars(self):
        self.stars = [(x, y, s, random.randint(50, 255)) for x, y, s, _ in self.stars]
        self.update()

    def resizeEvent(self, event):
        self.stars = []
        self.init_stars(150)
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(5, 5, 25))
        
        painter.setPen(Qt.NoPen)
        for x, y, size, alpha in self.stars:
            gradient = QRadialGradient(x, y, size*2)
            gradient.setColorAt(0, QColor(255, 255, 255, alpha))
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(QPoint(x, y), size, size)

class AnimatedBorderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self.gradient = QConicalGradient(0.5, 0.5, 0)
        self.gradient.setColorAt(0, QColor(100, 100, 255))
        self.gradient.setColorAt(0.5, QColor(50, 50, 200))
        self.gradient.setColorAt(1, QColor(100, 100, 255))
        
        self.animation = QPropertyAnimation(self, b"angle")
        self.animation.setDuration(3000)
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setLoopCount(-1)
        self.animation.start()

    def get_angle(self):
        return self._angle

    def set_angle(self, angle):
        self._angle = angle
        self.update()

    angle = Property(int, get_angle, set_angle)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect().adjusted(2, 2, -2, -2)
        self.gradient.setAngle(self.angle)
        pen = QPen(QBrush(self.gradient), 4)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 10, 10)

class Loader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1a1b1e; border-radius: 10px;")
        layout = QVBoxLayout(self)

        self.title_label = QLabel("Проверка новых курсоров...")
        self.title_label.setStyleSheet("""
            color: #aaccff;
            font-size: 42px;
            font-weight: bold;
            font-family: 'Segoe UI';
        """)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.file_label = QLabel("Инициализация...")
        self.file_label.setStyleSheet("""
            color: #88aaff;
            font-size: 16px;
            font-family: 'Segoe UI';
        """)
        self.file_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.file_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4466ff;
                border-radius: 5px;
                background-color: #2a2b2e;
                text-align: center;
                color: white;
                font-family: 'Segoe UI';
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #4466ff, stop:1 #88aaff);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("""
            color: #a0a0a0;
            font-size: 14px;
            font-family: 'Segoe UI';
        """)
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

class GitHubCheckWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            logging.info("Начало проверки новых курсоров с GitHub...")
            needs_update = self.verify_files()
            self.finished.emit(needs_update)
        except Exception as e:
            self.error.emit(str(e))

    def verify_files(self):
        logging.info("Проверка локальных файлов...")
        local_files = {}

        # Собираем локальные файлы и их MD5-хеши
        for path in [ANIME_PATH, CLASSIC_PATH]:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'rb') as f:
                            local_files[file_path] = hashlib.md5(f.read()).hexdigest()
                    except Exception as e:
                        logging.warning(f"Не удалось вычислить MD5 для {file_path}: {str(e)}")

        # Скачиваем архив с GitHub и проверяем содержимое
        response = requests.get(GITHUB_CURSORS_URL, stream=True)
        response.raise_for_status()

        zip_data = io.BytesIO()
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        start_time = time.time()

        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                zip_data.write(chunk)
                downloaded_size += len(chunk)
                if total_size > 0:
                    progress = int((downloaded_size / total_size) * 100)
                    elapsed_time = time.time() - start_time
                    speed = (downloaded_size / 1024 / 1024) / elapsed_time if elapsed_time > 0 else 0
                    self.progress.emit(progress, f"Скачивание архива... Скорость: {speed:.2f} МБ/с")

        zip_data.seek(0)
        github_files = {}
        with zipfile.ZipFile(zip_data, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            for idx, file_name in enumerate(file_list):
                if file_name.endswith(('.cur', '.ani')):
                    relative_path = file_name.replace("CursorsLib/", "", 1)
                    with zip_ref.open(file_name) as f:
                        github_files[relative_path] = hashlib.md5(f.read()).hexdigest()
                progress = int(((idx + 1) / total_files) * 100)
                self.progress.emit(progress, f"Проверка файла: {file_name}")

        # Сравниваем локальные файлы с файлами в архиве
        needs_update = False
        for file_path, github_md5 in github_files.items():
            local_md5 = local_files.get(file_path)
            if not local_md5 or local_md5 != github_md5:
                needs_update = True
                break

        return needs_update

class GitHubDownloadWorker(QObject):
    progress = Signal(int, str, float)
    finished = Signal()
    error = Signal(str)

    def __init__(self, url, install_dir):
        super().__init__()
        self.url = url
        self.install_dir = install_dir

    def run(self):
        try:
            logging.info(f"Начинается загрузка архива с {self.url}")
            response = requests.get(self.url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            zip_path = "temp_cursors.zip"

            with open(zip_path, 'wb') as f:
                start_time = time.time()
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            elapsed_time = time.time() - start_time
                            speed = (downloaded_size / 1024 / 1024) / elapsed_time if elapsed_time > 0 else 0
                            self.progress.emit(progress, "CursorsLib.zip", speed)

            logging.info("Загрузка завершена, начинаем распаковку")
            self.extract_zip(zip_path, self.install_dir)
            os.remove(zip_path)
            logging.info("Распаковка завершена")
            self.finished.emit()
        except Exception as e:
            logging.error(f"Ошибка в процессе загрузки: {str(e)}")
            self.error.emit(str(e))

    def extract_zip(self, zip_path, extract_to):
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to)
        os.makedirs(extract_to, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

class MainApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cursor Gallery")
        self.setGeometry(100, 100, 1180, 700)
        self.setStyleSheet("background-color: #2a2b2e;")
        self.setWindowIcon(QIcon("icon.png"))
        self.bg_image = "default_background.png"

        self.recent_cursors = []
        self.favorites = []
        self.current_cursors = {}
        self.cursor_options = []
        self.current_page = 0
        self.items_per_page = 12
        self.current_category = "anime"
        self.is_fav_mode = False

        self.init_ui()
        self.load_data()
        self.start_check_process()

    def check_cursors_exist(self):
        def has_files(path):
            return os.path.exists(path) and any(os.listdir(path))
        return all([
            has_files(CURSOR_LIB_PATH),
            has_files(ANIME_PATH),
            has_files(CLASSIC_PATH)
        ])

    def start_check_process(self):
        self.stacked.setCurrentWidget(self.loader)
        self.check_thread = QThread()
        self.check_worker = GitHubCheckWorker()
        self.check_worker.moveToThread(self.check_thread)
        self.check_thread.started.connect(self.check_worker.run)
        self.check_worker.progress.connect(self.update_check_progress)
        self.check_worker.finished.connect(self.handle_check_finished)
        self.check_worker.error.connect(self.handle_check_error)
        self.check_worker.finished.connect(self.check_thread.quit)
        self.check_thread.start()

    def update_check_progress(self, progress, message):
        self.loader.progress.setValue(progress)
        self.loader.file_label.setText(message)

    def handle_check_finished(self, needs_update):
        self.loader.title_label.setText("Проверка завершена!")
        self.loader.file_label.setText("Готово")
        self.loader.progress.setValue(100)
        self.loader.info_label.setText("")
        QTimer.singleShot(1000, lambda: (
            self.stacked.setCurrentWidget(self.browser),
            self.show_download_dialog() if needs_update else self.show_notification("Все курсоры актуальны!")
        ))

    def handle_check_error(self, error):
        logging.error(f"Ошибка проверки курсоров: {error}")
        self.loader.title_label.setText("Ошибка проверки")
        self.loader.file_label.setText(f"Ошибка: {error}")
        self.loader.progress.setValue(0)
        self.loader.info_label.setText("")
        QMessageBox.critical(self, "Ошибка", f"Ошибка проверки курсоров:\n{error}")
        QTimer.singleShot(2000, lambda: self.stacked.setCurrentWidget(self.browser))

    def show_download_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Обновление курсоров")
        dialog.setFixedSize(500, 250)
        dialog.setStyleSheet("background-color: #1a1b1e; border-radius: 10px;")
        
        layout = QVBoxLayout(dialog)
        label = QLabel("Обнаружены новые или отсутствующие курсоры.\nСкачать обновления с GitHub?")
        label.setStyleSheet("""
            color: #aaccff;
            font-size: 18px;
            font-family: 'Segoe UI';
        """)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        btn_box = QHBoxLayout()
        download_btn = QPushButton("Скачать")
        download_btn.setStyleSheet(self.button_style())
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet(self.button_style())
        
        download_btn.clicked.connect(lambda: self.start_download(dialog))
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_box.addWidget(download_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

        dialog.exec()

    def start_download(self, dialog):
        dialog.accept()
        self.stacked.setCurrentWidget(self.loader)
        self.loader.title_label.setText("Загрузка новых курсоров...")
        self.loader.file_label.setText("Подготовка...")
        self.loader.progress.setValue(0)

        self.download_thread = QThread()
        self.download_worker = GitHubDownloadWorker(GITHUB_CURSORS_URL, CURSOR_LIB_PATH)
        self.download_worker.moveToThread(self.download_thread)
        
        self.download_worker.progress.connect(self.update_progress)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.error.connect(self.handle_download_error)
        
        self.download_thread.started.connect(self.download_worker.run)
        self.download_thread.start()

    def update_progress(self, progress, file_name, speed):
        self.loader.file_label.setText(f"Файл: {file_name}")
        self.loader.progress.setValue(progress)
        self.loader.info_label.setText(f"Скорость: {speed:.2f} МБ/с")

    def on_download_finished(self):
        self.loader.title_label.setText("Загрузка завершена!")
        self.loader.file_label.setText("Обновление завершено")
        self.loader.progress.setValue(100)
        self.loader.info_label.setText("")
        QTimer.singleShot(1000, lambda: (
            self.stacked.setCurrentWidget(self.browser),
            self.load_data(),
            self.update_display()
        ))

    def handle_download_error(self, error):
        logging.error(f"Ошибка загрузки: {error}")
        self.loader.title_label.setText("Ошибка загрузки")
        self.loader.file_label.setText(f"Ошибка: {error}")
        self.loader.progress.setValue(0)
        self.loader.info_label.setText("")
        QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки: {error}")
        QTimer.singleShot(2000, self.show_main_menu)

    def load_data(self):
        if os.path.exists(RECENT_FILE):
            with open(RECENT_FILE, "r") as f:
                self.recent_cursors = json.load(f)
        if os.path.exists(FAV_FILE):
            with open(FAV_FILE, "r") as f:
                data = json.load(f)
                if data and isinstance(data[0], str):
                    self.favorites = [{"name": name, "category": "anime"} for name in data]
                else:
                    self.favorites = data

    def save_data(self):
        with open(RECENT_FILE, "w") as f:
            json.dump(self.recent_cursors, f, indent=2)
        with open(FAV_FILE, "w") as f:
            json.dump(self.favorites, f, indent=2)

    def init_ui(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"QWidget#browser {{ background-image: url({self.bg_image}); }}")
        self.stacked = QStackedWidget()
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.stacked)

        self.create_main_menu()
        self.create_category_menu()
        self.create_loader()
        self.create_browser()
        self.create_functions_menu()
        # Устанавливаем главное меню как стартовую вкладку
        self.stacked.setCurrentIndex(0)

    def create_main_menu(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        
        bg = StarryBackground()
        bg_layout = QVBoxLayout(bg)
        
        title = QLabel("Cursor Galaxy")
        title.setStyleSheet("""
            font-size: 42px; 
            color: #aaccff;
            font-weight: bold;
            background-color: transparent;
            font-family: 'Segoe UI';
        """)
        title.setAlignment(Qt.AlignCenter)
        bg_layout.addWidget(title)

        buttons = [
            ("Курсоры", self.show_category_menu),
            ("Функции", self.show_functions_menu)
        ]

        for text, callback in buttons:
            btn_container = AnimatedBorderWidget()
            btn_container.setFixedSize(300, 80)
            btn_layout = QVBoxLayout(btn_container)
            btn_layout.setContentsMargins(8, 8, 8, 8)
            
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(20,20,50,0.7);
                    color: #aaccff;
                    border: none;
                    border-radius: 8px;
                    font-size: 24px;
                    padding: 15px;
                    font-family: 'Segoe UI';
                }
                QPushButton:hover {
                    background-color: rgba(50,50,100,0.9);
                }
            """)
            btn.clicked.connect(callback)
            btn_layout.addWidget(btn)
            bg_layout.addWidget(btn_container, alignment=Qt.AlignCenter)

        layout.addWidget(bg)
        self.stacked.addWidget(container)

    def create_category_menu(self):
        widget = StarryBackground()
        widget.setObjectName("categoryMenu")
        widget.setStyleSheet(f"#categoryMenu {{ background-image: url({self.bg_image}); }}")
        layout = QVBoxLayout(widget)

        title = QLabel("Выберите категорию")
        title.setStyleSheet("""
            font-size: 42px; 
            color: #aaccff;
            font-weight: bold;
            background-color: transparent;
            font-family: 'Segoe UI';
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        categories = [
            ("Anime курсоры", "anime"),
            ("Classic курсоры", "classic")
        ]

        for text, category in categories:
            btn = QPushButton(text)
            btn.setFixedSize(300, 80)
            btn.setStyleSheet(self.button_style())
            btn.clicked.connect(lambda _, c=category: self.start_loading(c))
            layout.addWidget(btn, alignment=Qt.AlignCenter)

        back_btn = QPushButton("🔙 Назад")
        back_btn.setStyleSheet(self.button_style())
        back_btn.clicked.connect(self.show_main_menu)
        layout.addWidget(back_btn, alignment=Qt.AlignCenter)

        self.stacked.addWidget(widget)

    def create_loader(self):
        self.loader = Loader()
        self.stacked.addWidget(self.loader)

    def create_browser(self):
        self.browser = StarryBackground()
        self.browser.setObjectName("browser")
        layout = QVBoxLayout(self.browser)

        top_bar = QHBoxLayout()
        self.back_btn = QPushButton("🔙 Назад")
        self.back_btn.setStyleSheet(self.button_style())
        self.back_btn.clicked.connect(self.show_category_menu)
        top_bar.addWidget(self.back_btn)

        self.category_btns = {
            "anime": QPushButton("Anime"),
            "classic": QPushButton("Classic")
        }
        for btn in self.category_btns.values():
            btn.setStyleSheet(self.button_style())
            btn.clicked.connect(lambda _, c=btn.text().lower(): self.switch_category(c))
            top_bar.addWidget(btn)

        self.fav_btn = QPushButton("⭐ Избранное")
        self.fav_btn.setStyleSheet(self.button_style())
        self.fav_btn.clicked.connect(self.toggle_fav_mode)
        top_bar.addWidget(self.fav_btn)

        self.reset_cursor_btn = QPushButton("Сбросить курсор в стандартный")
        self.reset_cursor_btn.setStyleSheet(self.button_style())
        self.reset_cursor_btn.clicked.connect(self.reset_to_default_cursor)
        top_bar.addWidget(self.reset_cursor_btn)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск...")
        self.search.textChanged.connect(self.update_display)
        top_bar.addWidget(self.search)
        layout.addLayout(top_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.scroll.setWidget(self.grid_widget)
        layout.addWidget(self.scroll)

        pagination = QHBoxLayout()
        self.page_label = QLabel()
        self.page_label.setStyleSheet("color: white; font-family: 'Segoe UI';")
        pagination.addWidget(self.page_label)

        self.prev_btn = QPushButton("◀ Назад")
        self.prev_btn.setStyleSheet(self.button_style())
        self.prev_btn.clicked.connect(self.prev_page)
        pagination.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Вперед ▶")
        self.next_btn.setStyleSheet(self.button_style())
        self.next_btn.clicked.connect(self.next_page)
        pagination.addWidget(self.next_btn)
        layout.addLayout(pagination)

        self.stacked.addWidget(self.browser)

    def create_functions_menu(self):
        widget = StarryBackground()
        widget.setObjectName("functionsMenu")
        widget.setStyleSheet(f"#functionsMenu {{ background-image: url({self.bg_image}); }}")
        layout = QVBoxLayout(widget)

        title = QLabel("Функции")
        title.setStyleSheet("""
            font-size: 42px; 
            color: #aaccff;
            font-weight: bold;
            background-color: transparent;
            font-family: 'Segoe UI';
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        buttons = [
            ("❤ Поддержать", self.show_support),
            ("Обнова?", self.check_for_update),
            ("🔙 Назад", self.show_main_menu)
        ]

        for text, callback in buttons:
            btn_container = AnimatedBorderWidget()
            btn_container.setFixedSize(300, 80)
            btn_layout = QVBoxLayout(btn_container)
            btn_layout.setContentsMargins(8, 8, 8, 8)

            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(20,20,50,0.7);
                    color: #aaccff;
                    border: none;
                    border-radius: 8px;
                    font-size: 24px;
                    padding: 15px;
                    font-family: 'Segoe UI';
                }
                QPushButton:hover {
                    background-color: rgba(50,50,100,0.9);
                }
            """)
            btn.clicked.connect(callback)
            btn_layout.addWidget(btn)
            layout.addWidget(btn_container, alignment=Qt.AlignCenter)

        self.stacked.addWidget(widget)

    def button_style(self):
        return """
            QPushButton {
                background-color: rgba(30,30,60,0.8);
                color: #aaccff;
                border: 2px solid #4466ff;
                border-radius: 6px;
                padding: 8px;
                font-size: 16px;
                font-family: 'Segoe UI';
            }
            QPushButton:hover {
                background-color: rgba(50,50,100,0.9);
                border-color: #88aaff;
            }
        """

    def start_loading(self, category):
        self.current_category = category
        self.stacked.setCurrentWidget(self.loader)
        self.loader.title_label.setText("Загрузка курсоров...")
        self.loader.file_label.setText("Инициализация...")
        self.loader.progress.setValue(0)

        self.thread = QThread()
        self.worker = Worker(category)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.handle_loaded_data)
        self.worker.error.connect(self.handle_error)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def handle_loaded_data(self, cursors):
        self.current_cursors = cursors
        self.cursor_options = list(cursors.keys())
        self.current_page = 0
        self.update_display()
        self.stacked.setCurrentWidget(self.browser)

    def handle_error(self, message):
        logging.error(f"Ошибка загрузки курсоров: {message}")
        self.loader.title_label.setText("Ошибка")
        self.loader.file_label.setText(f"Ошибка: {message}")
        self.loader.progress.setValue(0)
        self.loader.info_label.setText("")
        QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки курсоров:\n{message}")
        self.show_category_menu()

    def update_display(self):
        search_text = self.search.text().lower()
        current_category = self.current_category if not self.is_fav_mode else None
        filtered = []

        for name in self.cursor_options:
            if self.is_fav_mode:
                if {"name": name, "category": self.current_category} in self.favorites:
                    if search_text in name.lower():
                        filtered.append(name)
            else:
                if search_text in name.lower():
                    filtered.append(name)

        if self.is_fav_mode:
            all_fav_names = [item["name"] for item in self.favorites]
            filtered = [name for name in all_fav_names if search_text in name.lower()]
            self.current_cursors = {}
            for item in self.favorites:
                path = ANIME_PATH if item["category"] == "anime" else CLASSIC_PATH
                full_path = os.path.join(path, item["name"])
                if os.path.isdir(full_path):
                    cursor_files = self.load_cursor_files(full_path)
                    if cursor_files:  # Только если есть файлы курсоров
                        self.current_cursors[item["name"]] = cursor_files

        total_pages = (len(filtered) - 1) // self.items_per_page + 1
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = filtered[start:end]

        while self.grid.count():
            child = self.grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        row, col = 0, 0
        for name in page_items:
            self.grid.addWidget(self.create_card(name), row, col)
            col = (col + 1) % 4
            if col == 0:
                row += 1

        self.page_label.setText(f"Страница {self.current_page + 1} из {total_pages}")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(end < len(filtered))

    def create_card(self, name):
        category = self.current_category if not self.is_fav_mode else next(
            (item["category"] for item in self.favorites if item["name"] == name), "anime"
        )
        card = QFrame()
        card.setStyleSheet("background-color: #3a3b3f; border-radius: 10px;")
        card.setFixedSize(230, 320)
        layout = QVBoxLayout(card)

        preview_path = self.find_preview(name, category)
        gif_widget = None
        if preview_path:
            gif_widget = AnimatedGIF(preview_path)
            layout.addWidget(gif_widget, alignment=Qt.AlignCenter)

        def enter_event(event):
            if gif_widget:
                gif_widget.start_animation()
            QFrame.enterEvent(card, event)

        def leave_event(event):
            if gif_widget:
                gif_widget.stop_animation()
            QFrame.leaveEvent(card, event)

        card.enterEvent = enter_event
        card.leaveEvent = leave_event

        title = QLabel(name)
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold; font-family: 'Segoe UI';")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        apply_btn = QPushButton("Применить")
        apply_btn.setStyleSheet(self.button_style())
        apply_btn.clicked.connect(lambda: self.apply_cursor(name))
        layout.addWidget(apply_btn)

        fav_btn = QPushButton("★" if {"name": name, "category": category} in self.favorites else "☆")
        fav_btn.setStyleSheet(self.button_style())
        fav_btn.clicked.connect(lambda: self.toggle_favorite(name, category, fav_btn))
        layout.addWidget(fav_btn)

        return card

    def find_preview(self, name, category):
        # Теперь ищем превью в CursorLib/CursorsLib/Anime/<name>/preview.gif или CursorLib/CursorsLib/Classic/<name>/preview.gif
        base_path = os.path.join(CURSOR_LIB_PATH, "CursorsLib")
        path = os.path.join(base_path, "Anime") if category == "anime" else os.path.join(base_path, "Classic")
        preview = os.path.join(path, name, "preview.gif")
        return preview if os.path.exists(preview) else None

    def apply_cursor(self, name):
        if self.is_fav_mode:
            category = next(item["category"] for item in self.favorites if item["name"] == name)
        else:
            category = self.current_category

        scheme = self.current_cursors.get(name)
        try:
            if not scheme:
                raise ValueError("Схема курсоров не найдена")

            import winreg
            reg_path = r"Control Panel\Cursors"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE) as key:
                for key_name, reg_name in CURSOR_KEYS.items():
                    if key_name in scheme:
                        winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, scheme[key_name])

            ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 3)
            self.update_recent(name)
            self.show_notification(f"Курсор '{name}' установлен!")
        except Exception as e:
            logging.error(f"Ошибка применения курсора {name}: {str(e)}")
            self.show_notification(f"Ошибка: {str(e)}")

    def update_recent(self, name):
        if name in self.recent_cursors:
            self.recent_cursors.remove(name)
        self.recent_cursors.insert(0, name)
        if len(self.recent_cursors) > 5:
            self.recent_cursors.pop()
        self.save_data()

    def toggle_favorite(self, name, category, btn):
        entry = {"name": name, "category": category}
        if entry in self.favorites:
            self.favorites.remove(entry)
            btn.setText("☆")
        else:
            self.favorites.append(entry)
            btn.setText("★")
        self.save_data()

    def toggle_fav_mode(self):
        self.is_fav_mode = not self.is_fav_mode
        self.fav_btn.setText("⭐ Избранное" if not self.is_fav_mode else "⭐ Избранное")
        self.update_display()

    def switch_category(self, category):
        self.current_category = category
        self.is_fav_mode = False
        self.start_loading(category)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_display()

    def next_page(self):
        self.current_page += 1
        self.update_display()

    def show_notification(self, message):
        logging.info(f"Уведомление: {message}")
        Notification(message).show()

    def show_main_menu(self):
        self.stacked.setCurrentIndex(0)

    def show_category_menu(self):
        self.stacked.setCurrentIndex(1)

    def show_functions_menu(self):
        self.stacked.setCurrentIndex(4)

    def show_support(self):
        dialog = QDialog(self)
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.setObjectName("supportDialog")
        dialog.setStyleSheet("""
            #supportDialog {
                background-color: rgba(42, 43, 46, 0.95);
                color: white;
                border-radius: 15px;
            }
        """)
        dialog.setWindowTitle("Поддержка")
        dialog.setGeometry(300, 300, 400, 300)
        layout = QVBoxLayout(dialog)

        methods = [
            ("PayPal", "shustovxd15032112@gmail.com"),
            ("Карта", "4441 1111 4578 3068"),
            ("USDT", "0x15f784a623554e085befe9c03131aa29e6226ed3")
        ]

        for service, data in methods:
            btn = QPushButton(f"{service}: {data}")
            btn.setStyleSheet(self.button_style() + "min-width: 200px;")
            btn.clicked.connect(lambda _, d=data: (
                QApplication.clipboard().setText(d),
                self.show_notification(f"Скопировано: {d}")
            ))
            layout.addWidget(btn)

        links = [
            ("Patreon", "https://patreon.com/Shustov?utm_medium=unknown&utm_source=join_link&utm_campaign=creatorshare_creator&utm_content=copyLink"),
            ("FunPay", "https://funpay.com/uk/users/6117488/")
        ]

        for text, url in links:
            btn = QPushButton(text)
            btn.setStyleSheet(self.button_style())
            btn.clicked.connect(lambda _, u=url: webbrowser.open(u))
            layout.addWidget(btn)

        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet(self.button_style())
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def load_cursor_files(self, folder_path):
        cursor_files = {}
        if os.path.exists(folder_path):
            for name in os.listdir(folder_path):
                if name.lower().endswith((".cur", ".ani")):
                    key = name.lower().split(".")[0]
                    cursor_files[key] = os.path.abspath(os.path.join(folder_path, name))
        return cursor_files

    def reset_to_default_cursor(self):
        try:
            import winreg
            reg_path = r"Control Panel\Cursors"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE) as key:
                for key_name, reg_name in CURSOR_KEYS.items():
                    winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, "")
            ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 3)
            self.show_notification("Восстановлен стандартный курсор Windows!")
        except Exception as e:
            logging.error(f"Ошибка сброса курсора: {str(e)}")
            self.show_notification(f"Ошибка: {str(e)}")

    def check_for_update(self):
        import requests
        import zipfile
        import io
        import shutil
        import subprocess

        repo_api = "https://api.github.com/repos/ShustovCarleone/Cursor-Galaxy/releases/latest"

        try:
            self.show_notification("Проверка обновлений...")
            response = requests.get(repo_api, timeout=10)
            response.raise_for_status()
            data = response.json()

            latest_version = data["tag_name"]
            zip_url = data["zipball_url"]

            if latest_version != APP_VERSION:
                reply = QMessageBox.question(
                    self,
                    "Новая версия доступна",
                    f"Обнаружена новая версия: {latest_version}.\nУстановить и перезапустить?",
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    zip_data = requests.get(zip_url)
                    with zipfile.ZipFile(io.BytesIO(zip_data.content)) as z:
                        temp_dir = "update_temp"
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)
                        z.extractall(temp_dir)

                    extracted_folders = os.listdir(temp_dir)
                    if extracted_folders:
                        extracted_path = os.path.join(temp_dir, extracted_folders[0])
                        for item in os.listdir(extracted_path):
                            s = os.path.join(extracted_path, item)
                            d = os.path.join(".", item)
                            if os.path.isdir(s):
                                if os.path.exists(d):
                                    shutil.rmtree(d)
                                shutil.copytree(s, d)
                            else:
                                shutil.copy2(s, d)

                        shutil.rmtree(temp_dir)
                        self.show_notification("Обновление завершено!")
                        
                        QMessageBox.information(self, "Перезапуск", "Программа будет перезапущена.")
                        self.restart_app()
            else:
                QMessageBox.information(self, "Обновлений нет", "Вы используете последнюю версию.")
        except Exception as e:
            logging.error(f"Ошибка проверки обновления: {str(e)}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось проверить обновление:\n{str(e)}")

    def restart_app(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def update_cursors(self):
        self.start_check_process()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainApp()
    window.show()
    sys.exit(app.exec())
