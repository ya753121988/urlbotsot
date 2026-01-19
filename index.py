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
# MongoDB URI আপনার এনভায়রনমেন্টে সেট না থাকলে নিচের কোটেশনে বসিয়ে দিন
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://user:pass@cluster.mongodb.net/test")
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
db = client['premium_url_bot']
urls_col = db['urls']
settings_col = db['settings']
channels_col = db['channels']
otp_col = db['otps']
ad_links_col = db['ad_links']
stats_col = db['stats']

# --- টেলিগ্রাম সেটিংস (রিকভারি ও ওটিপি এর জন্য) ---
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
            "direct_click_limit": 1,
            "main_theme": "sky", "step_theme": "blue"
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

def is_logged_in():
    return session.get('logged_in')

# --- ট্র্যাকিং ফাংশন (Internal Server Error ফিক্সড) ---
def track_click(short_code, ad_link=None):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip: ip = ip.split(',')[0]
    
    country = "Unknown"
    try:
        # কান্ট্রি ডিটেকশন (ip-api)
        res = requests.get(f"http://ip-api.com/json/{ip}", timeout=2).json()
        if res.get('status') == 'success':
            country = res.get('country', 'Unknown')
    except: pass

    # ডিভাইস ডিটেকশন
    ua = request.user_agent.string.lower()
    device = "Desktop/Laptop"
    if any(m in ua for m in ['android', 'iphone', 'ipad', 'mobile']):
        device = "Mobile"
    
    stats_col.insert_one({
        "short_code": short_code,
        "ad_link": ad_link,
        "country": country,
        "device": device,
        "timestamp": datetime.now(),
        "date": datetime.now().strftime("%Y-%m-%d")
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

# --- মূল রুট সমূহ ---

@app.route('/')
def index():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    return render_template_string(f'''
    <!DOCTYPE html><html><head><script src="https://cdn.tailwindcss.com"></script><title>{settings['site_name']}</title>
    <style>body {{ background: #0f172a; color: white; }} .glass {{ background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}</style>
    </head><body class="min-h-screen flex flex-col items-center justify-center p-6 text-center">
    <h1 class="text-7xl md:text-9xl font-black mb-6 {c['text']} italic tracking-tighter uppercase">{settings['site_name']}</h1>
    <p class="text-gray-200 mb-14 text-2xl md:text-4xl font-black uppercase tracking-widest">Premium URL System</p>
    <div class="glass p-5 rounded-[50px] w-full max-w-4xl shadow-3xl">
    <form action="/shorten" method="POST" class="flex flex-col md:flex-row gap-4">
    <input type="url" name="long_url" placeholder="PASTE YOUR LINK HERE..." required class="flex-1 bg-transparent p-6 outline-none text-white text-2xl font-black placeholder:text-gray-500">
    <button type="submit" class="{c['bg']} text-white px-14 py-6 rounded-[40px] font-black text-3xl hover:scale-105 transition uppercase shadow-2xl">Shorten</button>
    </form></div>{get_channels_html(settings.get('main_theme', 'sky'))}</body></html>''')

@app.route('/shorten', methods=['POST'])
def web_shorten():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    long_url = request.form.get('long_url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "1"})
    short_url = request.host_url + sc
    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 flex flex-col items-center justify-center min-h-screen p-4 text-white">
    <div class="bg-slate-800 p-16 rounded-[60px] shadow-2xl text-center max-w-2xl w-full border border-slate-700">
    <h2 class="text-5xl font-black mb-10 {c['text']} uppercase italic">Link Created!</h2>
    <input id="shortUrl" value="{short_url}" readonly class="w-full bg-slate-900 p-8 rounded-3xl border border-slate-700 {c['text']} font-black text-center mb-10 text-3xl">
    <button onclick="copyLink()" id="copyBtn" class="w-full {c['bg']} text-white py-8 rounded-[40px] font-black text-4xl uppercase shadow-2xl">COPY LINK</button>
    <a href="/" class="block mt-10 text-slate-500 font-black uppercase text-sm">Shorten Another</a>
    </div><script>function copyLink() {{ var copyText = document.getElementById("shortUrl"); copyText.select(); navigator.clipboard.writeText(copyText.value); document.getElementById("copyBtn").innerText = "COPIED!"; }}</script>
    </body></html>''')

# --- এডমিন প্যানেল (Dashboard & Analytics) ---

@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    
    # ডাটা কালেকশন
    all_urls = list(urls_col.find().sort("_id", -1).limit(50))
    channels = list(channels_col.find())
    ad_links = list(ad_links_col.find())
    
    # স্ট্যাটস প্রোসেসিং
    today = datetime.now().strftime("%Y-%m-%d")
    total_views = stats_col.count_documents({})
    today_views = stats_col.count_documents({"date": today})
    
    chart_labels = []
    chart_values = []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        chart_labels.append(d)
        chart_values.append(stats_col.count_documents({"date": d}))
        
    countries = list(stats_col.aggregate([{"$group": {"_id": "$country", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 5}]))
    devices = list(stats_col.aggregate([{"$group": {"_id": "$device", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]))
    
    ad_stats = []
    for al in ad_links:
        count = stats_col.count_documents({"ad_link": al['url']})
        ad_stats.append({"url": al['url'], "count": count})

    # Jinja2 দিয়ে HTML রেন্ডার করা যাতে f-string ব্র্যাকেট ঝামেলা না করে
    return render_template_string('''
    <!DOCTYPE html><html><head><title>Admin Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script><script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style> .tab-content { display: none; } .tab-content.active { display: block; } .active-btn { background: #1e293b !important; color: white !important; } body { font-family: sans-serif; } </style>
    </head><body class="bg-slate-50 flex min-h-screen">
        <!-- Sidebar -->
        <div class="w-72 bg-white border-r p-8 hidden lg:flex flex-col shadow-sm">
            <h2 class="text-2xl font-black mb-10 text-blue-600 italic tracking-tighter">PREMIUM ADMIN</h2>
            <nav class="space-y-2 flex-1">
                <button onclick="showTab('dash')" id="btn-dash" class="w-full text-left p-4 rounded-xl font-bold active-btn">📊 Dashboard</button>
                <button onclick="showTab('links')" id="btn-links" class="w-full text-left p-4 rounded-xl font-bold text-slate-500 hover:bg-slate-100">🔗 All Links</button>
                <button onclick="showTab('ads')" id="btn-ads" class="w-full text-left p-4 rounded-xl font-bold text-slate-500 hover:bg-slate-100">💰 Ads Manage</button>
                <button onclick="showTab('settings')" id="btn-settings" class="w-full text-left p-4 rounded-xl font-bold text-slate-500 hover:bg-slate-100">⚙️ Settings</button>
                <button onclick="showTab('partners')" id="btn-partners" class="w-full text-left p-4 rounded-xl font-bold text-slate-500 hover:bg-slate-100">📢 Partners</button>
            </nav>
            <a href="/logout" class="mt-auto p-4 bg-red-50 text-red-600 rounded-xl text-center font-bold">LOGOUT</a>
        </div>

        <!-- Content -->
        <div class="flex-1 p-6 lg:p-12 overflow-y-auto">
            
            <!-- Tab: Dashboard -->
            <div id="dash" class="tab-content active space-y-8">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="bg-blue-600 p-8 rounded-3xl text-white shadow-lg">
                        <p class="opacity-70 font-bold uppercase text-xs">Lifetime Views</p>
                        <h3 class="text-5xl font-black">{{total_views}}</h3>
                    </div>
                    <div class="bg-emerald-500 p-8 rounded-3xl text-white shadow-lg">
                        <p class="opacity-70 font-bold uppercase text-xs">Today's Views</p>
                        <h3 class="text-5xl font-black">{{today_views}}</h3>
                    </div>
                    <div class="bg-white p-8 rounded-3xl border shadow-sm">
                        <p class="text-slate-400 font-bold uppercase text-xs">Short Links</p>
                        <h3 class="text-5xl font-black text-slate-800">{{all_urls|length}}</h3>
                    </div>
                </div>

                <div class="grid grid-cols-1 xl:grid-cols-2 gap-8">
                    <div class="bg-white p-8 rounded-3xl border shadow-sm">
                        <h4 class="font-black mb-6 uppercase text-slate-400 text-sm">Traffic (Last 7 Days)</h4>
                        <canvas id="trafficChart"></canvas>
                    </div>
                    <div class="bg-white p-8 rounded-3xl border shadow-sm">
                        <h4 class="font-black mb-6 uppercase text-slate-400 text-sm">Devices & Countries</h4>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-xs font-bold text-blue-600 mb-2">DEVICES</p>
                                {% for d in devices %}
                                <div class="bg-slate-50 p-3 rounded-lg text-sm mb-2 flex justify-between">
                                    <span>{{d._id}}</span><b>{{d.count}}</b>
                                </div>
                                {% endfor %}
                            </div>
                            <div>
                                <p class="text-xs font-bold text-orange-600 mb-2">COUNTRIES</p>
                                {% for c in countries %}
                                <div class="bg-slate-50 p-3 rounded-lg text-sm mb-2 flex justify-between">
                                    <span>{{c._id}}</span><b>{{c.count}}</b>
                                </div>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="bg-white p-8 rounded-3xl border shadow-sm">
                    <h4 class="font-black mb-6 uppercase text-slate-400 text-sm">Direct Ad Performance</h4>
                    <div class="space-y-2">
                        {% for as in ad_stats %}
                        <div class="flex justify-between p-4 bg-slate-50 rounded-xl">
                            <span class="truncate max-w-md text-slate-600">{{as.url}}</span>
                            <span class="font-black text-emerald-600">{{as.count}} Clicks</span>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>

            <!-- Tab: Links -->
            <div id="links" class="tab-content space-y-6">
                <div class="bg-white rounded-3xl border shadow-sm overflow-hidden">
                    <table class="w-full text-left">
                        <thead class="bg-slate-50 text-xs font-bold uppercase text-slate-400">
                            <tr><th class="p-6">Date</th><th class="p-6">Code</th><th class="p-6">Original URL</th><th class="p-6">Clicks</th></tr>
                        </thead>
                        <tbody class="divide-y">
                            {% for u in all_urls %}
                            <tr class="hover:bg-slate-50">
                                <td class="p-6 text-xs text-slate-400">{{u.created_at}}</td>
                                <td class="p-6 font-bold text-blue-600">/{{u.short_code}}</td>
                                <td class="p-6 truncate max-w-xs text-slate-500 text-sm">{{u.long_url}}</td>
                                <td class="p-6 font-black">{{u.clicks}}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Tab: Ads -->
            <div id="ads" class="tab-content space-y-8">
                <div class="bg-white p-10 rounded-3xl border shadow-sm">
                    <h4 class="font-black text-xl mb-6">🔗 Manage Direct Ad Links</h4>
                    <form action="/admin/add_ad_link" method="POST" class="flex flex-col md:flex-row gap-4 mb-8">
                        <input type="url" name="ad_url" placeholder="Paste Ad Link..." required class="flex-1 p-4 bg-slate-100 rounded-2xl border-none font-bold">
                        <button class="bg-emerald-600 text-white px-10 py-4 rounded-2xl font-black uppercase">Add Link</button>
                    </form>
                    <div class="space-y-3">
                        {% for l in ad_links %}
                        <div class="flex items-center justify-between bg-slate-50 p-5 rounded-2xl">
                            <span class="truncate flex-1 font-mono text-xs">{{l.url}}</span>
                            <a href="/admin/delete_ad_link/{{l._id}}" class="bg-red-100 text-red-600 px-4 py-2 rounded-lg text-xs font-bold">DELETE</a>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>

            <!-- Tab: Settings -->
            <div id="settings" class="tab-content space-y-8">
                <form action="/admin/update" method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="bg-white p-10 rounded-3xl border shadow-sm space-y-6">
                        <h4 class="font-black text-xl">⚙️ Site Configuration</h4>
                        <input type="text" name="site_name" value="{{s.site_name}}" class="w-full p-4 bg-slate-100 rounded-xl font-bold">
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="text-xs font-bold text-slate-400 block mb-2">AD STEPS</label><input type="number" name="steps" value="{{s.steps}}" class="w-full p-4 bg-slate-100 rounded-xl font-bold"></div>
                            <div><label class="text-xs font-bold text-slate-400 block mb-2">TIMER (SEC)</label><input type="number" name="timer_seconds" value="{{s.timer_seconds}}" class="w-full p-4 bg-slate-100 rounded-xl font-bold"></div>
                        </div>
                        <input type="text" name="admin_telegram_id" value="{{s.admin_telegram_id}}" placeholder="Telegram Admin ID" class="w-full p-4 bg-slate-100 rounded-xl font-bold">
                        <input type="password" name="new_password" placeholder="New Password (Leave blank to keep same)" class="w-full p-4 bg-red-50 rounded-xl font-bold">
                    </div>
                    <div class="bg-white p-10 rounded-3xl border shadow-sm space-y-4">
                        <h4 class="font-black text-xl text-emerald-600">💰 Scripts & Monetization</h4>
                        <textarea name="popunder" placeholder="Popunder Script" class="w-full h-24 p-4 bg-slate-100 rounded-xl text-xs font-mono">{{s.popunder}}</textarea>
                        <textarea name="banner" placeholder="Banner Script" class="w-full h-24 p-4 bg-slate-100 rounded-xl text-xs font-mono">{{s.banner}}</textarea>
                        <textarea name="social_bar" placeholder="Social Bar Script" class="w-full h-24 p-4 bg-slate-100 rounded-xl text-xs font-mono">{{s.social_bar}}</textarea>
                        <button class="w-full bg-slate-900 text-white py-6 rounded-3xl font-black text-xl shadow-xl">SAVE SETTINGS</button>
                    </div>
                </form>
            </div>

            <!-- Tab: Partners -->
            <div id="partners" class="tab-content">
                <div class="bg-white p-10 rounded-3xl border shadow-sm">
                    <h4 class="font-black text-xl mb-6">📢 Official Channels</h4>
                    <form action="/admin/add_channel" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
                        <input type="text" name="name" placeholder="Name" required class="p-4 bg-slate-100 rounded-xl">
                        <input type="url" name="logo" placeholder="Banners Logo URL" required class="p-4 bg-slate-100 rounded-xl">
                        <input type="url" name="link" placeholder="Invite Link" required class="p-4 bg-slate-100 rounded-xl">
                        <button class="bg-blue-600 text-white rounded-xl font-bold">ADD CHANNEL</button>
                    </form>
                    <div class="space-y-6">
                        {% for ch in channels %}
                        <div class="flex items-center gap-6 p-4 bg-slate-50 rounded-2xl">
                            <img src="{{ch.logo}}" class="w-40 h-24 object-cover rounded-lg">
                            <div class="flex-1">
                                <p class="font-black uppercase">{{ch.name}}</p>
                                <p class="text-xs text-slate-400">{{ch.link}}</p>
                            </div>
                            <a href="/admin/delete_channel/{{ch._id}}" class="text-red-500 font-bold px-6">DELETE</a>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>

        </div>

        <script>
            function showTab(id) {
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                document.querySelectorAll('nav button').forEach(b => b.classList.remove('active-btn'));
                document.getElementById(id).classList.add('active');
                document.getElementById('btn-'+id).classList.add('active-btn');
            }

            const ctx = document.getElementById('trafficChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: {{chart_labels|tojson}},
                    datasets: [{
                        label: 'Views',
                        data: {{chart_values|tojson}},
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 4
                    }]
                },
                options: { responsive: true, plugins: { legend: { display: false } } }
            });
        </script>
    </body></html>
    ''', total_views=total_views, today_views=today_views, all_urls=all_urls, countries=countries, 
        devices=devices, ad_stats=ad_stats, ad_links=ad_links, channels=channels, s=settings,
        chart_labels=chart_labels, chart_values=chart_values)

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
        "social_bar": request.form.get('social_bar')
    }
    new_pass = request.form.get('new_password')
    if new_pass and len(new_pass) > 2:
        d["admin_password"] = generate_password_hash(new_pass)
    settings_col.update_one({}, {"$set": d})
    return redirect(url_for('admin_panel'))

# --- রিডাইরেক্ট ও ট্র্যাকিং লজিক ---

@app.route('/<short_code>')
def handle_ad_steps(short_code):
    step = int(request.args.get('step', 1))
    settings = get_settings()
    url_data = urls_col.find_one({"short_code": short_code})
    if not url_data: return "404 Not Found", 404
    
    if step > settings['steps']:
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        track_click(short_code) # মেইন ভিউ ট্র্যাকিং
        return redirect(url_data['long_url'])
    
    all_ads = [l['url'] for l in ad_links_col.find()]
    tc = COLOR_MAP.get(settings.get('step_theme', 'blue'), COLOR_MAP['blue'])
    
    return render_template_string('''
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    {{ s.popunder | safe }} {{ s.social_bar | safe }}
    </head><body class="bg-slate-50 flex flex-col items-center p-6 min-h-screen">
        <div class="mb-6">{{ s.banner | safe }}</div>
        <div class="bg-white p-12 md:p-20 rounded-[70px] shadow-2xl text-center max-w-2xl w-full border-t-[16px] {{tc.border}}">
            <p class="text-xl md:text-2xl font-black {{tc.text}} uppercase tracking-widest mb-4">Step {{step}} of {{total_steps}}</p>
            <h2 class="text-3xl md:text-5xl font-black text-slate-900 mb-8 tracking-tighter italic">Verifying User...</h2>
            <div id="timer_box" class="text-7xl md:text-8xl font-black {{tc.text}} mb-8 {{tc.light_bg}} w-40 h-40 md:w-48 md:h-48 flex items-center justify-center rounded-full mx-auto border-8 {{tc.border}} shadow-inner">{{timer}}</div>
            <button id="main_btn" onclick="handleClick()" class="hidden w-full {{tc.bg}} text-white py-8 rounded-[40px] font-black text-3xl uppercase shadow-2xl transition hover:scale-105">Continue</button>
        </div>
        <div class="mt-8">{{ partners_html | safe }}</div>

        <script>
            let sec = {{timer}};
            let ads = {{ads | tojson}};
            let clicks = 0;
            let limit = {{limit}};
            const timerBox = document.getElementById('timer_box');
            const mainBtn = document.getElementById('main_btn');

            const countdown = setInterval(() => {
                sec--;
                timerBox.innerText = sec;
                if(sec <= 0) {
                    clearInterval(countdown);
                    timerBox.style.display = 'none';
                    mainBtn.classList.remove('hidden');
                    updateBtn();
                }
            }, 1000);

            function updateBtn() {
                if(clicks < limit && ads.length > 0) {
                    mainBtn.innerText = "VERIFY (" + (clicks + 1) + "/" + limit + ")";
                } else {
                    mainBtn.innerText = "CONTINUE TO STEP " + ({{step}} + 1);
                }
            }

            function handleClick() {
                if(clicks < limit && ads.length > 0) {
                    let targetAd = ads[Math.floor(Math.random() * ads.length)];
                    // এড ক্লিক ট্র্যাকিং (ব্যাকগ্রাউন্ডে)
                    fetch('/track_click?sc={{sc}}&ad=' + encodeURIComponent(targetAd));
                    window.open(targetAd, '_blank');
                    clicks++;
                    updateBtn();
                } else {
                    window.location.href = "/{{sc}}?step=" + ({{step}} + 1);
                }
            }
        </script>
    </body></html>
    ''', s=settings, step=step, total_steps=settings['steps'], timer=settings['timer_seconds'], 
        tc=tc, ads=all_ads, limit=settings['direct_click_limit'], sc=short_code, 
        partners_html=get_channels_html(settings.get('step_theme', 'blue')))

@app.route('/track_click')
def ajax_track():
    sc = request.args.get('sc')
    ad = request.args.get('ad')
    if sc: track_click(sc, ad)
    return "ok"

# --- লগইন ও সিকিউরিটি ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        return "Access Denied!"
    return render_template_string('''<body style="background:#0f172a;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;"><form method="POST" style="background:white;padding:50px;border-radius:40px;text-align:center;box-shadow:0 0 50px rgba(0,0,0,0.5);"><h2 style="font-weight:900;margin-bottom:30px;font-size:24px;">ADMIN PORTAL</h2><input type="password" name="password" placeholder="Key" style="padding:15px;border-radius:15px;border:1px solid #eee;width:250px;display:block;margin-bottom:15px;background:#f9f9f9;outline:none;text-align:center;font-weight:bold;"><button style="width:100%;padding:15px;background:#1e293b;color:white;border:none;border-radius:15px;font-weight:900;cursor:pointer;">UNLOCK</button></form></body>''')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
