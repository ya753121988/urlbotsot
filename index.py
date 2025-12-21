import os
import random
import string
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "premium-secret-key-2025")

# --- ডাটাবেস কনফিগারেশন ---
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
db = client['premium_url_bot']
urls_col = db['urls']
settings_col = db['settings']

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

# --- ১. প্রফেশনাল এপিআই সিস্টেম ---
@app.route('/api')
def api_system():
    settings = get_settings()
    api_token = request.args.get('api')
    long_url = request.args.get('url')
    alias = request.args.get('alias')
    res_format = request.args.get('format', 'json').lower()

    if not api_token or api_token != settings['api_key']:
        return jsonify({"status": "error", "message": "Invalid API Token"}) if res_format != 'text' else "Error: Invalid Token"
    
    if not long_url:
        return jsonify({"status": "error", "message": "Missing URL"}) if res_format != 'text' else "Error: Missing URL"

    short_code = alias if alias else ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    
    if alias and urls_col.find_one({"short_code": alias}):
        return jsonify({"status": "error", "message": "Alias already exists"})
    
    urls_col.insert_one({
        "long_url": long_url, 
        "short_code": short_code, 
        "clicks": 0, 
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": "1"
    })
    
    shortened_url = request.host_url + short_code
    return shortened_url if res_format == 'text' else jsonify({"status": "success", "shortenedUrl": shortened_url})

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
        <title>{settings['site_name']} - Shorten & Earn</title>
        <style>
            body {{ background: #0f172a; color: white; font-family: 'Inter', sans-serif; }}
            .glass {{ background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }}
        </style>
    </head>
    <body class="min-h-screen flex flex-col">
        <nav class="p-6 flex justify-between items-center max-w-7xl mx-auto w-full">
            <h1 class="text-3xl font-black text-cyan-400 italic tracking-tighter">{settings['site_name']}</h1>
            <a href="/admin" class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-full text-sm font-bold transition">Admin Dashboard</a>
        </nav>

        <main class="flex-1 flex flex-col items-center justify-center px-4">
            <div class="text-center mb-10">
                <h1 class="text-5xl md:text-7xl font-black mb-4">Fast URL <span class="text-cyan-400">Shortener.</span></h1>
                <p class="text-gray-400 text-lg">Shorten your links and manage ads effortlessly.</p>
            </div>
            
            <div class="glass p-3 rounded-3xl w-full max-w-3xl">
                <form action="/shorten" method="POST" class="flex flex-col md:flex-row gap-2">
                    <input type="url" name="long_url" placeholder="Paste your long link here..." required 
                           class="flex-1 bg-transparent p-5 rounded-2xl outline-none text-white text-lg">
                    <button type="submit" class="bg-cyan-500 text-slate-900 px-10 py-5 rounded-2xl font-black text-lg hover:bg-cyan-400 transition transform hover:scale-105">SHORTEN</button>
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
    urls_col.insert_one({
        "long_url": long_url, 
        "short_code": sc, 
        "clicks": 0, 
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": "1"
    })
    final_url = request.host_url + sc
    return render_template_string(f'''
    <html><head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 flex items-center justify-center min-h-screen p-4 text-white">
        <div class="bg-slate-800 p-10 rounded-[40px] shadow-2xl text-center max-w-lg w-full border border-slate-700">
            <div class="w-16 h-16 bg-cyan-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg class="w-8 h-8 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
            </div>
            <h2 class="text-2xl font-bold mb-6">Your Link is Ready!</h2>
            <input id="shortUrl" value="{final_url}" readonly class="w-full bg-slate-900 p-5 rounded-2xl border border-slate-700 text-cyan-400 font-bold text-center mb-6">
            <button onclick="copyLink()" id="copyBtn" class="w-full bg-cyan-500 text-slate-900 py-5 rounded-2xl font-black text-xl hover:bg-cyan-400 transition">COPY LINK</button>
            <a href="/" class="block mt-6 text-slate-500 font-bold">Shorten Another</a>
        </div>
        <script>
            function copyLink() {{
                var copyText = document.getElementById("shortUrl");
                copyText.select();
                navigator.clipboard.writeText(copyText.value);
                document.getElementById("copyBtn").innerText = "COPIED!";
                setTimeout(() => document.getElementById("copyBtn").innerText = "COPY LINK", 2000);
            }}
        </script>
    </body></html>
    ''')

# --- ৪. প্রিমিয়াম এডমিন ড্যাশবোর্ড ---
@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    
    # স্ট্যাটাস ক্যালকুলেশন
    all_urls = list(urls_col.find().sort("_id", -1))
    total_urls = len(all_urls)
    total_clicks = sum(u.get('clicks', 0) for u in all_urls)

    return render_template_string(f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Pro - {settings['site_name']}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
        <style>body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}</style>
    </head>
    <body class="bg-gray-50 text-slate-800">
        <div class="flex flex-col md:flex-row min-h-screen">
            <!-- Sidebar -->
            <div class="w-full md:w-72 bg-slate-900 p-8 text-white">
                <h2 class="text-2xl font-extrabold text-cyan-400 italic mb-10">ADMIN PRO</h2>
                <nav class="space-y-4">
                    <a href="/" class="block p-4 rounded-xl hover:bg-slate-800 transition">🌐 View Website</a>
                    <a href="/logout" class="block p-4 rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white transition font-bold">🔒 Logout</a>
                </nav>
            </div>

            <!-- Main -->
            <div class="flex-1 p-6 md:p-12 overflow-y-auto">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-4">
                    <div>
                        <h1 class="text-4xl font-black tracking-tight">Dashboard Overview</h1>
                        <p class="text-slate-500">Manage your links, ads, and system settings.</p>
                    </div>
                    <div class="flex gap-4">
                        <div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
                            <p class="text-xs font-bold text-slate-400 uppercase">Total Links</p>
                            <p class="text-2xl font-black text-blue-600">{total_urls}</p>
                        </div>
                        <div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
                            <p class="text-xs font-bold text-slate-400 uppercase">Total Clicks</p>
                            <p class="text-2xl font-black text-emerald-500">{total_clicks}</p>
                        </div>
                    </div>
                </div>

                <form action="/admin/update" method="POST" class="grid grid-cols-1 xl:grid-cols-2 gap-8">
                    <!-- Settings -->
                    <div class="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 space-y-6">
                        <h3 class="text-xl font-bold flex items-center gap-2">⚙️ System Configuration</h3>
                        
                        <div>
                            <label class="block text-sm font-bold text-slate-600">Site Name</label>
                            <p class="text-[10px] text-slate-400 mb-1">আপনার ওয়েবসাইটের নাম এখানে দিন।</p>
                            <input type="text" name="site_name" value="{settings['site_name']}" class="w-full bg-slate-50 border-none p-4 rounded-2xl focus:ring-2 focus:ring-blue-500">
                        </div>

                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-bold text-slate-600">Ad Steps</label>
                                <p class="text-[10px] text-slate-400 mb-1">ইউজার কতবার বাটন ক্লিক করবে।</p>
                                <input type="number" name="steps" value="{settings['steps']}" class="w-full bg-slate-50 border-none p-4 rounded-2xl">
                            </div>
                            <div>
                                <label class="block text-sm font-bold text-slate-600">Timer (Sec)</label>
                                <p class="text-[10px] text-slate-400 mb-1">বাটন আসার জন্য কত সেকেন্ড ওয়েট করবে।</p>
                                <input type="number" name="timer_seconds" value="{settings['timer_seconds']}" class="w-full bg-slate-50 border-none p-4 rounded-2xl">
                            </div>
                        </div>

                        <div>
                            <label class="block text-sm font-bold text-blue-600">Direct Click Link (Redirect Ad)</label>
                            <p class="text-[10px] text-slate-400 mb-1">বাটনে ক্লিক করলে যে লিঙ্কে নিয়ে যাবে (Extra Earning)।</p>
                            <input type="url" name="direct_link" value="{settings.get('direct_link', '')}" class="w-full bg-blue-50 border-none p-4 rounded-2xl">
                        </div>

                        <div>
                            <label class="block text-sm font-bold text-red-600">Change Admin Password</label>
                            <p class="text-[10px] text-slate-400 mb-1">খালি রাখলে আগের পাসওয়ার্ড বহাল থাকবে।</p>
                            <input type="password" name="new_password" placeholder="Enter new password" class="w-full bg-red-50 border-none p-4 rounded-2xl">
                        </div>
                    </div>

                    <!-- Ads Card -->
                    <div class="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 space-y-4">
                        <h3 class="text-xl font-bold flex items-center gap-2">💰 Advertisement Scripts</h3>
                        
                        <div>
                            <label class="text-xs font-bold text-slate-500 uppercase">Popunder Script</label>
                            <textarea name="popunder" placeholder="Paste Popunder Code" class="w-full bg-slate-50 border-none p-4 h-24 rounded-2xl font-mono text-xs">{settings['popunder']}</textarea>
                        </div>
                        <div>
                            <label class="text-xs font-bold text-slate-500 uppercase">Banner Ad (Top)</label>
                            <textarea name="banner" placeholder="Paste Banner Script" class="w-full bg-slate-50 border-none p-4 h-24 rounded-2xl font-mono text-xs">{settings['banner']}</textarea>
                        </div>
                        <div>
                            <label class="text-xs font-bold text-slate-500 uppercase">Social Bar Script</label>
                            <textarea name="social_bar" placeholder="Paste Social Bar Code" class="w-full bg-slate-50 border-none p-4 h-24 rounded-2xl font-mono text-xs">{settings['social_bar']}</textarea>
                        </div>
                        <div>
                            <label class="text-xs font-bold text-slate-500 uppercase">Native / Negative Ads (Bottom)</label>
                            <textarea name="native" placeholder="Paste Native Code" class="w-full bg-slate-50 border-none p-4 h-24 rounded-2xl font-mono text-xs">{settings.get('native', '')}</textarea>
                        </div>
                    </div>

                    <div class="xl:col-span-2">
                        <button type="submit" class="w-full bg-slate-900 text-white p-6 rounded-3xl font-black text-xl hover:bg-blue-600 transition shadow-xl">SAVE ALL CHANGES</button>
                    </div>
                </form>

                <!-- URL LIST TABLE -->
                <div class="mt-12 bg-white rounded-[40px] shadow-sm border border-slate-100 overflow-hidden">
                    <div class="p-8 border-b border-slate-50">
                        <h3 class="text-xl font-bold">History: All Shortened Links</h3>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="bg-slate-50 text-slate-400 text-[10px] font-bold uppercase tracking-widest">
                                    <th class="p-6">Date</th>
                                    <th class="p-6">Short Link</th>
                                    <th class="p-6">Destination</th>
                                    <th class="p-6 text-center">Clicks</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-50 text-sm">
                                {"".join([f'''
                                <tr class="hover:bg-slate-50/50">
                                    <td class="p-6 font-medium text-slate-400">{u.get('created_at', 'N/A')}</td>
                                    <td class="p-6 font-bold text-blue-600 underline">/{u['short_code']}</td>
                                    <td class="p-6 text-slate-500 truncate max-w-xs">{u['long_url']}</td>
                                    <td class="p-6 text-center"><span class="bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full font-bold">{u['clicks']}</span></td>
                                </tr>
                                ''' for u in all_urls])}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    ''')

# --- ৫. রিডাইরেক্ট লজিক (Ads Injection) ---
@app.route('/<short_code>')
def handle_ad_steps(short_code):
    step = int(request.args.get('step', 1))
    settings = get_settings()
    url_data = urls_col.find_one({"short_code": short_code})

    if not url_data: return "404 - Not Found", 404

    # ফাইনাল ডেস্টিনেশন
    if step > settings['steps']:
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        return redirect(url_data['long_url'])

    return render_template_string(f'''
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        {settings['popunder']}
        {settings['social_bar']}
    </head>
    <body class="bg-slate-50 flex flex-col items-center justify-center min-h-screen p-4">
        <div class="w-full max-w-xl text-center">
            <div class="mb-6 mx-auto inline-block">{settings['banner']}</div>
            
            <div class="bg-white p-10 md:p-16 rounded-[60px] shadow-2xl border border-white">
                <span class="text-blue-600 font-bold tracking-widest uppercase text-xs">Step {step} of {settings['steps']}</span>
                <h2 class="text-3xl font-black text-slate-900 mt-2 mb-8">Verification Required</h2>
                
                <div id="timer" class="text-6xl font-black text-slate-900 mb-10 bg-slate-100 w-32 h-32 flex items-center justify-center rounded-full mx-auto border-4 border-blue-500 border-t-transparent animate-spin-slow">
                    {settings['timer_seconds']}
                </div>
                
                <button id="btn" onclick="handleClick()" class="hidden w-full bg-blue-600 text-white py-6 rounded-3xl font-black text-xl shadow-xl shadow-blue-500/30 hover:scale-105 transition">PLEASE WAIT</button>
            </div>

            <div class="mt-8 mx-auto inline-block">{settings['native']}</div>
        </div>

        <script>
            let t = {settings['timer_seconds']};
            let clicksDone = 0;
            let limit = {settings.get('direct_click_limit', 1)};
            let dLink = "{settings.get('direct_link', '')}";
            const timer = document.getElementById('timer');
            const btn = document.getElementById('btn');
            
            const iv = setInterval(() => {{
                t--; timer.innerText = t;
                if(t <= 0) {{ 
                    clearInterval(iv); 
                    timer.classList.add('hidden');
                    btn.classList.remove('hidden');
                    updateBtnText();
                }}
            }}, 1000);

            function updateBtnText() {{
                if (clicksDone < limit && dLink !== "") {{
                    btn.innerText = "CONTINUE (" + (clicksDone + 1) + "/" + limit + ")";
                    btn.style.backgroundColor = "#2563eb";
                }} else {{
                    btn.innerText = "NEXT STEP";
                    btn.style.backgroundColor = "#10b981";
                }}
            }}

            function handleClick() {{
                if (clicksDone < limit && dLink !== "") {{
                    window.open(dLink, '_blank');
                    clicksDone++;
                    updateBtnText();
                }} else {{
                    window.location.href = "/{short_code}?step={step + 1}";
                }}
            }}
        </script>
        <style>@keyframes spin-slow {{ to {{ transform: rotate(360deg); }} }} .animate-spin-slow {{ animation: none; }}</style>
    </body>
    </html>
    ''')

# --- লগইন ও আপডেট ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        return "Wrong Password!"
    return render_template_string('<body style="background:#0f172a; display:flex; justify-content:center; align-items:center; height:100vh;"><form method="POST" style="background:white; padding:40px; border-radius:30px; box-shadow:0 20px 50px rgba(0,0,0,0.3);"><h2 style="font-family:sans-serif; font-weight:900; margin-bottom:20px;">ADMIN LOGIN</h2><input type="password" name="password" placeholder="Admin Password" style="padding:15px; border-radius:15px; border:1px solid #ddd; outline:none; width:250px;"><button style="padding:15px 30px; background:#2563eb; color:white; border:none; margin-left:10px; border-radius:15px; cursor:pointer; font-weight:bold;">Login</button></form></body>')

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
