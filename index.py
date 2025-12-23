import os
import random
import string
import requests
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "premium-super-secret-key-2025")

# --- ডাটাবেস কানেকশন ---
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
db = client['premium_url_bot']
urls_col = db['urls']
settings_col = db['settings']
channels_col = db['channels']
otp_col = db['otps']

# --- টেলিগ্রাম সেটিংস ---
TELEGRAM_BOT_TOKEN = "8469682967:AAEWrNWBWjiYT3_L47Xe_byORfD6IIsFD34"

# --- থিম কালার ম্যাপ (Design Options) ---
COLOR_MAP = {
    "red": {"text": "text-red-500", "bg": "bg-red-600", "border": "border-red-500", "hover": "hover:bg-red-700", "light_bg": "bg-red-50"},
    "orange": {"text": "text-orange-500", "bg": "bg-orange-600", "border": "border-orange-500", "hover": "hover:bg-orange-700", "light_bg": "bg-orange-50"},
    "yellow": {"text": "text-yellow-500", "bg": "bg-yellow-500", "border": "border-yellow-500", "hover": "hover:bg-yellow-600", "light_bg": "bg-yellow-50"},
    "green": {"text": "text-green-500", "bg": "bg-green-600", "border": "border-green-500", "hover": "hover:bg-green-700", "light_bg": "bg-green-50"},
    "blue": {"text": "text-blue-500", "bg": "bg-blue-600", "border": "border-blue-500", "hover": "hover:bg-blue-700", "light_bg": "bg-blue-50"},
    "sky": {"text": "text-sky-400", "bg": "bg-sky-500", "border": "border-sky-400", "hover": "hover:bg-sky-600", "light_bg": "bg-sky-50"},
    "purple": {"text": "text-purple-500", "bg": "bg-purple-600", "border": "border-purple-500", "hover": "hover:bg-purple-700", "light_bg": "bg-purple-50"},
    "pink": {"text": "text-pink-500", "bg": "bg-pink-600", "border": "border-pink-500", "hover": "hover:bg-pink-700", "light_bg": "bg-pink-50"},
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
            "direct_link": "https://google.com", 
            "direct_click_limit": 1,
            "main_theme": "sky", "step_theme": "blue"
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

def is_logged_in():
    return session.get('logged_in')

# --- চ্যানেল বক্স জেনারেটর (320x180 ব্যানার স্টাইল) ---
def get_channels_html(theme_color="sky"):
    channels = list(channels_col.find())
    if not channels: return ""
    c = COLOR_MAP.get(theme_color, COLOR_MAP['sky'])
    html = f'''<div class="w-full max-w-5xl mx-auto mt-12 mb-8 p-8 rounded-[40px] border-2 border-white/10 glass shadow-2xl">
        <h3 class="text-center {c['text']} font-black mb-10 uppercase tracking-[0.3em] text-lg">Partner Channels</h3>
        <div class="flex flex-col items-center gap-10">'''
    for ch in channels:
        html += f'''<a href="{ch['link']}" target="_blank" class="flex flex-col items-center gap-3 group transition-transform hover:scale-105">
            <div class="text-center"><p class="text-lg font-black text-gray-100 uppercase italic tracking-wider">{ch.get('name', 'Join Our Channel')}</p></div>
            <img src="{ch['logo']}" style="width: 320px; height: 180px;" class="object-cover border-2 border-white/10 rounded-lg group-hover:border-white/40 shadow-2xl transition">
        </a>'''
    return html + '</div></div>'

# --- API সিস্টেম ---
@app.route('/api')
def api_system():
    settings = get_settings()
    raw_token = request.args.get('api') or request.args.get('api_key') or request.args.get('key')
    api_token = raw_token.strip() if raw_token else None
    
    long_url = request.args.get('url')
    alias = request.args.get('alias')
    res_format = request.args.get('format', 'json').lower()
    ad_type = request.args.get('type', '1')

    stored_token = settings['api_key'].strip()

    if not api_token or api_token != stored_token:
        return jsonify({"status": "error", "message": "Invalid API Token"}) if res_format != 'text' else "Error: Invalid Token"
    
    if not long_url:
        return jsonify({"status": "error", "message": "Missing URL"}) if res_format != 'text' else "Error: Missing URL"

    short_code = alias if alias else ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": short_code, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": ad_type})
    shortened_url = request.host_url + short_code
    return shortened_url if res_format == 'text' else jsonify({"status": "success", "shortenedUrl": shortened_url})

