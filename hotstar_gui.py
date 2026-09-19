#!/usr/bin/env python3
"""
JioHotstar Downloader GUI  v4
pip install requests
python hotstar_gui.py
"""

import sys, os, re, json, time, hmac, hashlib, subprocess, threading, uuid, datetime, signal
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ─────────────────────────────────────────────────────────────
#  CONSTANTS / HELPERS
# ─────────────────────────────────────────────────────────────

APP_DIR  = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(APP_DIR, "hotstar_cfg.json")
DID_FILE = os.path.join(APP_DIR, ".hotstar_did")

_HMAC_KEY = b"\x05\xfc\x1a\x01\xca\xc9\x4b\xc4\x12\xfc\x53\x12\x07\x75\xf9\xee"
FP_SAMPLE = (
    'MDA3MGYyZTAtZGYxMS00ODhjLThlNmItYjczYmEwNjNhYjIz.BPicufgJ44ZZHXqTv8pNoJXgX2WYShUBEW8vws'
    '__IjBu1VBsW5t32-Q0A8EFjVP0Wl7fvAEIDtfDMTqUQHJ5bNIRd9uO6-6mviC7-Axb9ZSwD3VCAclSrxGotyIgc'
    'axpXZSC9w6rijZGqbp8Hr3FkiHZTG6fqCdlVifI0ONKxowYqWKwfL9PqzngxBW4IGLm6k__sMgoPTDTEdUJDM3A'
    'gsFd2RIdw4WpU8ydA1OnXiyjlrqIJvNQ0riuqrLILC4UQ4j3oU_-yNwQPO1NRChLMCiQzLsG8Gr35oMPhcxoKur'
    '0Rv3M7oJR-PaFVrtwZhnreWtZ3Yyj5ySkkhFFh7qHENQRRj-paiWnaNny4BLhlcWPji1Lb6sZLTdjQAEvXTL38K'
    'MiFBcgxkaVgRAFhCiuTVqx4LPQ3oicviTI5LdocPAfGHunCSPwi-nnML_hEAXRlw3GXGZcsmujLeMgrJVwyn05y'
)

def get_device_id():
    if os.path.exists(DID_FILE):
        return open(DID_FILE).read().strip()
    did = str(uuid.uuid4())[:23]
    open(DID_FILE, 'w').write(did)
    return did

DEVICE_ID = get_device_id()

def make_auth():
    st = int(time.time()); exp = st + 6000
    msg = f"st={st}~exp={exp}~acl=/*"
    return f"{msg}~hmac={hmac.new(_HMAC_KEY, msg.encode(), hashlib.sha256).hexdigest()}"

def android_hdrs(token=None):
    h = {
        "User-Agent":          "Hotstar;in.startv.hotstar/26.09.05.0.11013 (Android/14)",
        "Content-Type":        "application/x-protobuf",
        "X-Country-Code":      "in", "X-HS-App": "11013",
        "X-HS-APP-ID":         "c86aad81-d602-46e5-b6a0-6d3891199063",
        "X-HS-Client":         "platform:android;app_id:in.startv.hotstar;app_version:26.09.05.0;os:Android;os_version:14;schema_version:0.0.1797;brand:Samsung;model:SM-S918B;carrier:airtel;network_data:NETWORK_TYPE_WIFI",
        "X-HS-Device-Id":      DEVICE_ID, "X-HS-Platform": "android",
        "X-HS-Schema-Version": "0.0.1797", "X-HS-FP-Info": FP_SAMPLE,
        "hotstarauth":         make_auth(),
    }
    if token: h["X-HS-Usertoken"] = token
    return h

def web_hdrs(token=None, ps=None):
    h = {
        "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept":        "application/json, text/plain, */*",
        "Content-Type":  "application/json",
        "Origin":        "https://www.hotstar.com",
        "Referer":       "https://www.hotstar.com/in",
        "x-country-code":"in", "x-hs-app": "260905000",
        "x-hs-client":   "platform:web;app_version:26.09.05.0;browser:Chrome;schema_version:0.0.1797;os:Windows;os_version:10;browser_version:137;network_data:4g",
        "x-hs-platform": "web", "hotstarauth": make_auth(),
    }
    if token: h["x-hs-usertoken"] = token
    if ps:    h["x-hs-proxystate"] = ps
    return h

