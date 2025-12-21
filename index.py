import os
import random
import string
import requests  # টেলিগ্রাম API কলের জন্য ইমপোর্ট করা হয়েছে
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta # timedelta যুক্ত করা হয়েছে ওটিপি মেয়াদের জন্য
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
otp_col = db['otps'] # OTP স্টোর করার জন্য কালেকশন

# --- টেলিগ্রাম সেটিংস ---
# আপনার টেলিগ্রাম বট টোকেনটি এখানে দিন অথবা এনভায়রনমেন্ট ভেরিয়েবলে সেট করুন
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8469682967:AAEWrNWBWjiYT3_L47Xe_byORfD6IIsFD34")

# --- থিম কালার ম্যাপ ---
COLOR_MAP = {
    "red": {"text": "text-red-500", "bg": "bg-red-600", "border": "border-red-500", "hover": "hover:bg-red-700", "light_bg": "bg-red-50"},
    "orange": {"text": "text-orange-500", "bg": "bg-orange-600", "border": "border-orange-500", "hover": "hover:bg-orange-700", "light_bg": "bg-orange-50"},
    "yellow": {"text": "text-yellow-500", "bg": "bg-yellow-500", "border": "border-yellow-500", "hover": "hover:bg-yellow-600", "light_bg": "bg-yellow-50"},
    "green": {"text": "text-green-500", "bg": "bg-green-600", "border": "border-green-500", "hover": "hover:bg-green-700", "light_bg": "bg-green-50"},
    "blue": {"text": "text-blue-500", "bg": "bg-blue-600", "border": "border-blue-500", "hover": "hover:bg-blue-700", "light_bg": "bg-blue-50"},
    "sky": {"text": "text-sky-400", "bg": "bg-sky-500", "border": "border-sky-400", "hover": "hover:bg-sky-600", "light_bg": "bg-sky-50"},
    "purple": {"text": "text-purple-500", "bg": "bg-purple-600", "border": "border-purple-500", "hover": "hover:bg-purple-700", "light_bg": "bg-purple-50"}
}

def get_settings():
    settings = settings_col.find_one()
    if not settings:
        default_settings = {
            "site_name": "Premium URL Shortener",
            "admin_telegram_id": "", # রিকভারি চ্যাট আইডি
            "steps": 2,
            "timer_seconds": 10,
            "admin_password": generate_password_hash("admin123"),
            "api_key": ''.join(random.choices(string.ascii_lowercase + string.digits, k=40)),
            "popunder": "",
            "banner": "",
            "social_bar": "",
            "native": "",
            "direct_link": "https://google.com", 
            "direct_click_limit": 1,
            "main_theme": "sky",
            "step_theme": "blue"
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

def is_logged_in():
    return session.get('logged_in')

def get_channels_html(theme_color="sky"):
    channels = list(channels_col.find())
    if not channels: return ""
    c = COLOR_MAP.get(theme_color, COLOR_MAP['sky'])
    
    html = f'''
    <div class="w-full max-w-4xl mx-auto mt-10 mb-6 p-6 rounded-[35px] border border-white/10 glass shadow-2xl">
        <h3 class="text-center {c['text']} font-black mb-6 uppercase tracking-[0.2em] text-xs">Premium Partner Channels</h3>
        <div class="flex flex-wrap justify-center gap-6">
    '''
    for ch in channels:
        html += f'''
        <a href="{ch['link']}" target="_blank" class="flex items-center gap-3 p-3 px-5 rounded-2xl bg-white/5 border border-white/5 hover:bg-white/10 hover:border-white/20 transition duration-300 group">
            <img src="{ch['logo']}" class="w-12 h-12 rounded-full object-cover border-2 border-white/10 group-hover:border-white/30 transition">
            <div class="text-left">
                <p class="text-[10px] text-gray-400 font-bold uppercase tracking-tighter">Join Our</p>
                <p class="text-sm font-black text-gray-100 italic">CHANNEL</p>
            </div>
        </a>'''
    return html + '</div></div>'

# --- API সিস্টেম ---
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
        return jsonify({"status": "error", "message": "Missing URL"}) if res_format != 'text' else "Error: Missing URL"

    short_code = alias if alias else ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    if alias and urls_col.find_one({"short_code": alias}):
        return jsonify({"status": "error", "message": "Alias exists"}) if res_format != 'text' else "Error: Alias exists"

    urls_col.insert_one({
        "long_url": long_url, 
        "short_code": short_code, 
        "clicks": 0, 
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), 
        "type": ad_type
    })
    shortened_url = request.host_url + short_code
    return shortened_url if res_format == 'text' else jsonify({"status": "success", "shortenedUrl": shortened_url})