# --- হোম পেজ ---
@app.route('/')
def index():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    return render_template_string(f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script><title>{settings['site_name']}</title><style>body {{ background: #0f172a; color: white; }} .glass {{ background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}</style></head><body class="min-h-screen flex flex-col items-center justify-center p-6 text-center"><h1 class="text-7xl md:text-9xl font-black mb-6 {c['text']} italic tracking-tighter uppercase">{settings['site_name']}</h1><p class="text-gray-200 mb-14 text-2xl md:text-4xl font-black uppercase tracking-widest">Fast • Secure • Premium</p><div class="glass p-5 rounded-[50px] w-full max-w-4xl shadow-3xl"><form action="/shorten" method="POST" class="flex flex-col md:flex-row gap-4"><input type="url" name="long_url" placeholder="PASTE YOUR LONG LINK HERE..." required class="flex-1 bg-transparent p-6 outline-none text-white text-2xl font-black placeholder:text-gray-500"><button type="submit" class="{c['bg']} text-white px-14 py-6 rounded-[40px] font-black text-3xl hover:scale-105 transition uppercase tracking-tighter shadow-2xl">Shorten</button></form></div>{get_channels_html(settings.get('main_theme', 'sky'))}</body></html>''')

# --- রেজাল্ট পেজ ---
@app.route('/shorten', methods=['POST'])
def web_shorten():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    long_url = request.form.get('long_url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "1"})
    return render_template_string(f'''<html><head><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-slate-900 flex flex-col items-center justify-center min-h-screen p-4 text-white"><div class="bg-slate-800 p-16 rounded-[60px] shadow-2xl text-center max-w-2xl w-full border border-slate-700"><h2 class="text-5xl font-black mb-10 {c['text']} uppercase italic">Link Created!</h2><input id="shortUrl" value="{request.host_url + sc}" readonly class="w-full bg-slate-900 p-8 rounded-3xl border border-slate-700 {c['text']} font-black text-center mb-10 text-3xl"><button onclick="copyLink()" id="copyBtn" class="w-full {c['bg']} text-white py-8 rounded-[40px] font-black text-4xl uppercase tracking-tighter transition shadow-2xl">COPY LINK</button><a href="/" class="block mt-10 text-slate-500 font-black uppercase text-sm hover:text-white transition">Shorten Another</a></div><script>function copyLink() {{ var copyText = document.getElementById("shortUrl"); copyText.select(); navigator.clipboard.writeText(copyText.value); document.getElementById("copyBtn").innerText = "COPIED!"; }}</script></body></html>''')

# --- প্রিমিয়াম এডমিন ড্যাশবোর্ড (Tab Design) ---
@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    all_urls = list(urls_col.find().sort("_id", -1))
    total_clicks = sum(u.get('clicks', 0) for u in all_urls)
    channels = list(channels_col.find())
    theme_options = sorted(COLOR_MAP.keys())

    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&display=swap" rel="stylesheet">
    <style> body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: #f8fafc; }} .active-tab {{ background: #1e293b !important; color: white !important; }} .tab-content {{ display: none; }} .tab-content.active {{ display: block; }} </style>
    </head>
    <body class="flex flex-col lg:flex-row min-h-screen">
        <!-- Sidebar Navigation -->
        <div class="lg:w-72 bg-white border-r p-8 flex flex-col shadow-sm">
            <h2 class="text-2xl font-black text-slate-900 mb-12 italic tracking-tighter">PREMIUM <span class="text-blue-600">ADMIN</span></h2>
            <nav class="space-y-3 flex-1">
                <button onclick="showTab('overview')" id="tab-overview-btn" class="w-full text-left p-4 rounded-2xl font-bold text-slate-500 hover:bg-slate-100 transition flex items-center gap-3 active-tab">📊 Analytics</button>
                <button onclick="showTab('config')" id="tab-config-btn" class="w-full text-left p-4 rounded-2xl font-bold text-slate-500 hover:bg-slate-100 transition flex items-center gap-3">⚙️ Design & Setup</button>
                <button onclick="showTab('partners')" id="tab-partners-btn" class="w-full text-left p-4 rounded-2xl font-bold text-slate-500 hover:bg-slate-100 transition flex items-center gap-3">📢 Partnerships</button>
            </nav>
            <a href="/logout" class="mt-10 p-4 bg-red-50 text-red-600 rounded-2xl text-center font-black uppercase text-xs tracking-widest hover:bg-red-100 transition">Logout Account</a>
        </div>

        <!-- Content Area -->
        <div class="flex-1 p-6 lg:p-12 overflow-y-auto">
            
            <!-- TAB 1: OVERVIEW -->
            <div id="overview" class="tab-content active space-y-10">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100">
                        <p class="text-slate-400 text-xs font-bold uppercase mb-1">Total Generated Links</p>
                        <h3 class="text-5xl font-black text-slate-900">{len(all_urls)}</h3>
                    </div>
                    <div class="bg-blue-600 p-8 rounded-[40px] shadow-lg text-white">
                        <p class="text-blue-200 text-xs font-bold uppercase mb-1">Total Redirect Clicks</p>
                        <h3 class="text-5xl font-black">{total_clicks}</h3>
                    </div>
                </div>
                <div class="bg-white rounded-[40px] border border-slate-100 shadow-sm overflow-hidden">
                    <table class="w-full text-left">
                        <thead class="bg-slate-50 text-[10px] font-black uppercase text-slate-400 tracking-widest">
                            <tr><th class="p-6">Time</th><th class="p-6">Short Link</th><th class="p-6 text-center">Clicks</th></tr>
                        </thead>
                        <tbody class="divide-y text-sm font-bold text-slate-700">
                            {" ".join([f'<tr class="hover:bg-slate-50 transition"><td class="p-6 text-xs text-slate-400">{u.get("created_at")}</td><td class="p-6 text-blue-600">/{u["short_code"]}</td><td class="p-6 text-center"><span class="bg-slate-100 px-4 py-1 rounded-full">{u["clicks"]}</span></td></tr>' for u in all_urls[:15]])}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- TAB 2: CONFIGURATIONS -->
            <div id="config" class="tab-content space-y-8">
                <form action="/admin/update" method="POST" class="grid grid-cols-1 xl:grid-cols-2 gap-8">
                    <div class="bg-white p-10 rounded-[50px] shadow-sm border border-slate-100 space-y-6">
                        <h4 class="font-black text-xl text-slate-900">🎨 UI & Design System</h4>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="text-xs font-bold text-slate-400 mb-2 block">HOME PAGE THEME</label>
                                <select name="main_theme" class="w-full p-4 bg-slate-50 rounded-2xl border-none font-bold text-slate-700">
                                    {"".join([f'<option value="{o}" {"selected" if settings.get("main_theme")==o else ""}>{o.upper()}</option>' for o in theme_options])}
                                </select>
                            </div>
                            <div>
                                <label class="text-xs font-bold text-slate-400 mb-2 block">STEP PAGE THEME</label>
                                <select name="step_theme" class="w-full p-4 bg-slate-50 rounded-2xl border-none font-bold text-slate-700">
                                    {"".join([f'<option value="{o}" {"selected" if settings.get("step_theme")==o else ""}>{o.upper()}</option>' for o in theme_options])}
                                </select>
                            </div>
                        </div>
                        <input type="text" name="site_name" value="{settings['site_name']}" class="w-full p-4 bg-slate-50 rounded-2xl border-none font-black text-lg" placeholder="Website Title">
                        
                        <div class="grid grid-cols-2 gap-4">
                            <input type="number" name="steps" value="{settings['steps']}" class="w-full p-4 bg-slate-50 rounded-2xl border-none" placeholder="Ad Steps">
                            <input type="number" name="timer_seconds" value="{settings['timer_seconds']}" class="w-full p-4 bg-slate-50 rounded-2xl border-none" placeholder="Timer Seconds">
                        </div>

                        <!-- API Key Management -->
                        <h4 class="font-black text-xl text-slate-900 pt-4">🔑 API Management</h4>
                        <div class="bg-orange-50 p-6 rounded-[30px] border border-orange-100 space-y-4">
                            <label class="text-xs font-bold text-orange-600 block uppercase">API Shortener Token</label>
                            <input type="text" id="api_key_field" name="api_key" value="{settings['api_key']}" class="w-full p-4 bg-white rounded-xl font-mono text-xs border border-orange-200 outline-none" placeholder="Your API Token">
                            <div class="flex gap-2">
                                <button type="button" onclick="copyAPI()" class="flex-1 bg-white border border-orange-200 text-orange-600 p-3 rounded-xl text-xs font-black hover:bg-orange-100 transition">COPY KEY</button>
                                <button type="button" onclick="generateAPI()" class="flex-1 bg-orange-600 text-white p-3 rounded-xl text-xs font-black hover:bg-orange-700 shadow-md transition">REGENERATE</button>
                            </div>
                        </div>

                        <input type="text" name="admin_telegram_id" value="{settings.get('admin_telegram_id','')}" class="w-full p-4 bg-slate-50 rounded-2xl border-none" placeholder="Telegram Admin ID">
                        <input type="password" name="new_password" class="w-full p-4 bg-red-50 rounded-2xl border-none" placeholder="Update Admin Password">
                    </div>

                    <div class="bg-white p-10 rounded-[50px] shadow-sm border border-slate-100 space-y-4">
                        <h4 class="font-black text-xl text-emerald-600">💰 Monetization (Scripts)</h4>
                        <div class="grid grid-cols-2 gap-4">
                            <input type="url" name="direct_link" value="{settings['direct_link']}" class="w-full p-4 bg-blue-50 rounded-2xl border-none font-bold text-blue-600" placeholder="Direct Link">
                            <input type="number" name="direct_click_limit" value="{settings.get('direct_click_limit', 1)}" class="w-full p-4 bg-blue-50 rounded-2xl border-none font-bold text-blue-600" placeholder="Limit">
                        </div>
                        <textarea name="popunder" placeholder="Popunder Script" class="w-full h-20 p-4 bg-slate-50 rounded-2xl text-xs font-mono">{settings['popunder']}</textarea>
                        <textarea name="banner" placeholder="Banner Ad Script" class="w-full h-20 p-4 bg-slate-50 rounded-2xl text-xs font-mono">{settings['banner']}</textarea>
                        <textarea name="social_bar" placeholder="Social Bar Script" class="w-full h-20 p-4 bg-slate-50 rounded-2xl text-xs font-mono">{settings['social_bar']}</textarea>
                        <textarea name="native" placeholder="Native/Bottom Script" class="w-full h-20 p-4 bg-slate-50 rounded-2xl text-xs font-mono">{settings['native']}</textarea>
                        <button class="w-full bg-slate-900 text-white p-6 rounded-[30px] font-black text-xl shadow-2xl hover:scale-[1.02] transition mt-4">Save All Changes</button>
                    </div>
                </form>
            </div>

            <!-- TAB 3: PARTNERS (Updated with Name and 468x60 Banner) -->
            <div id="partners" class="tab-content space-y-8">
                <div class="bg-white p-10 rounded-[50px] shadow-sm border border-slate-100">
                    <h4 class="font-black text-xl text-slate-900 mb-6">📢 Manage Official Channels</h4>
                    <form action="/admin/add_channel" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
                        <input type="text" name="name" placeholder="Channel Name" required class="w-full p-4 bg-slate-50 rounded-2xl border-none">
                        <input type="url" name="logo" placeholder="Banner URL (468x60)" required class="w-full p-4 bg-slate-50 rounded-2xl border-none">
                        <input type="url" name="link" placeholder="Invite Link" required class="w-full p-4 bg-slate-50 rounded-2xl border-none">
                        <button class="bg-blue-600 text-white p-4 rounded-2xl font-black uppercase shadow-lg hover:bg-blue-700 transition">Add Channel</button>
                    </form>
                    <div class="mt-12 space-y-8">
                        {" ".join([f'''
                        <div class="flex flex-col md:flex-row items-center gap-6 bg-slate-50 p-6 rounded-[30px] border border-slate-100 relative">
                            <div class="flex-1">
                                <p class="text-sm font-black text-slate-900 uppercase mb-2">{c.get('name', 'N/A')}</p>
                                <img src="{c["logo"]}" style="width: 468px; height: 60px;" class="object-cover rounded-lg shadow-sm border border-slate-200">
                            </div>
                            <a href="/admin/delete_channel/{c["_id"]}" class="bg-red-500 text-white px-4 py-2 rounded-xl text-xs font-bold shadow-md">Delete</a>
                        </div>''' for c in channels])}
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

            function copyAPI() {{
                const copyText = document.getElementById("api_key_field");
                copyText.select();
                navigator.clipboard.writeText(copyText.value);
                alert("API Key Copied!");
            }}

            function generateAPI() {{
                const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
                let newKey = "";
                for (let i = 0; i < 40; i++) {{
                    newKey += chars.charAt(Math.floor(Math.random() * chars.length));
                }}
                document.getElementById("api_key_field").value = newKey;
            }}
        </script>
    </body></html>
    ''')

# --- এডমিন অ্যাকশন ---
@app.route('/admin/add_channel', methods=['POST'])
def add_channel():
    if not is_logged_in(): return redirect(url_for('login'))
    name, logo, link = request.form.get('name'), request.form.get('logo'), request.form.get('link')
    if logo and link: channels_col.insert_one({"name": name, "logo": logo, "link": link})
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_channel/<id>')
def delete_channel(id):
    if not is_logged_in(): return redirect(url_for('login'))
    channels_col.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('admin_panel'))

@app.post('/admin/update')
def update_settings():
    if not is_logged_in(): return redirect(url_for('login'))
    raw_api_key = request.form.get('api_key', '')
    cleaned_api_key = raw_api_key.strip()
    d = {
        "site_name": request.form.get('site_name'),
        "admin_telegram_id": request.form.get('admin_telegram_id'),
        "steps": int(request.form.get('steps', 2)),
        "timer_seconds": int(request.form.get('timer_seconds', 10)),
        "popunder": request.form.get('popunder'),
        "banner": request.form.get('banner'),
        "social_bar": request.form.get('social_bar'),
        "native": request.form.get('native'),
        "direct_link": request.form.get('direct_link'),
        "direct_click_limit": int(request.form.get('direct_click_limit', 1)),
        "main_theme": request.form.get('main_theme'),
        "step_theme": request.form.get('step_theme'),
        "api_key": cleaned_api_key if cleaned_api_key else get_settings()['api_key']
    }
    new_pass = request.form.get('new_password')
    if new_pass and len(new_pass) > 2: d["admin_password"] = generate_password_hash(new_pass)
    settings_col.update_one({}, {"$set": d})
    return redirect(url_for('admin_panel'))

# --- রিডাইরেক্ট লজিক ---
@app.route('/<short_code>')
def handle_ad_steps(short_code):
    step = int(request.args.get('step', 1))
    settings = get_settings()
    url_data = urls_col.find_one({"short_code": short_code})
    if not url_data: return "404 - Link Not Found", 404
    if step > settings['steps']:
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        return redirect(url_data['long_url'])
    
    tc = COLOR_MAP.get(settings.get('step_theme', 'blue'), COLOR_MAP['blue'])
    return render_template_string(f'''
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script>
    {settings['popunder']} {settings['social_bar']}
    </head>
    <body class="bg-slate-50 flex flex-col items-center p-6 min-h-screen">
        <div class="mb-6">{settings['banner']}</div>
        <div class="bg-white p-12 md:p-20 rounded-[70px] shadow-3xl text-center max-w-2xl w-full border-t-[16px] {tc['border']} my-4">
            <p class="text-xl md:text-2xl font-black {tc['text']} uppercase tracking-widest mb-4">Step {step} of {settings['steps']}</p>
            <h2 class="text-3xl md:text-5xl font-black text-slate-900 mb-8 tracking-tighter italic">Verifying Status...</h2>
            
            <div id="timer_box" class="text-7xl md:text-8xl font-black {tc['text']} mb-8 {tc['light_bg']} w-40 h-40 md:w-48 md:h-48 flex items-center justify-center rounded-full mx-auto border-8 {tc['border']} italic shadow-inner">{settings['timer_seconds']}</div>
            
            <button id="main_btn" onclick="handleClick()" class="hidden w-full {tc['bg']} text-white py-8 rounded-[40px] font-black text-3xl uppercase shadow-2xl transition hover:scale-105">Continue</button>
        </div>
        <div class="mt-4">{settings['native']}</div>
        {get_channels_html(settings.get('step_theme', 'blue'))}
        
        <script>
            let timeLeft = {settings['timer_seconds']};
            let totalAdClicks = 0;
            let adLimit = {settings.get('direct_click_limit', 1)};
            let adUrl = "{settings['direct_link']}";
            
            const timerBox = document.getElementById('timer_box');
            const mainBtn = document.getElementById('main_btn');

            const countdown = setInterval(() => {{
                timeLeft--;
                timerBox.innerText = timeLeft;
                if(timeLeft <= 0) {{
                    clearInterval(countdown);
                    timerBox.style.display = 'none';
                    mainBtn.classList.remove('hidden');
                    refreshBtnText();
                }}
            }}, 1000);

            function refreshBtnText() {{
                if (totalAdClicks < adLimit && adUrl !== "") {{
                    mainBtn.innerText = "VERIFY (" + (totalAdClicks + 1) + "/" + adLimit + ")";
                }} else {{
                    mainBtn.innerText = "CONTINUE TO NEXT";
                }}
            }}

            function handleClick() {{
                if (totalAdClicks < adLimit && adUrl !== "") {{
                    window.open(adUrl, '_blank');
                    totalAdClicks++;
                    refreshBtnText();
                }} else {{
                    window.location.href = "/{short_code}?step={step + 1}";
                }}
            }}
        </script>
    </body></html>''')

# --- লগইন ও রিকভারি ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        return "Access Denied!"
    return render_template_string('''<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;"><form method="POST" style="background:white; padding:50px; border-radius:40px; text-align:center; box-shadow:0 0 50px rgba(0,0,0,0.5);"><h2 style="font-weight:900; margin-bottom:30px; font-size:24px;">ADMIN PORTAL</h2><input type="password" name="password" placeholder="Key" style="padding:15px; border-radius:15px; border:1px solid #eee; width:250px; display:block; margin-bottom:15px; background:#f9f9f9; outline:none; text-align:center; font-weight:bold;"><button style="width:100%; padding:15px; background:#1e293b; color:white; border:none; border-radius:15px; font-weight:900; cursor:pointer;">UNLOCK</button><a href="/forgot-password" style="display:block; margin-top:20px; font-size:12px; color:#3b82f6; text-decoration:none; font-weight:bold;">Forgot Passkey?</a></form></body>''')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        tg_id = request.form.get('telegram_id')
        settings = get_settings()
        if tg_id and tg_id == settings.get('admin_telegram_id'):
            otp = str(random.randint(100000, 999999))
            otp_col.update_one({"id": "admin_reset"}, {"$set": {"otp": otp, "expire_at": datetime.now() + timedelta(minutes=5)}}, upsert=True)
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": tg_id, "text": f"🛡️ YOUR SECURITY OTP: {otp}"})
            session['reset_id'] = tg_id
            return redirect(url_for('verify_otp'))
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;"><form method="POST" style="background:white; padding:40px; border-radius:30px; width:320px; text-align:center;"><h2 style="font-weight:900;">Recovery</h2><input type="text" name="telegram_id" placeholder="Telegram Chat ID" required style="width:100%; padding:15px; border-radius:15px; border:1px solid #ddd; margin:20px 0; text-align:center;"><button style="width:100%; padding:15px; background:#3b82f6; color:white; border:none; border-radius:15px; font-weight:bold;">GET OTP</button></form></body>')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if not session.get('reset_id'): return redirect('/forgot-password')
    if request.method == 'POST':
        otp = request.form.get('otp')
        data = otp_col.find_one({"id": "admin_reset"})
        if data and data['otp'] == otp and data['expire_at'] > datetime.now():
            session['otp_verified'] = True
            return redirect(url_for('reset_password'))
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;"><form method="POST" style="background:white; padding:40px; border-radius:30px; width:320px; text-align:center;"><h2 style="font-weight:900;">Verify</h2><input type="text" name="otp" placeholder="ENTER OTP" required style="width:100%; padding:15px; border-radius:15px; border:1px solid #ddd; margin:20px 0; text-align:center; font-size:24px; font-weight:bold; letter-spacing:5px;"><button style="width:100%; padding:15px; background:#10b981; color:white; border:none; border-radius:15px; font-weight:bold;">VERIFY</button></form></body>')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'): return redirect('/forgot-password')
    if request.method == 'POST':
        pw = request.form.get('password')
        settings_col.update_one({}, {"$set": {"admin_password": generate_password_hash(pw)}})
        session.clear()
        return 'SUCCESS! <a href="/login">LOGIN NOW</a>'
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;"><form method="POST" style="background:white; padding:40px; border-radius:30px; width:320px;"><h2 style="text-align:center; font-weight:900;">NEW PASSKEY</h2><input type="password" name="password" required placeholder="New Password" style="width:100%; padding:15px; border-radius:15px; border:1px solid #ddd; margin:20px 0;"><button style="width:100%; padding:15px; background:#1e293b; color:white; border:none; border-radius:15px; font-weight:bold;">UPDATE</button></form></body>')

if __name__ == '__main__':
    app.run()
