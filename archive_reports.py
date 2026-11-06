"""Архивация старых отчетов: объединяет отчеты старше 7 дней в месячные архивы."""
import os
import json
import glob
from datetime import datetime, timedelta
from collections import defaultdict

REPORTS_DIR = "reports"
ARCHIVE_DIR = "reports/archives"
ARCHIVE_THRESHOLD_DAYS = 7

os.makedirs(ARCHIVE_DIR, exist_ok=True)
threshold_date = datetime.now() - timedelta(days=ARCHIVE_THRESHOLD_DAYS)

# Группируем старые отчеты по месяцам (YYYY-MM)
monthly_data = defaultdict(list)
files_to_remove = []

for filepath in glob.glob(os.path.join(REPORTS_DIR, "*.json")):
    try:
        # Получаем дату из имени файла (формат: YYYY-MM-DD_HH-MM-SS_...)
        filename = os.path.basename(filepath)
        date_str = filename[:10]
        file_date = datetime.strptime(date_str, "%Y-%m-%d")
        
        if file_date < threshold_date:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            month_key = file_date.strftime("%Y-%m")
            monthly_data[month_key].append(data)
            files_to_remove.append(filepath)
    except Exception as e:
        print(f"Ошибка чтения {filepath}: {e}")

# Сохраняем архивы
for month_key, reports in monthly_data.items():
    archive_path = os.path.join(ARCHIVE_DIR, f"{month_key}.json")
    if os.path.exists(archive_path):
        with open(archive_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        existing.extend(reports)
        reports = existing
    
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    
    print(f"Архивировано {len(reports)} отчетов в {archive_path}")

# Удаляем старые файлы
for filepath in files_to_remove:
    os.remove(filepath)
    print(f"Удален обработанный файл: {filepath}")

print("Архивация завершена.")
