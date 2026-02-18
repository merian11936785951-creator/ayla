#!/usr/bin/env python3
"""
Uso:
  python3 proxycdn.py action=manifest id=230
  python3 proxycdn.py action=cdm     id=230
  python3 proxycdn.py action=manifest id=Content/Channel/SPOAGMHD/dsc3/manifest.mpd
"""

import base64
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import requests
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH as WidevinePSSH

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.environ.get("CLARO_RESULTS", os.path.join(_SCRIPT_DIR, "claro_tv_results.json"))

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(
    NoRedirect(),
    urllib.request.HTTPSHandler(context=ssl_ctx)
)

# ─────────────────────────────────────────────
# Claro TV API (gera o JSON quando ID não existe)
# ─────────────────────────────────────────────

class ClaroTVAPI:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.clarotvmais.com.br"
        self.xsrf_token = '8Q1ogAsWxee9UAVSUwJQcMqe6eFSPKqjuEmAjyM1Ct3HhkKQeUBREVWuA0DxrCRJ'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
        self.session.cookies.update({
            'optimizelyEndUserId': 'oeu1769989709232r0.9330823549578667',
            'optimizelySegments': '%7B%225106620719%22%3A%22ff%22%2C%225117170607%22%3A%22referral%22%2C%225102881182%22%3A%22false%22%7D',
            'optimizelyBuckets': '%7B%7D',
            '_gcl_au': '1.1.927248865.1769989715',
            '_vwo_uuid_v2': 'D5BD95F3B322EC6A2A88F58AA706317EF|f52d0b7750a9cc88d260430401eff0ff',
            '_sfid_f63e': '{%22anonymousId%22:%22ffa99c5f6dc0f841%22%2C%22consents%22:[]}',
            '_evga_cad8': '{%22uuid%22:%22ffa99c5f6dc0f841%22%2C%22puid%22:%22r2l9LFhurpx_JpsO_1V-t08J3GTD39vNkJSVVvpkE_PIn5BD6e02XNvYGHB635_TmaLmKTL99cA4YogpSV0L0-n2bSDuZMdYOAUWEmGjOHaj-supHxZ-Q-597yk8y5dVIZ-OIen7fiMaKYKkwY28C9Xf23SeE9Mb8Ytdr5QHadDHb5aZEKNup3IoHbl8q3mS3NFm5Bu28lGNljqlfld-iRTIqaMyEbrju2VtNIN5CI5JjxH5-cfEkD4FDc76KPROIW4lXNgbTRSFhsJBpHDPuqfG5Ok2l-EXcpN8-2nreuQJuvPyJfJ3c9zmhuPuVweb%22%2C%22affinityId%22:%220Em%22}',
            '_ga_XJJ199PE67': 'GS2.1.s1771358993$o8$g1$t1771359021$j32$l0$h0',
            '_ga': 'GA1.1.1061590803.1769989715',
            '_vwo_uuid': 'D5BD95F3B322EC6A2A88F58AA706317EF',
            '_vwo_ds': '3%241769989714%3A86.2079499%3A%3A%3A%3A%3A1771358993%3A1771307451%3A7',
            '_vis_opt_s': '6%7C',
            'OptanonConsent': 'isGpcEnabled=0&datestamp=Tue+Feb+17+2026+17%3A09%3A54+GMT-0300&version=202401.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&landingPath=NotLandingPage&groups=C0004%3A1%2CC0003%3A1%2CC0002%3A1%2CC0001%3A1&AwaitingReconsent=false',
            '_fbp': 'fb.2.1769989715910.730022792628906899',
            '_hjSessionUser_3379283': 'eyJpZCI6ImViODEyODgyLTg4NmItNTk1ZC05YmFiLWU5MGQ5MWZkNjA2ZCIsImNyZWF0ZWQiOjE3Njk5ODk3MTYwMDUsImV4aXN0ZW5jZSI6dHJ1ZX0=',
            '_tt_enable_cookie': '1',
            '_ttp': '01KGDSQE1VTXD1N9WP46927MVS_.tt.2',
            'ttcsid': '1771358994343::CMwJ5mrrdw3sO7pE_i3Y.7.1771359021469.0',
            'ttcsid_CEBNB9RC77UA05ON2VFG': '1771358994343::uqQLOjiMZd_2ErcIcDhD.7.1771359021469.1',
            'avs_browser_id': 'f9868aeb-3c6b-4317-9c24-2fcb6a07a85b',
            'cookiesession1': '678A3E2C79F8E49BAF57A964B7EEDD3A',
            'avs-client-user-session-id': 'ae9395b4-81a2-4e83-8b15-1dc4f53ba39d',
            'avs_cookie': 'eyJhbGciOiJIUzI1NiJ9.eyJwYXlsb2FkIjoiRlJZdzQ2a0hjZVdPeW9UVVluUFFQR20zR09uamY0SDh6NWFQQzdVNDJzYzV5aTd2dzlyOXE2UFhqUlU0Z0J5TFRHZUd6N3ROWFI4Q3BnY0FoQ3grOU5TM29WRFdMUWhVRUFaWHorOXZ5WXJtK28zd3J5QVBodTA2ZS92WDAxREVTTVVKeDVTRStXYXpQN0k0Mi95RXhzWmJWOXhmRFFIRiIsImlzcyI6IkFWUyIsInhzcmZUb2tlbiI6IjhRMW9nQXNXeGVlOVVBVlNVd0pRY01xZTZlRlNQS3FqdUVtQWp5TTFDdDNIaGtLUWVVQlJFVld1QTBEeHJDUkoiLCJleHAiOjE3ODY4MzQ5NTQsIm5vbmNlIjoiW0JANGZkYmQwZGQifQ.rn46eK4QgXaQ9uwOuVsnUX06XqlvaybqSQRrWSauK2g',
            'LoginInfo': '%7B%22resultCode%22%3A%22OK%22%2C%22errorDescription%22%3A%22%22%2C%22message%22%3A%22%22%2C%22systemTime%22%3A1771282955%2C%22crmAccountId%22%3A%22nocbrasil%22%2C%22userName%22%3A%22NET%20SAO%20PAULO%20LTDA%22%2C%22idmSessionId%22%3A%22%22%2C%22defaultServiceID%22%3A%22313560111003%22%2C%22serviceIDList%22%3Anull%2C%22isTvVas%22%3Afalse%7D',
            'avs_user_info': 'NET SAO PAULO LTDA||gustavo.carminatti@gmail.com',
            'avs_authmethod': 'PASSWORD',
            'xWingAllianceV2': 'ef7dc23c4a1dcd35bc568b366ed05c4d:b1bc049da020e617da0ced178db9b65b841bacedfc59845f93682da94443fef22e5c3695774c497037d90e433d3883116234a229dcbc6a90130545ab1a1a108ecfa6aacada933ff8830d5dbed6ad40c2',
            'up': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjIyLCJ1c2VybmFtZSI6Im5vY2JyYXNpbCIsInVzZXJQQ0xldmVsRXBnIjoiOTkiLCJ1c2VyUGNFeHRlbmRlZFJhdGluZ3MiOiIiLCJzdHJlYW1pbmdTZXNzaW9uSWQiOiJlYmZjODk0OC0wNjRmLTRkYzUtYjY1Yy00MDc5NjVlYzlmOTMiLCJpYXQiOjE3NzEyODQyNjB9.y7Y5tsO7kBtrbXwTZDugZ4ONtCquly63nNgblxYwIEs',
            'bitmovin_analytics_uuid': '33c95973-0bf4-4449-8763-83fb4cb82e48',
            'dtCookie': 'v_4_srv_-2D4533_sn_72UVGP2H9JV9MVPO0DK0DKJQPGTQI36C',
            'rxVisitor': '1771358985342BPD9OBN621F6UNT45V39262SKMV5ETUF',
            'dtPC': '-4533$158985338_134h119vFPUUMDAIRVGVNNEKJAIFDHFFHWWEGCIG-0e0',
            'rxvt': '1771360821519|1771358985342',
            'dtSa': '-',
            'sessionId': '196f91a8-de13-77a6-8212-55d4dff0d3b0',
            '6df00a0c49b6e342f9ed3346cca75ca4': 'c52850b5b9b47b7456750efba7beaa9d',
            'userToken': 'ny4qvPO624NwAeNtogLuFaCOBuVjWWt5buSqQTL5cCrD6AMT4bU9ooiF1O1vnzNEyc7o%2Ba%2FLs%2B4%3D',
            'subtitleDisclaimer': 'false',
            '_vwo_sn': '1369279%3A6%3A%3A%3A%3A%3A22',
            '_hjSession_3379283': 'eyJpZCI6IjYxY2RjNWZjLTgzMWItNDVlMy1hNDE3LWRiZDUwYzA2OWFhZCIsImMiOjE3NzEzNTg5OTQzOTUsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=',
            '_vis_opt_test_cookie': '1',
        })

    def fetch_channel(self, channel_id):
        """Busca dados CDN do canal e salva no JSON."""
        print(f"[API] Buscando canal {channel_id} na Claro TV...", file=sys.stderr)

        # Auth
        auth_headers = self.headers.copy()
        auth_headers.update({
            'x-xsrf-token': self.xsrf_token,
            'Referer': f"{self.base_url}/?",
        })
        self.session.get(
            f"{self.base_url}/avsclient/user/auth",
            params={'channel': 'PCTV'},
            headers=auth_headers
        )

        # CDN info
        cdn_headers = self.headers.copy()
        cdn_headers.update({
            'x-xsrf-token': self.xsrf_token,
            'Referer': f"{self.base_url}/player/{channel_id}/no-ar",
        })
        resp = self.session.get(
            f"{self.base_url}/avsclient/playback/getcdn",
            params={
                'id': channel_id, 'type': 'LIVE', 'player': 'bitmovin',
                'tvChannelId': channel_id, 'location': 'MARINGA,PARANA', 'channel': 'PCTV'
            },
            headers=cdn_headers
        )

        if resp.status_code != 200:
            print(f"[API] Erro HTTP {resp.status_code}", file=sys.stderr)
            return False

        data = resp.json()

        # Stop content
        stop_headers = self.headers.copy()
        stop_headers.update({'x-xsrf-token': self.xsrf_token, 'Referer': f"{self.base_url}/?'"})
        self.session.get(
            f"{self.base_url}/avsclient/playback/stopcontent",
            params={'scId': '', 'contentId': channel_id, 'deltaThreshold': '4',
                    'type': 'LIVE', 'bookmark': '0', 'channel': 'PCTV'},
            headers=stop_headers
        )

        # Carrega JSON existente ou cria novo
        try:
            with open(RESULTS_FILE) as f:
                results = json.load(f)
        except Exception:
            results = {}

        results[str(channel_id)] = {
            'status': 'success',
            'data': data,
            'cookies': {c.name: c.value for c in self.session.cookies}
        }

        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"[API] Canal {channel_id} salvo em {RESULTS_FILE}", file=sys.stderr)
        return True