def find_jwt(data):
    src = data if isinstance(data, str) else (data.decode('utf-8','replace') if isinstance(data,bytes) else str(data))
    hits = [h for h in re.findall(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+', src) if len(h)>200]
    return max(hits, key=len) if hits else None

def jwt_exp(tok):
    try:
        import base64
        p = tok.split('.')[1]; p += '='*(4-len(p)%4)
        return json.loads(base64.b64decode(p))['exp']
    except: return 0

def tok_valid(tok): return bool(tok) and jwt_exp(tok) > time.time()+60
def tok_str(tok):
    h = (jwt_exp(tok)-time.time())/3600
    return f"{h:.1f}h remaining" if h>0 else "expired"

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────

DEFAULT_CFG = {
    "token_file":    os.path.join(APP_DIR, "hotstar_token.json"),
    "output_dir":    r"E:\Downloads",
    "n_m3u8dl_path": r"E:\N_m3u8DL-RE.exe",
    "ytdlp_path":    "yt-dlp",
    "ffmpeg_path":   "ffmpeg",
    "threads":       16,
    "grab_subs":     False,
    "engine":        "auto",   # "auto" | "n_m3u8dl" | "ytdlp" | "ffmpeg"
}

def load_cfg():
    c = dict(DEFAULT_CFG)
    if os.path.exists(CFG_FILE):
        try: c.update(json.load(open(CFG_FILE)))
        except: pass
    return c

def save_cfg(c): json.dump(c, open(CFG_FILE,'w'), indent=2)

def load_token(cfg):
    path = cfg.get("token_file","")
    candidates = [path, os.path.join(APP_DIR,"hotstar_token.json"), os.path.join(APP_DIR,"hs_token.json")]
    for p in candidates:
        if p and os.path.exists(p):
            try:
                d = json.load(open(p)); t = d.get("user_token","")
                if tok_valid(t): return t, p
            except: pass
    return None, None

def save_token(tok, phone, cfg):
    path = cfg.get("token_file", os.path.join(APP_DIR,"hotstar_token.json"))
    json.dump({"user_token":tok,"phone":phone,"saved_at":int(time.time()),"expires_at":jwt_exp(tok)},
              open(path,'w'), indent=2)
    return path

# ─────────────────────────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────────────────────────

def api_guest():
    try:
        r = requests.post("https://apix.hotstar.com/v2/freshstart",
            params={"client_capabilities":json.dumps({"package":["dash","hls"],"container":["fmp4","ts"],
                "encryption":["plain","widevine"],"video_codec":["h264"],"ladder":["phone"],
                "resolution":["sd","hd","fhd"],"dynamic_range":["sdr"]}),
                "drm_parameters":json.dumps({"widevine_security_level":["HW_SECURE_ALL","SW_SECURE_DECODE"],
                "hdcp_version":["HDCP_V2_2"]}),"subs":"null","login":"UNKNOWN"},
            headers=android_hdrs(), data=b'', timeout=15)
        g = r.headers.get("x-hs-updatedusertoken") or find_jwt(r.content)
        if g: return g, None
    except: pass
    try:
        r = requests.post("https://www.hotstar.com/api/internal/bff/v2/start",
            params={"journey":"login"}, headers=web_hdrs(),
            json={"deeplink_url":"","context":{"url":"type.googleapis.com/context.StateContext","value":"CgQaAggC"},"app_launch_count":1},
            timeout=15)
        g = r.headers.get("x-hs-updatedusertoken")
        ps = r.headers.get("x-hs-setproxystate")
        if g: return g, ps
    except: pass
    return None, None

def api_send_otp(phone, guest, ps=None):
    try:
        r = requests.post(
            "https://www.hotstar.com/api/internal/bff/v2/pages/1/spaces/1/widgets/8",
            params={"action":"sendOtp","pageRef":"myspace","page_enum":"onboarding_login","qrCode":"true"},
            headers=web_hdrs(token=guest, ps=ps),
            json={"body":{"@type":"type.googleapis.com/feature.login.InitiatePhoneLoginRequest",
                          "initiate_by":0,"recaptcha_token":"","phone_number":phone}},
            timeout=15)
        if r.status_code in (200,201,202):
            d = {}
            try: d = r.json()
            except: pass
            if "error" not in d: return True,"web"
    except: pass
    try:
        pb = phone.encode()
        inner = b'\x0a'+bytes([len(pb)])+pb
        outer = b'\x0a'+bytes([len(inner)])+inner
        r = requests.post("https://apix.hotstar.com/v2/pages/1/spaces/1/widgets/8",
            params={"action":"sendOtp"}, headers=android_hdrs(guest), data=outer, timeout=15)
        if r.status_code==200: return True,"android"
    except: pass
    return False,None

def api_verify_otp(phone, otp, guest, ps=None, method="web"):
    if method=="web":
        try:
            r = requests.post(
                "https://www.hotstar.com/api/internal/bff/v2/pages/1/spaces/1/widgets/9",
                params={"action":"verifyOtp","pageRef":"myspace","page_enum":"onboarding_login","qrCode":"true"},
                headers=web_hdrs(token=guest, ps=ps),
                json={"body":{"@type":"type.googleapis.com/feature.login.VerifyPhoneLoginRequest",
                              "verification_code":otp,
                              "login_device_meta":{"device_name":"Chrome Browser on Windows"},
                              "phone_number":phone}},
                timeout=15)
            tok = r.headers.get("x-hs-updatedusertoken") or find_jwt(r.text)
            if tok and len(tok)>200: return tok
        except: pass
    try:
        pb,ob = phone.encode(),otp.encode()
        inner = b'\x0a'+bytes([len(pb)])+pb+b'\x12'+bytes([len(ob)])+ob
        outer = b'\x0a'+bytes([len(inner)])+inner
        r = requests.post("https://apix.hotstar.com/v2/pages/1/spaces/1/widgets/9",
            params={"action":"verifyOtp"}, headers=android_hdrs(guest), data=outer, timeout=15)
        tok = r.headers.get("x-hs-updatedusertoken") or find_jwt(r.content)
        if tok and len(tok)>200: return tok
    except: pass
    return None

# ─────────────────────────────────────────────────────────────
#  STREAM / QUALITY
# ─────────────────────────────────────────────────────────────

CLIENT_CAPS = json.dumps({"package":["dash","hls"],"container":["fmp4","fmp4br","ts"],
    "ads":["non_ssai"],"audio_channel":["stereo"],"encryption":["plain"],"video_codec":["h264"],
    "ladder":["phone","web","tv"],"resolution":["sd","hd","fhd"],"dynamic_range":["sdr"]})
DRM_PARAMS  = json.dumps({"widevine_security_level":[],"hdcp_version":["HDCP_V2_2"]})

def fetch_stream(content_id, token):
    r = requests.get("https://apix.hotstar.com/v2/pages/watch",
        params={"content_id":content_id,"filters":"content_type=EPISODE",
                "client_capabilities":CLIENT_CAPS,"drm_parameters":DRM_PARAMS},
        headers=android_hdrs(token), timeout=15)
    if r.status_code != 200: return None, None, r.status_code
    raw = r.content
    urls = [u.decode('utf-8','replace') for u in re.findall(rb'https://[A-Za-z0-9.\-_/?=&%~:@+]+', raw)]
    mpd  = next((u for u in urls if '.mpd'  in u and 'hdnea' in u), next((u for u in urls if '.mpd'  in u), None))
    m3u8 = next((u for u in urls if '.m3u8' in u and 'hdnea' in u), next((u for u in urls if '.m3u8' in u), None))
    return mpd, m3u8, 200

def get_duration_secs(mpd_text):
    try:
        m = re.search(r'mediaPresentationDuration="PT(?:(\d+)H)?(?:(\d+)M)?([0-9.]+)S"', mpd_text)
        if m:
            return int(m.group(1) or 0)*3600 + int(m.group(2) or 0)*60 + float(m.group(3) or 0)
    except: pass
    return None

def fmt_size(b):
    if b is None: return "?"
    if b < 1024**2: return f"{b/1024:.0f} KB"
    if b < 1024**3: return f"{b/1024**2:.0f} MB"
    return f"{b/1024**3:.2f} GB"

LANG_NAMES = {
    "hin":"Hindi","tam":"Tamil","tel":"Telugu","eng":"English","kan":"Kannada",
    "mal":"Malayalam","ben":"Bengali","mar":"Marathi","pun":"Punjabi","guj":"Gujarati",
    "urd":"Urdu","arb":"Arabic","fre":"French","spa":"Spanish","ger":"German",
    "jpn":"Japanese","kor":"Korean","chi":"Chinese","zho":"Chinese","por":"Portuguese",
}

def lang_label(code):
    return LANG_NAMES.get(code.lower(), code.upper())

def parse_qualities(mpd_url):
    try:
        r = requests.get(mpd_url, timeout=10, headers={"Referer":"https://www.hotstar.com/"})
        txt = r.text
        dur = get_duration_secs(txt)

        # ── parse video qualities ──
        all_reps = re.findall(r'<Representation\b([^>]+)>', txt)
        seen, out, video_idx = set(), [], 0
        for attrs in all_reps:
            w_m  = re.search(r'width="(\d+)"', attrs)
            h_m  = re.search(r'height="(\d+)"', attrs)
            bw_m = re.search(r'bandwidth="(\d+)"', attrs)
            id_m = re.search(r'\bid="([^"]+)"', attrs)
            if not (w_m and h_m and bw_m): continue
            w, h, bw = int(w_m.group(1)), int(h_m.group(1)), int(bw_m.group(1))
            rid = id_m.group(1) if id_m else f"{w}x{h}"
            lbl = f"{h}p"
            if h < 144: continue
            if lbl not in seen:
                seen.add(lbl)
                est = int((bw/8) * dur * 1.2) if dur else None
                out.append({"label":lbl,"height":h,"width":w,"bw":bw,"id":rid,
                             "mpd_video_idx":video_idx,"est_size":fmt_size(est),"mbps":bw/1e6})
            video_idx += 1
        out.sort(key=lambda x: x["height"], reverse=True)

        # ── parse audio tracks — collect max bitrate per lang ──
        audio_tracks = []
        seen_audio   = {}   # lang -> max_kbps
        for block in re.finditer(r'<AdaptationSet[^>]+mimeType="audio/mp4"[^>]*>(.*?)</AdaptationSet>',
                                  txt, re.DOTALL | re.IGNORECASE):
            lang_m = re.search(r'lang="([^"]+)"', block.group(0))
            lang   = lang_m.group(1) if lang_m else "und"
            # extract all Representation bandwidths inside this AdaptationSet
            bws = [int(m)/1000 for m in re.findall(r'bandwidth="(\d+)"', block.group(1))]
            max_kbps = max(bws) if bws else 128
            if lang not in seen_audio or max_kbps > seen_audio[lang]:
                seen_audio[lang] = max_kbps
        for lang, max_kbps in seen_audio.items():
            audio_tracks.append({"code": lang, "label": lang_label(lang), "max_kbps": max_kbps})

        # ── parse subtitle tracks ──
        sub_tracks = []
        seen_subs = set()
        for block in re.finditer(r'<AdaptationSet[^>]+contentType="text"[^>]*>(.*?)</AdaptationSet>',
                                  txt, re.DOTALL | re.IGNORECASE):
            lang_m = re.search(r'lang="([^"]+)"', block.group(0))
            lang   = lang_m.group(1) if lang_m else "und"
            if lang not in seen_subs:
                seen_subs.add(lang)
                sub_tracks.append({"code": lang, "label": lang_label(lang)})

        return out, dur, audio_tracks, sub_tracks
    except:
        return [], None, [], []

def extract_cid(s):
    s = s.strip().split('?')[0]
    if s.isdigit(): return s
    m = re.search(r'/(\d{9,12})(?:/|$)', s)
    return m.group(1) if m else None

def extract_show_info(url):
    try:
        clean = url.strip().split('?')[0].rstrip('/')
        if clean.endswith('/watch'): clean = clean[:-6]
        clean = re.sub(r'/\d{9,12}$', '', clean)
        parts = [p for p in clean.split('/') if p and not p.isdigit()]
        show, ep = "", ""
        if 'shows' in parts:
            idx = parts.index('shows')
            if idx+1 < len(parts): show = parts[idx+1].replace('-',' ').title()
            if idx+2 < len(parts): ep   = parts[idx+2].replace('-',' ').title()
        elif 'movies' in parts:
            idx = parts.index('movies')
            if idx+1 < len(parts): show = parts[idx+1].replace('-',' ').title()
        elif parts:
            show = parts[-1].replace('-',' ').title()
        return show, ep
    except: return "", ""

def make_filename(url, quality_height, codec="H264"):
    show, ep = extract_show_info(url)
    def clean(s): return re.sub(r'[^\w]', '_', s).strip('_')
    parts = []
    if show: parts.append(clean(show[:30]))
    if ep:   parts.append(clean(ep[:40]))
    parts.append(f"{quality_height}p")
    parts.append(codec)
    return '_'.join(filter(None, parts)) or f"hotstar_{quality_height}p"

# ─────────────────────────────────────────────────────────────
#  DOWNLOADER  (N_m3u8DL-RE → yt-dlp → ffmpeg)
# ─────────────────────────────────────────────────────────────

def find_exe(candidates):
    """Return first executable that runs, or None."""
    for c in candidates:
        if not c: continue
        try:
            if subprocess.run([c, "--version"], capture_output=True, timeout=5).returncode == 0:
                return c
        except: pass
    return None

def ts_to_secs(ts):
    try:
        p = ts.split(':')
        return int(p[0])*3600 + int(p[1])*60 + float(p[2])
    except: return 0

def run_download(stream_url, out_dir, out_name, quality, cfg, progress_cb, log_cb, cancel_flag):
    """
    cancel_flag: threading.Event — set it to abort
    Returns (True/False, out_path or None)
    """
    os.makedirs(out_dir, exist_ok=True)
    n_path    = cfg.get("n_m3u8dl_path","")
    ytdlp_path= cfg.get("ytdlp_path","yt-dlp")
    ff_path   = cfg.get("ffmpeg_path","ffmpeg")
    threads   = cfg.get("threads", 16)
    subs      = cfg.get("grab_subs", False)
    dur       = cfg.get("_duration")
    height    = quality["height"] if quality else 0
    out_mp4   = os.path.join(out_dir, out_name+".mkv")
    engine    = cfg.get("engine", "auto")               # "auto"|"n_m3u8dl"|"ytdlp"|"ffmpeg"
    audio_lang     = cfg.get("audio_lang", "best")      # "best" | "hi,te,ta" | "te" etc
    sub_lang       = cfg.get("sub_lang",   "NONE")      # "NONE" | "ALL" | lang code
    audio_max_kbps = cfg.get("_audio_max_kbps", {})     # {lang: max_kbps} from MPD parse

    def run_proc(cmd, parse_fn):
        """Run subprocess, stream output, respect cancel_flag."""
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, errors='replace')
            for line in proc.stdout:
                if cancel_flag.is_set():
                    proc.terminate()
                    try: proc.wait(timeout=3)
                    except: proc.kill()
                    log_cb("\n[!] Cancelled by user\n")
                    return -99
                log_cb(line)
                parse_fn(line)
            proc.wait()
            return proc.returncode
        except Exception as e:
            log_cb(f"[!] Error: {e}\n")
            return -1

    # ── 1. N_m3u8DL-RE (fastest — aria2c parallel) ──
    use_n = engine in ("auto", "n_m3u8dl")
    if use_n and n_path and os.path.exists(n_path):
        res_map = {1080:"res='1920x1080'",720:"res='1280x720'",
                   480:"res='854x480'",360:"res='640x360'",240:"res='426x240'",180:"res='320x180'"}
        sel = res_map.get(height)
        cmd = [n_path, stream_url,
               "--save-name", out_name, "--save-dir", out_dir,
               "--binary-merge", "--del-after-done", "--no-date-info",
               "--thread-count", str(threads),
               "-mt",                              # concurrent download: video+audio+subs in parallel
               "--mux-after-done", "format=mkv",   # merge all tracks into one MKV after done
               "--header", "Referer: https://www.hotstar.com/",
               "--header", "Origin: https://www.hotstar.com"]
        # ── audio selection ──────────────────────────────────────────────────────
        # N_m3u8DL-RE only accepts ONE --select-audio flag total.
        #
        # Correct multi-lang syntax (from official README):
        #   -sa lang="hi|te|ta":for=bestN
        #   → picks the top N tracks by bandwidth from all tracks whose lang
        #     matches the regex.  With 3 langs each at 129/65/49 kbps, the
        #     top 3 by bandwidth are hi@129 + te@129 + ta@129. ✓
        #
        # DO NOT use multiple --select-audio flags (parser error).
        # DO NOT use --drop-audio "Bandwidth<N" (not a valid property; use bwMin/bwMax).
        # ─────────────────────────────────────────────────────────────────────────
        if audio_lang and audio_lang not in ("best", ""):
            codes = [c.strip() for c in audio_lang.split(",") if c.strip()]
            if len(codes) == 1:
                # single lang — just grab the best track for that language
                cmd += ["--select-audio", f"lang={codes[0]}:for=best"]
            else:
                # multi-lang — pipe-join langs and pick top N by bandwidth
                # e.g. lang=hi|te|ta:for=best3 → hi@129 + te@129 + ta@129
                lang_re = "|".join(codes)
                n       = len(codes)
                cmd += ["--select-audio", f"lang={lang_re}:for=best{n}"]
        else:
            cmd += ["--select-audio", "best"]

        if sel: cmd += ["--select-video", sel]
        else:   cmd += ["--select-video", "best"]

        # subtitle selection — single flag with regex OR for multi-sub
        if sub_lang == "ALL" or subs:
            cmd += ["--select-subtitle", "all"]
        elif sub_lang and sub_lang not in ("NONE", ""):
            codes_s = [c.strip() for c in sub_lang.split(",") if c.strip()]
            if len(codes_s) == 1:
                cmd += ["--select-subtitle", f"lang={codes_s[0]}"]
            else:
                sub_re = "|".join(codes_s)
                cmd += ["--select-subtitle", f"lang=({sub_re})"]
        log_cb(f"[N_m3u8DL-RE] {threads} threads | {height}p\n\n")
        pct_re   = re.compile(r'(\d+(?:\.\d+)?)\s*%')
        spd_re   = re.compile(r'(\d+(?:\.\d+)?)\s*(K|M|G)B/s', re.I)
        def parse_n(line):
            pm = pct_re.search(line); sm = spd_re.search(line)
            if pm: progress_cb(float(pm.group(1)), f"{sm.group(1)} {sm.group(2)}B/s" if sm else "")
        rc = run_proc(cmd, parse_n)
        if rc == 0:   progress_cb(100,""); return True, out_mp4
        if rc == -99: return False, None
        # N_m3u8DL-RE failed — if user explicitly chose it, stop here with clear error
        if engine == "n_m3u8dl":
            log_cb("[✗] N_m3u8DL-RE failed. Check the log above.\n")
            return False, None
        log_cb("[!] N_m3u8DL-RE failed, trying yt-dlp...\n\n")

    # ── 2. yt-dlp (concurrent fragments — much faster than ffmpeg) ──
    use_yt = engine in ("auto", "ytdlp")
    ytdlp = None
    if use_yt:
        ytdlp = find_exe([ytdlp_path, "yt-dlp", r"E:\yt-dlp.exe", os.path.join(APP_DIR,"yt-dlp.exe")])
        if not ytdlp:
            log_cb("[~] yt-dlp not found, installing via pip...\n")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"], timeout=60)
                ytdlp = find_exe(["yt-dlp"])
                if ytdlp: log_cb("[✓] yt-dlp installed\n\n")
            except: pass

    if use_yt and ytdlp:
        # For DASH MPD: yt-dlp can take a direct MPD URL
        # format: best video at target height + best audio
        # yt-dlp audio language filter — single lang only (yt-dlp can't mux multi-audio)
        if audio_lang and audio_lang not in ("best", ""):
            first_lang = audio_lang.split(",")[0].strip()
            audio_fmt = f"bestaudio[language={first_lang}]/bestaudio"
        else:
            audio_fmt = "bestaudio"
        fmt = (f"bestvideo[height<={height}]+{audio_fmt}/best[height<={height}]"
               if height else f"bestvideo+{audio_fmt}/best")
        cmd = [
            ytdlp, stream_url,
            "-f", fmt,
            "--concurrent-fragments", str(min(threads, 16)),
            "--no-playlist",
            "-o", out_mp4,
            "--add-header", "Referer: https://www.hotstar.com/",
            "--add-header", "Origin: https://www.hotstar.com",
            "--merge-output-format", "mkv",
            "--no-warnings",
            "--newline",
        ]
        log_cb(f"[yt-dlp] {min(threads,16)} concurrent fragments | {height}p\n\n")
        pct_re = re.compile(r'\[download\]\s+(\d+\.?\d*)%.*?(\d+\.?\d*\s*\w+/s)')
        pct_re2= re.compile(r'\[download\]\s+(\d+\.?\d*)%')
        def parse_yt(line):
            m = pct_re.search(line)
            if m: progress_cb(float(m.group(1)), m.group(2)); return
            m = pct_re2.search(line)
            if m: progress_cb(float(m.group(1)), "")
        rc = run_proc(cmd, parse_yt)
        if rc == 0:   progress_cb(100,""); return True, out_mp4
        if rc == -99: return False, None
        if engine == "ytdlp":
            log_cb("[✗] yt-dlp failed. Check the log above.\n")
            return False, None
        log_cb("[!] yt-dlp failed, falling back to ffmpeg\n\n")

    # ── 3. ffmpeg (sequential fallback) ──
    use_ff = engine in ("auto", "ffmpeg")
    ff = find_exe([ff_path, "ffmpeg", r"E:\ffmpeg.exe", r"E:\ffmpeg\bin\ffmpeg.exe"])
    if not ff:
        log_cb("[✗] No downloader found.\n    Install yt-dlp: pip install yt-dlp\n    Or ffmpeg from ffmpeg.org\n")
        return False, None

    mpd_idx = quality.get("mpd_video_idx") if quality else None
    cmd = [ff, "-allowed_extensions","ALL",
           "-headers","Referer: https://www.hotstar.com/\r\nOrigin: https://www.hotstar.com\r\n",
           "-i", stream_url]
    if mpd_idx is not None:
        cmd += ["-map", f"0:v:{mpd_idx}", "-map", "0:a:0"]
    cmd += ["-c","copy", out_mp4, "-y",
            "-progress","pipe:1","-nostats","-loglevel","error"]
    log_cb(f"[ffmpeg] sequential fallback | {height}p stream #{mpd_idx}\n\n")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, bufsize=1, errors='replace')
        def read_err():
            for l in proc.stderr: log_cb(l)
        threading.Thread(target=read_err, daemon=True).start()
        spd = ""
        for line in proc.stdout:
            if cancel_flag.is_set():
                proc.terminate()
                try: proc.wait(timeout=3)
                except: proc.kill()
                log_cb("\n[!] Cancelled\n")
                return False, None
            m = re.search(r'out_time=(\d+:\d+:\d+\.\d+)', line)
            sm= re.search(r'speed=\s*([0-9.]+)x', line)
            if sm: spd = f"{sm.group(1)}x"
            if m and dur:
                pct = min(ts_to_secs(m.group(1))/dur*100, 99.9)
                progress_cb(pct, spd)
        proc.wait()
        if proc.returncode==0: progress_cb(100,""); return True, out_mp4
    except Exception as e:
        log_cb(f"[!] ffmpeg error: {e}\n")
    return False, None

