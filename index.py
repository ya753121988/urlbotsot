import os
import random
import string
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "premium-super-secret-2025")

# --- ডাটাবেস কানেকশন ---
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
            "banner": "",
            "social_bar": "",
            "native": "",
            "direct_link": "https://google.com", 
            "direct_click_limit": 1 
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

def is_logged_in():
    return session.get('logged_in')

# --- ১. প্রফেশনাল এপিআই সিস্টেম (Fixed) ---
@app.route('/api')
def api_system():
    settings = get_settings()
    api_token = request.args.get('api')
    long_url = request.args.get('url')
    alias = request.args.get('alias')
    res_format = request.args.get('format', 'json').lower()
    ad_type = request.args.get('type', '1') # 1 = Ads, 0 = Direct

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
    if res_format == 'text': return shortened_url
    return jsonify({"status": "success", "shortenedUrl": shortened_url})

# --- ২. মেইন হোম পেজ ---
@app.route('/')
def index():
    settings = get_settings()
    return render_template_string(f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <title>{settings['site_name']}</title>
        <style>body {{ background: #0f172a; color: white; }} .glass {{ background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); }}</style>
    </head>
    <body class="min-h-screen flex flex-col items-center justify-center p-6 text-center">
        <h1 class="text-6xl font-black mb-4 text-cyan-400 italic">{settings['site_name']}</h1>
        <p class="text-gray-400 mb-10">Premium URL Shortening Solution with Multi-Step Ads</p>
        <div class="glass p-3 rounded-3xl w-full max-w-2xl border border-white/10">
            <form action="/shorten" method="POST" class="flex flex-col md:flex-row gap-2">
                <input type="url" name="long_url" placeholder="Paste link here..." required class="flex-1 bg-transparent p-5 outline-none text-white">
                <button type="submit" class="bg-cyan-500 text-slate-900 px-10 py-5 rounded-2xl font-black">SHORTEN</button>
            </form>
        </div>
    </body></html>
    ''')

# --- ৩. লিঙ্ক শর্ট রেজাল্ট পেজ ---
@app.route('/shorten', methods=['POST'])
def web_shorten():
    long_url = request.form.get('long_url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "1"})
    final_url = request.host_url + sc
    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 flex items-center justify-center min-h-screen p-4 text-white">
        <div class="bg-slate-800 p-10 rounded-[40px] text-center max-w-lg w-full border border-slate-700">
            <h2 class="text-2xl font-bold mb-6 text-cyan-400">Your Link is Ready!</h2>
            <input id="shortUrl" value="{final_url}" readonly class="w-full bg-slate-900 p-5 rounded-2xl text-cyan-400 font-bold text-center mb-6">
            <button onclick="copyLink()" id="copyBtn" class="w-full bg-cyan-500 text-slate-900 py-5 rounded-2xl font-black">COPY LINK</button>
            <a href="/" class="block mt-6 text-slate-500">Shorten Another</a>
        </div>
        <script>function copyLink() {{ var copyText = document.getElementById("shortUrl"); copyText.select(); navigator.clipboard.writeText(copyText.value); document.getElementById("copyBtn").innerText = "COPIED!"; }}</script>
    </body></html>
    ''')

# --- ৪. প্রিমিয়াম এডমিন ড্যাশবোর্ড (সব ফিউচার সহ) ---
@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    all_urls = list(urls_col.find().sort("_id", -1))
    total_clicks = sum(u.get('clicks', 0) for u in all_urls)

    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-gray-100 font-sans">
        <div class="flex flex-col lg:flex-row min-h-screen">
            <div class="lg:w-64 bg-slate-900 text-white p-6">
                <h2 class="text-2xl font-black text-cyan-400 mb-10">ADMIN PRO</h2>
                <div class="space-y-4">
                    <div class="bg-white/10 p-4 rounded-xl">Links: <b>{len(all_urls)}</b></div>
                    <div class="bg-white/10 p-4 rounded-xl">Clicks: <b>{total_clicks}</b></div>
                    <a href="/logout" class="block bg-red-500 p-4 rounded-xl text-center font-bold">Logout</a>
                </div>
            </div>
            <div class="flex-1 p-6 lg:p-12 overflow-y-auto">
                <h1 class="text-3xl font-black mb-8">System Settings</h1>
                <form action="/admin/update" method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="bg-white p-8 rounded-[30px] shadow-sm space-y-4">
                        <h3 class="font-bold border-b pb-2">⚙️ Basic Config</h3>
                        <label class="text-xs font-bold text-gray-400">Site Name</label>
                        <input type="text" name="site_name" value="{settings['site_name']}" class="w-full bg-gray-50 p-4 rounded-xl">
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="text-xs font-bold text-gray-400">Steps</label>
                            <input type="number" name="steps" value="{settings['steps']}" class="w-full bg-gray-50 p-4 rounded-xl"></div>
                            <div><label class="text-xs font-bold text-gray-400">Timer (Sec)</label>
                            <input type="number" name="timer_seconds" value="{settings['timer_seconds']}" class="w-full bg-gray-50 p-4 rounded-xl"></div>
                        </div>
                        <label class="text-xs font-bold text-blue-600">Direct Link (Redirect Ad)</label>
                        <input type="url" name="direct_link" value="{settings['direct_link']}" class="w-full bg-blue-50 p-4 rounded-xl">
                        <label class="text-xs font-bold text-blue-600">Direct Link Click Limit (Per Step)</label>
                        <input type="number" name="direct_click_limit" value="{settings['direct_click_limit']}" class="w-full bg-blue-50 p-4 rounded-xl">
                        <label class="text-xs font-bold text-red-500">New Password (Leave blank to keep same)</label>
                        <input type="password" name="new_password" class="w-full bg-red-50 p-4 rounded-xl">
                        <label class="text-xs font-bold text-gray-400">Developer API Key</label>
                        <input type="text" name="api_key" value="{settings['api_key']}" readonly class="w-full bg-gray-200 p-4 rounded-xl text-xs font-mono">
                    </div>
                    <div class="bg-white p-8 rounded-[30px] shadow-sm space-y-4">
                        <h3 class="font-bold border-b pb-2">💰 Ad Scripts Box</h3>
                        <textarea name="popunder" placeholder="Popunder Code" class="w-full bg-gray-50 p-4 h-24 rounded-xl text-xs">{settings['popunder']}</textarea>
                        <textarea name="banner" placeholder="Banner Ad Code" class="w-full bg-gray-50 p-4 h-24 rounded-xl text-xs">{settings['banner']}</textarea>
                        <textarea name="social_bar" placeholder="Social Bar Code" class="w-full bg-gray-50 p-4 h-24 rounded-xl text-xs">{settings['social_bar']}</textarea>
                        <textarea name="native" placeholder="Native Ad Code" class="w-full bg-gray-50 p-4 h-24 rounded-xl text-xs">{settings['native']}</textarea>
                    </div>
                    <button class="md:col-span-2 bg-slate-900 text-white p-6 rounded-3xl font-black text-xl">SAVE CONFIGURATION</button>
                </form>

                <h2 class="text-2xl font-black mt-12 mb-6">Shortened Links History</h2>
                <div class="bg-white rounded-3xl shadow-sm overflow-hidden">
                    <table class="w-full text-left">
                        <thead class="bg-gray-50 text-xs font-bold uppercase">
                            <tr><th class="p-6">Date</th><th class="p-6">Short URL</th><th class="p-6 text-center">Clicks</th></tr>
                        </thead>
                        <tbody class="divide-y text-sm">
                            {"".join([f'<tr><td class="p-6 text-gray-400">{u.get("created_at","N/A")}</td><td class="p-6 font-bold text-blue-600">/{u["short_code"]}</td><td class="p-6 text-center font-black">{u["clicks"]}</td></tr>' for u in all_urls])}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body></html>
    ''')

# --- ৫. রিডাইরেক্ট ও অ্যাড লিমিট লজিক (Fixed) ---
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
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script>
    {settings['popunder']} {settings['social_bar']}
    </head>
    <body class="bg-slate-50 flex flex-col items-center justify-center min-h-screen p-4">
        <div class="mb-4">{settings['banner']}</div>
        <div class="bg-white p-12 rounded-[50px] shadow-2xl text-center max-w-md w-full border">
            <p class="text-xs font-bold text-gray-400 uppercase tracking-widest">Step {step} of {settings['steps']}</p>
            <h2 class="text-2xl font-black mb-8">Wait for Button</h2>
            <div id="timer" class="text-6xl font-black text-blue-600 mb-8 bg-blue-50 w-24 h-24 flex items-center justify-center rounded-full mx-auto">{settings['timer_seconds']}</div>
            <button id="btn" onclick="handleClick()" class="hidden bg-blue-600 text-white px-10 py-5 rounded-2xl font-black text-xl w-full transition transform hover:scale-105">PLEASE WAIT</button>
        </div>
        <div class="mt-8">{settings['native']}</div>
        <script>
            let t = {settings['timer_seconds']};
            let clicks = 0; let limit = {settings['direct_click_limit']};
            const iv = setInterval(() => {{ t--; document.getElementById('timer').innerText = t; if(t <= 0) {{ clearInterval(iv); document.getElementById('timer').classList.add('hidden'); document.getElementById('btn').classList.remove('hidden'); updateBtn(); }} }}, 1000);
            function updateBtn() {{ if(clicks < limit && "{settings['direct_link']}" !== "") document.getElementById('btn').innerText = "CONTINUE ("+(clicks+1)+"/"+limit+")"; else document.getElementById('btn').innerText = "NEXT STEP"; }}
            function handleClick() {{ if(clicks < limit && "{settings['direct_link']}" !== "") {{ window.open("{settings['direct_link']}", "_blank"); clicks++; updateBtn(); }} else {{ window.location.href = "/{short_code}?step={step + 1}"; }} }}
        </script>
    </body></html>
    ''')

# --- লগইন ও পাসওয়ার্ড চেঞ্জ ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        return "Wrong Password!"
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh;"><form method="POST" style="background:white; padding:40px; border-radius:30px;"><h2 style="font-family:sans-serif; font-weight:900; margin-bottom:20px;">ADMIN LOGIN</h2><input type="password" name="password" placeholder="Password" style="padding:15px; border-radius:15px; border:1px solid #ddd; outline:none;"><button style="padding:15px; background:#2563eb; color:white; border:none; margin-left:10px; border-radius:15px; font-weight:bold;">Login</button></form></body>')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

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
        "direct_link": request.form.get('direct_link'),
        "direct_click_limit": int(request.form.get('direct_click_limit', 1))
    }
    new_pass = request.form.get('new_password')
    if new_pass and len(new_pass) > 2: d["admin_password"] = generate_password_hash(new_pass)
    settings_col.update_one({}, {"$set": d})
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run()
