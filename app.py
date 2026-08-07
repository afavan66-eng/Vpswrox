import os
import subprocess
import sys
import json
import time
import shutil
import re
from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)

# === BOT YÖNETİCİ ===
class BotManager:
    def __init__(self):
        self.bots = {}
        self.load_state()
    
    def load_state(self):
        if os.path.exists('state.json'):
            with open('state.json', 'r') as f:
                self.bots = json.load(f)
    
    def save_state(self):
        with open('state.json', 'w') as f:
            json.dump(self.bots, f, indent=2)
    
    def detect_requirements(self, file_path):
        """Python dosyasından import edilen paketleri algıla"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        std_libs = {
            'os', 'sys', 'time', 'datetime', 'json', 're', 'math',
            'random', 'string', 'collections', 'itertools', 'functools',
            'typing', 'abc', 'enum', 'io', 'logging', 'threading',
            'queue', 'subprocess', 'socket', 'http', 'urllib', 'xml',
            'html', 'csv', 'sqlite3', 'hashlib', 'base64', 'binascii'
        }
        
        imports = set()
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('import '):
                match = re.match(r'^import\s+(\w+)', line)
                if match:
                    module = match.group(1).split('.')[0]
                    if module not in std_libs and not module.startswith('_'):
                        imports.add(module)
            elif line.startswith('from '):
                match = re.match(r'^from\s+(\w+)', line)
                if match:
                    module = match.group(1).split('.')[0]
                    if module not in std_libs and not module.startswith('_'):
                        imports.add(module)
        
        package_map = {
            'telegram': 'python-telegram-bot',
            'discord': 'discord.py',
            'flask': 'flask',
            'requests': 'requests',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'beautifulsoup': 'beautifulsoup4',
            'bs4': 'beautifulsoup4',
            'selenium': 'selenium',
            'aiohttp': 'aiohttp',
            'websockets': 'websockets',
            'fastapi': 'fastapi',
            'uvicorn': 'uvicorn',
            'django': 'django',
            'scikit': 'scikit-learn',
            'sklearn': 'scikit-learn',
            'tensorflow': 'tensorflow',
            'torch': 'torch',
            'opencv': 'opencv-python',
            'cv2': 'opencv-python',
            'PIL': 'pillow',
            'pillow': 'pillow',
            'pygame': 'pygame',
            'tweepy': 'tweepy',
            'spotipy': 'spotipy',
            'pymongo': 'pymongo',
            'sqlalchemy': 'sqlalchemy',
            'redis': 'redis',
            'celery': 'celery',
            'gunicorn': 'gunicorn',
            'openai': 'openai',
            'anthropic': 'anthropic'
        }
        
        requirements = []
        for imp in imports:
            if imp in package_map:
                requirements.append(package_map[imp])
            else:
                requirements.append(imp)
        
        return list(set(requirements))
    
    def create_bot(self, file_content, filename):
        """Yeni bot oluştur"""
        bot_id = f"bot_{int(time.time())}"
        bot_dir = os.path.join('uploads', bot_id)
        os.makedirs(bot_dir, exist_ok=True)
        
        bot_path = os.path.join(bot_dir, filename)
        with open(bot_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        requirements = self.detect_requirements(bot_path)
        
        self.bots[bot_id] = {
            'id': bot_id,
            'name': filename,
            'path': bot_path,
            'dir': bot_dir,
            'requirements': requirements,
            'status': 'created',
            'pid': None,
            'log': os.path.join('logs', f'{bot_id}.log'),
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        self.save_state()
        return bot_id, requirements
    
    def install_requirements(self, bot_id):
        """Paketleri yükle"""
        bot = self.bots.get(bot_id)
        if not bot:
            return False, "Bot bulunamadı"
        
        if not bot['requirements']:
            return True, "Paket yok"
        
        try:
            for pkg in bot['requirements']:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', pkg],
                    capture_output=True,
                    timeout=120
                )
            return True, "Paketler yüklendi"
        except Exception as e:
            return False, f"Hata: {str(e)}"
    
    def start_bot(self, bot_id):
        """Botu başlat"""
        bot = self.bots.get(bot_id)
        if not bot:
            return False, "Bot bulunamadı"
        
        if bot['status'] == 'running':
            return False, "Bot zaten çalışıyor"
        
        try:
            # Paketleri yükle
            self.install_requirements(bot_id)
            
            # Botu çalıştır
            log_file = bot['log']
            process = subprocess.Popen(
                [sys.executable, bot['path']],
                stdout=open(log_file, 'a'),
                stderr=subprocess.STDOUT,
                cwd=bot['dir']
            )
            
            bot['pid'] = process.pid
            bot['status'] = 'running'
            bot['start_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self.save_state()
            
            return True, f"Bot başlatıldı (PID: {process.pid})"
        except Exception as e:
            return False, f"Hata: {str(e)}"
    
    def stop_bot(self, bot_id):
        """Botu durdur"""
        bot = self.bots.get(bot_id)
        if not bot:
            return False, "Bot bulunamadı"
        
        if bot['status'] != 'running':
            return False, "Bot çalışmıyor"
        
        try:
            import signal
            os.kill(bot['pid'], signal.SIGTERM)
            bot['status'] = 'stopped'
            bot['pid'] = None
            self.save_state()
            return True, "Bot durduruldu"
        except Exception as e:
            return False, f"Hata: {str(e)}"
    
    def delete_bot(self, bot_id):
        """Botu sil"""
        bot = self.bots.get(bot_id)
        if not bot:
            return False, "Bot bulunamadı"
        
        if bot['status'] == 'running':
            self.stop_bot(bot_id)
        
        shutil.rmtree(bot['dir'], ignore_errors=True)
        if os.path.exists(bot['log']):
            os.remove(bot['log'])
        
        del self.bots[bot_id]
        self.save_state()
        return True, "Bot silindi"
    
    def get_logs(self, bot_id, lines=100):
        """Bot loglarını getir"""
        bot = self.bots.get(bot_id)
        if not bot:
            return "Bot bulunamadı"
        
        if not os.path.exists(bot['log']):
            return "Log dosyası yok"
        
        try:
            with open(bot['log'], 'r', encoding='utf-8') as f:
                logs = f.readlines()
                return ''.join(logs[-lines:]) if logs else "Log boş"
        except:
            return "Log okunamadı"

manager = BotManager()

# === ROTALAR ===
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya gerekli'}), 400
    
    file = request.files['file']
    if not file.filename.endswith('.py'):
        return jsonify({'error': 'Sadece .py dosyaları'}), 400
    
    content = file.read().decode('utf-8')
    filename = file.filename
    
    bot_id, requirements = manager.create_bot(content, filename)
    
    return jsonify({
        'success': True,
        'bot_id': bot_id,
        'requirements': requirements,
        'message': 'Bot oluşturuldu!'
    })

@app.route('/api/bots', methods=['GET'])
def list_bots():
    return jsonify(list(manager.bots.values()))

@app.route('/api/bots/<bot_id>/start', methods=['POST'])
def start_bot(bot_id):
    success, message = manager.start_bot(bot_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/bots/<bot_id>/stop', methods=['POST'])
def stop_bot(bot_id):
    success, message = manager.stop_bot(bot_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/bots/<bot_id>/logs', methods=['GET'])
def get_logs(bot_id):
    lines = request.args.get('lines', 100, type=int)
    logs = manager.get_logs(bot_id, lines)
    return jsonify({'logs': logs})

@app.route('/api/bots/<bot_id>', methods=['DELETE'])
def delete_bot(bot_id):
    success, message = manager.delete_bot(bot_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/system', methods=['GET'])
def system():
    import psutil
    return jsonify({
        'cpu': psutil.cpu_percent(),
        'memory': psutil.virtual_memory()._asdict(),
        'bots': len(manager.bots),
        'running': sum(1 for b in manager.bots.values() if b['status'] == 'running')
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
