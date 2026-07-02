"""
使用 cryptography 套件生成品勢計分系統用的自簽 SSL 憑證
執行後在同目錄產生 cert.pem 與 key.pem
"""
import os
import sys
import datetime
import ipaddress
import socket

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# 強制 stdout 使用 utf-8（Windows cmd cp950 的 workaround）
if sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_self_signed_cert(cert_file="cert.pem", key_file="key.pem"):
    local_ip = get_local_ip()
    print(f"[INFO] Local IP: {local_ip}")

    # 1. 產生 RSA 私鑰
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # 2. 建立憑證主體
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "TW"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Taiwan"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Taipei"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Poomsae Scoring System"),
        x509.NameAttribute(NameOID.COMMON_NAME, local_ip),
    ])

    # 3. 建構憑證，加入 SAN（Chrome / Android 必需有 IP SAN 才能信任）
    san_list = [
        x509.IPAddress(ipaddress.ip_address(local_ip)),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.DNSName("localhost"),
    ]

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3 * 365)
        )
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # 4. 寫入 PEM 檔案
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(script_dir, cert_file)
    key_path  = os.path.join(script_dir, key_file)

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    print(f"[OK] cert.pem -> {cert_path}")
    print(f"[OK] key.pem  -> {key_path}")
    print()
    print("=" * 55)
    print(f"  HTTPS URL: https://{local_ip}:5003")
    print("=" * 55)
    print()
    print("[Android Chrome - Quick]")
    print(f"  Open https://{local_ip}:5003 -> Advanced -> Proceed")
    print()
    print("[Android - Full PWA]")
    print(f"  Transfer cert.pem to phone")
    print(f"  Settings -> Security -> Install certificate -> CA certificate")
    print()
    print("[iOS Safari - Full PWA]")
    print(f"  AirDrop cert.pem -> Install profile -> Trust in Settings")
    return cert_path, key_path, local_ip


if __name__ == "__main__":
    generate_self_signed_cert()
