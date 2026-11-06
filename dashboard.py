import sys
import json
import base64
import os
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QCheckBox, QMessageBox, QStackedWidget, QTextEdit, 
                             QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QRadioButton, QComboBox, QSpinBox, QGroupBox)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal

GITHUB_REPO = "sidserg/ofz-assistant-pro"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}"
CONFIG_FILE = "local_settings.json"

def load_local_settings():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_local_settings(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

class GitHubWorker(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, pat, tinkoff_token, create_portfolio, schedule_data):
        super().__init__()
        self.pat = pat
        self.tinkoff_token = tinkoff_token
        self.create_portfolio = create_portfolio
        self.schedule_data = schedule_data
        
    def run(self):
        try:
            headers = {"Authorization": f"token {self.pat}", "Accept": "application/vnd.github.v3+json"}
            config_url = f"{GITHUB_API_URL}/contents/config.json"
            r = requests.get(config_url, headers=headers)
            if r.status_code != 200:
                self.finished.emit(False, f"Ошибка: {r.text}")
                return
            content_data = r.json()
            current_config = json.loads(base64.b64decode(content_data["content"]).decode('utf-8'))
            current_config["create_portfolio"] = self.create_portfolio
            current_config["schedule"] = self.schedule_data
            new_content = base64.b64encode(json.dumps(current_config, indent=2).encode('utf-8')).decode('utf-8')
            update_data = {"message": "Update config", "content": new_content, "sha": content_data["sha"]}
            r = requests.put(config_url, headers=headers, json=update_data)
            if r.status_code not in [200, 201]:
                self.finished.emit(False, f"Ошибка: {r.text}")
                return
            self.finished.emit(True, "Расписание сохранено!")
        except Exception as e:
            self.finished.emit(False, str(e))

class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OFZ Assistant Pro")
        self.setGeometry(0, 0, 1920, 1080)
        self.setStyleSheet("QMainWindow { background-color: #f0f2f5; } QWidget { font-size: 20px; }")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Меню ---
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background-color: #2c3e50; color: white;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        title = QLabel("OFZ PRO")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ecf0f1; padding-left: 20px;")
        sidebar_layout.addWidget(title)
        sidebar_layout.addSpacing(20)

        self.btn_status = self.create_menu_button("Статус")
        self.btn_calendar = self.create_menu_button("Календарь")
        self.btn_schedule = self.create_menu_button("Расписание")
        self.btn_settings = self.create_menu_button("Настройки")
        self.btn_create = self.create_menu_button("Создать портфель")

        sidebar_layout.addWidget(self.btn_status)
        sidebar_layout.addWidget(self.btn_calendar)
        sidebar_layout.addWidget(self.btn_schedule)
        sidebar_layout.addWidget(self.btn_settings)
        sidebar_layout.addWidget(self.btn_create)
        sidebar_layout.addStretch()

        self.btn_status.clicked.connect(lambda: self.show_status())
        self.btn_calendar.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_schedule.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.btn_settings.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        self.btn_create.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        main_layout.addWidget(sidebar)

        # --- Контент ---
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #ffffff;")

        # 0: Статус
        page_status = QWidget()
        status_layout = QVBoxLayout(page_status)
        status_layout.setContentsMargins(20, 20, 20, 20)
        status_layout.addWidget(QLabel("<h2>Последний результат отработки</h2>"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-size: 16px; background: #ecf0f1; padding: 10px;")
        self.log_output.setPlaceholderText("Загрузка последнего отчета...")
        status_layout.addWidget(self.log_output)
        self.stack.addWidget(page_status)

        # 1: Календарь
        page_calendar = QWidget()
        cal_layout = QVBoxLayout(page_calendar)
        cal_layout.setContentsMargins(20, 20, 20, 20)
        cal_layout.addWidget(QLabel("<h2>Календарь</h2>"))
        
        cal_header = QHBoxLayout()
        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedSize(40, 40)
        self.btn_prev.clicked.connect(self.prev_month)
        self.lbl_month_year = QLabel()
        self.lbl_month_year.setAlignment(Qt.AlignCenter)
        self.lbl_month_year.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.btn_next = QPushButton(">")
        self.btn_next.setFixedSize(40, 40)
        self.btn_next.clicked.connect(self.next_month)
        cal_header.addWidget(self.btn_prev)
        cal_header.addWidget(self.lbl_month_year, 1)
        cal_header.addWidget(self.btn_next)
        cal_layout.addLayout(cal_header)

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(0)
        days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        for i, day in enumerate(days):
            lbl = QLabel(day)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet('font-weight: bold; padding: 10px; background: #f8f9fa; border: 1px solid #dee2e6;')
            self.grid_layout.addWidget(lbl, 0, i)
        self.calendar_days = []
        for row in range(1, 7):
            for col in range(7):
                btn = QPushButton()
                btn.setFixedHeight(80)
                btn.setStyleSheet('background: white; border: 1px solid #dee2e6; font-size: 16px;')
                self.grid_layout.addWidget(btn, row, col)
                self.calendar_days.append(btn)
        cal_layout.addLayout(self.grid_layout)
        cal_layout.addStretch(1)

        self.current_year = QDate.currentDate().year()
        self.current_month = QDate.currentDate().month()
        self.render_calendar()
        self.stack.addWidget(page_calendar)

        # 2: Расписание
        page_schedule = QWidget()
        schedule_layout = QVBoxLayout(page_schedule)
        schedule_layout.setContentsMargins(40, 40, 40, 40)
        schedule_layout.setSpacing(15)

        title = QLabel("График выполнения")
        title.setStyleSheet("font-size: 36px; font-weight: bold; margin-bottom: 5px;")
        schedule_layout.addWidget(title)

        msk_label = QLabel("Время указывается по Москве (МСК)")
        msk_label.setStyleSheet("font-size: 20px; color: #7f8c8d; margin-bottom: 20px;")
        schedule_layout.addWidget(msk_label)

        radio_style = "font-size: 18px; padding: 5px;"
        spin_style = "font-size: 22px; padding: 5px; background: white; border: 1px solid #bdc3c7; border-radius: 4px;"

        # 1. Каждые N минут
        row1 = QHBoxLayout()
        self.radio_minute = QRadioButton("Каждые")
        self.radio_minute.setStyleSheet(radio_style)
        self.combo_minute = QSpinBox()
        self.combo_minute.setRange(1, 59)
        self.combo_minute.setValue(15)
        self.combo_minute.setStyleSheet(spin_style)
        self.combo_minute.setFixedSize(80, 40)
        row1.addWidget(self.radio_minute)
        row1.addWidget(self.combo_minute)
        row1.addWidget(QLabel("минут(ы)"))
        row1.addStretch()
        schedule_layout.addLayout(row1)

        # 2. Каждый день в
        row2 = QHBoxLayout()
        self.radio_daily = QRadioButton("Каждый день в")
        self.radio_daily.setChecked(True)
        self.radio_daily.setStyleSheet(radio_style)
        
        self.combo_hour_d = QSpinBox()
        self.combo_hour_d.setRange(0, 23)
        self.combo_hour_d.setValue(20)
        self.combo_hour_d.setStyleSheet(spin_style)
        self.combo_hour_d.setFixedSize(80, 40)
        
        self.combo_min_d = QSpinBox()
        self.combo_min_d.setRange(0, 59)
        self.combo_min_d.setSingleStep(5)
        self.combo_min_d.setStyleSheet(spin_style)
        self.combo_min_d.setFixedSize(80, 40)
        
        row2.addWidget(self.radio_daily)
        row2.addWidget(self.combo_hour_d)
        row2.addWidget(QLabel(":"))
        row2.addWidget(self.combo_min_d)
        row2.addStretch()
        schedule_layout.addLayout(row2)

        # 3. Каждые N месяцев
        row3 = QHBoxLayout()
        self.radio_monthly = QRadioButton("Каждые")
        self.radio_monthly.setStyleSheet(radio_style)
        
        self.combo_month = QSpinBox()
        self.combo_month.setRange(1, 12)
        self.combo_month.setStyleSheet(spin_style)
        self.combo_month.setFixedSize(80, 40)
        
        row3.addWidget(self.radio_monthly)
        row3.addWidget(self.combo_month)
        row3.addWidget(QLabel("месяца в"))
        
        self.combo_hour_m = QSpinBox()
        self.combo_hour_m.setRange(0, 23)
        self.combo_hour_m.setValue(19)
        self.combo_hour_m.setStyleSheet(spin_style)
        self.combo_hour_m.setFixedSize(80, 40)
        
        self.combo_min_m = QSpinBox()
        self.combo_min_m.setRange(0, 59)
        self.combo_min_m.setSingleStep(5)
        self.combo_min_m.setStyleSheet(spin_style)
        self.combo_min_m.setFixedSize(80, 40)
        
        row3.addWidget(self.combo_hour_m)
        row3.addWidget(QLabel(":"))
        row3.addWidget(self.combo_min_m)
        row3.addStretch()
        schedule_layout.addLayout(row3)

        schedule_layout.addSpacing(30)

        # Кнопка Сохранить
        btn_save_schedule = QPushButton("Сохранить")
        btn_save_schedule.setFixedSize(200, 45)
        btn_save_schedule.setStyleSheet("background-color: #27ae60; color: white; font-size: 22px; font-weight: bold; border-radius: 6px;")
        btn_save_schedule.clicked.connect(self.save_custom_schedule)
        schedule_layout.addWidget(btn_save_schedule, alignment=Qt.AlignLeft)

        schedule_layout.addStretch()
        self.stack.addWidget(page_schedule)

        # 3: Настройки
        page_settings = QWidget()
        settings_layout = QVBoxLayout(page_settings)
        settings_layout.setContentsMargins(20, 20, 20, 20)
        settings_layout.addWidget(QLabel("<h2>Настройки</h2>"))
        settings_layout.addWidget(QLabel("Токен Т-Инвестиций:"))
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setStyleSheet("font-size: 18px; padding: 5px;")
        settings_layout.addWidget(self.token_input)
        settings_layout.addWidget(QLabel("GitHub PAT:"))
        self.github_pat_input = QLineEdit()
        self.github_pat_input.setEchoMode(QLineEdit.Password)
        self.github_pat_input.setStyleSheet("font-size: 18px; padding: 5px;")
        settings_layout.addWidget(self.github_pat_input)
        self.save_btn = QPushButton("Сохранить в GitHub")
        self.save_btn.setStyleSheet("font-size: 18px; padding: 10px;")
        self.save_btn.clicked.connect(self.save_settings)
        settings_layout.addWidget(self.save_btn)
        settings_layout.addStretch()
        self.stack.addWidget(page_settings)

        # 4: Создать портфель
        page_create = QWidget()
        create_layout = QVBoxLayout(page_create)
        create_layout.setContentsMargins(20, 20, 20, 20)
        create_layout.addWidget(QLabel("<h2>Создание портфеля</h2>"))
        self.create_portfolio_cb = QCheckBox("Разрешить создать портфель")
        self.create_portfolio_cb.setStyleSheet("font-size: 18px; padding: 10px;")
        create_layout.addWidget(self.create_portfolio_cb)
        self.btn_apply_create = QPushButton("Применить")
        self.btn_apply_create.setStyleSheet("font-size: 18px; padding: 10px;")
        self.btn_apply_create.clicked.connect(self.save_settings)
        create_layout.addWidget(self.btn_apply_create)
        create_layout.addStretch()
        self.stack.addWidget(page_create)

        # 5: Детали
        self.page_details = QWidget()
        details_layout = QVBoxLayout(self.page_details)
        details_layout.setContentsMargins(20, 20, 20, 20)
        back_btn = QPushButton("< Назад к календарю")
        back_btn.setFixedWidth(200)
        back_btn.setStyleSheet("font-size: 18px; padding: 10px;")
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        details_layout.addWidget(back_btn)
        details_layout.addWidget(QLabel("<h2>Отчет за дату</h2>"))
        self.table_assets = QTableWidget()
        self.table_assets.setColumnCount(4)
        self.table_assets.setHorizontalHeaderLabels(["Тикер", "Название", "Кол-во", "Цена (руб)"])
        self.table_assets.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_assets.setFixedHeight(400)
        details_layout.addWidget(self.table_assets)
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setStyleSheet("background: #ecf0f1; font-size: 18px; padding: 10px;")
        details_layout.addWidget(QLabel("<h3>Результат отработки:</h3>"))
        details_layout.addWidget(self.report_text)
        self.stack.addWidget(self.page_details)

        main_layout.addWidget(self.stack)
        self.load_tokens()
        self.show_status()

    def load_tokens(self):
        settings = load_local_settings()
        if "tinkoff_token" in settings:
            self.token_input.setText(settings["tinkoff_token"])
        if "github_pat" in settings:
            self.github_pat_input.setText(settings["github_pat"])

    def save_custom_schedule(self):
        import base64
        import requests
        import re
        from PyQt5.QtWidgets import QMessageBox

        if self.radio_daily.isChecked():
            hour = self.combo_hour_d.value()
            minute = self.combo_min_d.value()
        else:
            QMessageBox.warning(self, 'Внимание', 'Пока поддерживается только ежедневный запуск.')
            return

        hour_utc = (hour - 3) % 24
        cron_expr = f"{minute} {hour_utc} * * *"

        try:
            with open('config.json', 'r') as f:
                cfg = json.load(f)
            cfg['schedule'] = f"{minute:02d} {hour:02d} * * *"
            with open('config.json', 'w') as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось сохранить конфиг: {e}')
            return

        pat = self.github_pat_input.text().strip()
        if not pat:
            QMessageBox.warning(self, 'Внимание', 'Введите GitHub PAT в настройках.')
            return

        repo = 'sidserg/ofz-assistant-pro'
        url = f'https://api.github.com/repos/{repo}/contents/.github/workflows/bot.yml'
        headers = {'Authorization': f'token {pat}', 'Accept': 'application/vnd.github.v3+json'}

        try:
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            file_data = r.json()
            content = base64.b64decode(file_data['content']).decode('utf-8')
            sha = file_data['sha']

            new_content = re.sub(r"cron: '.*?'(.*)", f"cron: '{cron_expr}'  # {hour:02d}:{minute:02d} MSK", content)

            put_data = {
                'message': f'Update schedule to {hour:02d}:{minute:02d} MSK',
                'content': base64.b64encode(new_content.encode('utf-8')).decode('utf-8'),
                'sha': sha
            }
            put_r = requests.put(url, headers=headers, json=put_data)
            if put_r.status_code not in (200, 201):
                raise Exception(f'{put_r.status_code}: {put_r.text}')

            QMessageBox.information(self, 'Успех', f'Расписание обновлено в GitHub! Запуск в {hour:02d}:{minute:02d} МСК.')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка GitHub', f'Не удалось обновить GitHub: {e}')

    def show_status(self):
        self.stack.setCurrentIndex(0)
        self.log_output.setText("Загрузка последнего отчета...")
        pat = self.github_pat_input.text().strip()
        if not pat:
            self.log_output.setText("Введите GitHub PAT в настройках.")
            return
            
        headers = {"Authorization": f"token {pat}", "Accept": "application/vnd.github.v3+json"}
        url = f"{GITHUB_API_URL}/contents/reports"
        r = requests.get(url, headers=headers)
        
        if r.status_code != 200:
            self.log_output.setText(f"Ошибка: {r.text}")
            return
            
        files = r.json()
        if not files:
            self.log_output.setText("Отчетов пока нет.")
            return
            
        latest_file = sorted(files, key=lambda x: x["name"], reverse=True)[0]
        file_r = requests.get(latest_file["download_url"])
        
        if file_r.status_code == 200:
            data = file_r.json()
            
            text = f"<div style='font-size: 24px;'>"
            text += f"<b>Дата:</b> {data.get('date')}<br>"
            text += f"<b>Портфель:</b> {data.get('portfolio')}<br>"
            text += f"<b>Баланс:</b> {data.get('free_rub')} руб.<br>"
            text += f"<b>Статус:</b> {data.get('status')}<br>"
            text += f"<b>Действие:</b> {data.get('action', 'Нет данных')}<br><br>"
            
            assets = data.get("assets", [])
            shares = [a for a in assets if a['type'] == 'share']
            bonds = [a for a in assets if a['type'] == 'bond']
            others = [a for a in assets if a['type'] not in ('share', 'bond', 'currency')]
            currencies = [a for a in assets if a['type'] == 'currency']

            if shares:
                text += "<b>Акции:</b><br>"
                for a in shares:
                    text += f"&nbsp;&nbsp;• {a['ticker']} ({a['name']}): {a['quantity']} шт x {a['price']:.2f} руб.<br>"
                text += "<br>"
            if bonds:
                text += "<b>Облигации:</b><br>"
                for a in bonds:
                    text += f"&nbsp;&nbsp;• {a['ticker']} ({a['name']}): {a['quantity']} шт x {a['price']:.2f} руб.<br>"
                text += "<br>"
            if others:
                text += "<b>Другие активы:</b><br>"
                for a in others:
                    text += f"&nbsp;&nbsp;• {a['ticker']} ({a['name']}): {a['quantity']} шт x {a['price']:.2f} руб.<br>"
                text += "<br>"
            if currencies:
                text += "<b>Денежные средства:</b><br>"
                for a in currencies:
                    text += f"&nbsp;&nbsp;• {a['ticker']} ({a['name']}): {a['quantity']} шт x {a['price']:.2f} руб.<br>"
                text += "<br>"
            
            text += "</div>"
            self.log_output.setHtml(text)
        else:
            self.log_output.setText("Ошибка загрузки файла отчета.")

    def create_menu_button(self, text):
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton { text-align: left; padding-left: 20px; font-size: 18px; background: transparent; border: none; color: #bdc3c7; }
            QPushButton:hover { background: #34495e; color: white; }
            QPushButton:checked { background: #1abc9c; color: white; border-left: 4px solid #16a085; }
        """)
        btn.setFixedHeight(50)
        btn.setCheckable(True)
        if not hasattr(self, 'menu_group'):
            self.menu_group = []
        self.menu_group.append(btn)
        btn.clicked.connect(lambda: self.toggle_menu(btn))
        return btn

    def toggle_menu(self, clicked_btn):
        for btn in self.menu_group:
            if btn != clicked_btn:
                btn.setChecked(False)
        clicked_btn.setChecked(True)

    def render_calendar(self):
        date = QDate(self.current_year, self.current_month, 1)
        self.lbl_month_year.setText(date.toString("MMMM yyyy"))
        for btn in self.calendar_days:
            btn.setText("")
            btn.setEnabled(False)
            btn.setStyleSheet('background: #f8f9fa; border: 1px solid #dee2e6; color: #ccc;')
        first_day = date.dayOfWeek()
        days_in_month = date.daysInMonth()
        day = 1
        for i in range(42):
            if i >= first_day - 1 and day <= days_in_month:
                btn = self.calendar_days[i]
                btn.setText(str(day))
                btn.setEnabled(True)
                btn.setStyleSheet('background: white; border: 1px solid #dee2e6; color: black; font-weight: bold;')
                btn.clicked.connect(lambda checked, d=day: self.on_date_clicked(d))
                day += 1

    def on_date_clicked(self, day):
        date_str = f"{self.current_year}-{self.current_month:02d}-{day:02d}"
        self.load_report_from_github(date_str)
        self.stack.setCurrentIndex(5)
        
    def load_report_from_github(self, date_str):
        pat = self.github_pat_input.text().strip()
        if not pat:
            self.report_text.setText("Введите GitHub PAT в настройках.")
            return
            
        headers = {"Authorization": f"token {pat}", "Accept": "application/vnd.github.v3+json"}
        url = f"{GITHUB_API_URL}/contents/reports"
        r = requests.get(url, headers=headers)
        
        if r.status_code != 200:
            self.report_text.setText(f"Ошибка: {r.text}")
            return
            
        files = r.json()
        found = False
        report_text = f"--- Отчеты за {date_str} ---\n\n"
        assets_data = []
        
        for file in files:
            if date_str in file["name"]:
                found = True
                file_url = file["download_url"]
                file_r = requests.get(file_url)
                if file_r.status_code == 200:
                    data = file_r.json()
                    report_text += f"Портфель: {data.get('portfolio')}\n"
                    report_text += f"Баланс: {data.get('free_rub')} руб.\n"
                    report_text += f"Результат: {data.get('status')}\n\n"
                    assets_data = data.get("assets", [])
        
        if not found:
            report_text = f"Отчетов за {date_str} не найдено."
            
        self.report_text.setText(report_text)
        
        self.table_assets.setRowCount(0)
        
        def sort_key(a):
            t = a.get('type', '')
            if t == 'share': return 1
            if t == 'bond': return 2
            if t == 'currency': return 4
            return 3
            
        sorted_assets = sorted(assets_data, key=sort_key)
        
        for i, asset in enumerate(sorted_assets):
            self.table_assets.insertRow(i)
            self.table_assets.setItem(i, 0, QTableWidgetItem(str(asset.get("ticker", ""))))
            self.table_assets.setItem(i, 1, QTableWidgetItem(str(asset.get("name", ""))))
            self.table_assets.setItem(i, 2, QTableWidgetItem(str(asset.get("quantity", ""))))
            self.table_assets.setItem(i, 3, QTableWidgetItem(f"{asset.get('price', 0):.2f}"))

    def prev_month(self):
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self.render_calendar()

    def next_month(self):
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self.render_calendar()

    def save_settings(self, custom_schedule=None):
        token = self.token_input.text().strip()
        pat = self.github_pat_input.text().strip()
        create = self.create_portfolio_cb.isChecked()
        
        if not token or not pat:
            QMessageBox.warning(self, "Ошибка", "Заполните оба токена!")
            return
            
        cron = custom_schedule if custom_schedule else "0 19 * * *"
        
        save_local_settings({"tinkoff_token": token, "github_pat": pat})
        
        self.save_btn.setEnabled(False)
        self.worker = GitHubWorker(pat, token, create, cron)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
        
    def on_finished(self, success, message):
        self.save_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "Успех", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    sys.exit(app.exec_())