# ─────────────────────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────────────────────

BG   = "#0d0f18"
BG2  = "#13151f"   # cards
BG3  = "#1c1e2e"   # inputs / hover
BG4  = "#22253a"   # row hover
ACC  = "#7c6af7"   # primary purple
ACC2 = "#5a48e0"   # hover
ACC3 = "#a599ff"   # light purple
FG   = "#e4e4f0"
FG2  = "#7a7a9d"
FG3  = "#44445a"
GRN  = "#4ade80"
RED  = "#f87171"
YLW  = "#fbbf24"
ORG  = "#fb923c"
FONT  = ("Segoe UI", 10)
FONTB = ("Segoe UI", 10, "bold")
MONO  = ("Consolas", 10)

# ─────────────────────────────────────────────────────────────
#  CUSTOM CHECKBOX WIDGET  (visible tick mark)
# ─────────────────────────────────────────────────────────────

class CheckRow(tk.Frame):
    """A full-row clickable checkbox with columns for quality info."""
    def __init__(self, parent, var, height_p, width_p, mbps, est_size, is_top=False, **kw):
        super().__init__(parent, bg=BG2, cursor="hand2", **kw)
        self.var = var
        self._hovered = False

        # Canvas checkbox (18×18)
        self.cv = tk.Canvas(self, width=18, height=18, bg=BG2,
                             highlightthickness=0, cursor="hand2")
        self.cv.pack(side="left", padx=(6,8), pady=6)
        self._draw()

        # quality label — color by resolution
        q_color = {1080: ACC3, 720: GRN, 480: YLW, 360: ORG}.get(height_p, FG2)
        tk.Label(self, text=f"{height_p}p", bg=BG2, fg=q_color,
                 font=("Consolas", 10, "bold"), width=6, anchor="w").pack(side="left")
        tk.Label(self, text=f"{width_p}×{height_p}", bg=BG2, fg=FG2,
                 font=("Consolas", 9), width=11, anchor="w").pack(side="left")
        tk.Label(self, text=f"{mbps:.1f} Mbps", bg=BG2, fg=FG2,
                 font=("Consolas", 9), width=10, anchor="w").pack(side="left")
        tk.Label(self, text=est_size, bg=BG2, fg=FG2 if not is_top else GRN,
                 font=("Consolas", 9, "bold" if is_top else "normal"), width=10, anchor="w").pack(side="left")

        # bind click everywhere on the row
        self._bind_all(self)
        self.var.trace_add("write", lambda *a: self._draw())

    def _bind_all(self, w):
        w.bind("<Button-1>", self._toggle)
        w.bind("<Enter>",    self._on_enter)
        w.bind("<Leave>",    self._on_leave)
        for child in w.winfo_children():
            self._bind_all(child)

    def _toggle(self, e=None):
        self.var.set(not self.var.get())

    def _on_enter(self, e=None):
        self._hovered = True
        self._set_bg(BG4)

    def _on_leave(self, e=None):
        self._hovered = False
        self._set_bg(BG2)

    def _set_bg(self, c):
        self.configure(bg=c)
        self.cv.configure(bg=c)
        for w in self.winfo_children():
            try: w.configure(bg=c)
            except: pass

    def _draw(self):
        cv = self.cv
        cv.delete("all")
        checked = self.var.get()
        # box
        fill  = ACC if checked else BG3
        outline = ACC if checked else FG3
        cv.create_rectangle(1,1,17,17, fill=fill, outline=outline, width=1)
        # checkmark
        if checked:
            cv.create_line(3,9, 7,13, fill="#fff", width=2, capstyle="round")
            cv.create_line(7,13,15,5, fill="#fff", width=2, capstyle="round")

