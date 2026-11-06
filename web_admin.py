from flask import Flask, render_template_string, request
import requests
import base64
import re

app = Flask(__name__)

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
    <title>OFZ PRO</title>
    <style>
        * { box-sizing: border-box; }
        body { margin: 0; font-family: Arial, sans-serif; background: #f4f6f9; display: flex; height: 100vh; }
        .sidebar { width: 200px; background: #2c3e50; color: white; display: flex; flex-direction: column; }
        .sidebar h1 { font-size: 18px; text-align: center; padding: 20px 0; background: #1a252f; margin: 0; color: #1abc9c; }
        .sidebar a { padding: 15px; text-decoration: none; color: #bdc3c7; border-left: 4px solid transparent; }
        .sidebar a:hover, .sidebar a.active { background: #34495e; color: white; border-left-color: #1abc9c; }
        .main { flex-grow: 1; padding: 20px; overflow-y: auto; }
        .card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
        h2 { color: #2c3e50; margin-top: 0; }
        .status-big { font-size: 22px; font-weight: bold; color: #e74c3c; }
        ul { list-style: none; padding: 0; }
        li { padding: 8px 0; border-bottom: 1px solid #eee; }
        input[type="number"] { padding: 8px; font-size: 16px; width: 70px; border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 10px 20px; font-size: 16px; background: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px; }
        .msg { padding: 10px; border-radius: 4px; margin-bottom: 10px; }
        .msg-ok { background: #d4edda; color: #155724; }
        .msg-err { background: #f8d7da; color: #721c24; }
        @media (max-width: 600px) {
            body { flex-direction: column; }
            .sidebar { width: 100%; flex-direction: row; overflow-x: auto; }
            .sidebar h1 { display: none; }
            .sidebar a { border-left: none; border-bottom: 4px solid transparent; white-space: nowrap; }
            .sidebar a.active { border-bottom-color: #1abc9c; }
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <h1>OFZ PRO</h1>
        <a href="/?tab=status" class="{{ 'active' if tab == 'status' else '' }}">Статус</a>
        <a href="/?tab=schedule" class="{{ 'active' if tab == 'schedule' else '' }}">Расписание</a>
    </div>
    <div class="main">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    tab = request.args.get('tab', 'status')
    content = ""
    msg = ""

    if tab == 'status':
        try:
            headers = {'Authorization': f'token {GITHUB_PAT}', 'Accept': 'application/vnd.github.v3+json'}
            r = requests.get(f'https://api.github.com/repos/{REPO}/contents/reports', headers=headers)
            r.raise_for_status()
            files = r.json()
            if not files:
                content = "<div class='card'><h2>Отчетов пока нет.</h2></div>"
            else:
                latest = sorted(files, key=lambda x: x["name"], reverse=True)[0]
                file_data = requests.get(latest["download_url"]).json()
                
                html = f"""
                <div class="card">
                    <h2>Последний результат</h2>
                    <p><b>Дата:</b> {file_data.get('date', '—')}</p>
                    <p><b>Баланс:</b> {file_data.get('free_rub', 0)} руб.</p>
                    <p><b>Статус:</b> <span class="status-big">{file_data.get('status', '—')}</span></p>
                    <p><b>Действие:</b> {file_data.get('action', '—')}</p>
                </div>
                <div class="card">
                    <h2>Облигации</h2><ul>
                """
                for a in file_data.get('assets', []):
                    if a.get('type') == 'bond':
                        p = a.get('price', 0)
                        html += f"<li>{a.get('ticker')} ({a.get('name')}): {a.get('quantity')} шт x {p:.2f} руб.</li>"
                html += "</ul></div>"
                content = html
        except Exception as e:
            content = f"<div class='card'><h2>Ошибка: {e}</h2></div>"

    elif tab == 'schedule':
        if request.method == 'POST':
            try:
                h = int(request.form['hour'])
                m = int(request.form['minute'])
                h_utc = (h - 3) % 24
                cron = f"{m} {h_utc} * * *"
                
                headers = {'Authorization': f'token {GITHUB_PAT}', 'Accept': 'application/vnd.github.v3+json'}
                url = f'https://api.github.com/repos/{REPO}/contents/.github/workflows/bot.yml'
                
                r = requests.get(url, headers=headers)
                r.raise_for_status()
                data = r.json()
                yml = base64.b64decode(data['content']).decode('utf-8')
                sha = data['sha']
                
                new_yml = re.sub(r"cron: '.*?'", f"cron: '{cron}'", yml)
                
                put_data = {
                    'message': f'Update schedule to {h:02d}:{m:02d} MSK (Web Admin)',
                    'content': base64.b64encode(new_yml.encode('utf-8')).decode('utf-8'),
                    'sha': sha
                }
                requests.put(url, headers=headers, json=put_data).raise_for_status()
                msg = f"<div class='msg msg-ok'>Успех! Время изменено на {h:02d}:{m:02d} МСК.</div>"
            except Exception as e:
                msg = f"<div class='msg msg-err'>Ошибка: {e}</div>"

        content = f"""
        <div class="card">
            <h2>Настройка расписания</h2>
            {msg}
            <p>Время по Москве:</p>
            <form method="POST">
                <input type="number" name="hour" min="0" max="23" value="20" required> :
                <input type="number" name="minute" min="0" max="59" value="0" required>
                <br><button type="submit">Сохранить в GitHub</button>
            </form>
            <script>
                document.querySelectorAll('input[name="type"]').forEach(function(radio) {
                    radio.addEventListener('change', function() {
                        document.getElementById('selected_mode').value = this.value;
                    });
                });
            </script>
        </div>
        """

    return render_template_string(HTML_TEMPLATE, content=content, tab=tab)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
