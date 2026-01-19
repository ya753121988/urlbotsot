import os
import random
import string
import requests
import json
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
ad_links_col = db['ad_links']
stats_col = db['stats'] # বিস্তারিত ট্র্যাকিং এর জন্য

# --- টেলিগ্রাম সেটিংস ---
TELEGRAM_BOT_TOKEN = "8469682967:AAEWrNWBWjiYT3_L47Xe_byORfD6IIsFD34"

# --- থিম কালার ম্যাপ ---
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

# --- অ্যানালিটিক্স ট্র্যাকিং ---
def track_click(short_code, ad_link=None):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip: ip = ip.split(',')[0]
    country = "Unknown"
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}", timeout=2).json()
        if res.get('status') == 'success':
            country = res.get('country', 'Unknown')
    except: pass
    ua_str = request.user_agent.string.lower()
    device = "Desktop/Laptop"
    if any(keyword in ua_str for keyword in ['android', 'iphone', 'ipad', 'mobile']):
        device = "Mobile"
    stats_col.insert_one({
        "short_code": short_code, "ad_link": ad_link, "country": country,
        "device": device, "timestamp": datetime.now(), "date": datetime.now().strftime("%Y-%m-%d")
    })

# --- চ্যানেল বক্স জেনারেটর ---
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
    if not api_token or api_token != settings['api_key'].strip():
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

