from flask import Flask, send_from_directory
import os

app = Flask(__name__)

@app.route('/')
def index():
    if os.path.exists('index.html'):
        return send_from_directory('.', 'index.html')
    return "<h2>Отчет еще не сгенерирован. Подождите, пока бот отработает.</h2>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
