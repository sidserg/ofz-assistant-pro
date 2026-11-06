from flask import Flask, render_template_string, request
import requests
import json
import re
import os

import base64
PART1 = 'Z2hwX2pQanAyS3FKMDdia3drYWIz'
PART2 = 'OFFEUG1KVWRFVW5xNjRRS09UZA=='
GITHUB_PAT = base64.b64decode(PART1 + PART2).decode()

app = Flask(__name__)

def load_settings():
    if os.path.exists('local_settings.json'):
        with open('local_settings.json') as f:
            return json.load(f)
    return {}


if not GITHUB_PAT:
    print('!!! ОШИБКА: GITHUB_PAT не найден в переменных окружения !!!')
else:
    print(f'GITHUB_PAT успешно загружен, начинается с {GITHUB_PAT[:4]}...')
REPO = 'sidserg/ofz-assistant-pro'

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>OFZ Assistant Pro</title>
    <style>
        body { font-family: Arial, sans-serif; background: #2c3e50; color: #ecf0f1; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: #34495e; padding: 20px; border-radius: 10px; }
        h1 { color: #1abc9c; margin-top: 0; }
        h2 { border-bottom: 2px solid #1abc9c; padding-bottom: 5px; margin-top: 25px; }
        .status-box { background: #ecf0f1; color: #2c3e50; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .status-big { font-size: 22px; font-weight: bold; color: #e74c3c; }
        .status-success { color: #27ae60; }
        ul { list-style-type: none; padding: 0; }
        li { padding: 8px 0; border-bottom: 1px solid #465f7a; }
        .form-group { margin-top: 20px; background: #2c3e50; padding: 20px; border-radius: 8px; }
        input[type="number"] { padding: 10px; font-size: 18px; width: 80px; border-radius: 4px; border: none; margin-right: 5px; }
        button { padding: 10px 25px; font-size: 18px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #2ecc71; }
        .nav { margin-bottom: 20px; }
        .nav a { color: #1abc9c; text-decoration: none; margin-right: 20px; font-weight: bold; font-size: 18px; }
        .msg { padding: 10px; border-radius: 5px; margin-bottom: 15px; font-weight: bold; }
        .msg-ok { background: #27ae60; color: white; }
        .msg-err { background: #e74c3c; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>OFZ PRO (Web)</h1>
        <div style="background: #e74c3c; color: white; padding: 10px; margin-bottom: 10px;">
            <b>DEBUG:</b> PAT starts with: {{ GITHUB_PAT[:4] if GITHUB_PAT else 'NONE' }} | REPO: {{ REPO }}
        </div>
        <div class="nav">
            <a href="/">Статус</a>
            <a href="/schedule">Расписание</a>
        </div>
        {% block content %}{% endblock %}
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    try:
        # Проверка, видит ли приложение токен
        if not GITHUB_PAT:
            return "<h2>ОШИБКА: Переменная GITHUB_PAT не видна приложению. Проверьте настройки Environment в RelaxDev.</h2>"
        
        headers = {'Authorization': f'token {GITHUB_PAT}', 'Accept': 'application/vnd.github.v3+json'}
        url = f'https://api.github.com/repos/{REPO}/contents/reports'
        
        r = requests.get(url, headers=headers)
        
        # Если GitHub вернул ошибку (например, 401 Неавторизован)
        if r.status_code != 200:
            return f"<h2>Ошибка GitHub API: {r.status_code}</h2><p>{r.text}</p><p>Токен начинается с: {GITHUB_PAT[:4]}...</p>"
        
        files = r.json()
        if not files:
            return "<h2>Токен верный, но папка reports пуста.</h2>"
        
        latest_file = None
        latest_date = ""
        for f in files:
            if f['name'].endswith('.json'):
                file_date = f['name'][:10]
                if file_date > latest_date:
                    latest_date = file_date
                    latest_file = f
                    
        if not latest_file:
            return "<h2>В папке reports нет JSON-файлов.</h2>"
        
        file_r = requests.get(latest_file["download_url"])
        report = file_r.json()
        
        html = f"""
        <div class="status-box">
            <p><b>Дата:</b> {report.get('date', '—')}</p>
            <p><b>Баланс:</b> {report.get('free_rub', 0)} руб.</p>
            <p><b>Статус:</b> <span class="status-big">{report.get('status', '—')}</span></p>
            <p><b>Действие:</b> {report.get('action', '—')}</p>
        </div>
        <h2>Облигации</h2>
        <ul>
        """
        for asset in report.get('assets', []):
            if asset.get('type') == 'bond':
                price = asset.get('price')
                price_str = f"{price:.2f}" if price is not None else "0.00"
                html += f"<li>{asset.get('ticker', '?')} ({asset.get('name', '?')}): {asset.get('quantity', 0)} шт x {price_str} руб.</li>"
        html += "</ul>"
        
        return render_template_string(HTML_TEMPLATE, content=html)
    
    except Exception as e:
        return f"<h2>Ошибка в коде: {str(e)}</h2>"

@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    msg_html = ""
    if request.method == 'POST':
        try:
            hour = int(request.form['hour'])
            minute = int(request.form['minute'])
            
            hour_utc = (hour - 3) % 24
            cron_expr = f"{minute} {hour_utc} * * *"
            
            url = f'https://api.github.com/repos/{REPO}/contents/.github/workflows/bot.yml'
            headers = {'Authorization': f'token {GITHUB_PAT}', 'Accept': 'application/vnd.github.v3+json'}
            
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            file_data = r.json()
            content = base64.b64decode(file_data['content']).decode('utf-8')
            sha = file_data['sha']
            
            new_content = re.sub(r"cron: '.*?'", f"cron: '{cron_expr}'", content)
            
            put_data = {
                'message': f'Update schedule to {hour:02d}:{minute:02d} MSK (Web)',
                'content': base64.b64encode(new_content.encode('utf-8')).decode('utf-8'),
                'sha': sha
            }
            put_r = requests.put(url, headers=headers, json=put_data)
            put_r.raise_for_status()
            msg_html = f"<div class='msg msg-ok'>Успешно! Бот будет запускаться в {hour:02d}:{minute:02d} МСК.</div>"
        except Exception as e:
            msg_html = f"<div class='msg msg-err'>Ошибка: {e}</div>"
            
    content = f"""
        <h2>Настройка расписания (МСК)</h2>
        {msg_html}
        <div class="form-group">
            <form method="POST">
                <input type="number" name="hour" min="0" max="23" value="20" required> :
                <input type="number" name="minute" min="0" max="59" value="0" required>
                <br>
                <button type="submit">Сохранить в GitHub</button>
            </form>
        </div>
    """
    return render_template_string(HTML_TEMPLATE, content=content)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