# --- এডমিন ড্যাশবোর্ড ---
@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    all_urls = list(urls_col.find().sort("_id", -1).limit(50))
    channels = list(channels_col.find())
    ad_links = list(ad_links_col.find())
    
    # --- অ্যানালিটিক্স লজিক ---
    today = datetime.now().strftime("%Y-%m-%d")
    total_views = stats_col.count_documents({})
    today_views = stats_col.count_documents({"date": today})
    chart_labels, chart_values = [], []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        chart_labels.append(d); chart_values.append(stats_col.count_documents({"date": d}))
    countries = list(stats_col.aggregate([{"$group": {"_id": "$country", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 5}]))
    devices = list(stats_col.aggregate([{"$group": {"_id": "$device", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]))
    ad_stats = []
    for al in ad_links:
        ad_stats.append({"url": al['url'], "count": stats_col.count_documents({"ad_link": al['url']})})

    return render_template_string('''
    <html><head><script src="https://cdn.tailwindcss.com"></script><script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style> .tab-content { display: none; } .tab-content.active { display: block; } .active-btn { background: #1e293b !important; color: white !important; } </style>
    </head><body class="flex flex-col lg:flex-row min-h-screen bg-slate-50">
        <div class="lg:w-72 bg-white border-r p-8 flex flex-col shadow-sm">
            <h2 class="text-2xl font-black text-slate-900 mb-12 italic">PREMIUM ADMIN</h2>
            <nav class="space-y-3 flex-1">
                <button onclick="tab('dash')" id="tab-dash-btn" class="w-full text-left p-4 rounded-2xl font-bold active-btn">📊 Dashboard</button>
                <button onclick="tab('links')" id="tab-links-btn" class="w-full text-left p-4 rounded-2xl font-bold text-slate-500">🔗 Links</button>
                <button onclick="tab('config')" id="tab-config-btn" class="w-full text-left p-4 rounded-2xl font-bold text-slate-500">⚙️ Settings</button>
                <button onclick="tab('ads')" id="tab-ads-btn" class="w-full text-left p-4 rounded-2xl font-bold text-slate-500">💰 Ads Management</button>
                <button onclick="tab('partners')" id="tab-partners-btn" class="w-full text-left p-4 rounded-2xl font-bold text-slate-500">📢 Partners</button>
            </nav>
            <a href="/logout" class="mt-10 p-4 bg-red-50 text-red-600 rounded-2xl text-center font-black">LOGOUT</a>
        </div>
        <div class="flex-1 p-6 lg:p-12 overflow-y-auto">
            <!-- Dashboard -->
            <div id="dash" class="tab-content active space-y-8">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="bg-blue-600 p-8 rounded-[40px] text-white shadow-xl"><p class="text-xs font-bold opacity-70">LIFETIME VIEWS</p><h3 class="text-5xl font-black">{{total_views}}</h3></div>
                    <div class="bg-emerald-500 p-8 rounded-[40px] text-white shadow-xl"><p class="text-xs font-bold opacity-70">TODAY'S VIEWS</p><h3 class="text-5xl font-black">{{today_views}}</h3></div>
                    <div class="bg-white p-8 rounded-[40px] border shadow-sm"><p class="text-xs font-bold text-slate-400">TOTAL LINKS</p><h3 class="text-5xl font-black text-slate-800">{{all_urls|length}}</h3></div>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div class="bg-white p-8 rounded-[40px] border shadow-sm"><h4 class="font-black mb-6">Traffic Trend</h4><canvas id="trafficChart"></canvas></div>
                    <div class="bg-white p-8 rounded-[40px] border shadow-sm">
                        <h4 class="font-black mb-6">Countries & Devices</h4>
                        <div class="space-y-4">
                            {% for c in countries %}<div class="flex justify-between p-4 bg-slate-50 rounded-2xl"><span>{{c._id}}</span><b>{{c.count}}</b></div>{% endfor %}
                            <hr class="my-4">
                            {% for d in devices %}<div class="flex justify-between p-4 bg-blue-50 rounded-2xl"><span>{{d._id}}</span><b>{{d.count}}</b></div>{% endfor %}
                        </div>
                    </div>
                </div>
                <div class="bg-white p-8 rounded-[40px] border shadow-sm"><h4 class="font-black mb-6">Unlimited Ad Link Clicks</h4>
                    <div class="grid gap-4">{% for as in ad_stats %}<div class="p-4 bg-slate-50 rounded-2xl flex justify-between"><span class="truncate max-w-md">{{as.url}}</span><b class="text-emerald-600">{{as.count}} Clicks</b></div>{% endfor %}</div>
                </div>
            </div>
            <!-- Links -->
            <div id="links" class="tab-content space-y-6">
                <div class="bg-white rounded-[40px] border shadow-sm overflow-hidden">
                    <table class="w-full text-left"><thead class="bg-slate-50 text-xs font-bold uppercase"><tr><th class="p-6">Created</th><th class="p-6">Short Link</th><th class="p-6">Original URL</th><th class="p-6">Clicks</th></tr></thead>
                    <tbody class="divide-y text-sm font-bold">{% for u in all_urls %}<tr><td class="p-6 text-slate-400">{{u.created_at}}</td><td class="p-6 text-blue-600">/{{u.short_code}}</td><td class="p-6 truncate max-w-xs">{{u.long_url}}</td><td class="p-6">{{u.clicks}}</td></tr>{% endfor %}</tbody></table>
                </div>
            </div>
            <!-- Settings -->
            <div id="config" class="tab-content">
                <form action="/admin/update" method="POST" class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div class="bg-white p-10 rounded-[50px] shadow-sm border space-y-6">
                        <h4 class="font-black text-xl">🎨 Design & General</h4>
                        <input type="text" name="site_name" value="{{s.site_name}}" class="w-full p-4 bg-slate-50 rounded-2xl" placeholder="Site Name">
                        <div class="grid grid-cols-2 gap-4">
                            <select name="main_theme" class="p-4 bg-slate-50 rounded-2xl">{% for k in colors %}<option value="{{k}}" {% if s.main_theme == k %}selected{% endif %}>HOME: {{k|upper}}</option>{% endfor %}</select>
                            <select name="step_theme" class="p-4 bg-slate-50 rounded-2xl">{% for k in colors %}<option value="{{k}}" {% if s.step_theme == k %}selected{% endif %}>STEP: {{k|upper}}</option>{% endfor %}</select>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <input type="number" name="steps" value="{{s.steps}}" class="p-4 bg-slate-50 rounded-2xl" placeholder="Steps">
                            <input type="number" name="timer_seconds" value="{{s.timer_seconds}}" class="p-4 bg-slate-50 rounded-2xl" placeholder="Timer">
                        </div>
                        <input type="text" name="admin_telegram_id" value="{{s.admin_telegram_id}}" class="w-full p-4 bg-slate-50 rounded-2xl" placeholder="Telegram Admin ID">
                        <input type="password" name="new_password" class="w-full p-4 bg-red-50 rounded-2xl" placeholder="New Password">
                        <div class="bg-orange-50 p-6 rounded-3xl"><p class="text-xs font-bold mb-2">API KEY</p><input type="text" name="api_key" value="{{s.api_key}}" class="w-full bg-white p-3 rounded-xl text-xs font-mono" readonly></div>
                    </div>
                    <div class="bg-white p-10 rounded-[50px] shadow-sm border space-y-6">
                        <h4 class="font-black text-xl text-emerald-600">💰 Monetization</h4>
                        <input type="number" name="direct_click_limit" value="{{s.direct_click_limit}}" class="w-full p-4 bg-blue-50 rounded-2xl" placeholder="Direct Ad Clicks">
                        <textarea name="popunder" placeholder="Popunder Script" class="w-full h-24 p-4 bg-slate-50 rounded-2xl text-xs font-mono">{{s.popunder}}</textarea>
                        <textarea name="banner" placeholder="Banner Script" class="w-full h-24 p-4 bg-slate-50 rounded-2xl text-xs font-mono">{{s.banner}}</textarea>
                        <textarea name="social_bar" placeholder="Social Bar" class="w-full h-24 p-4 bg-slate-50 rounded-2xl text-xs font-mono">{{s.social_bar}}</textarea>
                        <textarea name="native" placeholder="Native/Bottom Script" class="w-full h-24 p-4 bg-slate-50 rounded-2xl text-xs font-mono">{{s.native}}</textarea>
                        <button class="w-full bg-slate-900 text-white py-6 rounded-3xl font-black shadow-xl">SAVE ALL CHANGES</button>
                    </div>
                </form>
            </div>
            <!-- Ads Management -->
            <div id="ads" class="tab-content space-y-8">
                <div class="bg-white p-10 rounded-[50px] shadow-sm border">
                    <h4 class="font-black text-xl mb-6">🔗 Add Unlimited Ad Links</h4>
                    <form action="/admin/add_ad_link" method="POST" class="flex flex-col md:flex-row gap-4 mb-8">
                        <input type="url" name="ad_url" placeholder="Paste Direct Ad/CPA Link..." required class="flex-1 p-4 bg-slate-50 rounded-2xl">
                        <button class="bg-emerald-600 text-white px-10 py-4 rounded-2xl font-black uppercase shadow-lg">Add Link</button>
                    </form>
                    <div class="space-y-3">{% for l in ad_links %}<div class="flex items-center justify-between bg-slate-50 p-5 rounded-3xl"><span>{{l.url}}</span><a href="/admin/delete_ad_link/{{l._id}}" class="bg-red-500 text-white px-6 py-2 rounded-xl text-xs font-bold">DELETE</a></div>{% endfor %}</div>
                </div>
            </div>
            <!-- Partners -->
            <div id="partners" class="tab-content space-y-8">
                <div class="bg-white p-10 rounded-[50px] shadow-sm border">
                    <h4 class="font-black text-xl mb-6">📢 Manage Channels</h4>
                    <form action="/admin/add_channel" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
                        <input type="text" name="name" placeholder="Name" required class="p-4 bg-slate-50 rounded-2xl">
                        <input type="url" name="logo" placeholder="Banners Logo URL" required class="p-4 bg-slate-50 rounded-2xl">
                        <input type="url" name="link" placeholder="Invite Link" required class="p-4 bg-slate-50 rounded-2xl">
                        <button class="bg-blue-600 text-white rounded-2xl font-black">ADD CHANNEL</button>
                    </form>
                    <div class="grid gap-6">{% for ch in channels %}<div class="flex items-center gap-6 p-6 bg-slate-50 rounded-3xl"><img src="{{ch.logo}}" class="w-40 h-24 object-cover rounded-xl shadow-sm"><div class="flex-1 font-black uppercase">{{ch.name}}</div><a href="/admin/delete_channel/{{ch._id}}" class="text-red-500 font-bold">Delete</a></div>{% endfor %}</div>
                </div>
            </div>
        </div>
        <script>
            function tab(id) {
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                document.querySelectorAll('nav button').forEach(b => b.classList.remove('active-btn'));
                document.getElementById(id).classList.add('active');
                document.getElementById('tab-'+id+'-btn').classList.add('active-btn');
            }
            new Chart(document.getElementById('trafficChart'), {
                type: 'line',
                data: { labels: {{chart_labels|tojson}}, datasets: [{ label: 'Views', data: {{chart_values|tojson}}, borderColor: '#2563eb', backgroundColor: 'rgba(37, 99, 235, 0.1)', fill: true, tension: 0.4, borderWidth: 4 }] },
                options: { responsive: true, plugins: { legend: { display: false } } }
            });
        </script>
    </body></html>
    ''', total_views=total_views, today_views=today_views, all_urls=all_urls, countries=countries, 
        devices=devices, ad_stats=ad_stats, ad_links=ad_links, channels=channels, s=settings, 
        colors=COLOR_MAP.keys(), chart_labels=chart_labels, chart_values=chart_values)

# --- এডমিন অ্যাকশনস ---
@app.route('/admin/add_ad_link', methods=['POST'])
def add_ad_link():
    if not is_logged_in(): return redirect(url_for('login'))
    url = request.form.get('ad_url')
    if url: ad_links_col.insert_one({"url": url})
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_ad_link/<id>')
def delete_ad_link(id):
    if not is_logged_in(): return redirect(url_for('login'))
    ad_links_col.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('admin_panel'))

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
    d = {
        "site_name": request.form.get('site_name'),
        "admin_telegram_id": request.form.get('admin_telegram_id'),
        "steps": int(request.form.get('steps', 2)),
        "timer_seconds": int(request.form.get('timer_seconds', 10)),
        "popunder": request.form.get('popunder'),
        "banner": request.form.get('banner'),
        "social_bar": request.form.get('social_bar'),
        "native": request.form.get('native'),
        "direct_click_limit": int(request.form.get('direct_click_limit', 1)),
        "main_theme": request.form.get('main_theme'),
        "step_theme": request.form.get('step_theme')
    }
    np = request.form.get('new_password')
    if np and len(np) > 2: d["admin_password"] = generate_password_hash(np)
    settings_col.update_one({}, {"$set": d})
    return redirect(url_for('admin_panel'))

# --- রিডাইরেক্ট ও ট্র্যাকিং ---
@app.route('/<short_code>')
def handle_ad_steps(short_code):
    step = int(request.args.get('step', 1))
    settings = get_settings()
    url_data = urls_col.find_one({"short_code": short_code})
    if not url_data: return "404 Not Found", 404
    if step > settings['steps']:
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        track_click(short_code)
        return redirect(url_data['long_url'])
    ads = [l['url'] for l in ad_links_col.find()]
    tc = COLOR_MAP.get(settings.get('step_theme', 'blue'), COLOR_MAP['blue'])
    return render_template_string('''
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script>
    {{ s.popunder|safe }} {{ s.social_bar|safe }}</head><body class="bg-slate-50 flex flex-col items-center p-6 min-h-screen">
        <div class="mb-6">{{ s.banner|safe }}</div>
        <div class="bg-white p-12 md:p-20 rounded-[70px] shadow-2xl text-center max-w-2xl w-full border-t-[16px] {{tc.border}}">
            <p class="text-xl md:text-2xl font-black {{tc.text}} uppercase tracking-widest mb-4">Step {{step}} of {{total_steps}}</p>
            <div id="timer_box" class="text-7xl md:text-8xl font-black {{tc.text}} mb-8 {{tc.light_bg}} w-40 h-40 flex items-center justify-center rounded-full mx-auto border-8 {{tc.border}} shadow-inner">{{timer}}</div>
            <button id="main_btn" onclick="handleClick()" class="hidden w-full {{tc.bg}} text-white py-8 rounded-[40px] font-black text-3xl uppercase shadow-2xl">Continue</button>
        </div>
        <div class="mt-8">{{ partners_html|safe }}</div>
        <div class="mt-4">{{ s.native|safe }}</div>
        <script>
            let sec = {{timer}}, ads = {{ads|tojson}}, clicks = 0, limit = {{limit}};
            const timerBox = document.getElementById('timer_box'), mainBtn = document.getElementById('main_btn');
            const iv = setInterval(() => { sec--; timerBox.innerText = sec; if(sec<=0) { clearInterval(iv); timerBox.style.display='none'; mainBtn.classList.remove('hidden'); updateBtn(); } }, 1000);
            function updateBtn() { mainBtn.innerText = (clicks < limit && ads.length > 0) ? "VERIFY ("+(clicks+1)+"/"+limit+")" : "CONTINUE TO STEP "+({{step}}+1); }
            function handleClick() {
                if(clicks < limit && ads.length > 0) {
                    let r = ads[Math.floor(Math.random()*ads.length)];
                    fetch('/track_ajax?sc={{sc}}&ad='+encodeURIComponent(r));
                    window.open(r, '_blank'); clicks++; updateBtn();
                } else { window.location.href = "/{{sc}}?step="+({{step}}+1); }
            }
        </script>
    </body></html>
    ''', s=settings, step=step, total_steps=settings['steps'], timer=settings['timer_seconds'], 
        tc=tc, ads=ads, limit=settings['direct_click_limit'], sc=short_code, partners_html=get_channels_html(settings.get('step_theme', 'blue')))

@app.route('/track_ajax')
def track_ajax():
    track_click(request.args.get('sc'), request.args.get('ad'))
    return "ok"

# --- লগইন ও পাসওয়ার্ড রিকভারি ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True; return redirect(url_for('admin_panel'))
    return render_template_string('<body style="background:#0f172a;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;"><form method="POST" style="background:white;padding:50px;border-radius:40px;text-align:center;"><h2 style="font-weight:900;margin-bottom:30px;">ADMIN PORTAL</h2><input type="password" name="password" placeholder="Key" style="padding:15px;border-radius:15px;border:1px solid #eee;width:250px;display:block;margin-bottom:15px;text-align:center;font-weight:bold;"><button style="width:100%;padding:15px;background:#1e293b;color:white;border:none;border-radius:15px;font-weight:900;cursor:pointer;">UNLOCK</button><a href="/forgot-password" style="display:block;margin-top:20px;font-size:12px;color:#3b82f6;text-decoration:none;">Forgot Passkey?</a></form></body>')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        tg_id = request.form.get('telegram_id')
        settings = get_settings()
        if tg_id == settings.get('admin_telegram_id'):
            otp = str(random.randint(100000, 999999))
            otp_col.update_one({"id": "admin_reset"}, {"$set": {"otp": otp, "expire_at": datetime.now() + timedelta(minutes=5)}}, upsert=True)
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": tg_id, "text": f"🛡️ RESET OTP: {otp}"})
            session['reset_id'] = tg_id; return redirect(url_for('verify_otp'))
    return render_template_string('<body style="background:#0f172a;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="POST" style="background:white;padding:40px;border-radius:30px;width:320px;text-align:center;"><h2>Recovery</h2><input type="text" name="telegram_id" placeholder="Telegram ID" required style="width:100%;padding:15px;margin:20px 0;text-align:center;"><button style="width:100%;padding:15px;background:#3b82f6;color:white;border:none;border-radius:15px;font-weight:bold;">GET OTP</button></form></body>')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if not session.get('reset_id'): return redirect('/forgot-password')
    if request.method == 'POST':
        otp = request.form.get('otp'); data = otp_col.find_one({"id": "admin_reset"})
        if data and data['otp'] == otp and data['expire_at'] > datetime.now():
            session['otp_verified'] = True; return redirect(url_for('reset_password'))
    return render_template_string('<body style="background:#0f172a;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="POST" style="background:white;padding:40px;border-radius:30px;width:320px;text-align:center;"><h2>Verify</h2><input type="text" name="otp" placeholder="OTP" required style="width:100%;padding:15px;margin:20px 0;text-align:center;font-size:24px;"><button style="width:100%;padding:15px;background:#10b981;color:white;border:none;border-radius:15px;font-weight:bold;">VERIFY</button></form></body>')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'): return redirect('/forgot-password')
    if request.method == 'POST':
        pw = request.form.get('password')
        settings_col.update_one({}, {"$set": {"admin_password": generate_password_hash(pw)}})
        session.clear(); return 'SUCCESS! <a href="/login">LOGIN NOW</a>'
    return render_template_string('<body style="background:#0f172a;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="POST" style="background:white;padding:40px;border-radius:30px;width:320px;"><h2 style="text-align:center;">NEW PASSWORD</h2><input type="password" name="password" required placeholder="New Password" style="width:100%;padding:15px;margin:20px 0;"><button style="width:100%;padding:15px;background:#1e293b;color:white;border:none;border-radius:15px;font-weight:bold;">UPDATE</button></form></body>')

if __name__ == '__main__':
    app.run(debug=True)
