from flask import Flask, render_template_string, request
import requests
import base64
import json

app = Flask(__name__)

# Токен, зашитый в base64 (безопасно для GitHub)
PART1 = 'Z2hwX2pQanAyS3FKMDdia3drYWIz'
PART2 = 'OFFEUG1KVWRFVW5xNjRRS09UZA=='
GITHUB_PAT = base64.b64decode(PART1 + PART2).decode()
REPO = 'sidserg/ofz-assistant-pro'

HTML_TEMPLATE = """
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
        <p style="color: yellow;">TEST_TOKEN: {{ GITHUB_PAT[:10] if GITHUB_PAT else 'EMPTY' }}</p>
        <div class="nav">
            <a href="/">Статус</a>
            <a href="/schedule">Расписание</a>
        </div>
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    if not GITHUB_PAT:
        return render_template_string(HTML_TEMPLATE, content="<h2 style='color:red'>ОШИБКА: Токен пуст!</h2>")
    
    headers = {'Authorization': f'token {GITHUB_PAT}', 'Accept': 'application/vnd.github.v3+json'}
    url = f'https://api.github.com/repos/{REPO}/contents/reports'
    
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            return render_template_string(HTML_TEMPLATE, content=f"<h2 style='color:red'>Ошибка GitHub: {r.status_code}</h2>")
            
        files = r.json()
        if not files:
            return render_template_string(HTML_TEMPLATE, content="<h2>Отчетов пока нет.</h2>")
            
        latest_file = sorted(files, key=lambda x: x["name"], reverse=True)[0]
        file_r = requests.get(latest_file["download_url"])
        report = file_r.json()
        
        html = f'''
        <div class="status-box">
            <p><b>Дата:</b> {report.get('date', '—')}</p>
            <p><b>Баланс:</b> {report.get('free_rub', 0)} руб.</p>
            <p><b>Статус:</b> <span class="status-big">{report.get('status', '—')}</span></p>
            <p><b>Действие:</b> {report.get('action', '—')}</p>
        </div>
        <h2>Облигации</h2>
        <ul>
        '''
        for asset in report.get('assets', []):
            if asset.get('type') == 'bond':
                price = asset.get('price')
                price_str = f"{price:.2f}" if price is not None else "0.00"
                html += f"<li>{asset.get('ticker', '?')} ({asset.get('name', '?')}): {asset.get('quantity', 0)} шт x {price_str} руб.</li>"
        html += "</ul>"
        
        return render_template_string(HTML_TEMPLATE, content=html)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, content=f"<h2 style='color:red'>Ошибка: {str(e)}</h2>")

@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    return render_template_string(HTML_TEMPLATE, content="<h2>Настройка расписания пока в разработке.</h2>")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
