import os
import sys

# 確保工作目錄為程式所在之目錄，防止資料產生在錯誤的執行路徑上
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="numpy")
import tkinter as tk
import threading
import socket
import atexit
import ssl as _ssl_module
import ipaddress as _ipaddress
import datetime as _dt

# === 導入重構模組 ===
import config
import database
import web_server
import gui_main

# === Monkey Patch subprocess.Popen for pyngrok Windows encoding issue ===
import subprocess
_original_popen = subprocess.Popen
def _patched_popen(*args, **kwargs):
    is_ngrok = False
    if args and isinstance(args[0], list) and args[0] and "ngrok" in str(args[0][0]).lower():
        is_ngrok = True
    elif "args" in kwargs and isinstance(kwargs["args"], list) and kwargs["args"] and "ngrok" in str(kwargs["args"][0]).lower():
        is_ngrok = True
    
    if is_ngrok:
        if kwargs.get("universal_newlines") or kwargs.get("text"):
            kwargs["encoding"] = "utf-8"
    return _original_popen(*args, **kwargs)
subprocess.Popen = _patched_popen


# --- 全域設定 ---
PORT = 5003
USE_SSL = False
INTERNAL_SCHEME = "http"

_CERT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cert.pem')
_KEY_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'key.pem')

def _get_local_ip():
    """取得目前本機在區網中的 IP 位址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def _get_cert_ip(cert_path):
    """讀取 cert.pem 中的第一個 IP SAN，若無則回傳 None"""
    try:
        from cryptography import x509 as _cx509
        with open(cert_path, "rb") as f:
            cert_data = f.read()
        cert_obj = _cx509.load_pem_x509_certificate(cert_data)
        san_ext = cert_obj.extensions.get_extension_for_class(_cx509.SubjectAlternativeName)
        ip_list = san_ext.value.get_values_for_type(_cx509.IPAddress)
        for ip in ip_list:
            if str(ip) != "127.0.0.1":
                return str(ip)
        return str(ip_list[0]) if ip_list else None
    except Exception:
        return None

def _generate_ssl_cert(local_ip):
    """使用 cryptography 套件生成自簽憑證，並加入正確的 IP SAN"""
    from cryptography import x509 as _cx509
    from cryptography.x509.oid import NameOID as _NameOID, ExtendedKeyUsageOID as _EKU
    from cryptography.hazmat.primitives import hashes as _hashes, serialization as _ser
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa

    print(f"[SSL] Generating new certificate for IP: {local_ip}")
    private_key = _rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = _cx509.Name([
        _cx509.NameAttribute(_NameOID.COUNTRY_NAME, "TW"),
        _cx509.NameAttribute(_NameOID.ORGANIZATION_NAME, "Poomsae Scoring System"),
        _cx509.NameAttribute(_NameOID.COMMON_NAME, local_ip),
    ])

    san_list = [
        _cx509.IPAddress(_ipaddress.ip_address(local_ip)),
        _cx509.IPAddress(_ipaddress.ip_address("127.0.0.1")),
        _cx509.DNSName("localhost"),
    ]

    cert = (
        _cx509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(_cx509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.timezone.utc))
        .not_valid_after(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=3 * 365))
        .add_extension(_cx509.SubjectAlternativeName(san_list), critical=False)
        .add_extension(_cx509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            _cx509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False, data_encipherment=False,
                key_agreement=False, encipher_only=False, decipher_only=False,
            ), critical=True,
        )
        .add_extension(_cx509.ExtendedKeyUsage([_EKU.SERVER_AUTH]), critical=False)
        .sign(private_key, _hashes.SHA256())
    )

    with open(_CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(_ser.Encoding.PEM))
    with open(_KEY_FILE, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=_ser.Encoding.PEM,
            format=_ser.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=_ser.NoEncryption(),
        ))
    print(f"[SSL] Certificate saved to {_CERT_FILE}")

def _ensure_ssl_cert():
    local_ip = _get_local_ip()
    print(f"[HTTP] 本地 HTTPS 已停用，專為 Cloudflare Tunnel 優化。")
    return None, None, local_ip

# 啟動時執行自動憑證檢查
_cert_result = _ensure_ssl_cert()
_LOCAL_IP = _cert_result[2] if len(_cert_result) == 3 else _get_local_ip()
USE_SSL = (_cert_result[0] is not None)
INTERNAL_SCHEME = 'https' if USE_SSL else 'http'

_INTERNAL_SSL_CTX = _ssl_module.SSLContext(_ssl_module.PROTOCOL_TLS_CLIENT)
_INTERNAL_SSL_CTX.check_hostname = False
_INTERNAL_SSL_CTX.verify_mode = _ssl_module.CERT_NONE

# 傳遞 SSL / 協議配置給 config 與 web_server
config.PORT = PORT
config.USE_SSL = USE_SSL
config.INTERNAL_SCHEME = INTERNAL_SCHEME
config.INTERNAL_SSL_CTX = _INTERNAL_SSL_CTX

web_server.PORT = PORT
web_server.USE_SSL = USE_SSL
web_server.INTERNAL_SCHEME = INTERNAL_SCHEME
web_server.INTERNAL_SSL_CTX = _INTERNAL_SSL_CTX

def run_flask():
    if USE_SSL:
        print(f"[HTTPS] SSL enabled.")
        print(f"[HTTPS] Judge URL: https://{_LOCAL_IP}:{PORT}")
        web_server.socketio.run(web_server.app, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True,
                               keyfile=_KEY_FILE, certfile=_CERT_FILE)
    else:
        print(f"[HTTP] Running without HTTPS.")
        web_server.socketio.run(web_server.app, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    # 自動檢查更新（必須在 database.init_db() 與 tkinter 視窗建立前執行）
    try:
        import json as _json_update
        # --onefile 模式下 __file__ 指向暫存解壓目錄，需改用 sys.executable 取得 exe 真實路徑
        if getattr(sys, 'frozen', False):
            _base_dir = os.path.dirname(sys.executable)
        else:
            _base_dir = os.path.dirname(os.path.abspath(__file__))
        _settings_path = os.path.join(_base_dir, 'settings.json')
        with open(_settings_path, 'r', encoding='utf-8') as _f:
            _s = _json_update.load(_f)
        _update_source = _s.get("update_source", "")
        if _update_source:
            from packaging_tools.updater import check_and_update
            check_and_update("PoomsaeScoringSystem.exe", _update_source)
    except Exception as _update_err:
        print(f"自動更新檢查失敗: {_update_err}")

    # 執行授權驗證
    try:
        from packaging_tools.license_verifier import check_and_enforce
        check_and_enforce("poomsae")
    except Exception as _lic_err:
        print(f"授權驗證載入失敗: {_lic_err}")
        sys.exit(1)

    database.init_db()
    
    # Enable High DPI Awareness (System DPI Aware) to prevent the main window from shrinking
    # when the projection window is moved to an external monitor with different DPI scaling.
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    root = tk.Tk()
    root.option_add('*Font', '微軟正黑體 10')
    gui = gui_main.PoomsaeReplicaGUI(root)
    
    # 啟動 Flask背景執行緒
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # 自動啟動 Ngrok Tunnel
    def start_ngrok():
        try:
            # 檢查是否啟用雲端連線
            config.load_settings()
            if not config.system_settings.get("enable_cloud", True):
                print("\n[Ngrok] 雲端連線已停用，不啟動 Ngrok 專屬通道。\n")
                if gui:
                    gui.root.after(0, gui.update_qr_code, "")
                return

            import sys
            import json
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, 'ngrok_config.json')
            
            
            if not os.path.exists(config_path):
                default_config = {
                    "auth_token": "請在此填寫您的_Auth_Token",
                    "domain": "請在此填寫您的_固定網域.ngrok-free.dev"
                }
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                print(f"\n[Ngrok] 尚未設定專屬網址！")
                print(f"[Ngrok] 系統已自動產生設定檔： {config_path}")
                print(f"[Ngrok] 請用記事本打開該檔案，填寫後再重新啟動系統。\n")
                return

            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            
            auth_token = cfg.get("auth_token", "").strip()
            domain = cfg.get("domain", "").strip()

            if not auth_token or "請在此填寫" in auth_token:
                print(f"\n[Ngrok] 請先至 ngrok_config.json 填寫正確的 Auth Token！\n")
                return

            from pyngrok import ngrok
            print(f"[Ngrok] 正在讀取設定並啟動專屬安全通道 ({domain})...")
            
            ngrok.set_auth_token(auth_token)
            public_url = ngrok.connect(PORT, domain=domain).public_url
            
            print(f"\n=======================================================")
            print(f" [Ngrok] 專屬安全通道啟動成功！")
            print(f" -> 裁判請使用手機開啟此網址：\n {public_url}")
            print(f"=======================================================\n")
            
            if gui:
                gui.root.after(0, gui.update_qr_code, public_url)
                
        except Exception as e:
            print(f"\n[Ngrok] 無法啟動通道: {e}")
            print(f"[Ngrok] 請確認網路連線，或檢查設定檔 (ngrok_config.json) 是否設定正確。\n")

    def stop_ngrok():
        try:
            from pyngrok import ngrok
            ngrok.kill()
            print("\n[Ngrok] 雲端連線已動態關閉並釋放通道。\n")
        except Exception as e:
            print(f"[Ngrok] 關閉通道時發生異常: {e}")
        if gui:
            gui.root.after(0, gui.update_qr_code, "")

    # 註冊雲端控制回呼至 gui
    gui.start_tunnel_callback = start_ngrok
    gui.stop_tunnel_callback = stop_ngrok

    t_ngrok = threading.Thread(target=start_ngrok)
    t_ngrok.daemon = True
    t_ngrok.start()

    def cleanup_ngrok():
        try:
            from pyngrok import ngrok
            ngrok.kill()
        except:
            pass
    atexit.register(cleanup_ngrok)

    root.mainloop()