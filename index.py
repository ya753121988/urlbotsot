import os
import random
import string
import json
import requests
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from collections import Counter

app = Flask(__name__)

# --- [VERCEL OPTIMIZED CONFIG] ---
# Vercel-এ সেশন স্থায়ী করার জন্য নিচের কনফিগারেশনগুলো জরুরি
app.secret_key = os.environ.get("SECRET_KEY", "premium-super-secret-key-2025")
app.config['SESSION_COOKIE_NAME'] = 'admin_session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS নিশ্চিত করে
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

MONGO_URI = os.environ.get("MONGO_URI") 
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8469682967:AAEWrNWBWjiYT3_L47Xe_byORfD6IIsFD34")

# --- ডাটাবেস কানেকশন ---
if not MONGO_URI:
    print("Warning: MONGO_URI is not set!")
    
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
db = client['premium_url_bot']
urls_col = db['urls']
settings_col = db['settings']
channels_col = db['channels']
otp_col = db['otps']
direct_links_col = db['direct_links']

# --- ডাটাবেস ইনডেক্সিং ---
try:
    urls_col.create_index("short_code", unique=True)
    urls_col.create_index("created_at")
except:
    pass

# --- থিম কালার ম্যাপ ---
COLOR_MAP = {
    "red": {"text": "text-red-500", "bg": "bg-red-600", "border": "border-red-500", "hover": "hover:bg-red-700", "light_bg": "bg-red-50"},
    "blue": {"text": "text-blue-500", "bg": "bg-blue-600", "border": "border-blue-500", "hover": "hover:bg-blue-700", "light_bg": "bg-blue-50"},
    "sky": {"text": "text-sky-400", "bg": "bg-sky-500", "border": "border-sky-400", "hover": "hover:bg-sky-600", "light_bg": "bg-sky-50"},
    "green": {"text": "text-green-500", "bg": "bg-green-600", "border": "border-green-500", "hover": "hover:bg-green-700", "light_bg": "bg-green-50"},
    "purple": {"text": "text-purple-500", "bg": "bg-purple-600", "border": "border-purple-500", "hover": "hover:bg-purple-700", "light_bg": "bg-purple-50"},
    "slate": {"text": "text-slate-400", "bg": "bg-slate-700", "border": "border-slate-500", "hover": "hover:bg-slate-800", "light_bg": "bg-slate-50"}
}

def get_settings():
    settings = settings_col.find_one()
    if not settings:
        default_settings = {
            "site_name": "Premium URL Shortener",
            "admin_telegram_id": "", 
            "steps": 2,
            "timer_seconds": 10,
            "admin_password": generate_password_hash("admin123"),
            "api_key": ''.join(random.choices(string.ascii_lowercase + string.digits, k=40)),
            "popunder": "", "banner": "", "social_bar": "", "native": "",
            "direct_click_limit": 1,
            "main_theme": "sky", "step_theme": "blue",
            "template_style": "standard" 
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

def is_logged_in():
    return session.get('logged_in') == True

# --- Geo & Device Helper ---
def get_user_country(ip):
    try:
        if not ip or ip == '127.0.0.1': return "US"
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=2)
        data = response.json()
        if data.get('status') == 'success':
            return data.get("countryCode", "US")
    except:
        pass
    return "Global"

def get_user_device():
    ua = request.user_agent.string.lower()
    if 'android' in ua or 'iphone' in ua or 'ipad' in ua or 'mobile' in ua:
        return 'Mobile'
    return 'Desktop'

def get_channels_html(theme_color="sky"):
    channels = list(channels_col.find())
    if not channels: return ""
    c = COLOR_MAP.get(theme_color, COLOR_MAP['sky'])
    html = f'''<div class="w-full max-w-5xl mx-auto mt-8 mb-8 p-6 rounded-[30px] border border-white/10 glass shadow-xl">
        <h3 class="text-center {c['text']} font-black mb-6 uppercase tracking-[0.2em] text-sm">Sponsored Channels</h3>
        <div class="flex flex-col items-center gap-6">'''
    for ch in channels:
        html += f'''<a href="{ch['link']}" target="_blank" class="flex flex-col items-center gap-2 group transition-transform hover:scale-105 w-full">
            <img src="{ch['logo']}" class="w-full max-w-md h-auto object-cover border border-white/10 rounded-xl group-hover:border-white/30 shadow-lg transition">
            <span class="text-xs font-bold text-gray-300 uppercase tracking-widest bg-white/5 px-4 py-1 rounded-full">{ch.get('name', 'Join Now')}</span>
        </a>'''
    return html + '</div></div>'

