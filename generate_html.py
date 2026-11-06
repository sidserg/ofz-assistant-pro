import json
import os
import glob

def generate_html_report():
    reports = sorted(glob.glob("reports/*.json"), reverse=True)
    if not reports:
        return
    
    with open(reports[0], 'r', encoding='utf-8') as f:
        report = f.read()
    
    data = json.loads(report)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>OFZ Assistant Pro</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #2c3e50; color: #ecf0f1; margin: 0; padding: 20px; }}
            .container {{ max-width: 800px; margin: 0 auto; background: #34495e; padding: 20px; border-radius: 10px; }}
            h1 {{ color: #1abc9c; margin-top: 0; }}
            h2 {{ border-bottom: 2px solid #1abc9c; padding-bottom: 5px; }}
            .status-box {{ background: #ecf0f1; color: #2c3e50; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .status-big {{ font-size: 22px; font-weight: bold; color: #e74c3c; }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ padding: 8px 0; border-bottom: 1px solid #465f7a; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>OFZ PRO (Web)</h1>
            <div class="status-box">
                <p><b>Дата:</b> {data.get('date', '—')}</p>
                <p><b>Баланс:</b> {data.get('free_rub', 0)} руб.</p>
                <p><b>Статус:</b> <span class="status-big">{data.get('status', '—')}</span></p>
                <p><b>Действие:</b> {data.get('action', '—')}</p>
            </div>
            <h2>Облигации</h2>
            <ul>
    """
    for asset in data.get('assets', []):
        if asset.get('type') == 'bond':
            price = asset.get('price', 0)
            html += f"<li>{asset.get('ticker')} ({asset.get('name')}): {asset.get('quantity')} шт x {price:.2f} руб.</li>"
    
    html += "</ul></div></body></html>"
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML-отчет сгенерирован: index.html")

if __name__ == "__main__":
    generate_html_report()