# ─────────────────────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JioHotstar Downloader")
        self.geometry("960x760")
        self.minsize(800,600)
        self.configure(bg=BG)
        try: self.iconbitmap(default='')
        except: pass

        self.cfg        = load_cfg()
        self._guest     = self._ps = self._method = self._phone = None
        self._mpd       = self._m3u8 = None
        self._quals     = []
        self._q_vars    = []
        self._duration  = None
        self._orig_url  = ""
        self._log_open  = False
        self._dl_thread = None
        self._cancel    = threading.Event()
        self._url_list  = []
        self._active_proc = None  # for hard-kill

        self._build_styles()
        self._build_ui()
        self._refresh_status()

    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, font=FONT)
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("TButton", background=ACC, foreground="#fff",
                    font=FONTB, borderwidth=0, padding=(14,7), relief="flat")
        s.map("TButton",
              background=[("active",ACC2),("disabled",BG3)],
              foreground=[("disabled",FG2)])
        s.configure("Ghost.TButton", background=BG3, foreground=FG2,
                    font=("Segoe UI",9), padding=(10,5), relief="flat", borderwidth=0)
        s.map("Ghost.TButton",
              background=[("active",ACC),("disabled",BG3)],
              foreground=[("active","#fff"),("disabled",FG3)])
        s.configure("Cancel.TButton", background="#7f1d1d", foreground=RED,
                    font=FONTB, padding=(14,7), relief="flat", borderwidth=0)
        s.map("Cancel.TButton", background=[("active","#991b1b")])
        s.configure("TEntry", fieldbackground=BG3, foreground=FG,
                    insertcolor=ACC3, borderwidth=0, relief="flat", padding=6)
        s.configure("TNotebook", background=BG, tabmargins=[0,0,0,0], borderwidth=0)
        s.configure("TNotebook.Tab", background=BG2, foreground=FG2,
                    padding=[22,9], font=FONT, borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected",ACC),("active",BG3)],
              foreground=[("selected","#fff"),("active",FG)])
        s.configure("Prog.Horizontal.TProgressbar",
                    troughcolor=BG3, background=ACC, borderwidth=0, thickness=8,
                    lightcolor=ACC, darkcolor=ACC2)
        s.configure("TCheckbutton", background=BG2, foreground=FG, font=FONT)
        s.map("TCheckbutton", background=[("active",BG2)])
        s.configure("TScale", background=BG2, troughcolor=BG3,
                    sliderlength=16, borderwidth=0)

    # ───────────────────── BUILD UI ─────────────────────

    def _build_ui(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=BG2, height=54)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        lf = tk.Frame(hdr, bg=BG2); lf.pack(side="left", padx=18, pady=12)
        tk.Label(lf, text="▶", bg=BG2, fg=ACC, font=("Segoe UI",15,"bold")).pack(side="left")
        tk.Label(lf, text="  JioHotstar Downloader", bg=BG2, fg=FG,
                 font=("Segoe UI",13,"bold")).pack(side="left")

        rf = tk.Frame(hdr, bg=BG2); rf.pack(side="right", padx=18, pady=14)
        self._status_txt = tk.Label(rf, text="", bg=BG2, fg=FG2, font=("Segoe UI",9))
        self._status_txt.pack(side="right", padx=(0,6))
        self._status_dot = tk.Label(rf, text="●", bg=BG2, fg=RED, font=("Segoe UI",10))
        self._status_dot.pack(side="right")

        tk.Frame(self, bg=ACC, height=2).pack(fill="x")

        # ── Tabs ──
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self._t_login = ttk.Frame(nb); nb.add(self._t_login, text="  Login  ")
        self._t_dl    = ttk.Frame(nb); nb.add(self._t_dl,    text="  Download  ")
        self._t_cfg   = ttk.Frame(nb); nb.add(self._t_cfg,   text="  Settings  ")
        self._build_login()
        self._build_download()
        self._build_settings()

        # ── Footer ──
        foot = tk.Frame(self, bg=BG2, height=30)
        foot.pack(fill="x", side="bottom"); foot.pack_propagate(False)
        tk.Frame(foot, bg=FG3, height=1).pack(fill="x")
        tk.Label(foot, text="Made by Rvind", bg=BG2, fg=FG3,
                 font=("Segoe UI",8)).pack(side="right", padx=14, pady=5)
        tk.Label(foot, text="v6  •  plain DASH  •  yt-dlp/N_m3u8DL-RE/ffmpeg",
                 bg=BG2, fg=FG3, font=("Segoe UI",8)).pack(side="left", padx=14, pady=5)

    # ───────────────────── LOGIN TAB ─────────────────────

    def _build_login(self):
        f = self._t_login
        col = tk.Frame(f, bg=BG); col.pack(anchor="n", padx=60, pady=28, fill="x")

        card = tk.Frame(col, bg=BG2, padx=30, pady=26); card.pack(fill="x")
        tk.Label(card, text="Phone Login", bg=BG2, fg=ACC,
                 font=("Segoe UI",13,"bold")).grid(row=0,column=0,columnspan=3,sticky="w",pady=(0,20))

        tk.Label(card, text="Phone number  (10 digits, no +91)", bg=BG2, fg=FG2,
                 font=("Segoe UI",9)).grid(row=1,column=0,sticky="w")
        self._phone_e = tk.Entry(card, bg=BG3, fg=FG, insertbackground=ACC3,
                                  font=("Consolas",12), relief="flat", width=18, bd=0)
        self._phone_e.grid(row=2,column=0,pady=(5,0),ipady=7,padx=(0,12),sticky="w")
        self._send_btn = ttk.Button(card, text="Send OTP", command=self._send_otp)
        self._send_btn.grid(row=2,column=1,pady=(5,0),sticky="w")

        tk.Label(card, text="OTP", bg=BG2, fg=FG2,
                 font=("Segoe UI",9)).grid(row=3,column=0,sticky="w",pady=(18,0))
        self._otp_e = tk.Entry(card, bg=BG3, fg=FG, insertbackground=ACC3,
                                font=("Consolas",13), relief="flat", width=12, bd=0, state="disabled")
        self._otp_e.grid(row=4,column=0,pady=(5,0),ipady=7,padx=(0,12),sticky="w")
        self._verify_btn = ttk.Button(card, text="Verify & Login",
                                       command=self._verify_otp, state="disabled")
        self._verify_btn.grid(row=4,column=1,pady=(5,0),sticky="w")

        self._login_msg = tk.Label(card, text="", bg=BG2, fg=FG2,
                                    font=("Segoe UI",9), wraplength=460, justify="left")
        self._login_msg.grid(row=5,column=0,columnspan=3,pady=(18,0),sticky="w")

        tok_card = tk.Frame(col, bg=BG2, padx=22, pady=18); tok_card.pack(fill="x",pady=(16,0))
        tk.Label(tok_card, text="Session", bg=BG2, fg=ACC,
                 font=("Segoe UI",9,"bold")).pack(anchor="w")
        self._tok_detail = tk.Label(tok_card, text="Checking...", bg=BG2, fg=FG2,
                                     font=("Segoe UI",9), wraplength=600, justify="left")
        self._tok_detail.pack(anchor="w",pady=(6,10))
        ttk.Button(tok_card, text="Clear Token", style="Ghost.TButton",
                   command=self._clear_token).pack(anchor="w")

    # ───────────────────── DOWNLOAD TAB ─────────────────────

    def _build_download(self):
        f = self._t_dl
        PAD = dict(padx=14, pady=(10,4))

        # URL card
        uc = tk.Frame(f, bg=BG2); uc.pack(fill="x", **PAD)
        ui = tk.Frame(uc, bg=BG2, padx=16, pady=14); ui.pack(fill="x")
        tk.Label(ui, text="Hotstar URL or Content ID", bg=BG2, fg=FG2,
                 font=("Segoe UI",9)).pack(anchor="w",pady=(0,6))
        ur = tk.Frame(ui, bg=BG2); ur.pack(fill="x")
        self._url_e = tk.Entry(ur, bg=BG3, fg=FG, insertbackground=ACC3,
                                font=MONO, relief="flat", bd=0)
        self._url_e.pack(side="left",fill="x",expand=True,ipady=7,padx=(0,10))
        self._fetch_btn = ttk.Button(ur, text="🔍  Fetch Qualities", command=self._fetch)
        self._fetch_btn.pack(side="left")
        br = tk.Frame(ui, bg=BG2); br.pack(fill="x",pady=(8,0))
        tk.Label(br, text="or add to queue:", bg=BG2, fg=FG2, font=("Segoe UI",8)).pack(side="left")
        ttk.Button(br, text="+ Queue", style="Ghost.TButton",
                   command=self._add_to_queue).pack(side="left",padx=8)
        self._queue_lbl = tk.Label(br, text="Queue: 0 items", bg=BG2, fg=FG2, font=("Segoe UI",8))
        self._queue_lbl.pack(side="left")

        # Quality card
        qc = tk.Frame(f, bg=BG2); qc.pack(fill="x", **PAD)
        qi = tk.Frame(qc, bg=BG2, padx=16, pady=12); qi.pack(fill="x")
        qt = tk.Frame(qi, bg=BG2); qt.pack(fill="x",pady=(0,6))
        tk.Label(qt, text="Select Qualities to Download", bg=BG2, fg=FG2,
                 font=("Segoe UI",9)).pack(side="left")
        ttk.Button(qt, text="None", style="Ghost.TButton",
                   command=lambda: self._check_all(False)).pack(side="right",padx=(4,0))
        ttk.Button(qt, text="All", style="Ghost.TButton",
                   command=lambda: self._check_all(True)).pack(side="right")
        self._q_frame = tk.Frame(qi, bg=BG2); self._q_frame.pack(fill="x")
        self._q_hint = tk.Label(self._q_frame,
                                 text="← paste a URL and click  Fetch Qualities",
                                 bg=BG2, fg=FG3, font=("Segoe UI",9))
        self._q_hint.pack(anchor="w", pady=6)

        # Output + download card
        dc = tk.Frame(f, bg=BG2); dc.pack(fill="x", **PAD)
        di = tk.Frame(dc, bg=BG2, padx=16, pady=14); di.pack(fill="x")
        tk.Label(di, text="Output Directory", bg=BG2, fg=FG2, font=("Segoe UI",9)).pack(anchor="w",pady=(0,5))
        or_ = tk.Frame(di, bg=BG2); or_.pack(fill="x",pady=(0,12))
        self._out_var = tk.StringVar(value=self.cfg.get("output_dir",""))
        tk.Entry(or_, textvariable=self._out_var, bg=BG3, fg=FG, insertbackground=ACC3,
                  font=MONO, relief="flat", bd=0).pack(side="left",fill="x",expand=True,ipady=6,padx=(0,10))
        ttk.Button(or_, text="Browse", style="Ghost.TButton", command=self._browse_out).pack(side="left")

        tk.Frame(di, bg=BG3, height=1).pack(fill="x", pady=(0,12))

        # buttons row
        br2 = tk.Frame(di, bg=BG2); br2.pack(fill="x")
        self._dl_btn = ttk.Button(br2, text="⬇  Download", command=self._start_dl)
        self._dl_btn.pack(side="left")
        self._cancel_btn = ttk.Button(br2, text="✕  Cancel", style="Cancel.TButton",
                                       command=self._cancel_dl)
        # cancel hidden by default — shown during download
        self._open_btn = ttk.Button(br2, text="📂 Open Folder", style="Ghost.TButton",
                                     command=self._open_folder, state="disabled")
        self._open_btn.pack(side="left", padx=10)
        self._dl_status = tk.Label(br2, text="", bg=BG2, fg=FG2, font=("Segoe UI",9))
        self._dl_status.pack(side="left")

        # progress bar
        pr = tk.Frame(di, bg=BG2); pr.pack(fill="x", pady=(12,0))
        self._prog = ttk.Progressbar(pr, style="Prog.Horizontal.TProgressbar",
                                      orient="horizontal", mode="determinate", maximum=100)
        self._prog.pack(fill="x",expand=True)
        self._prog_txt = tk.Label(di, text="", bg=BG2, fg=FG2, font=("Segoe UI",8))
        self._prog_txt.pack(anchor="w", pady=(4,0))

        # Log toggle
        lh = tk.Frame(f, bg=BG, cursor="hand2"); lh.pack(fill="x",padx=14,pady=(4,0))
        self._log_lbl_var = tk.StringVar(value="▸  Show log")
        self._log_lbl = tk.Label(lh, textvariable=self._log_lbl_var,
                                   bg=BG, fg=FG2, font=("Segoe UI",9), cursor="hand2")
        self._log_lbl.pack(side="left",pady=3,padx=2)
        for w in (lh, self._log_lbl):
            w.bind("<Button-1>", lambda e: self._toggle_log())

        self._log_frame = tk.Frame(f, bg=BG)
        self._log_box = scrolledtext.ScrolledText(
            self._log_frame, height=9, state="disabled",
            bg="#080a11", fg="#6a6aaa", font=("Consolas",8),
            borderwidth=0, insertbackground=FG, wrap="word",
            selectbackground=ACC2, selectforeground="#fff")
        self._log_box.pack(fill="both",expand=True,padx=14,pady=(3,10))

    # ───────────────────── SETTINGS TAB ─────────────────────

    def _build_settings(self):
        f = self._t_cfg
        outer = tk.Frame(f, bg=BG); outer.pack(fill="both",expand=True)
        card = tk.Frame(outer, bg=BG2, padx=26, pady=24); card.pack(fill="x",padx=26,pady=22)
        tk.Label(card, text="Settings", bg=BG2, fg=ACC,
                 font=("Segoe UI",13,"bold")).grid(row=0,column=0,columnspan=4,sticky="w",pady=(0,10))
        self._cfg_vars = {}

        # ── Download Engine selector ──────────────────────────────
        tk.Label(card, text="╌╌  Download Engine  ╌╌", bg=BG2, fg=FG3,
                 font=("Segoe UI",8)).grid(row=1,column=0,columnspan=4,sticky="w",pady=(0,6))

        eng_frame = tk.Frame(card, bg=BG2); eng_frame.grid(row=2,column=0,columnspan=4,sticky="w",pady=(0,12))
        self._engine_var = tk.StringVar(value=self.cfg.get("engine","auto"))

        engines = [
            ("auto",      "🔄  Auto",           "Try N_m3u8DL-RE → yt-dlp → ffmpeg in order"),
            ("n_m3u8dl",  "⚡  N_m3u8DL-RE",    "Fastest · parallel streams · multi-audio MKV · recommended"),
            ("ytdlp",     "📦  yt-dlp",          "Good fallback · single audio track only"),
            ("ffmpeg",    "🔧  ffmpeg",           "Slow but always works · sequential download"),
        ]
        for col,(val,lbl,tip) in enumerate(engines):
            cell = tk.Frame(eng_frame, bg=BG3, padx=10, pady=8, cursor="hand2")
            cell.grid(row=0, column=col, padx=(0,8), sticky="n")
            rb = tk.Radiobutton(cell, text=lbl, variable=self._engine_var, value=val,
                                bg=BG3, fg=FG, selectcolor=BG3, activebackground=BG3,
                                activeforeground=ACC, font=("Segoe UI",9,"bold"),
                                indicatoron=True, bd=0, highlightthickness=0)
            rb.pack(anchor="w")
            tk.Label(cell, text=tip, bg=BG3, fg=FG2,
                     font=("Segoe UI",7), wraplength=130, justify="left").pack(anchor="w",pady=(4,0))
            cell.bind("<Button-1>", lambda e,v=val: self._engine_var.set(v))

        # highlight selected cell
        def _refresh_eng_ui(*_):
            selected = self._engine_var.get()
            for col,(val,_,__) in enumerate(engines):
                w = eng_frame.grid_slaves(row=0,column=col)
                if w:
                    w[0].configure(bg=ACC if val==selected else BG3)
                    for child in w[0].winfo_children():
                        child.configure(bg=ACC if val==selected else BG3)
        self._engine_var.trace_add("write", _refresh_eng_ui)
        _refresh_eng_ui()

        # ── Paths ─────────────────────────────────────────────────
        tk.Label(card, text="╌╌  Paths  ╌╌", bg=BG2, fg=FG3,
                 font=("Segoe UI",8)).grid(row=3,column=0,columnspan=4,sticky="w",pady=(4,6))

        rows = [
            ("token_file",    "Token File",     "Path to save/load your login token"),
            ("output_dir",    "Output Folder",  "Default download destination"),
            ("n_m3u8dl_path", "N_m3u8DL-RE exe","⚡ Fastest engine. Download from github.com/nilaoda/N_m3u8DL-RE"),
            ("ytdlp_path",    "yt-dlp exe",     "📦 Fallback engine. pip install yt-dlp  OR  path to yt-dlp.exe"),
            ("ffmpeg_path",   "ffmpeg exe",     "🔧 Required for muxing. 'ffmpeg' if in PATH"),
        ]
        for i,(k,lbl,hint) in enumerate(rows):
            r = i+4
            tk.Label(card, text=lbl, bg=BG2, fg=FG, font=FONTB,
                     width=16, anchor="w").grid(row=r,column=0,sticky="w",pady=7)
            var = tk.StringVar(value=self.cfg.get(k,""))
            self._cfg_vars[k] = var
            tk.Entry(card, textvariable=var, bg=BG3, fg=FG, insertbackground=ACC3,
                      font=("Consolas",9), relief="flat", bd=0, width=46
                      ).grid(row=r,column=1,padx=8,ipady=6,sticky="w")
            ttk.Button(card, text="Browse", style="Ghost.TButton",
                       command=lambda k=k,v=var: self._cfg_browse(k,v)
                       ).grid(row=r,column=2,padx=6)
            tk.Label(card, text=hint, bg=BG2, fg=FG2, font=("Segoe UI",8),
                     wraplength=180).grid(row=r,column=3,padx=8,sticky="w")

        r = len(rows)+4
        tk.Frame(card, bg=BG3, height=1).grid(row=r,column=0,columnspan=4,sticky="ew",pady=14)
        r += 1
        tk.Label(card, text="DL Threads", bg=BG2, fg=FG, font=FONTB,
                 anchor="w").grid(row=r,column=0,sticky="w",pady=8)
        self._threads_var = tk.IntVar(value=self.cfg.get("threads",16))
        tr = tk.Frame(card, bg=BG2); tr.grid(row=r,column=1,sticky="w",pady=8)
        ttk.Scale(tr, from_=4, to=64, variable=self._threads_var, orient="horizontal", length=200,
                  command=lambda v: self._threads_lbl.configure(text=str(int(float(v))))
                  ).pack(side="left")
        self._threads_lbl = tk.Label(tr, text=str(self.cfg.get("threads",16)),
                                      bg=BG2, fg=ACC3, font=("Consolas",10,"bold"), width=3)
        self._threads_lbl.pack(side="left",padx=8)
        tk.Label(card, text="Parallel threads / concurrent fragments per download", bg=BG2, fg=FG2,
                 font=("Segoe UI",8)).grid(row=r,column=3,sticky="w",padx=8)
        r += 1
        tk.Label(card, text="Subtitles", bg=BG2, fg=FG, font=FONTB,
                 anchor="w").grid(row=r,column=0,sticky="w",pady=8)
        self._subs_var = tk.BooleanVar(value=self.cfg.get("grab_subs",False))
        ttk.Checkbutton(card, text="Always grab subtitle tracks (N_m3u8DL-RE only)",
                        variable=self._subs_var).grid(row=r,column=1,columnspan=3,sticky="w")
        r += 1
        tk.Frame(card, bg=BG3, height=1).grid(row=r,column=0,columnspan=4,sticky="ew",pady=14)
        r += 1
        ttk.Button(card, text="Save Settings", command=self._save_cfg
                   ).grid(row=r,column=0,sticky="w")
        self._cfg_msg = tk.Label(card, text="", bg=BG2, fg=GRN, font=("Segoe UI",9))
        self._cfg_msg.grid(row=r,column=1,sticky="w",padx=10)

    # ───────────────────── ACTIONS ─────────────────────

    def _log_w(self, t):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", t)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _toggle_log(self):
        if self._log_open:
            self._log_frame.pack_forget()
            self._log_lbl_var.set("▸  Show log")
        else:
            self._log_frame.pack(fill="both", expand=True)
            self._log_lbl_var.set("▾  Hide log")
        self._log_open = not self._log_open

    def _refresh_status(self):
        tok, path = load_token(self.cfg)
        if tok:
            s = tok_str(tok)
            self._status_dot.configure(fg=GRN)
            self._status_txt.configure(text=f"Logged in  •  {s}", fg=FG2)
            self._tok_detail.configure(text=f"✓  Valid token  •  {s}\n{path}", fg=GRN)
        else:
            self._status_dot.configure(fg=RED)
            self._status_txt.configure(text="Not logged in", fg=FG2)
            self._tok_detail.configure(text="✗  No token — use Login tab", fg=RED)

    def _clear_token(self):
        p = self.cfg.get("token_file","")
        if p and os.path.exists(p): os.remove(p)
        self._refresh_status()
        self._tok_detail.configure(text="Token cleared.", fg=FG2)

    # ── Login ──

    def _send_otp(self):
        phone = self._phone_e.get().strip().replace("+91","").replace(" ","")
        if not phone.isdigit() or len(phone)!=10:
            self._login_msg.configure(text="✗ Enter a valid 10-digit number", fg=RED); return
        self._phone = phone
        self._send_btn.configure(state="disabled", text="Sending...")
        self._login_msg.configure(text="Getting guest session...", fg=FG2)
        def _w():
            g,ps = api_guest()
            if not g:
                self.after(0, lambda: self._login_msg.configure(text="✗ Guest token failed", fg=RED))
                self.after(0, lambda: self._send_btn.configure(state="normal", text="Send OTP"))
                return
            self._guest, self._ps = g, ps
            ok, m = api_send_otp(phone, g, ps)
            self._method = m
            if ok:
                self.after(0, self._otp_ok)
            else:
                self.after(0, lambda: self._login_msg.configure(text="✗ OTP failed. Check number.", fg=RED))
                self.after(0, lambda: self._send_btn.configure(state="normal", text="Send OTP"))
        threading.Thread(target=_w, daemon=True).start()

    def _otp_ok(self):
        self._login_msg.configure(text=f"✓ OTP sent to +91 {self._phone}", fg=GRN)
        self._send_btn.configure(state="normal", text="Resend OTP")
        self._otp_e.configure(state="normal")
        self._verify_btn.configure(state="normal")
        self._otp_e.focus()

    def _verify_otp(self):
        otp = self._otp_e.get().strip()
        if not otp.isdigit():
            self._login_msg.configure(text="✗ Invalid OTP", fg=RED); return
        self._verify_btn.configure(state="disabled", text="Verifying...")
        def _w():
            tok = api_verify_otp(self._phone, otp, self._guest, self._ps, self._method or "web")
            if tok:
                path = save_token(tok, self._phone, self.cfg)
                self.after(0, lambda: self._login_msg.configure(
                    text=f"✓ Login successful!\nToken: {path}", fg=GRN))
                self.after(0, self._refresh_status)
                self.after(0, lambda: self._verify_btn.configure(state="normal",text="Verify & Login"))
            else:
                self.after(0, lambda: self._login_msg.configure(
                    text="✗ Wrong OTP or expired. Try again.", fg=RED))
                self.after(0, lambda: self._verify_btn.configure(state="normal",text="Verify & Login"))
        threading.Thread(target=_w, daemon=True).start()

    # ── Download ──

    def _browse_out(self):
        d = filedialog.askdirectory(initialdir=self._out_var.get())
        if d: self._out_var.set(d)

    def _add_to_queue(self):
        url = self._url_e.get().strip()
        if url:
            self._url_list.append(url)
            self._queue_lbl.configure(text=f"Queue: {len(self._url_list)} items")
            self._url_e.delete(0,"end")

    def _check_all(self, val):
        for v in self._q_vars: v.set(val)

    def _fetch(self):
        url = self._url_e.get().strip()
        if not url: messagebox.showwarning("No URL","Paste a URL or content ID first."); return
        cid = extract_cid(url)
        if not cid: messagebox.showerror("Bad URL","Can't extract content ID."); return
        tok, _ = load_token(self.cfg)
        if not tok: messagebox.showerror("Not logged in","Login first."); return
        self._orig_url = url

        for w in self._q_frame.winfo_children(): w.destroy()
        tk.Label(self._q_frame, text="Fetching stream info...",
                 bg=BG2, fg=FG2, font=("Segoe UI",9)).pack(anchor="w",pady=6)
        self._q_vars = []
        self._fetch_btn.configure(state="disabled")

        def _w():
            mpd, m3u8, status = fetch_stream(cid, tok)
            self.after(0, lambda: self._fetch_btn.configure(state="normal"))
            if status != 200:
                self.after(0, lambda: self._show_err(f"API error {status}")); return
            self._mpd, self._m3u8 = mpd, m3u8
            quals, dur, audio_tracks, sub_tracks = parse_qualities(mpd) if mpd else ([], None, [], [])
            self._quals, self._duration = quals, dur
            self._audio_tracks, self._sub_tracks = audio_tracks, sub_tracks
            self.after(0, lambda: self._show_quals(quals, audio_tracks, sub_tracks))
        threading.Thread(target=_w, daemon=True).start()

    def _show_err(self, msg):
        for w in self._q_frame.winfo_children(): w.destroy()
        tk.Label(self._q_frame, text=f"✗ {msg}", bg=BG2, fg=RED, font=("Segoe UI",9)).pack(anchor="w")

    def _make_mini_cb(self, parent, var, label, color=None):
        """Tiny canvas checkbox + label, returns the frame."""
        fg = color or FG
        f = tk.Frame(parent, bg=BG2, cursor="hand2")
        cv = tk.Canvas(f, width=14, height=14, bg=BG2, highlightthickness=0)
        cv.pack(side="left", padx=(0, 3))
        lbl = tk.Label(f, text=label, bg=BG2, fg=fg, font=("Segoe UI", 8))
        lbl.pack(side="left")
        def _draw(*_):
            cv.delete("all")
            on = var.get()
            cv.create_rectangle(1, 1, 13, 13, fill=ACC if on else BG3,
                                 outline=ACC if on else FG3, width=1)
            if on:
                cv.create_line(2, 7, 5, 11, fill="#fff", width=1, capstyle="round")
                cv.create_line(5, 11, 12, 3, fill="#fff", width=1, capstyle="round")
        _draw()
        var.trace_add("write", _draw)
        def _toggle(e=None): var.set(not var.get())
        cv.bind("<Button-1>", _toggle); lbl.bind("<Button-1>", _toggle); f.bind("<Button-1>", _toggle)
        return f

    def _show_quals(self, quals, audio_tracks=None, sub_tracks=None):
        for w in self._q_frame.winfo_children(): w.destroy()
        self._q_vars = []

        # ── audio language checkboxes (default ALL checked) ──
        audio_tracks = audio_tracks or []
        sub_tracks   = sub_tracks or []
        self._audio_cb_vars = {}   # code -> BooleanVar
        self._sub_cb_vars   = {}   # code -> BooleanVar

        if audio_tracks:
            ar = tk.Frame(self._q_frame, bg=BG2); ar.pack(fill="x", pady=(0, 4))
            tk.Label(ar, text="🔊 Audio:", bg=BG2, fg=FG2,
                     font=("Segoe UI", 8, "bold"), width=8, anchor="w").pack(side="left")
            for i, t in enumerate(audio_tracks):
                v = tk.BooleanVar(value=(i == 0))   # only first track checked by default
                self._audio_cb_vars[t["code"]] = v
                self._make_mini_cb(ar, v, t["label"]).pack(side="left", padx=(0, 8))
            # "ALL" toggle shortcut
            def _toggle_all_audio():
                new = not all(v.get() for v in self._audio_cb_vars.values())
                for v in self._audio_cb_vars.values(): v.set(new)
            btn = tk.Label(ar, text="[all]", bg=BG2, fg=ACC, font=("Segoe UI", 7),
                           cursor="hand2")
            btn.pack(side="left", padx=(4, 0))
            btn.bind("<Button-1>", lambda e: _toggle_all_audio())

        # ── subtitle checkboxes (default ALL checked) ──
        if sub_tracks:
            sr = tk.Frame(self._q_frame, bg=BG2); sr.pack(fill="x", pady=(0, 6))
            tk.Label(sr, text="💬 Subs:", bg=BG2, fg=FG2,
                     font=("Segoe UI", 8, "bold"), width=8, anchor="w").pack(side="left")
            for t in sub_tracks:
                v = tk.BooleanVar(value=False)   # subs off by default
                self._sub_cb_vars[t["code"]] = v
                self._make_mini_cb(sr, v, t["label"]).pack(side="left", padx=(0, 8))
            def _toggle_all_subs():
                new = not all(v.get() for v in self._sub_cb_vars.values())
                for v in self._sub_cb_vars.values(): v.set(new)
            btn2 = tk.Label(sr, text="[all]", bg=BG2, fg=ACC, font=("Segoe UI", 7),
                            cursor="hand2")
            btn2.pack(side="left", padx=(4, 0))
            btn2.bind("<Button-1>", lambda e: _toggle_all_subs())

        if audio_tracks or sub_tracks:
            tk.Frame(self._q_frame, bg=BG3, height=1).pack(fill="x", pady=(4, 6))

        if quals:
            # header
            hdr = tk.Frame(self._q_frame, bg=BG2); hdr.pack(fill="x")
            tk.Label(hdr, text="   ", bg=BG2, width=3).pack(side="left")  # checkbox space
            for txt, w in [("Quality",7),("Resolution",12),("Bitrate",11),("Est. Size",10)]:
                tk.Label(hdr, text=txt, bg=BG2, fg=FG3, font=("Segoe UI",8),
                         width=w, anchor="w").pack(side="left")
            tk.Frame(self._q_frame, bg=BG3, height=1).pack(fill="x", pady=(3,3))

            for i, q in enumerate(quals):
                var = tk.BooleanVar(value=(i==0))
                self._q_vars.append(var)
                row = CheckRow(self._q_frame, var,
                               height_p=q["height"], width_p=q["width"],
                               mbps=q["mbps"], est_size=q.get("est_size","?"),
                               is_top=(i==0))
                row.pack(fill="x", pady=1)
        else:
            var = tk.BooleanVar(value=True)
            self._q_vars.append(var)
            row = tk.Frame(self._q_frame, bg=BG2); row.pack(fill="x",pady=4)
            cb_canvas = tk.Canvas(row, width=18, height=18, bg=BG2, highlightthickness=0)
            cb_canvas.pack(side="left",padx=(6,8),pady=6)
            var.set(True)
            def _draw_fb(v=var, cv=cb_canvas):
                cv.delete("all")
                cv.create_rectangle(1,1,17,17, fill=ACC if v.get() else BG3, outline=ACC if v.get() else FG3)
                if v.get():
                    cv.create_line(3,9,7,13, fill="#fff",width=2,capstyle="round")
                    cv.create_line(7,13,15,5, fill="#fff",width=2,capstyle="round")
            _draw_fb()
            var.trace_add("write", lambda *a: _draw_fb())
            tk.Label(row, text="Best available (auto)", bg=BG2, fg=FG,
                     font=MONO, anchor="w").pack(side="left")
            row.bind("<Button-1>", lambda e,v=var: v.set(not v.get()))

    def _cancel_dl(self):
        self._cancel.set()
        self._dl_status.configure(text="Cancelling...", fg=YLW)

    def _start_dl(self):
        if self._dl_thread and self._dl_thread.is_alive():
            messagebox.showinfo("Busy","Download already running."); return
        tok, _ = load_token(self.cfg)
        if not tok: messagebox.showerror("Not logged in","Login first."); return
        stream = self._mpd or self._m3u8
        if not stream: messagebox.showwarning("No stream","Fetch qualities first."); return

        selected = [(i,q) for i,(q,v) in enumerate(
            zip(self._quals if self._quals else [None]*len(self._q_vars), self._q_vars)
        ) if v.get()]
        if not selected: messagebox.showwarning("Nothing selected","Check at least one quality."); return

        out_dir = self._out_var.get().strip() or self.cfg.get("output_dir", APP_DIR)
        self.cfg["output_dir"] = out_dir
        cfg_snap = dict(self.cfg)
        cfg_snap["threads"]    = int(self._threads_var.get())
        cfg_snap["grab_subs"]  = self._subs_var.get()
        cfg_snap["engine"]     = self._engine_var.get()
        cfg_snap["_duration"]  = self._duration
        # collect checked audio languages — always pass explicit codes, never "ALL"
        audio_cb = getattr(self, "_audio_cb_vars", {})
        checked_audio = [code for code, v in audio_cb.items() if v.get()]
        if checked_audio:
            cfg_snap["audio_lang"] = ",".join(checked_audio)   # e.g. "hi,te,ta" or "te"
        else:
            cfg_snap["audio_lang"] = "best"
        # pass per-lang max bitrates so downloader can filter dynamically
        all_tracks = getattr(self, "_audio_tracks", [])
        cfg_snap["_audio_max_kbps"] = {t["code"]: t.get("max_kbps", 128) for t in all_tracks}

        # collect checked subtitle languages
        sub_cb = getattr(self, "_sub_cb_vars", {})
        checked_subs = [code for code, v in sub_cb.items() if v.get()]
        if not sub_cb or not checked_subs:
            cfg_snap["sub_lang"] = "NONE"
        elif len(checked_subs) == len(sub_cb):
            cfg_snap["sub_lang"] = "ALL"
        else:
            cfg_snap["sub_lang"] = ",".join(checked_subs)

        self._cancel.clear()
        self._dl_btn.configure(state="disabled", text="Downloading...")
        self._cancel_btn.pack(side="left", padx=(0,10))   # show cancel
        self._open_btn.configure(state="disabled")
        self._prog.configure(value=0)
        self._prog_txt.configure(text="")
        self._dl_status.configure(text="Starting...", fg=FG2)
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0","end")
        self._log_box.configure(state="disabled")

        orig_url = self._orig_url
        last_out = [None]

        def _work():
            all_ok = True
            for idx,(i,q) in enumerate(selected):
                if self._cancel.is_set(): break
                q_height = q["height"] if q else 0
                q_tag    = f"{q_height}p" if q_height else "best"
                fname    = make_filename(orig_url, q_height, "H264") if orig_url else \
                           f"hotstar_{q_tag}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.after(0, lambda t=q_tag, n=idx+1, tot=len(selected):
                    self._dl_status.configure(text=f"[{n}/{tot}] {t}", fg=FG2))

                ok, out_path = run_download(
                    stream, out_dir, fname, q, cfg_snap,
                    lambda pct,spd: self.after(0, lambda p=pct,s=spd: (
                        self._prog.configure(value=p),
                        self._prog_txt.configure(text=f"{p:.1f}%{'   '+s if s else ''}")
                    )),
                    lambda t: self.after(0, lambda t=t: self._log_w(t)),
                    self._cancel
                )
                if ok: last_out[0] = out_path
                else:  all_ok = False

            def _done():
                self._dl_btn.configure(state="normal", text="⬇  Download")
                self._cancel_btn.pack_forget()   # hide cancel
                if self._cancel.is_set():
                    self._dl_status.configure(text="Cancelled", fg=YLW)
                elif all_ok:
                    self._prog.configure(value=100)
                    self._dl_status.configure(text="✓ Done!", fg=GRN)
                    self._open_btn.configure(state="normal")
                else:
                    self._dl_status.configure(text="✗ Failed — check log", fg=RED)
                    if not self._log_open: self._toggle_log()
                self._refresh_status()
            self.after(0, _done)

        self._dl_thread = threading.Thread(target=_work, daemon=True)
        self._dl_thread.start()

    def _open_folder(self):
        d = self._out_var.get() or self.cfg.get("output_dir","")
        if d and os.path.isdir(d):
            if sys.platform=="win32": os.startfile(d)
            else: subprocess.Popen(["xdg-open", d])

    # ── Settings ──

    def _cfg_browse(self, key, var):
        if any(x in key for x in ("dir","folder","output")):
            d = filedialog.askdirectory()
            if d: var.set(d)
        else:
            f = filedialog.askopenfilename(filetypes=[("All","*.*"),("Exe","*.exe")])
            if f: var.set(f)

    def _save_cfg(self):
        for k,v in self._cfg_vars.items(): self.cfg[k] = v.get()
        self.cfg["threads"]   = int(self._threads_var.get())
        self.cfg["grab_subs"] = self._subs_var.get()
        self.cfg["engine"]    = self._engine_var.get()
        self._out_var.set(self.cfg.get("output_dir",""))
        save_cfg(self.cfg)
        self._cfg_msg.configure(text="✓ Saved")
        self.after(2000, lambda: self._cfg_msg.configure(text=""))
        self._refresh_status()


if __name__ == "__main__":
    app = App()
    app.mainloop()