# ─────────────────────────────────────────────
# Funções de suporte ao proxy
# ─────────────────────────────────────────────

def jwt_expiry(qsig):
    try:
        part = qsig.split(".")[1]
        part += "=" * (-len(part) % 4)
        return float(json.loads(base64.urlsafe_b64decode(part)).get("exp", 0))
    except Exception:
        return 0.0


def load_entry(entry_id):
    """Carrega entrada do JSON. Se não existir, busca via API e tenta de novo."""
    try:
        with open(RESULTS_FILE) as f:
            data = json.load(f)
    except Exception:
        data = {}

    entry = data.get(str(entry_id))
    if entry:
        return entry

    # Não encontrou -> busca via API
    print(f"[INFO] ID {entry_id} nao encontrado no JSON. Buscando via API...", file=sys.stderr)
    api = ClaroTVAPI()
    ok = api.fetch_channel(entry_id)
    if not ok:
        print(f"[ERRO] Nao foi possivel obter dados do canal {entry_id}", file=sys.stderr)
        sys.exit(1)

    # Recarrega após salvar
    with open(RESULTS_FILE) as f:
        data = json.load(f)

    entry = data.get(str(entry_id))
    if not entry:
        print(f"[ERRO] Mesmo apos busca, ID {entry_id} nao foi encontrado", file=sys.stderr)
        sys.exit(1)

    return entry


