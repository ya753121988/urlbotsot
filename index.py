import os
import random
import string
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "premium-super-secret-key-2025")

# --- ডাটাবেস কানেকশন ---
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
db = client['premium_url_bot']
urls_col = db['urls']
settings_col = db['settings']
channels_col = db['channels'] # নতুন কালেকশন চ্যানেল এর জন্য

def get_settings():
    settings = settings_col.find_one()
    if not settings:
        default_settings = {
            "site_name": "Premium URL Shortener",
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

# --- চ্যানেল বক্স জেনারেটর (সব পেজে দেখানোর জন্য) ---
def get_channels_html():
    channels = list(channels_col.find())
    if not channels:
        return ""
    
    html = '''
    <div class="w-full max-w-4xl mx-auto mt-10 mb-6 p-4 rounded-3xl border border-white/10 glass">
        <h3 class="text-center text-cyan-400 font-bold mb-4 uppercase tracking-widest text-sm">Join Our Premium Channels</h3>
        <div class="flex flex-wrap justify-center gap-4">
    '''
    for ch in channels:
        html += f'''
        <a href="{ch['link']}" target="_blank" class="flex items-center gap-3 p-2 px-4 rounded-2xl bg-white/5 border border-white/5 hover:bg-cyan-500/20 hover:border-cyan-500/50 transition duration-300">
            <img src="{ch['logo']}" class="w-10 h-10 rounded-full object-cover border border-white/10 shadow-lg">
            <span class="text-sm font-bold text-gray-200">Join Channel</span>
        </a>
        '''
    html += '</div></div>'
    return html

# --- ১. প্রফেশনাল এপিআই (JSON & Text Support) ---
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
    if res_format == 'text': return shortened_url
    return jsonify({"status": "success", "shortenedUrl": shortened_url})

# --- ২. হোম পেজ ইন্টারফেস ---
@app.route('/')
def index():
    settings = get_settings()
    channel_box = get_channels_html()
    return render_template_string(f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <title>{settings['site_name']}</title>
        <style>body {{ background: #0f172a; color: white; }} .glass {{ background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}</style>
    </head>
    <body class="min-h-screen flex flex-col items-center justify-center p-6">
        <h1 class="text-6xl font-black mb-4 text-cyan-400 italic tracking-tighter">{settings['site_name']}</h1>
        <p class="text-gray-400 mb-10 text-lg">Shorten, Share and Earn with Advanced Ad Control.</p>
        
        <div class="glass p-3 rounded-3xl w-full max-w-2xl">
            <form action="/shorten" method="POST" class="flex flex-col md:flex-row gap-2">
                <input type="url" name="long_url" placeholder="Enter your long URL here..." required class="flex-1 bg-transparent p-5 rounded-2xl outline-none text-white text-lg">
                <button type="submit" class="bg-cyan-500 text-slate-900 px-10 py-5 rounded-2xl font-black text-lg hover:scale-105 transition">SHORTEN</button>
            </form>
        </div>

        {channel_box}
    </body></html>
    ''')

# --- ৩. শর্ট লিঙ্ক রেজাল্ট ---
@app.route('/shorten', methods=['POST'])
def web_shorten():
    long_url = request.form.get('long_url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "1"})
    final_url = request.host_url + sc
    channel_box = get_channels_html()
    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script>
    <style>body {{ background: #0f172a; color: white; }} .glass {{ background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}</style>
    </head>
    <body class="bg-slate-900 flex flex-col items-center justify-center min-h-screen p-4 text-white">
        <div class="bg-slate-800 p-10 rounded-[40px] shadow-2xl text-center max-w-lg w-full border border-slate-700">
            <h2 class="text-2xl font-bold mb-6 text-cyan-400 tracking-tight">Your Link is Ready!</h2>
            <input id="shortUrl" value="{final_url}" readonly class="w-full bg-slate-900 p-5 rounded-2xl border border-slate-700 text-cyan-400 font-bold text-center mb-6">
            <button onclick="copyLink()" id="copyBtn" class="w-full bg-cyan-500 text-slate-900 py-5 rounded-2xl font-black text-xl hover:bg-cyan-400 transition">COPY LINK</button>
            <a href="/" class="block mt-6 text-slate-500 font-bold uppercase text-xs">Shorten Another</a>
        </div>
        {channel_box}
        <script>function copyLink() {{ var copyText = document.getElementById("shortUrl"); copyText.select(); navigator.clipboard.writeText(copyText.value); document.getElementById("copyBtn").innerText = "COPIED!"; }}</script>
    </body></html>
    ''')

# --- ৪. প্রিমিয়াম এডমিন ড্যাশবোর্ড ---
@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    all_urls = list(urls_col.find().sort("_id", -1))
    total_clicks = sum(u.get('clicks', 0) for u in all_urls)
    channels = list(channels_col.find())

    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-50 text-slate-800 font-sans">
        <div class="flex flex-col lg:flex-row min-h-screen">
            <!-- Sidebar -->
            <div class="lg:w-72 bg-slate-900 text-white p-8">
                <h2 class="text-2xl font-black text-cyan-400 mb-10 italic">ADMIN PRO</h2>
                <div class="space-y-4">
                    <div class="bg-slate-800 p-5 rounded-2xl border border-slate-700">
                        <p class="text-xs text-slate-400 font-bold uppercase">Total Links</p>
                        <p class="text-2xl font-black text-blue-400">{len(all_urls)}</p>
                    </div>
                    <div class="bg-slate-800 p-5 rounded-2xl border border-slate-700">
                        <p class="text-xs text-slate-400 font-bold uppercase">Total Clicks</p>
                        <p class="text-2xl font-black text-emerald-400">{total_clicks}</p>
                    </div>
                    <a href="/logout" class="block bg-red-500/10 text-red-500 p-4 rounded-xl text-center font-bold hover:bg-red-500 hover:text-white transition">Logout</a>
                </div>
            </div>

            <!-- Main Content -->
            <div class="flex-1 p-6 lg:p-12 overflow-y-auto">
                <h1 class="text-4xl font-black mb-10">Global Configuration</h1>
                
                <form action="/admin/update" method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="bg-white p-8 rounded-[40px] shadow-sm border space-y-5">
                        <h3 class="font-bold border-b pb-3 text-lg flex items-center gap-2">⚙️ System Settings</h3>
                        <div>
                            <label class="text-xs font-bold text-gray-400">Site Name</label>
                            <input type="text" name="site_name" value="{settings['site_name']}" class="w-full bg-gray-50 border p-4 rounded-xl">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="text-xs font-bold text-gray-400">Ad Steps</label>
                            <input type="number" name="steps" value="{settings['steps']}" class="w-full bg-gray-50 border p-4 rounded-xl"></div>
                            <div><label class="text-xs font-bold text-gray-400">Timer</label>
                            <input type="number" name="timer_seconds" value="{settings['timer_seconds']}" class="w-full bg-gray-50 border p-4 rounded-xl"></div>
                        </div>
                        <div>
                            <label class="text-xs font-bold text-blue-600">Direct Ad Link</label>
                            <input type="url" name="direct_link" value="{settings['direct_link']}" class="w-full bg-blue-50 border p-4 rounded-xl">
                        </div>
                        <div>
                            <label class="text-xs font-bold text-blue-600">Direct Click Limit</label>
                            <input type="number" name="direct_click_limit" value="{settings['direct_click_limit']}" class="w-full bg-blue-50 border p-4 rounded-xl">
                        </div>
                        <div>
                            <label class="text-xs font-bold text-red-500">Change Admin Password</label>
                            <input type="password" name="new_password" placeholder="Leave blank to keep same" class="w-full bg-red-50 border p-4 rounded-xl">
                        </div>
                    </div>

                    <div class="bg-white p-8 rounded-[40px] shadow-sm border space-y-4">
                        <h3 class="font-bold border-b pb-3 text-lg flex items-center gap-2">💰 Ad Scripts</h3>
                        <textarea name="popunder" placeholder="Popunder" class="w-full bg-gray-50 border p-4 h-24 rounded-xl text-xs font-mono">{settings['popunder']}</textarea>
                        <textarea name="banner" placeholder="Banner" class="w-full bg-gray-50 border p-4 h-24 rounded-xl text-xs font-mono">{settings['banner']}</textarea>
                        <textarea name="social_bar" placeholder="Social Bar" class="w-full bg-gray-50 border p-4 h-24 rounded-xl text-xs font-mono">{settings['social_bar']}</textarea>
                        <textarea name="native" placeholder="Native" class="w-full bg-gray-50 border p-4 h-24 rounded-xl text-xs font-mono">{settings['native']}</textarea>
                    </div>
                    <button class="md:col-span-2 bg-slate-900 text-white p-6 rounded-3xl font-black text-xl hover:bg-blue-600 transition shadow-xl">SAVE CONFIGURATION</button>
                </form>

                <!-- চ্যানেল ম্যানেজমেন্ট সেকশন -->
                <h2 class="text-2xl font-black mt-16 mb-6">📢 Manage Premium Channels</h2>
                <div class="bg-white p-8 rounded-[40px] shadow-sm border mb-10">
                    <form action="/admin/add_channel" method="POST" class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                        <div>
                            <label class="text-xs font-bold text-gray-400">Logo URL</label>
                            <input type="url" name="logo" required placeholder="https://logo-link.com/img.png" class="w-full bg-gray-50 border p-4 rounded-xl text-sm">
                        </div>
                        <div>
                            <label class="text-xs font-bold text-gray-400">Channel Link</label>
                            <input type="url" name="link" required placeholder="https://t.me/yourchannel" class="w-full bg-gray-50 border p-4 rounded-xl text-sm">
                        </div>
                        <button class="bg-cyan-500 text-slate-900 p-4 rounded-xl font-bold hover:bg-cyan-600 transition">Add Channel</button>
                    </form>
                    
                    <div class="mt-8 flex flex-wrap gap-4">
                        {"".join([f'''
                        <div class="flex items-center gap-3 bg-gray-50 p-3 pr-5 rounded-2xl border">
                            <img src="{c['logo']}" class="w-10 h-10 rounded-full object-cover">
                            <span class="text-sm font-bold truncate max-w-[100px]">Channel</span>
                            <a href="/admin/delete_channel/{c['_id']}" class="text-red-500 hover:text-red-700 font-bold ml-2">×</a>
                        </div>
                        ''' for c in channels])}
                    </div>
                </div>

                <!-- URL List Table -->
                <h2 class="text-2xl font-black mb-6">🔗 Link Management</h2>
                <div class="bg-white rounded-[30px] shadow-sm border overflow-hidden">
                    <table class="w-full text-left border-collapse">
                        <thead class="bg-gray-50 text-[10px] font-bold uppercase tracking-widest text-gray-400">
                            <tr><th class="p-6">Created</th><th class="p-6">Short Link</th><th class="p-6">Long URL</th><th class="p-6 text-center">Clicks</th></tr>
                        </thead>
                        <tbody class="divide-y text-sm font-medium">
                            {"".join([f'''<tr class="hover:bg-slate-50 transition"><td class="p-6 text-gray-400">{u.get('created_at','N/A')}</td><td class="p-6 font-bold text-blue-600">/{u['short_code']}</td><td class="p-6 text-gray-500 truncate max-w-xs">{u['long_url']}</td><td class="p-6 text-center"><span class="bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">{u['clicks']}</span></td></tr>''' for u in all_urls])}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body></html>
    ''')

# --- ৫. চ্যানেল অ্যাড ও ডিলিট রুটস ---
@app.route('/admin/add_channel', methods=['POST'])
def add_channel():
    if not is_logged_in(): return redirect(url_for('login'))
    logo = request.form.get('logo')
    link = request.form.get('link')
    if logo and link:
        channels_col.insert_one({"logo": logo, "link": link})
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_channel/<id>')
def delete_channel(id):
    if not is_logged_in(): return redirect(url_for('login'))
    from bson.objectid import ObjectId
    channels_col.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('admin_panel'))

# --- ৬. রিডাইরেক্ট লজিক (Ads & Timer & Direct Limit) ---
@app.route('/<short_code>')
def handle_ad_steps(short_code):
    step = int(request.args.get('step', 1))
    settings = get_settings()
    url_data = urls_col.find_one({"short_code": short_code})
    channel_box = get_channels_html()
    
    if not url_data: return "404 - Link Not Found", 404
    
    if url_data.get('type') == '0' or step > settings['steps']:
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        return redirect(url_data['long_url'])

    return render_template_string(f'''
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script>
    {settings['popunder']} {settings['social_bar']}
    <style>body {{ background: #0f172a; color: white; }} .glass {{ background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}</style>
    </head>
    <body class="bg-slate-50 flex flex-col items-center justify-center min-h-screen p-4">
        <div class="mb-6">{settings['banner']}</div>
        <div class="bg-white p-10 md:p-16 rounded-[60px] shadow-2xl text-center max-w-md w-full border border-white">
            <p class="text-[10px] font-bold text-blue-500 uppercase tracking-widest mb-2">Verification Step {step}/{settings['steps']}</p>
            <h2 class="text-2xl font-black text-slate-900 mb-8">Please wait for the timer</h2>
            <div id="timer" class="text-6xl font-black text-blue-600 mb-10 bg-blue-50 w-28 h-28 flex items-center justify-center rounded-full mx-auto border-4 border-blue-100 italic">{settings['timer_seconds']}</div>
            <button id="btn" onclick="handleClick()" class="hidden w-full bg-blue-600 text-white py-6 rounded-3xl font-black text-xl shadow-xl hover:scale-105 transition">PLEASE WAIT</button>
        </div>
        <div class="mt-8">{settings['native']}</div>
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

# --- লগইন ও পাসওয়ার্ড হ্যান্ডলিং ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        return "Wrong Password!"
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh;"><form method="POST" style="background:white; padding:50px; border-radius:30px;"><h2 style="font-family:sans-serif; font-weight:900; margin-bottom:20px; text-align:center;">ADMIN LOGIN</h2><input type="password" name="password" placeholder="Password" style="padding:15px; border-radius:15px; border:1px solid #ddd; outline:none; width:250px; display:block; margin-bottom:10px;"><button style="width:100%; padding:15px; background:#2563eb; color:white; border:none; border-radius:15px; font-weight:bold; cursor:pointer;">Enter Dashboard</button></form></body>')

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
    if new_pass and len(new_pass) > 2:
        d["admin_password"] = generate_password_hash(new_pass)
    settings_col.update_one({}, {"$set": d})
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run()