# --- API ---
@app.route('/api')
def api_system():
    settings = get_settings()
    raw_token = request.args.get('api') or request.args.get('api_key') or request.args.get('key')
    api_token = raw_token.strip() if raw_token else None
    long_url = request.args.get('url')
    alias = request.args.get('alias')
    res_format = request.args.get('format', 'json').lower()
    
    if not api_token or api_token != settings['api_key'].strip():
        return jsonify({"status": "error", "message": "Invalid API Token"}) if res_format != 'text' else "Error: Invalid Token"
    
    if not long_url:
        return jsonify({"status": "error", "message": "Missing URL"}) if res_format != 'text' else "Error: Missing URL"

    short_code = alias if alias else ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": short_code, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "api"})
    shortened_url = request.host_url + short_code
    return shortened_url if res_format == 'text' else jsonify({"status": "success", "shortenedUrl": shortened_url})

# --- হোম পেজ ---
@app.route('/')
def index():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    return render_template_string(f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script><title>{settings['site_name']}</title><style>body {{ background: #0f172a; color: white; }} .glass {{ background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}</style></head><body class="min-h-screen flex flex-col items-center justify-center p-6 text-center"><h1 class="text-6xl md:text-8xl font-black mb-4 {c['text']} italic tracking-tighter uppercase">{settings['site_name']}</h1><p class="text-gray-400 mb-12 text-xl font-bold uppercase tracking-widest">Enterprise Link Management</p><div class="glass p-5 rounded-[40px] w-full max-w-3xl shadow-3xl mb-8"><form action="/shorten" method="POST" class="flex flex-col md:flex-row gap-4"><input type="url" name="long_url" placeholder="PASTE LINK HERE..." required class="flex-1 bg-transparent p-5 outline-none text-white text-xl font-bold placeholder:text-slate-600"><button type="submit" class="{c['bg']} text-white px-10 py-5 rounded-[30px] font-black text-xl hover:scale-105 transition uppercase shadow-xl">Shorten</button></form></div>{get_channels_html(settings.get('main_theme', 'sky'))}</body></html>''')

@app.route('/shorten', methods=['POST'])
def web_shorten():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    long_url = request.form.get('long_url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "web"})
    return render_template_string(f'''<html><head><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-slate-900 flex flex-col items-center justify-center min-h-screen p-4 text-white"><div class="bg-slate-800 p-12 rounded-[50px] shadow-2xl text-center max-w-xl w-full border border-slate-700"><h2 class="text-4xl font-black mb-8 {c['text']} uppercase italic">Success!</h2><input id="shortUrl" value="{request.host_url + sc}" readonly class="w-full bg-slate-900 p-6 rounded-2xl border border-slate-700 {c['text']} font-bold text-center mb-8 text-xl"><button onclick="copyLink()" id="copyBtn" class="w-full {c['bg']} text-white py-6 rounded-[30px] font-black text-2xl uppercase tracking-tighter transition shadow-xl">COPY LINK</button><a href="/" class="block mt-8 text-slate-500 font-bold uppercase text-xs hover:text-white transition">Create New</a></div><script>function copyLink() {{ var copyText = document.getElementById("shortUrl"); copyText.select(); navigator.clipboard.writeText(copyText.value); document.getElementById("copyBtn").innerText = "COPIED!"; }}</script></body></html>''')

# --- এডমিন প্যানেল ---
@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    all_urls = list(urls_col.find().sort("_id", -1))
    total_clicks = sum(u.get('clicks', 0) for u in all_urls)
    channels = list(channels_col.find())
    direct_links = list(direct_links_col.find())
    
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    date_counts = Counter([u['created_at'].split(' ')[0] for u in all_urls])
    chart_data = [date_counts.get(d, 0) for d in dates]
    theme_options = sorted(COLOR_MAP.keys())

    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&display=swap" rel="stylesheet">
    <style> body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: #f1f5f9; }} .active-tab {{ background: #0f172a !important; color: white !important; }} .tab-content {{ display: none; }} .tab-content.active {{ display: block; }} </style>
    </head>
    <body class="flex flex-col lg:flex-row min-h-screen">
        <div class="lg:w-72 bg-white border-r p-6 flex flex-col shadow-sm">
            <h2 class="text-2xl font-black text-slate-900 mb-10 italic tracking-tighter">ADMIN <span class="text-blue-600">PRO</span></h2>
            <nav class="space-y-2 flex-1">
                <button onclick="showTab('overview')" id="tab-overview-btn" class="w-full text-left p-4 rounded-xl font-bold text-slate-500 hover:bg-slate-50 transition active-tab">📊 Analytics</button>
                <button onclick="showTab('config')" id="tab-config-btn" class="w-full text-left p-4 rounded-xl font-bold text-slate-500 hover:bg-slate-50 transition">⚙️ Settings & UI</button>
                <button onclick="showTab('bulk')" id="tab-bulk-btn" class="w-full text-left p-4 rounded-xl font-bold text-slate-500 hover:bg-slate-50 transition">🚀 Bulk Tools</button>
                <button onclick="showTab('links')" id="tab-links-btn" class="w-full text-left p-4 rounded-xl font-bold text-slate-500 hover:bg-slate-50 transition">🔗 Direct Links</button>
            </nav>
            <a href="/logout" class="mt-8 p-4 bg-red-50 text-red-600 rounded-xl text-center font-bold text-xs hover:bg-red-100 transition">Log Out</a>
        </div>

        <div class="flex-1 p-6 lg:p-10 overflow-y-auto">
            <div id="overview" class="tab-content active space-y-8">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-white p-8 rounded-[30px] shadow-sm border border-slate-100">
                        <p class="text-slate-400 text-xs font-bold uppercase">Total Links</p>
                        <h3 class="text-4xl font-black text-slate-900">{len(all_urls)}</h3>
                    </div>
                    <div class="bg-blue-600 p-8 rounded-[30px] shadow-lg text-white">
                        <p class="text-blue-200 text-xs font-bold uppercase">Total Clicks</p>
                        <h3 class="text-4xl font-black">{total_clicks}</h3>
                    </div>
                </div>
                <div class="bg-white p-8 rounded-[30px] shadow-sm border border-slate-100">
                    <h4 class="font-bold text-slate-700 mb-4 text-xs uppercase">Growth (7 Days)</h4>
                    <canvas id="linkChart" height="70"></canvas>
                </div>
            </div>

            <div id="config" class="tab-content space-y-6">
                <form action="/admin/update" method="POST" class="grid grid-cols-1 xl:grid-cols-2 gap-8">
                    <div class="bg-white p-8 rounded-[30px] shadow-sm space-y-5 border border-slate-100">
                        <h4 class="font-black text-lg text-slate-900">🎨 Design & Templates</h4>
                        <div class="p-4 bg-purple-50 rounded-2xl border border-purple-100">
                            <label class="text-xs font-bold text-purple-600 mb-2 block uppercase">Ad Page Template</label>
                            <select name="template_style" class="w-full p-3 bg-white rounded-xl font-bold text-slate-700 border-none outline-none">
                                <option value="standard" {"selected" if settings.get("template_style")=="standard" else ""}>Standard Timer</option>
                                <option value="video" {"selected" if settings.get("template_style")=="video" else ""}>Fake Video Player</option>
                                <option value="download" {"selected" if settings.get("template_style")=="download" else ""}>File Download Style</option>
                            </select>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="text-[10px] font-bold">MAIN THEME</label>
                            <select name="main_theme" class="w-full p-3 bg-slate-50 rounded-xl font-bold text-sm">{"".join([f'<option value="{o}" {"selected" if settings.get("main_theme")==o else ""}>{o.upper()}</option>' for o in theme_options])}</select></div>
                            <div><label class="text-[10px] font-bold">STEP THEME</label>
                            <select name="step_theme" class="w-full p-3 bg-slate-50 rounded-xl font-bold text-sm">{"".join([f'<option value="{o}" {"selected" if settings.get("step_theme")==o else ""}>{o.upper()}</option>' for o in theme_options])}</select></div>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <input type="number" name="steps" value="{settings['steps']}" class="p-3 bg-slate-50 rounded-xl text-sm font-bold" placeholder="Steps">
                            <input type="number" name="timer_seconds" value="{settings['timer_seconds']}" class="p-3 bg-slate-50 rounded-xl text-sm font-bold" placeholder="Seconds">
                        </div>
                        <input type="text" name="site_name" value="{settings['site_name']}" class="w-full p-3 bg-slate-50 rounded-xl font-bold text-sm" placeholder="Site Name">
                    </div>

                    <div class="bg-white p-8 rounded-[30px] shadow-sm space-y-4 border border-slate-100">
                        <h4 class="font-black text-lg text-emerald-600">💰 Monetization Scripts</h4>
                        <input type="number" name="direct_click_limit" value="{settings.get('direct_click_limit', 1)}" class="w-full p-3 bg-blue-50 rounded-xl font-bold text-sm" placeholder="Clicks Limit">
                        <textarea name="popunder" placeholder="Popunder JS" class="w-full h-16 p-3 bg-slate-50 rounded-xl text-xs font-mono">{settings['popunder']}</textarea>
                        <textarea name="banner" placeholder="Banner JS" class="w-full h-16 p-3 bg-slate-50 rounded-xl text-xs font-mono">{settings['banner']}</textarea>
                        <textarea name="social_bar" placeholder="Social Bar JS" class="w-full h-16 p-3 bg-slate-50 rounded-xl text-xs font-mono">{settings['social_bar']}</textarea>
                        <textarea name="native" placeholder="Native JS" class="w-full h-16 p-3 bg-slate-50 rounded-xl text-xs font-mono">{settings['native']}</textarea>
                        <button class="w-full bg-slate-900 text-white p-4 rounded-2xl font-black shadow-xl">Save All</button>
                    </div>
                </form>
            </div>

            <div id="bulk" class="tab-content space-y-6">
                <div class="bg-white p-10 rounded-[40px] shadow-sm">
                    <h4 class="font-black text-xl mb-4">🚀 Bulk Shorten</h4>
                    <form action="/admin/bulk_shorten" method="POST">
                        <textarea name="bulk_urls" class="w-full h-64 p-5 bg-slate-50 rounded-2xl font-mono text-xs border-none outline-none mb-4" placeholder="One URL per line..."></textarea>
                        <button class="bg-blue-600 text-white px-8 py-4 rounded-2xl font-black uppercase">Shorten All</button>
                    </form>
                </div>
            </div>

            <div id="links" class="tab-content space-y-6">
                 <div class="bg-white p-10 rounded-[40px] shadow-sm border border-slate-100">
                     <h4 class="font-black text-xl text-purple-600 mb-4">🔗 Smart Direct Links</h4>
                     <form action="/admin/add_direct_link" method="POST" class="flex flex-col md:flex-row gap-4 mb-8">
                        <input type="url" name="direct_link_url" placeholder="Direct Link..." required class="flex-[2] p-4 bg-purple-50 rounded-2xl border-none font-bold text-sm">
                        <select name="country" class="flex-1 p-4 bg-purple-50 rounded-2xl font-bold text-sm">
                            <option value="Global">🌍 Global</option>
                            <option value="US">🇺🇸 USA</option><option value="GB">🇬🇧 UK</option><option value="CA">🇨🇦 Canada</option><option value="IN">🇮🇳 India</option>
                        </select>
                        <select name="device" class="flex-1 p-4 bg-purple-50 rounded-2xl font-bold text-sm">
                            <option value="All">📱 All</option><option value="Mobile">📱 Mobile</option><option value="Desktop">💻 Desktop</option>
                        </select>
                        <button class="bg-purple-600 text-white px-6 py-4 rounded-2xl font-black">Add</button>
                     </form>
                     <div class="space-y-3">
                        {"".join([f'<div class="flex items-center justify-between bg-slate-50 p-4 rounded-2xl border border-slate-100"><span class="text-xs font-mono truncate">{dl["url"]}</span><a href="/admin/delete_direct_link/{dl["_id"]}" class="bg-red-100 text-red-600 px-3 py-2 rounded-xl text-[10px] font-black">DEL</a></div>' for dl in direct_links])}
                     </div>
                </div>
            </div>
        </div>

        <script>
            function showTab(tabId) {{
                document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('nav button').forEach(b => b.classList.remove('active-tab'));
                document.getElementById(tabId).classList.add('active');
                document.getElementById('tab-' + tabId + '-btn').classList.add('active-tab');
            }}
            const ctx = document.getElementById('linkChart').getContext('2d');
            new Chart(ctx, {{ type: 'line', data: {{ labels: {json.dumps(dates)}, datasets: [{{ label: 'Links', data: {json.dumps(chart_data)}, borderColor: '#2563eb', tension: 0.4 }}] }} }});
        </script>
    </body></html>
    ''')

# --- রাউটস হ্যান্ডলারস ---
@app.route('/admin/bulk_shorten', methods=['POST'])
def bulk_shorten():
    if not is_logged_in(): return redirect(url_for('login'))
    raw_text = request.form.get('bulk_urls', '')
    urls = [u.strip() for u in raw_text.split('\n') if u.strip()]
    if urls:
        new_entries = [{"long_url": u, "short_code": ''.join(random.choices(string.ascii_letters + string.digits, k=6)), "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "bulk"} for u in urls]
        urls_col.insert_many(new_entries)
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_direct_link', methods=['POST'])
def add_direct_link():
    if not is_logged_in(): return redirect(url_for('login'))
    url = request.form.get('direct_link_url')
    country = request.form.get('country', 'Global')
    device = request.form.get('device', 'All')
    if url: direct_links_col.insert_one({"url": url, "country": country, "device": device, "created_at": datetime.now()})
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_direct_link/<id>')
def delete_direct_link(id):
    if not is_logged_in(): return redirect(url_for('login'))
    direct_links_col.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('admin_panel'))

@app.post('/admin/update')
def update_settings():
    if not is_logged_in(): return redirect(url_for('login'))
    d = {
        "site_name": request.form.get('site_name'),
        "steps": int(request.form.get('steps', 2)),
        "timer_seconds": int(request.form.get('timer_seconds', 10)),
        "popunder": request.form.get('popunder'),
        "banner": request.form.get('banner'),
        "social_bar": request.form.get('social_bar'),
        "native": request.form.get('native'),
        "direct_click_limit": int(request.form.get('direct_click_limit', 1)),
        "main_theme": request.form.get('main_theme'),
        "step_theme": request.form.get('step_theme'),
        "template_style": request.form.get('template_style', 'standard')
    }
    settings_col.update_one({}, {"$set": d})
    return redirect(url_for('admin_panel'))

@app.route('/<short_code>')
def handle_ad_steps(short_code):
    step = int(request.args.get('step', 1))
    settings = get_settings()
    url_data = urls_col.find_one({"short_code": short_code})
    
    if not url_data: return "404 - Not Found", 404
    if step > settings['steps']:
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        return redirect(url_data['long_url'])
    
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    user_country = get_user_country(user_ip)
    user_device = get_user_device()
    
    all_links = list(direct_links_col.find({
        "$and": [
            {"$or": [{"country": user_country}, {"country": "Global"}]},
            {"$or": [{"device": user_device}, {"device": "All"}]}
        ]
    }))
    link_list = [l['url'] for l in all_links] if all_links else ["https://google.com"]
    js_link_array = json.dumps(link_list)
    tc = COLOR_MAP.get(settings.get('step_theme', 'blue'), COLOR_MAP['blue'])
    template_style = settings.get('template_style', 'standard')

    # Main Content Logic
    main_content = ""
    if template_style == 'video':
        main_content = f'''<div class="bg-black rounded-3xl overflow-hidden aspect-video flex items-center justify-center cursor-pointer relative" id="main_btn"><div class="z-10 bg-red-600 rounded-full w-20 h-20 flex items-center justify-center shadow-xl"><svg class="w-10 h-10 text-white ml-2" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></div><div id="timer_box" class="absolute top-4 right-4 bg-white/20 px-4 py-2 rounded-full font-bold text-white">{settings['timer_seconds']}</div></div>'''
    elif template_style == 'download':
        main_content = f'''<div class="bg-white p-10 rounded-[40px] shadow-2xl text-center border-4 {tc['border']}"><h2 class="text-2xl font-black mb-4">File Ready</h2><div id="timer_box" class="text-5xl font-black {tc['text']} mb-8">{settings['timer_seconds']}</div><button id="main_btn" class="hidden w-full bg-blue-600 text-white py-5 rounded-2xl font-bold uppercase">Download</button></div>'''
    else:
        main_content = f'''<div class="bg-white p-12 rounded-[50px] shadow-3xl text-center max-w-2xl w-full border-t-[12px] {tc['border']}"><p class="text-xl font-black {tc['text']} mb-4">Step {step} / {settings['steps']}</p><div id="timer_box" class="text-7xl font-black mb-8">{settings['timer_seconds']}</div><button id="main_btn" class="hidden w-full {tc['bg']} text-white py-6 rounded-[30px] font-black uppercase">Continue</button></div>'''

    return render_template_string(f'''
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script>{settings['popunder']}{settings['social_bar']}</head>
    <body class="bg-slate-100 flex flex-col items-center p-4 min-h-screen">
        <div class="w-full max-w-3xl mb-4">{settings['banner']}</div>
        {main_content}
        <div class="mt-8 w-full max-w-3xl">{settings['native']}</div>
        <script>
            let timeLeft = {settings['timer_seconds']};
            let totalClicks = 0;
            const adLimit = {settings.get('direct_click_limit', 1)};
            const links = {js_link_array};
            const timerBox = document.getElementById('timer_box');
            const mainBtn = document.getElementById('main_btn');

            const countdown = setInterval(() => {{
                timeLeft--;
                if(timerBox) timerBox.innerText = timeLeft;
                if(timeLeft <= 0) {{
                    clearInterval(countdown);
                    if(mainBtn) mainBtn.classList.remove('hidden');
                }}
            }}, 1000);

            mainBtn.addEventListener('click', () => {{
                if(totalClicks < adLimit) {{
                    window.open(links[Math.floor(Math.random() * links.length)], '_blank');
                    totalClicks++;
                }} else {{
                    window.location.href = "/{short_code}?step={step + 1}";
                }}
            }});
        </script>
    </body></html>''')

# --- লগইন ও পাসওয়ার্ড ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        settings = get_settings()
        if check_password_hash(settings['admin_password'], request.form.get('password')):
            session.permanent = True
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
    return render_template_string('''<body style="background:#0f172a;height:100vh;display:grid;place-items:center;font-family:sans-serif"><form method="POST" style="background:white;padding:40px;border-radius:30px;text-align:center"><h2 style="font-weight:900;margin-bottom:20px">ADMIN ACCESS</h2><input type="password" name="password" placeholder="Passkey" style="padding:15px;border:1px solid #ddd;border-radius:10px;width:100%;margin-bottom:15px"><button style="padding:15px;width:100%;background:black;color:white;border:none;border-radius:10px;font-weight:bold">LOGIN</button></form></body>''')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        tg_id = request.form.get('telegram_id')
        settings = get_settings()
        if tg_id and tg_id == settings.get('admin_telegram_id'):
            otp = str(random.randint(100000, 999999))
            otp_col.update_one({"id": "admin_reset"}, {"$set": {"otp": otp, "expire_at": datetime.now() + timedelta(minutes=5)}}, upsert=True)
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": tg_id, "text": f"OTP: {otp}"})
            session['reset_id'] = tg_id
            return redirect(url_for('verify_otp'))
    return render_template_string('<body style="display:grid;place-items:center;height:100vh;font-family:sans-serif"><form method="POST"><input name="telegram_id" placeholder="Telegram ID" style="padding:10px"><button>Send OTP</button></form></body>')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if not session.get('reset_id'): return redirect('/forgot-password')
    if request.method == 'POST':
        otp = request.form.get('otp')
        data = otp_col.find_one({"id": "admin_reset"})
        if data and data['otp'] == otp and data['expire_at'] > datetime.now():
            session['otp_verified'] = True
            return redirect(url_for('reset_password'))
    return render_template_string('<body style="display:grid;place-items:center;height:100vh;font-family:sans-serif"><form method="POST"><input name="otp" placeholder="OTP" style="padding:10px"><button>Verify</button></form></body>')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'): return redirect('/forgot-password')
    if request.method == 'POST':
        settings_col.update_one({}, {"$set": {"admin_password": generate_password_hash(request.form.get('password'))}})
        session.clear()
        return 'Done. <a href="/login">Login</a>'
    return render_template_string('<body style="display:grid;place-items:center;height:100vh;font-family:sans-serif"><form method="POST"><input type="password" name="password" placeholder="New Password" style="padding:10px"><button>Update</button></form></body>')

# Vercel-এর জন্য এক্সপোর্ট
app = app

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