# --- হোম পেজ ---
@app.route('/')
def index():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    channel_box = get_channels_html(settings.get('main_theme', 'sky'))
    return render_template_string(f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <title>{settings['site_name']} - Premium URL Shortener</title>
        <style>body {{ background: #0f172a; color: white; }} .glass {{ background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}</style>
    </head>
    <body class="min-h-screen flex flex-col items-center justify-center p-6">
        <h1 class="text-6xl md:text-8xl font-black mb-4 {c['text']} italic tracking-tighter">{settings['site_name']}</h1>
        <p class="text-gray-400 mb-12 text-lg font-medium">Fast, Secure and Highly Rewarding URL Shortener.</p>
        <div class="glass p-3 rounded-[40px] w-full max-w-3xl shadow-2xl">
            <form action="/shorten" method="POST" class="flex flex-col md:flex-row gap-2">
                <input type="url" name="long_url" placeholder="Paste your long link here..." required class="flex-1 bg-transparent p-6 outline-none text-white text-lg">
                <button type="submit" class="{c['bg']} text-white px-12 py-6 rounded-[30px] font-black text-xl hover:scale-105 transition uppercase tracking-widest shadow-xl">Shorten</button>
            </form>
        </div>
        {channel_box}
    </body></html>
    ''')

# --- রেজাল্ট পেজ ---
@app.route('/shorten', methods=['POST'])
def web_shorten():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    long_url = request.form.get('long_url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "1"})
    final_url = request.host_url + sc
    channel_box = get_channels_html(settings.get('main_theme', 'sky'))
    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script>
    <style>body {{ background: #0f172a; color: white; }} .glass {{ background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}</style>
    </head>
    <body class="bg-slate-900 flex flex-col items-center justify-center min-h-screen p-4 text-white">
        <div class="bg-slate-800 p-12 rounded-[50px] shadow-2xl text-center max-w-lg w-full border border-slate-700">
            <h2 class="text-3xl font-black mb-8 {c['text']}">Link Created!</h2>
            <input id="shortUrl" value="{final_url}" readonly class="w-full bg-slate-900 p-6 rounded-3xl border border-slate-700 {c['text']} font-black text-center mb-8 text-xl">
            <button onclick="copyLink()" id="copyBtn" class="w-full {c['bg']} text-white py-6 rounded-3xl font-black text-2xl uppercase transition">COPY LINK</button>
            <a href="/" class="block mt-8 text-slate-500 font-bold uppercase text-xs hover:text-white transition">Shorten Another</a>
        </div>
        {channel_box}
        <script>function copyLink() {{ var copyText = document.getElementById("shortUrl"); copyText.select(); navigator.clipboard.writeText(copyText.value); document.getElementById("copyBtn").innerText = "COPIED!"; }}</script>
    </body></html>
    ''')

# --- এডমিন ড্যাশবোর্ড ---
@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    all_urls = list(urls_col.find().sort("_id", -1))
    total_clicks = sum(u.get('clicks', 0) for u in all_urls)
    channels = list(channels_col.find())
    theme_options = ["red", "orange", "yellow", "green", "blue", "sky", "purple"]

    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&display=swap" rel="stylesheet">
    <style>body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}</style>
    </head>
    <body class="bg-gray-100 text-slate-800">
        <div class="flex flex-col lg:flex-row min-h-screen">
            <!-- Sidebar -->
            <div class="lg:w-80 bg-slate-900 text-white p-10">
                <h2 class="text-3xl font-black text-sky-400 mb-12 italic">ADMIN PRO</h2>
                <div class="space-y-6">
                    <div class="bg-slate-800 p-6 rounded-3xl border border-slate-700">
                        <p class="text-xs text-slate-400 font-bold uppercase">Links</p>
                        <p class="text-3xl font-black">{len(all_urls)}</p>
                    </div>
                    <div class="bg-slate-800 p-6 rounded-3xl border border-slate-700">
                        <p class="text-xs text-slate-400 font-bold uppercase">Total Clicks</p>
                        <p class="text-3xl font-black text-emerald-400">{total_clicks}</p>
                    </div>
                    <a href="/logout" class="block bg-red-500 p-5 rounded-2xl text-center font-black uppercase text-sm tracking-widest shadow-xl">Logout</a>
                </div>
            </div>

            <div class="flex-1 p-8 lg:p-16 overflow-y-auto">
                <h1 class="text-4xl font-black mb-12 tracking-tight">System Controls</h1>
                
                <form action="/admin/update" method="POST" class="grid grid-cols-1 xl:grid-cols-2 gap-10">
                    <!-- Config -->
                    <div class="bg-white p-10 rounded-[50px] shadow-sm border space-y-6">
                        <h3 class="font-black text-xl border-b pb-4">⚙️ General & Appearance</h3>
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="text-xs font-bold text-gray-400">Home Theme</label>
                            <select name="main_theme" class="w-full bg-gray-50 p-4 rounded-2xl border">{"".join([f'<option value="{o}" {"selected" if settings.get("main_theme")==o else ""}>{o.capitalize()}</option>' for o in theme_options])}</select></div>
                            <div><label class="text-xs font-bold text-gray-400">Step Theme</label>
                            <select name="step_theme" class="w-full bg-gray-50 p-4 rounded-2xl border">{"".join([f'<option value="{o}" {"selected" if settings.get("step_theme")==o else ""}>{o.capitalize()}</option>' for o in theme_options])}</select></div>
                        </div>
                        <input type="text" name="site_name" value="{settings['site_name']}" class="w-full bg-gray-50 p-5 rounded-2xl border font-bold" placeholder="Website Name">
                        
                        <!-- নতুন: টেলিগ্রাম আইডি ইনপুট -->
                        <label class="text-xs font-bold text-blue-600">Telegram Chat ID (রিকভারির জন্য)</label>
                        <input type="text" name="admin_telegram_id" value="{settings.get('admin_telegram_id', '')}" class="w-full bg-blue-50 p-5 rounded-2xl border font-bold" placeholder="Example: 12345678">

                        <div class="grid grid-cols-2 gap-4">
                            <input type="number" name="steps" value="{settings['steps']}" class="w-full bg-gray-50 p-5 rounded-2xl border" placeholder="Ad Steps">
                            <input type="number" name="timer_seconds" value="{settings['timer_seconds']}" class="w-full bg-gray-50 p-5 rounded-2xl border" placeholder="Timer (Sec)">
                        </div>
                        <label class="text-xs font-bold text-blue-600">Direct Ad Link</label>
                        <input type="url" name="direct_link" value="{settings['direct_link']}" class="w-full bg-blue-50 p-5 rounded-2xl border font-bold" placeholder="https://ad-link.com">
                        <label class="text-xs font-bold text-blue-600">Click Limit</label>
                        <input type="number" name="direct_click_limit" value="{settings['direct_click_limit']}" class="w-full bg-blue-50 p-5 rounded-2xl border font-bold">
                        
                        <label class="text-xs font-bold text-gray-400">Manage API Key</label>
                        <input type="text" name="api_key" value="{settings['api_key']}" class="w-full bg-gray-100 p-4 rounded-2xl text-xs font-mono border border-blue-100">
                        
                        <input type="password" name="new_password" placeholder="Change Admin Password" class="w-full bg-red-50 p-5 rounded-2xl border">
                    </div>

                    <!-- Ads -->
                    <div class="bg-white p-10 rounded-[50px] shadow-sm border space-y-5">
                        <h3 class="font-black text-xl border-b pb-4 text-emerald-600">💰 Script Management</h3>
                        <textarea name="popunder" placeholder="Popunder Script" class="w-full bg-gray-50 p-4 h-24 rounded-2xl text-xs font-mono border">{settings['popunder']}</textarea>
                        <textarea name="banner" placeholder="Banner Script" class="w-full bg-gray-50 p-4 h-24 rounded-2xl text-xs font-mono border">{settings['banner']}</textarea>
                        <textarea name="social_bar" placeholder="Social Bar Script" class="w-full bg-gray-50 p-4 h-24 rounded-2xl text-xs font-mono border">{settings['social_bar']}</textarea>
                        <textarea name="native" placeholder="Native/Bottom Script" class="w-full bg-gray-50 p-4 h-24 rounded-2xl text-xs font-mono border">{settings['native']}</textarea>
                    </div>
                    <button class="xl:col-span-2 bg-slate-900 text-white p-7 rounded-[35px] font-black text-2xl shadow-2xl hover:bg-black transition">UPDATE ALL SETTINGS</button>
                </form>

                <!-- Channels -->
                <h2 class="text-3xl font-black mt-20 mb-8">📢 Manage Channels</h2>
                <div class="bg-white p-10 rounded-[50px] border shadow-sm">
                    <form action="/admin/add_channel" method="POST" class="grid grid-cols-1 md:grid-cols-3 gap-6 items-end">
                        <div><label class="text-xs font-bold text-gray-400 mb-1 block">Logo Image URL</label>
                        <input type="url" name="logo" required class="w-full bg-gray-50 p-4 rounded-xl border"></div>
                        <div><label class="text-xs font-bold text-gray-400 mb-1 block">Target Link</label>
                        <input type="url" name="link" required class="w-full bg-gray-50 p-4 rounded-xl border"></div>
                        <button class="bg-cyan-500 text-white p-4 rounded-xl font-black uppercase text-sm">Add New Channel</button>
                    </form>
                    <div class="mt-10 flex flex-wrap gap-6">
                        {" ".join([f'''
                        <div class="flex items-center gap-4 bg-gray-50 p-4 rounded-2xl border relative group">
                            <img src="{c['logo']}" class="w-12 h-12 rounded-full object-cover">
                            <a href="/admin/delete_channel/{c['_id']}" class="absolute -top-2 -right-2 bg-red-500 text-white w-6 h-6 rounded-full text-center text-xs leading-6 font-bold">×</a>
                        </div>''' for c in channels])}
                    </div>
                </div>

                <!-- History -->
                <h2 class="text-3xl font-black mt-20 mb-8 tracking-tight">🔗 Link Management</h2>
                <div class="bg-white rounded-[40px] border shadow-sm overflow-hidden">
                    <table class="w-full text-left">
                        <thead class="bg-gray-50 text-[11px] font-black uppercase tracking-widest text-gray-400">
                            <tr><th class="p-8">Created</th><th class="p-8">Short Code</th><th class="p-8">Destination URL</th><th class="p-8 text-center">Clicks</th></tr>
                        </thead>
                        <tbody class="divide-y text-sm font-semibold">
                            {" ".join([f'''
                            <tr class="hover:bg-slate-50 transition">
                                <td class="p-8 text-gray-400 font-medium text-xs">{u.get('created_at','N/A')}</td>
                                <td class="p-8 text-blue-600 font-bold">/{u['short_code']}</td>
                                <td class="p-8 text-gray-500 truncate max-w-[200px]">{u['long_url']}</td>
                                <td class="p-8 text-center"><span class="bg-emerald-100 text-emerald-700 px-4 py-2 rounded-full font-black">{u['clicks']}</span></td>
                            </tr>''' for u in all_urls])}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body></html>
    ''')

# --- এডমিন অ্যাকশন রুটস ---
@app.route('/admin/add_channel', methods=['POST'])
def add_channel():
    if not is_logged_in(): return redirect(url_for('login'))
    logo, link = request.form.get('logo'), request.form.get('link')
    if logo and link: channels_col.insert_one({"logo": logo, "link": link})
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_channel/<id>')
def delete_channel(id):
    if not is_logged_in(): return redirect(url_for('login'))
    channels_col.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('admin_panel'))

# --- রিডাইরেক্ট লজিক ---
@app.route('/<short_code>')
def handle_ad_steps(short_code):
    step = int(request.args.get('step', 1))
    settings = get_settings()
    url_data = urls_col.find_one({"short_code": short_code})
    tc = COLOR_MAP.get(settings.get('step_theme', 'blue'), COLOR_MAP['blue'])
    channel_box = get_channels_html(settings.get('step_theme', 'blue'))
    
    if not url_data: return "404 - Link Not Found", 404
    if url_data.get('type') == '0' or step > settings['steps']:
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        return redirect(url_data['long_url'])

    return render_template_string(f'''
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script>
    {settings['popunder']} {settings['social_bar']}
    </head>
    <body class="bg-slate-50 flex flex-col items-center justify-center min-h-screen p-4">
        <div class="mb-4">{settings['banner']}</div>
        <div class="bg-white p-12 md:p-20 rounded-[70px] shadow-2xl text-center max-w-md w-full border-t-[12px] {tc['border']}">
            <p class="text-[11px] font-black {tc['text']} uppercase tracking-[0.3em] mb-4">Step {step}/{settings['steps']}</p>
            <h2 class="text-3xl font-black text-slate-900 mb-10 tracking-tighter italic">Ready to Proceed?</h2>
            <div id="timer" class="text-7xl font-black {tc['text']} mb-12 {tc['light_bg']} w-32 h-32 flex items-center justify-center rounded-full mx-auto border-4 {tc['border']} italic shadow-inner">{settings['timer_seconds']}</div>
            <button id="btn" onclick="handleClick()" class="hidden w-full {tc['bg']} text-white py-7 rounded-[35px] font-black text-2xl uppercase shadow-2xl hover:scale-105 transition tracking-widest">Continue</button>
        </div>
        <div class="mt-10">{settings['native']}</div>
        {channel_box}
        <script>
            let t = {settings['timer_seconds']};
            let clicks = 0; let limit = {settings['direct_click_limit']};
            let dLink = "{settings['direct_link']}";
            const timerDiv = document.getElementById('timer'); const btn = document.getElementById('btn');
            const iv = setInterval(() => {{ t--; timerDiv.innerText = t; if(t <= 0) {{ clearInterval(iv); timerDiv.classList.add('hidden'); btn.classList.remove('hidden'); updateBtn(); }} }}, 1000);
            function updateBtn() {{ if (clicks < limit && dLink !== "") btn.innerText = "CONTINUE (" + (clicks + 1) + "/" + limit + ")"; else btn.innerText = "NEXT STEP"; }}
            function handleClick() {{ if (clicks < limit && dLink !== "") {{ window.open(dLink, '_blank'); clicks++; updateBtn(); }} else {{ window.location.href = "/{short_code}?step={step + 1}"; }} }}
        </script>
    </body></html>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        return "Wrong Password!"
    return render_template_string('''
    <body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh;">
        <form method="POST" style="background:white; padding:60px; border-radius:40px; box-shadow:0 20px 80px rgba(0,0,0,0.4); text-align:center;">
            <h2 style="font-family:sans-serif; font-weight:900; margin-bottom:30px; letter-spacing:-1px;">ADMIN ACCESS</h2>
            <input type="password" name="password" placeholder="Key" style="padding:18px; border-radius:20px; border:1px solid #eee; width:280px; display:block; margin-bottom:15px; background:#f9f9f9; outline:none; font-weight:bold; text-align:center;">
            <button style="width:100%; padding:18px; background:#1e293b; color:white; border:none; border-radius:20px; font-weight:900; cursor:pointer; text-transform:uppercase; letter-spacing:2px;">Unlock</button>
            <a href="/forgot-password" style="display:block; margin-top:20px; font-family:sans-serif; font-size:12px; color:gray; text-decoration:none;">Forgot Password?</a>
        </form>
    </body>''')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.post('/admin/update')
def update_settings():
    if not is_logged_in(): return redirect(url_for('login'))
    
    d = {
        "site_name": request.form.get('site_name'),
        "admin_telegram_id": request.form.get('admin_telegram_id'), # আপডেট
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
        "api_key": request.form.get('api_key')
    }
    
    new_pass = request.form.get('new_password')
    if new_pass and len(new_pass) > 2: d["admin_password"] = generate_password_hash(new_pass)
    settings_col.update_one({}, {"$set": d})
    return redirect(url_for('admin_panel'))

# --- রিকভারি লজিক ---
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        tg_id = request.form.get('telegram_id')
        settings = get_settings()
        if tg_id and tg_id == settings.get('admin_telegram_id'):
            otp = str(random.randint(100000, 999999))
            otp_col.update_one({"id": "admin_reset"}, {"$set": {"otp": otp, "expire_at": datetime.now() + timedelta(minutes=5)}}, upsert=True)
            token = TELEGRAM_BOT_TOKEN
            msg = f"🛡️ Admin Reset OTP: {otp}"
            try:
                requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": tg_id, "text": msg})
                session['reset_id'] = tg_id
                return redirect(url_for('verify_otp'))
            except Exception as e:
                return f"Bot Token Error or Network Issue: {str(e)}"
        return "Invalid ID!"
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;"><form method="POST" style="background:white; padding:40px; border-radius:30px; width:320px;"><h2 style="text-align:center;">Recovery</h2><input type="text" name="telegram_id" placeholder="Telegram Chat ID" required style="width:100%; padding:15px; border-radius:15px; border:1px solid #ddd; margin:20px 0; text-align:center;"><button style="width:100%; padding:15px; background:#3b82f6; color:white; border:none; border-radius:15px; font-weight:bold; cursor:pointer;">Send OTP</button><a href="/login" style="display:block; text-align:center; margin-top:15px; font-size:12px; color:#3b82f6; text-decoration:none;">Back to Login</a></form></body>')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if not session.get('reset_id'): return redirect('/forgot-password')
    if request.method == 'POST':
        otp = request.form.get('otp')
        data = otp_col.find_one({"id": "admin_reset"})
        if data and data['otp'] == otp and data['expire_at'] > datetime.now():
            session['otp_verified'] = True
            return redirect(url_for('reset_password'))
        return "Wrong OTP or Expired!"
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;"><form method="POST" style="background:white; padding:40px; border-radius:30px; width:320px;"><h2 style="text-align:center;">Verify</h2><input type="text" name="otp" placeholder="Enter OTP" required style="width:100%; padding:15px; border-radius:15px; border:1px solid #ddd; margin:20px 0; text-align:center; font-size:20px; font-weight:bold; letter-spacing:5px;"><button style="width:100%; padding:15px; background:#10b981; color:white; border:none; border-radius:15px; font-weight:bold; cursor:pointer;">Verify</button></form></body>')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'): return redirect('/forgot-password')
    if request.method == 'POST':
        pw = request.form.get('password')
        settings_col.update_one({}, {"$set": {"admin_password": generate_password_hash(pw)}})
        session.clear()
        return 'Password Updated Successfully! <a href="/login">Login Now</a>'
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;"><form method="POST" style="background:white; padding:40px; border-radius:30px; width:320px;"><h2 style="text-align:center;">New Password</h2><input type="password" name="password" placeholder="Enter New Password" required style="width:100%; padding:15px; border-radius:15px; border:1px solid #ddd; margin:20px 0; outline:none;"><button style="width:100%; padding:15px; background:#1e293b; color:white; border:none; border-radius:15px; font-weight:bold; cursor:pointer;">Update Password</button></form></body>')

if __name__ == '__main__':
    app.run()
