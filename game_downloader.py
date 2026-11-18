import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import os
import re
import threading
import concurrent.futures

PORT = 8877
BASE_DIR = "/mnt/c/Users/sinyoabe/Downloads"
os.makedirs(BASE_DIR, exist_ok=True)

status_log = []
is_downloading = False

HTML_UI = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Offline Game Archiver (Port 8877)</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; max-width: 800px; margin: 40px auto; padding: 0 20px; }
        .card { background: #1e293b; padding: 24px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); margin-bottom: 20px; }
        h1 { margin-top: 0; color: #38bdf8; font-size: 1.5rem; }
        input[type="text"] { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; box-sizing: border-box; margin: 10px 0 16px; font-size: 1rem; }
        button { background: #0284c7; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 1rem; }
        button:hover { background: #0369a1; }
        button:disabled { background: #475569; cursor: not-allowed; }
        #log { background: #020617; color: #4ade80; font-family: monospace; padding: 16px; border-radius: 8px; height: 280px; overflow-y: auto; white-space: pre-wrap; font-size: 0.9rem; line-height: 1.4; }
        .game-list { list-style: none; padding: 0; }
        .game-list li { background: #0f172a; padding: 10px 14px; border-radius: 6px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
        .badge { background: #15803d; color: #dcfce7; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🎮 Universal HTML5 Offline Game Archiver</h1>
        <p>Mendukung Construct 2, Construct 3, CreateJS, & HTML5 Canvas (tersimpan ke <strong>Downloads</strong>):</p>
        <input type="text" id="gameUrl" placeholder="Contoh: https://www.safekidgames.com/solve-math/">
        <button id="btnStart" onclick="startDownload()">Download Game Penuh</button>
    </div>

    <div class="card">
        <h3>Log Proses Unduhan</h3>
        <div id="log">Siap menerima URL...</div>
    </div>

    <div class="card">
        <h3>Folder Game di Downloads (Siap Pindah ke Win 7)</h3>
        <ul class="game-list" id="gameList"></ul>
    </div>

    <script>
        function startDownload() {
            const url = document.getElementById('gameUrl').value.trim();
            if (!url) return alert('Masukkan URL game terlebih dahulu!');
            document.getElementById('btnStart').disabled = true;
            fetch('/start?url=' + encodeURIComponent(url));
        }

        setInterval(() => {
            fetch('/status').then(r => r.json()).then(data => {
                const logEl = document.getElementById('log');
                logEl.textContent = data.logs.join('\\n');
                logEl.scrollTop = logEl.scrollHeight;
                document.getElementById('btnStart').disabled = data.running;

                const listEl = document.getElementById('gameList');
                listEl.innerHTML = data.games.map(g => 
                    `<li><span>📁 <strong>${g}</strong></span><span class="badge">Siap Offline + Win 7</span></li>`
                ).join('') || '<li>Belum ada game diunduh.</li>';
            });
        }, 1000);
    </script>
</body>
</html>
"""

SERVER_PS1 = """$port = 8899
$gameDir = (Get-Location).Path
$parentDir = Split-Path -Parent $gameDir
$gameSlug = Split-Path -Leaf $gameDir
$targetUrl = "http://localhost:$port/$gameSlug/index.html"

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$port/")

try {
    $listener.Start()
} catch {
    # Jika server port 8899 sudah aktif dari game lain, langsung buka tab game baru
    Start-Process $targetUrl
    exit
}

Start-Process $targetUrl
Write-Host "Server Koleksi Game aktif di http://localhost:$port (Root: $parentDir)"
Write-Host "Jangan tutup jendela ini selama bermain."

while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    $relPath = [Uri]::UnescapeDataString($ctx.Request.Url.LocalPath.TrimStart('/'))
    if ([string]::IsNullOrEmpty($relPath)) {
        $ctx.Response.Redirect("/$gameSlug/index.html")
        $ctx.Response.Close()
        continue
    }
    $path = Join-Path $parentDir $relPath
    if (Test-Path $path -PathType Container) {
        $path = Join-Path $path 'index.html'
    }
    if (Test-Path $path -PathType Leaf) {
        $ext = [IO.Path]::GetExtension($path).ToLower()
        $mime = @{'.html'='text/html';'.js'='application/javascript';'.css'='text/css';'.png'='image/png';'.jpg'='image/jpeg';'.jpeg'='image/jpeg';'.gif'='image/gif';'.svg'='image/svg+xml';'.webp'='image/webp';'.ogg'='audio/ogg';'.mp3'='audio/mpeg';'.wav'='audio/wav';'.m4a'='audio/mp4';'.webm'='audio/webm';'.json'='application/json';'.wasm'='application/wasm';'.woff'='font/woff';'.woff2'='font/woff2';'.ttf'='font/ttf'}[$ext]
        if ($mime) { $ctx.Response.ContentType = $mime }
        $ctx.Response.Headers.Add('Cache-Control', 'no-store, no-cache, must-revalidate')
        $bytes = [IO.File]::ReadAllBytes($path)
        $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    } else {
        $ctx.Response.StatusCode = 404
    }
    $ctx.Response.Close()
}
"""

BAT_LAUNCHER = """@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "server.ps1"
"""

def log(msg):
    status_log.append(msg)
    print(msg)

def fetch_bytes(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read()

def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for i in obj:
            yield from walk_strings(i)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk_strings(v)

def resolve_game_url(input_url):
    if 'media.' in input_url or input_url.endswith('.html'):
        return input_url if input_url.endswith('.html') else input_url.rstrip('/') + '/index.html'
    
    log(f"[*] Mendeteksi halaman artikel: {input_url}")
    page_html = fetch_bytes(input_url).decode('utf-8', errors='ignore')
    
    matches = re.findall(r'(?:src|data-src)=["\'](https?://[^"\']+/(?:index\.html)?)["\']', page_html, re.IGNORECASE)
    for m in matches:
        if 'media.' in m or 'games' in m or 'cdn' in m:
            if not any(ad in m for ad in ['doubleclick', 'googlesyndication', 'facebook', 'youtube']):
                target = m if m.endswith('.html') else m.rstrip('/') + '/index.html'
                log(f"[+] Berhasil menemukan URL game asli: {target}")
                return target
                
    slug = input_url.rstrip('/').split('/')[-1]
    fallback = f"https://media.safekidgames.com/{slug}/index.html"
    log(f"[*] Mencoba jalur standar server media: {fallback}")
    return fallback

def download_game_worker(raw_url):
    global is_downloading
    is_downloading = True
    status_log.clear()
    try:
        target_url = resolve_game_url(raw_url)
        base_url = target_url.rsplit('/', 1)[0] + '/'
        game_name = target_url.rstrip('/').split('/')[-2]
        game_dir = os.path.join(BASE_DIR, game_name)
        os.makedirs(game_dir, exist_ok=True)

        log(f"[*] Memulai pengarsipan game: {game_name}")

        index_bytes = fetch_bytes(target_url)
        with open(os.path.join(game_dir, "index.html"), "wb") as f:
            f.write(index_bytes)
        index_text = index_bytes.decode('utf-8', errors='ignore')

        core_files = {
            "data.js", "data.json", "c2runtime.js", "appmanifest.json", "offline.json", "sw.js",
            "style.css", "workermain.js", "xmldom.js", "xpath.js", "box2d.asm.js", "box2d.wasm.js", "box2d.wasm",
            "scripts/main.js", "scripts/c3runtime.js", "scripts/supportcheck.js", "scripts/modernjscheck.js",
            "scripts/offlineclient.js", "scripts/register-sw.js", "scripts/dispatchworker.js",
            "scripts/jobworker.js", "scripts/objRefTable.js", "scripts/project/scriptsInEvents.js", "scripts/project/main.js"
        }
        for ref in re.findall(r'(?:src|href)=["\']([^"\']+\.(?:js|css|json|wasm|png|ico))["\']', index_text):
            if not ref.startswith(('http', '//')):
                core_files.add(ref.lstrip('./'))

        for cf in sorted(core_files):
            try:
                content = fetch_bytes(base_url + urllib.parse.quote(cf))
                if len(content) > 10:
                    out_p = os.path.join(game_dir, cf)
                    os.makedirs(os.path.dirname(out_p), exist_ok=True)
                    with open(out_p, "wb") as f:
                        f.write(content)
                    log(f"[+] File inti terunduh: {cf}")
            except Exception:
                pass

        asset_cands = set()
        # 1. Cek offline.json & appmanifest.json
        for mf in ("offline.json", "appmanifest.json"):
            mp = os.path.join(game_dir, mf)
            if os.path.exists(mp):
                try:
                    mdata = json.load(open(mp, encoding="utf-8-sig"))
                    for fitem in mdata.get("fileList", []):
                        asset_cands.add(fitem.lstrip('./'))
                    for s in walk_strings(mdata):
                        if "/" in s and "." in s and not s.startswith("http"):
                            asset_cands.add(s.lstrip('./'))
                except Exception:
                    pass

        # 2. Parse data.js atau data.json (Construct 2 / 3)
        data_obj = None
        for df in ("data.js", "data.json"):
            dp = os.path.join(game_dir, df)
            if os.path.exists(dp):
                data_obj = json.load(open(dp, encoding="utf-8-sig"))
                log(f"[*] Terdeteksi struktur {df} ({'Construct 3' if df == 'data.json' else 'Construct 2'})")
                break

        if data_obj:
            for s in set(walk_strings(data_obj)):
                if s.startswith(("images/", "media/", "icons/", "fonts/")) and "." in s:
                    asset_cands.add(s)
                elif s and "/" not in s and len(s) < 60:
                    for name in {s.lower(), s}:
                        for ext in (".ogg", ".m4a", ".webm"):
                            asset_cands.add(f"media/{name}{ext}")
                        for ext in (".png", ".jpg", ".webp"):
                            asset_cands.add(f"images/{name}{ext}")

        # 3. Universal HTML5 Scanner: Pindai semua file JS/CSS/HTML lokal untuk mencari aset
        log("[*] Memindai kode skrip JS/CSS untuk menemukan referensi aset tambahan...")
        ext_pattern = r'["\'\(]([a-zA-Z0-9_ ./-]+\.(?:png|jpg|jpeg|gif|svg|webp|ogg|mp3|wav|m4a|webm|json|xml|wasm|js|ttf|woff|woff2))["\'\)]'
        for root, _, files in os.walk(game_dir):
            for fname in files:
                if fname.endswith(('.js', '.css', '.html')):
                    fpath = os.path.join(root, fname)
                    try:
                        txt = open(fpath, encoding="utf-8", errors="ignore").read()
                        for m in re.findall(ext_pattern, txt):
                            clean_m = m.strip().lstrip('./')
                            if not clean_m.startswith(('http', '//', 'data:')) and len(clean_m) < 120:
                                asset_cands.add(clean_m)
                                # Jika referensi relatif terhadap subfolder (misal ../assets/ atau assets/ di dalam js/)
                                rel_dir = os.path.relpath(root, game_dir)
                                if rel_dir != '.':
                                    joined = os.path.normpath(os.path.join(rel_dir, clean_m)).replace('\\', '/')
                                    if not joined.startswith('..'):
                                        asset_cands.add(joined)
                    except Exception:
                        pass

        # Tambahkan pasangan ekstensi audio alternatif (.mp3 <-> .ogg) untuk game CreateJS
        for ac in list(asset_cands):
            if ac.endswith(".ogg"):
                asset_cands.add(ac[:-4] + ".mp3")
            elif ac.endswith(".mp3"):
                asset_cands.add(ac[:-4] + ".ogg")

        log(f"[*] Mengecek {len(asset_cands)} kandidat aset (gambar, audio, skrip, font)...")

        def dl_asset(rel_path):
            out_file = os.path.join(game_dir, rel_path)
            if os.path.exists(out_file) and os.path.getsize(out_file) > 10:
                return None
            url = base_url + urllib.parse.quote(rel_path)
            try:
                content = fetch_bytes(url)
                if len(content) > 10:
                    os.makedirs(os.path.dirname(out_file), exist_ok=True)
                    with open(out_file, "wb") as f:
                        f.write(content)
                    return rel_path
            except Exception:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
            for res in ex.map(dl_asset, sorted(asset_cands)):
                if res:
                    log(f"  [OK] {res}")

        with open(os.path.join(game_dir, "server.ps1"), "w", encoding="utf-8") as f:
            f.write(SERVER_PS1)
        with open(os.path.join(game_dir, "Mainkan_Game.bat"), "w", encoding="utf-8") as f:
            f.write(BAT_LAUNCHER)

        log(f"[✓] SELESAI! Folder '{game_name}' tersimpan di Downloads & siap untuk Windows 7.")
    except Exception as e:
        log(f"[!] Terjadi kesalahan: {e}")
    finally:
        is_downloading = False

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_UI.encode('utf-8'))
        elif parsed.path == '/start':
            qs = urllib.parse.parse_qs(parsed.query)
            url = qs.get('url', [''])[0]
            if url and not is_downloading:
                threading.Thread(target=download_game_worker, args=(url,), daemon=True).start()
            self.send_response(200)
            self.end_headers()
        elif parsed.path == '/status':
            games = [d for d in sorted(os.listdir(BASE_DIR)) if os.path.isfile(os.path.join(BASE_DIR, d, "Mainkan_Game.bat"))]
            payload = json.dumps({"logs": status_log, "running": is_downloading, "games": games})
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(payload.encode('utf-8'))

print(f"Web UI aktif (Universal HTML5)! Akses: http://localhost:{PORT}")
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
