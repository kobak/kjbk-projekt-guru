#!/usr/bin/env python3
"""Generate local/production environment without overwriting existing secrets."""
import argparse
import base64
import os
import secrets
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

parser=argparse.ArgumentParser()
parser.add_argument("--local",action="store_true")
parser.add_argument("--url",default="")
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
target=root/".env"
if target.exists():
    raise SystemExit("A .env már létezik; nem írom felül.")
if not args.local and not args.url.startswith("https://"):
    raise SystemExit("Éles telepítéshez add meg: --url https://projekt.sajatdomain.hu")
key=ec.generate_private_key(ec.SECP256R1())
def b64(value):return base64.urlsafe_b64encode(value).decode().rstrip("=")
private=b64(key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
public=b64(key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint))
url=args.url or "http://localhost:8000"
from urllib.parse import urlparse
db_password=secrets.token_urlsafe(32)
content=f'''DEBUG={"true" if args.local else "false"}
SECRET_KEY={secrets.token_urlsafe(64)}
APP_URL={url.rstrip('/')}
ALLOWED_HOSTS={urlparse(url).hostname},localhost,127.0.0.1
POSTGRES_PASSWORD={db_password}
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_PICKER_CLIENT_ID=
GOOGLE_PICKER_API_KEY=
GOOGLE_PICKER_APP_ID=
VAPID_PUBLIC_KEY={public}
VAPID_PRIVATE_KEY={private}
VAPID_SUBJECT=mailto:admin@{urlparse(url).hostname}
'''
fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"w") as f:f.write(content)
print("Elkészült a .env, egyedi titkos kulcsokkal. Ne tedd verziókezelőbe.")