def claro_manifest(channel_id):
    try:
        out = subprocess.run(
            ["python3", "/root/v3p/scripts/claropro.py", "action=manifest", f"id={channel_id}"],
            capture_output=True, timeout=10
        )
        return json.loads(out.stdout) if out.returncode == 0 else None
    except Exception:
        return None


def fetch_token(channel_id, profile):
    fallback = profile.replace("dsc", "h4f", 1)
    url = (f"https://getcdn.nowonline.com.br/Content/Channel/"
           f"{channel_id}/{fallback}/index.m3u8?response=200&bk-ml=1")

    for attempt in range(3):
        if attempt:
            time.sleep(min(2 ** attempt, 5))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            loc = ""
            try:
                resp = opener.open(req, timeout=5)
                loc = resp.headers.get("Location", "")
                resp.close()
            except urllib.error.HTTPError as e:
                loc = e.headers.get("Location", "")
            if loc:
                return loc
        except Exception as e:
            print(f"[WARN] tentativa {attempt+1}: {e}", file=sys.stderr)
    return None


def resolve(channel_id, profile, sub_path):
    data = claro_manifest(channel_id)
    if data and data.get("ManifestUrl"):
        return data["ManifestUrl"], data.get("Headers") or {}

    loc = fetch_token(channel_id, profile)
    if not loc:
        print("[ERRO] Nao foi possivel obter token CDN", file=sys.stderr)
        sys.exit(1)

    host = loc.split("/Content/")[0]
    qsig = loc.split("qsig=")[1]
    return f"{host}/Content/Channel/{channel_id}/{profile}/{sub_path}?qsig={qsig}&bk-ml=1", {}


