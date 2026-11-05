"""auth.py — 用 Google（Gmail）登入（用戶 2026-11-06 要求）：OAuth 2.0 授權碼流程，只攞 email。
- 准登入：ALLOWED_EMAILS（逗號分隔，默認 etchan112@gmail.com,manhey@gmail.com）。
- 要 GOOGLE_CLIENT_ID／GOOGLE_CLIENT_SECRET（可以同報告中心共用同一個 Google OAuth 用戶端），
  Google Cloud Console 嗰個用戶端要加「已授權重新導向 URI」：https://<網站網址>/auth/callback。
- 登入後發一個簽咗名嘅 cookie（HMAC-SHA256，30 日），伺服器唔使記 session。簽名金鑰：SESSION_SECRET，冇就自動產生存喺 DATA_DIR/session_secret。
- 用戶揀「只用 Google」：Google 設定好之後密碼登入自動關閉；未設定好（冇 GOOGLE_CLIENT_ID）先暫時照用 GEN_PASSWORD，免得被鎖喺外面。
  想 Google 設定好之後仍然保留密碼，可以設 PASSWORD_LOGIN=1。"""
import base64, hashlib, hmac, json, os, secrets, time, urllib.parse, urllib.request

CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
ALLOWED = {e.strip().lower() for e in os.environ.get('ALLOWED_EMAILS', 'etchan112@gmail.com,manhey@gmail.com').split(',') if e.strip()}
COOKIE = 'jlgen_session'
MAX_AGE = 30 * 86400


def google_on(): return bool(CLIENT_ID and CLIENT_SECRET)
def password_on(): return bool(os.environ.get('GEN_PASSWORD')) and (not google_on() or os.environ.get('PASSWORD_LOGIN') == '1')


def _secret(data_dir):
    s = os.environ.get('SESSION_SECRET')
    if s: return s.encode()
    f = os.path.join(data_dir, 'session_secret')
    try: return open(f, 'rb').read().strip()
    except FileNotFoundError:
        v = secrets.token_hex(32).encode()
        with open(f, 'wb') as fh: fh.write(v)
        os.chmod(f, 0o600); return v


def _b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def _unb64(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def make_cookie(email, data_dir):
    payload = _b64(json.dumps({'e': email, 'x': int(time.time()) + MAX_AGE}).encode())
    sig = _b64(hmac.new(_secret(data_dir), payload.encode(), hashlib.sha256).digest())
    return f'{payload}.{sig}'


def read_cookie(header, data_dir):
    """Cookie header → 已登入嘅 email（簽名啱、未過期、仲喺准登入名單）；否則 None"""
    if not header: return None
    val = next((c.split('=', 1)[1] for c in header.split(';') if c.strip().startswith(COOKIE + '=')), None)
    if not val or '.' not in val: return None
    payload, sig = val.strip().rsplit('.', 1)
    want = _b64(hmac.new(_secret(data_dir), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, want): return None
    try: d = json.loads(_unb64(payload))
    except Exception: return None
    if d.get('x', 0) < time.time() or d.get('e', '').lower() not in ALLOWED: return None
    return d['e']


def base_url(headers):
    dom = os.environ.get('PUBLIC_URL') or ('https://' + os.environ['RAILWAY_PUBLIC_DOMAIN'] if os.environ.get('RAILWAY_PUBLIC_DOMAIN') else '')
    if dom: return dom.rstrip('/')
    return f"http://{headers.get('Host', 'localhost')}"


def login_url(headers, state):
    q = {'client_id': CLIENT_ID, 'redirect_uri': base_url(headers) + '/auth/callback', 'response_type': 'code',
         'scope': 'openid email', 'state': state, 'prompt': 'select_account'}
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(q)


def exchange(code, headers):
    """授權碼 → Google 驗證過嘅 email。id_token 係經 TLS 直接由 Google token endpoint 攞返（OIDC 授權碼流程），驗 aud／iss／email_verified。"""
    data = urllib.parse.urlencode({'code': code, 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
                                   'redirect_uri': base_url(headers) + '/auth/callback', 'grant_type': 'authorization_code'}).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST',
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=30) as r: tok = json.load(r)
    claims = json.loads(_unb64(tok['id_token'].split('.')[1]))
    if claims.get('aud') != CLIENT_ID or claims.get('iss') not in ('https://accounts.google.com', 'accounts.google.com'):
        raise ValueError('Google 回覆唔啱（aud／iss）')
    if claims.get('exp', 0) < time.time(): raise ValueError('Google 登入過期，請再試')
    if not claims.get('email_verified'): raise ValueError('Google 帳戶 email 未驗證')
    return claims['email'].lower()
