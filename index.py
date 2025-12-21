import os
import random
import string
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key-premium-99")

# --- ডাটাবেস কনফিগারেশন ---
# ভার্সেল এনভায়রনমেন্ট থেকে MONGO_URI নিবে
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
db = client['premium_url_bot']
urls_col = db['urls']
settings_col = db['settings']

def get_settings():
    settings = settings_col.find_one()
    if not settings:
        default_settings = {
            "site_name": "Premium Shortener",
            "steps": 2,
            "timer_seconds": 10,
            "admin_password": generate_password_hash("admin123"),
            "api_key": ''.join(random.choices(string.ascii_lowercase + string.digits, k=40)),
            "popunder": "",
            "banner": "<!-- Banner Ad Code -->",
            "social_bar": "",
            "native": "",
            "direct_link": "https://www.google.com", 
            "direct_click_limit": 1 
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

def is_logged_in(): 
    return session.get('logged_in')

# --- ১. প্রফেশনাল এপিআই ---
@app.route('/api')
def api_system():
    settings = get_settings()
    api_token = request.args.get('api')
    long_url = request.args.get('url')
    alias = request.args.get('alias')
    res_format = request.args.get('format', 'json').lower()
    ad_type = request.args.get('type', '1')

    if not api_token or api_token != settings['api_key']:
        return jsonify({"status": "error", "message": "Invalid API Token"}) if res_format != 'text' else "Error: Invalid Token"
    
    if not long_url:
        return jsonify({"status": "error", "message": "Missing URL parameter"}) if res_format != 'text' else "Error: Missing URL"

    short_code = alias if alias else ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    
    if alias and urls_col.find_one({"short_code": alias}):
        return jsonify({"status": "error", "message": "Alias already exists"}) if res_format != 'text' else "Error: Alias exists"

    urls_col.insert_one({"long_url": long_url, "short_code": short_code, "clicks": 0, "type": ad_type})
    shortened_url = request.host_url + short_code
    
    if res_format == 'text': return shortened_url
    return jsonify({"status": "success", "shortenedUrl": shortened_url})

# --- ২. মেইন ইউজার ইন্টারফেস ---
@app.route('/')
def index():
    settings = get_settings()
    return render_template_string(f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <title>{settings['site_name']}</title>
        <style>
            body {{ background: #0f172a; color: white; }}
            .premium-card {{ background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}
        </style>
    </head>
    <body class="flex flex-col min-h-screen">
        <nav class="p-6 flex justify-between items-center max-w-7xl mx-auto w-full">
            <h1 class="text-3xl font-black text-cyan-400 italic">{settings['site_name']}</h1>
            <a href="/admin" class="bg-blue-600 px-6 py-2 rounded-full text-sm font-bold shadow-lg shadow-blue-500/20">Admin</a>
        </nav>
        <main class="flex-1 flex flex-col items-center justify-center px-4">
            <h1 class="text-5xl md:text-7xl font-black mb-4 text-center">Shorten & <span class="text-cyan-400">Earn.</span></h1>
            <div class="premium-card p-2 rounded-3xl w-full max-w-3xl">
                <form action="/shorten" method="POST" class="flex flex-col md:flex-row gap-2">
                    <input type="url" name="long_url" placeholder="Enter your long URL here..." required class="flex-1 bg-transparent p-5 rounded-2xl outline-none text-white text-lg">
                    <button type="submit" class="bg-cyan-500 text-slate-900 px-10 py-5 rounded-2xl font-black text-lg">SHORTEN</button>
                </form>
            </div>
        </main>
    </body>
    </html>
    ''')

# --- ৩. লিঙ্ক শর্ট রেজাল্ট ---
@app.route('/shorten', methods=['POST'])
def web_shorten():
    long_url = request.form.get('long_url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "type": "1"})
    final_url = request.host_url + sc
    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 flex items-center justify-center min-h-screen p-4 font-sans text-white">
        <div class="bg-slate-800 p-10 rounded-[40px] shadow-2xl text-center max-w-lg w-full border border-slate-700">
            <h2 class="text-3xl font-black mb-2">Link Ready!</h2>
            <input id="shortUrl" value="{final_url}" readonly class="w-full bg-slate-900 p-5 rounded-2xl border border-slate-700 text-cyan-400 font-bold text-center mb-6">
            <button onclick="copyLink()" id="copyBtn" class="w-full bg-cyan-500 text-slate-900 py-5 rounded-2xl font-black text-xl">COPY LINK</button>
            <a href="/" class="block mt-6 text-slate-500 font-bold">Back to Home</a>
        </div>
        <script>
            function copyLink() {{
                var copyText = document.getElementById("shortUrl");
                copyText.select();
                navigator.clipboard.writeText(copyText.value);
                document.getElementById("copyBtn").innerText = "COPIED!";
            }}
        </script>
    </body></html>
    ''')

# --- ৪. প্রিমিয়াম এডমিন ড্যাশবোর্ড ---
@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    total_urls = urls_col.count_documents({})
    total_clicks_res = list(urls_col.aggregate([{"$group": {"_id": None, "total": {"$sum": "$clicks"}}}]))
    clicks = total_clicks_res[0]['total'] if total_clicks_res else 0
    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-50 p-6 md:p-12">
        <div class="max-w-6xl mx-auto flex justify-between mb-8">
            <h1 class="text-4xl font-black">Admin Pro</h1>
            <div class="flex gap-4">
                <div class="bg-white p-4 rounded-xl border">Links: {total_urls}</div>
                <div class="bg-white p-4 rounded-xl border">Clicks: {clicks}</div>
                <a href="/logout" class="bg-red-500 text-white p-4 rounded-xl font-bold">Logout</a>
            </div>
        </div>
        <form action="/admin/update" method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-6xl mx-auto">
            <div class="bg-white p-8 rounded-[40px] border space-y-4">
                <h3 class="text-xl font-bold mb-4">API & Security</h3>
                <input type="text" name="api_key" value="{settings['api_key']}" class="w-full bg-gray-50 p-4 rounded-xl border">
                <div class="grid grid-cols-2 gap-4">
                    <input type="number" name="steps" value="{settings['steps']}" class="p-4 bg-gray-50 border rounded-xl">
                    <input type="number" name="timer_seconds" value="{settings['timer_seconds']}" class="p-4 bg-gray-50 border rounded-xl">
                </div>
                <input type="url" name="direct_link" value="{settings.get('direct_link', '')}" placeholder="Direct Link" class="w-full bg-blue-50 p-4 border rounded-xl">
                <input type="number" name="direct_click_limit" value="{settings.get('direct_click_limit', 1)}" class="w-full bg-blue-50 p-4 border rounded-xl">
            </div>
            <div class="bg-white p-8 rounded-[40px] border space-y-4">
                <h3 class="text-xl font-bold mb-4">Ad Scripts</h3>
                <textarea name="popunder" class="w-full bg-gray-50 p-4 h-24 border rounded-xl">{settings['popunder']}</textarea>
                <textarea name="banner" class="w-full bg-gray-50 p-4 h-24 border rounded-xl">{settings['banner']}</textarea>
                <textarea name="social_bar" class="w-full bg-gray-50 p-4 h-24 border rounded-xl">{settings['social_bar']}</textarea>
            </div>
            <button class="md:col-span-2 bg-slate-900 text-white p-6 rounded-3xl font-black text-xl">SAVE</button>
        </form>
    </body></html>
    ''')

# --- ৫. রিডাইরেক্ট লজিক ---
@app.route('/<short_code>')
def handle_ad_steps(short_code):
    step = int(request.args.get('step', 1))
    settings = get_settings()
    url_data = urls_col.find_one({"short_code": short_code})
    if not url_data: return "404 - Not Found", 404
    if url_data.get('type') == '0' or step > settings['steps']:
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        return redirect(url_data['long_url'])
    return render_template_string(f'''
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script>{settings['popunder']}</head>
    <body class="bg-gray-50 flex flex-col items-center justify-center min-h-screen p-4">
        <div class="bg-white p-10 rounded-[50px] shadow-2xl text-center max-w-md w-full border">
            <h2 class="text-2xl font-black mb-2 uppercase italic">STEP {step} OF {settings['steps']}</h2>
            <div id="timer" class="text-7xl font-mono font-bold text-blue-600 mb-8 bg-blue-50 px-10 py-6 rounded-3xl inline-block">{settings['timer_seconds']}</div>
            <button id="btn" onclick="handleClick()" class="hidden bg-blue-600 text-white px-12 py-5 rounded-full font-black text-xl w-full">PLEASE WAIT</button>
        </div>
        <script>
            let t = {settings['timer_seconds']};
            let clicksDone = 0; let limit = {settings.get('direct_click_limit', 1)}; let dLink = "{settings.get('direct_link', '')}";
            const timer = document.getElementById('timer'); const btn = document.getElementById('btn');
            const iv = setInterval(() => {{ t--; timer.innerText = t; if(t <= 0) {{ clearInterval(iv); timer.style.display = 'none'; btn.classList.remove('hidden'); updateBtn(); }} }}, 1000);
            function updateBtn() {{ if(clicksDone < limit && dLink !== "") btn.innerText = "CONTINUE ("+(clicksDone+1)+"/"+limit+")"; else btn.innerText = "FINAL CONTINUE"; }}
            function handleClick() {{ if(clicksDone < limit && dLink !== "") {{ window.open(dLink, '_blank'); clicksDone++; updateBtn(); }} else window.location.href = "/{short_code}?step={step + 1}"; }}
        </script>
        {settings['social_bar']}
    </body></html>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        return "Wrong Password!"
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh;"><form method="POST" style="background:#1e293b; padding:40px; border-radius:20px;"><input type="password" name="password" placeholder="Admin Password" style="padding:15px; border-radius:10px;"><button style="padding:15px; background:cyan; border:none; margin-left:10px;">Login</button></form></body>')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.post('/admin/update')
def update_settings():
    if not is_logged_in(): return redirect(url_for('login'))
    d = {
        "api_key": request.form.get('api_key'),
        "steps": int(request.form.get('steps', 2)),
        "timer_seconds": int(request.form.get('timer_seconds', 10)),
        "popunder": request.form.get('popunder'),
        "banner": request.form.get('banner'),
        "social_bar": request.form.get('social_bar'),
        "direct_link": request.form.get('direct_link'),
        "direct_click_limit": int(request.form.get('direct_click_limit', 1))
    }
    new_pass = request.form.get('new_password')
    if new_pass: d["admin_password"] = generate_password_hash(new_pass)
    settings_col.update_one({}, {"$set": d})
    return redirect(url_for('admin_panel'))

# ভার্সেলের জন্য এটি দরকার
app.debug = False