def resolve_raise(channel_id, profile, sub_path):
    """Como resolve() mas levanta RuntimeError em falha (para uso pela API HTTP)."""
    data = claro_manifest(channel_id)
    if data and data.get("ManifestUrl"):
        return data["ManifestUrl"], data.get("Headers") or {}
    loc = fetch_token(channel_id, profile)
    if not loc:
        raise RuntimeError("Nao foi possivel obter token CDN")
    host = loc.split("/Content/")[0]
    qsig = loc.split("qsig=")[1].split("&")[0]
    return f"{host}/Content/Channel/{channel_id}/{profile}/{sub_path}?qsig={qsig}&bk-ml=1", {}


def load_entry_raise(entry_id):
    """Carrega entrada do JSON ou via API; levanta RuntimeError se falhar (para API HTTP)."""
    try:
        with open(RESULTS_FILE) as f:
            data = json.load(f)
    except Exception:
        data = {}
    entry = data.get(str(entry_id))
    if entry:
        return entry
    api = ClaroTVAPI()
    if not api.fetch_channel(entry_id):
        raise RuntimeError(f"Nao foi possivel obter dados do canal {entry_id}")
    with open(RESULTS_FILE) as f:
        data = json.load(f)
    entry = data.get(str(entry_id))
    if not entry:
        raise RuntimeError(f"Canal {entry_id} nao encontrado apos busca")
    return entry


def get_manifest_url(entry_id):
    """Retorna (url, headers) do manifest para o canal entry_id (ID numerico). Levanta em erro."""
    entry = load_entry_raise(entry_id)
    src = entry["data"]["response"]["src"]
    path = src.split("/Content/Channel/")[1] if "/Content/Channel/" in src else src
    parts = path.split("/")
    if len(parts) < 2:
        raise RuntimeError("Caminho invalido")
    channel_id, profile = parts[0], parts[1]
    sub_path = "/".join(parts[2:]) or "manifest.mpd"
    if any(sub_path.endswith(x) for x in (".mpd", ".m4v", ".m4a")):
        profile = profile.replace("h4f", "dsc", 1)
    return resolve_raise(channel_id, profile, sub_path)


# Margem em segundos antes do vmxToken expirar para já renovar
VMX_TOKEN_EXPIRY_MARGIN = 60


def get_cdm_keys(entry_id, refresh=False):
    """Retorna lista de strings 'kid:key' para o canal. Levanta em erro.
    Gera novo (chama API) somente se: refresh=True, ou entrada nao existe, ou vmxToken expirado.
    Caso contrario usa tokens/cookies ja salvos em claro_tv_results.json."""
    entry = load_entry_raise(entry_id)
    resp = entry["data"]["response"]
    vmx, src = resp["vmxToken"], resp["src"]
    src_path = src.split("/Content/Channel/")[1]
    src_parts = src_path.split("/")
    ch_id, profile = src_parts[0], src_parts[1]
    sub = "/".join(src_parts[2:]) or "manifest.mpd"

    # Renovar da API só se forçado ou se o token tiver exp e estiver expirado/prestes a expirar
    exp = jwt_expiry(vmx)
    need_refresh = refresh or (exp > 0 and time.time() >= exp - VMX_TOKEN_EXPIRY_MARGIN)
    if need_refresh:
        api = ClaroTVAPI()
        api.fetch_channel(entry_id)
        with open(RESULTS_FILE) as f:
            fresh = json.load(f)
        resp = fresh[str(entry_id)]["data"]["response"]
        vmx, src = resp["vmxToken"], resp["src"]
        src_path = src.split("/Content/Channel/")[1]
        src_parts = src_path.split("/")
        ch_id, profile = src_parts[0], src_parts[1]
        sub = "/".join(src_parts[2:]) or "manifest.mpd"

    claro = claro_manifest(ch_id)
    if claro and claro.get("ManifestUrl"):
        mpd_url = claro["ManifestUrl"]
    else:
        loc = fetch_token(ch_id, profile)
        if not loc:
            raise RuntimeError("Nao foi possivel obter token qsig para o MPD")
        host = loc.split("/Content/")[0]
        qsig = loc.split("qsig=")[1].split("&")[0]
        mpd_url = f"{host}/Content/Channel/{ch_id}/{profile}/{sub}?qsig={qsig}&bk-ml=1"

    mpd_resp = requests.get(mpd_url, verify=False, timeout=15)
    mpd_resp.raise_for_status()
    root = ET.fromstring(mpd_resp.text)

    pssh_list = root.findall(".//{urn:mpeg:cenc:2013}pssh")
    if not pssh_list:
        pssh_list = [el for el in root.iter() if el.tag.endswith("}pssh") or el.tag == "pssh"]
    pssh_list = [p for p in pssh_list if p.text and len(p.text.strip()) > 50]

    if pssh_list:
        pssh_data = pssh_list[-1].text.strip()
    else:
        ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}
        seg_tmpl = root.find(".//mpd:SegmentTemplate", ns) or root.find(".//{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate")
        init_tmpl = seg_tmpl.get("initialization") if seg_tmpl is not None else None
        rep = root.find(".//mpd:Representation", ns) or root.find(".//{urn:mpeg:dash:schema:mpd:2011}Representation")
        rep_id = rep.get("id") if rep is not None else "stream_01"
        init_file = init_tmpl.replace("$RepresentationID$", rep_id) if init_tmpl else f"{rep_id}/1_init.m4i"
        base_url = mpd_url.split("manifest.mpd")[0]
        init_url = base_url + init_file
        init_resp = requests.get(init_url, verify=False, timeout=15)
        init_resp.raise_for_status()
        init_data = init_resp.content
        WIDEVINE_SYS_ID = bytes.fromhex("edef8ba979d64acea3c827dcd51d21ed")
        pssh_data = None
        i = 0
        while i < len(init_data) - 28:
            if init_data[i+4:i+8] == b"pssh":
                box_size = int.from_bytes(init_data[i:i+4], "big")
                if 32 <= box_size <= len(init_data) - i:
                    box = init_data[i:i+box_size]
                    if box[12:28] == WIDEVINE_SYS_ID:
                        pssh_data = base64.b64encode(box).decode()
                        break
            i += 1
        if not pssh_data:
            raise RuntimeError("PSSH Widevine nao encontrado")

    wvd_path = os.path.join(_SCRIPT_DIR, "WVDs.wvd")
    if not os.path.isfile(wvd_path):
        wvd_path = os.path.join(_SCRIPT_DIR, "device.wvd")
    pssh = WidevinePSSH(pssh_data)
    device = Device.load(wvd_path)
    cdm = Cdm.from_device(device)
    session = cdm.open()
    challenge = cdm.get_license_challenge(session, pssh)
    lic_resp = requests.post(
        "https://multidrm.core.verimatrixcloud.net/widevine",
        data=challenge,
        headers={
            "accept": "*/*", "authorization": vmx,
            "content-type": "application/json",
            "origin": "https://www.clarotvmais.com.br",
            "referer": "https://www.clarotvmais.com.br/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        },
        timeout=15
    )
    lic_resp.raise_for_status()
    cdm.parse_license(session, lic_resp.content)
    keys = [k for k in cdm.get_keys(session) if k.type != "SIGNING"]
    cdm.close(session)
    if not keys:
        raise RuntimeError("Nenhuma chave encontrada")
    out = []
    for k in keys:
        kid = str(k.kid).replace("-", "")
        key = k.key.hex() if hasattr(k.key, "hex") else k.key
        out.append(f"{kid}:{key}")
    expires_at = int(jwt_expiry(vmx))  # Unix timestamp para cache no frontend
    return out, expires_at


# ─────────────────────────────────────────────
# API HTTP (backend para o frontend Node/Streamlink)
# ─────────────────────────────────────────────

def run_http_server(port=9000):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            print(f"[API] {args[0]}", file=sys.stderr)

        def do_GET(self):
            path = self.path.split("?")[0]
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = urllib.parse.parse_qs(qs)
            refresh = params.get("refresh", ["0"])[0].lower() in ("1", "true", "yes")
            parts = path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "api" and parts[1] == "stream":
                entry_id = parts[2]
                try:
                    url, headers = get_manifest_url(entry_id)
                    keys, expires_at = get_cdm_keys(entry_id, refresh=refresh)
                    key = keys[0] if keys else None
                    key2 = keys[1] if len(keys) > 1 else None
                    body = json.dumps({"url": url, "key": key, "key2": key2, "expires_at": expires_at}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", len(body))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as e:
                    body = json.dumps({"error": str(e)}).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", len(body))
                    self.end_headers()
                    self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[API] Backend proxycdn rodando em http://0.0.0.0:{port}", file=sys.stderr)
    print(f"[API] GET /api/stream/<id> -> {{ url, key, key2 }}", file=sys.stderr)
    server.serve_forever()


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    if "--serve" in sys.argv:
        idx = sys.argv.index("--serve")
        port = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 9000
        run_http_server(port)
        return

    args = {a.split("=")[0]: a.split("=", 1)[1] for a in sys.argv[1:] if "=" in a}
    action   = args.get("action")
    entry_id = args.get("id")

    if action not in ("manifest", "cdm") or not entry_id:
        print("Uso:")
        print("  python3 proxycdn.py action=manifest id=230")
        print("  python3 proxycdn.py action=cdm     id=230")
        print("  python3 proxycdn.py --serve [porta]   # API HTTP para frontend (default 9000)")
        sys.exit(1)

    # ── action=cdm ────────────────────────────
    if action == "cdm":
        entry  = load_entry(entry_id)
        resp   = entry["data"]["response"]
        vmx    = resp["vmxToken"]
        src    = resp["src"]

        # Extrai channel_id e profile do src para obter URL autenticada com qsig
        # src ex: https://getcdn.../Content/Channel/MRGGLHD/dsc1/manifest.mpd
        src_path  = src.split("/Content/Channel/")[1]   # MRGGLHD/dsc1/manifest.mpd
        src_parts = src_path.split("/")
        ch_id     = src_parts[0]
        profile   = src_parts[1]
        sub       = "/".join(src_parts[2:]) or "manifest.mpd"

        # Gera novo (API) somente se token tiver exp e estiver expirado/prestes a expirar
        exp = jwt_expiry(vmx)
        need_refresh = exp > 0 and time.time() >= exp - VMX_TOKEN_EXPIRY_MARGIN
        if need_refresh:
            print(f"[CDM] Token expirado ou proximo, atualizando via API para canal {entry_id}...", file=sys.stderr)
            api = ClaroTVAPI()
            api.fetch_channel(entry_id)
            with open(RESULTS_FILE) as _f:
                _fresh = json.load(_f)
            resp = _fresh[str(entry_id)]["data"]["response"]
            vmx  = resp["vmxToken"]
            src  = resp["src"]
            src_path  = src.split("/Content/Channel/")[1]
            src_parts = src_path.split("/")
            ch_id     = src_parts[0]
            profile   = src_parts[1]
            sub       = "/".join(src_parts[2:]) or "manifest.mpd"
        else:
            print(f"[CDM] Usando token em cache para {entry_id}", file=sys.stderr)

        print(f"[CDM] Obtendo URL autenticada para {ch_id}/{profile}...", file=sys.stderr)

        # Busca token qsig (mesmo fluxo do action=manifest)
        claro = claro_manifest(ch_id)
        if claro and claro.get("ManifestUrl"):
            mpd_url = claro["ManifestUrl"]
        else:
            loc = fetch_token(ch_id, profile)
            if not loc:
                print("[ERRO] Nao foi possivel obter token qsig para o MPD", file=sys.stderr)
                sys.exit(1)
            host = loc.split("/Content/")[0]
            qsig = loc.split("qsig=")[1]
            mpd_url = f"{host}/Content/Channel/{ch_id}/{profile}/{sub}?qsig={qsig}&bk-ml=1"

        print(f"[CDM] MPD autenticado: {mpd_url}", file=sys.stderr)
        print(f"[CDM] Extraindo PSSH...", file=sys.stderr)

        # 1. Baixa MPD e extrai PSSH
        mpd_resp = requests.get(mpd_url, verify=False, timeout=15)
        mpd_resp.raise_for_status()
        root = ET.fromstring(mpd_resp.text)

        # Tenta extrair PSSH inline do MPD
        pssh_list = root.findall(".//{urn:mpeg:cenc:2013}pssh")
        if not pssh_list:
            pssh_list = [el for el in root.iter() if el.tag.endswith("}pssh") or el.tag == "pssh"]
        pssh_list = [p for p in pssh_list if p.text and len(p.text.strip()) > 50]

        if pssh_list:
            pssh_data = pssh_list[-1].text.strip()  # pega o ultimo (Widevine)
            print(f"[CDM] PSSH extraido do MPD", file=sys.stderr)
        else:
            # PSSH nao esta no MPD — busca no init segment
            print(f"[CDM] PSSH nao encontrado no MPD, buscando no init segment...", file=sys.stderr)

            # Extrai URL base e template do init segment
            ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}
            seg_tmpl = root.find(".//mpd:SegmentTemplate", ns)
            if seg_tmpl is None:
                seg_tmpl = root.find(".//{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate")

            init_tmpl = seg_tmpl.get("initialization") if seg_tmpl is not None else None
            rep = root.find(".//mpd:Representation", ns)
            if rep is None:
                rep = root.find(".//{urn:mpeg:dash:schema:mpd:2011}Representation")

            rep_id = rep.get("id") if rep is not None else "stream_01"

            if init_tmpl:
                init_file = init_tmpl.replace("$RepresentationID$", rep_id)
            else:
                # fallback: monta manualmente pelo padrao do MPD
                init_file = f"{rep_id}/1_init.m4i"

            base_url = mpd_url.split("manifest.mpd")[0]
            init_url = base_url + init_file
            print(f"[CDM] Baixando init segment: {init_url}", file=sys.stderr)

            init_resp = requests.get(init_url, verify=False, timeout=15)
            init_resp.raise_for_status()
            init_data = init_resp.content

            # Escaneia todos os bytes procurando caixas pssh (podem estar aninhadas em moov)
            WIDEVINE_SYS_ID = bytes.fromhex("edef8ba979d64acea3c827dcd51d21ed")
            import base64 as _b64
            pssh_data = None
            # Busca por offset: procura "pssh" em qualquer posicao
            i = 0
            while i < len(init_data) - 28:
                if init_data[i+4:i+8] == b"pssh":
                    box_size = int.from_bytes(init_data[i:i+4], "big")
                    if 32 <= box_size <= len(init_data) - i:
                        box = init_data[i:i+box_size]
                        sys_id = box[12:28]
                        if sys_id == WIDEVINE_SYS_ID:
                            pssh_data = _b64.b64encode(box).decode()
                            print(f"[CDM] PSSH Widevine extraido do init segment", file=sys.stderr)
                            break
                i += 1

            if not pssh_data:
                print("[ERRO] PSSH Widevine nao encontrado no init segment", file=sys.stderr)
                sys.exit(1)

        print(f"[CDM] PSSH extraido com sucesso", file=sys.stderr)

        # 2. Monta CDM e gera challenge
        wvd_path = os.path.join(_SCRIPT_DIR, "WVDs.wvd")
        if not os.path.isfile(wvd_path):
            wvd_path = os.path.join(_SCRIPT_DIR, "device.wvd")
        pssh    = WidevinePSSH(pssh_data)
        device  = Device.load(wvd_path)
        cdm     = Cdm.from_device(device)
        session = cdm.open()
        challenge = cdm.get_license_challenge(session, pssh)

        print(f"[CDM] Solicitando licenca...", file=sys.stderr)

        # 3. POST do challenge com vmxToken
        lic_resp = requests.post(
            "https://multidrm.core.verimatrixcloud.net/widevine",
            data=challenge,
            headers={
                "accept": "*/*",
                "authorization": vmx,
                "content-type": "application/json",
                "origin": "https://www.clarotvmais.com.br",
                "referer": "https://www.clarotvmais.com.br/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
            timeout=15
        )
        lic_resp.raise_for_status()

        # 4. Parseia licenca e extrai keys
        cdm.parse_license(session, lic_resp.content)
        keys = [k for k in cdm.get_keys(session) if k.type != "SIGNING"]
        cdm.close(session)

        if not keys:
            print("[ERRO] Nenhuma chave encontrada", file=sys.stderr)
            sys.exit(1)

        print(f"[CDM] {len(keys)} chave(s) obtida(s)", file=sys.stderr)

        # 5. Imprime kid:key
        for k in keys:
            kid = str(k.kid).replace("-", "")
            key = k.key.hex() if hasattr(k.key, "hex") else k.key
            print(f"{kid}:{key}")

        return

    # ── action=manifest ───────────────────────
    value = entry_id

    if value.isdigit():
        entry = load_entry(value)
        src   = entry["data"]["response"]["src"]
        print(f"[JSON] ID {value} -> {src}", file=sys.stderr)
        path  = src.split("/Content/Channel/")[1] if "/Content/Channel/" in src else src
    else:
        path = value.lstrip("/")
        if path.startswith("Content/Channel/"):
            path = path[len("Content/Channel/"):]

    parts = path.split("/")
    if len(parts) < 2:
        print("[ERRO] Caminho invalido.", file=sys.stderr)
        sys.exit(1)

    channel_id = parts[0]
    profile    = parts[1]
    sub_path   = "/".join(parts[2:]) or "manifest.mpd"

    if any(sub_path.endswith(x) for x in (".mpd", ".m4v", ".m4a")):
        profile = profile.replace("h4f", "dsc", 1)

    print(f"[INFO] channel={channel_id} profile={profile} path={sub_path}", file=sys.stderr)

    final_url, extra_headers = resolve(channel_id, profile, sub_path)
    print(f"[URL]  {final_url}", file=sys.stderr)

    req = urllib.request.Request(final_url, headers={"User-Agent": "Mozilla/5.0"})
    for k, v in extra_headers.items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as resp:
            print(f"[HTTP] {resp.status} {resp.reason}", file=sys.stderr)
            sys.stdout.buffer.write(resp.read())
    except Exception as e:
        print(f"[ERRO] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
