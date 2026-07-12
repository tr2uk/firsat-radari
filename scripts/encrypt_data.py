#!/usr/bin/env python3
"""public/data.json -> AES-256-GCM ile public/data.enc; düz metni siler.
Parola: SITE_PASSPHRASE ortam değişkeni (GitHub secret)."""
import os, json, base64, hashlib, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

pw = os.environ.get("SITE_PASSPHRASE")
if not pw:
    print("HATA: SITE_PASSPHRASE tanımlı değil", file=sys.stderr); sys.exit(1)
data = open("public/data.json", "rb").read()
salt = os.urandom(16); iters = 250000
key = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, iters, dklen=32)
iv = os.urandom(12)
ct = AESGCM(key).encrypt(iv, data, None)   # ct = şifreli veri + GCM tag
json.dump({"v": 1, "kdf": "PBKDF2-SHA256", "iterations": iters,
           "salt": base64.b64encode(salt).decode(),
           "iv": base64.b64encode(iv).decode(),
           "ciphertext": base64.b64encode(ct).decode()},
          open("public/data.enc", "w"))
os.remove("public/data.json")   # düz metin YAYINLANMASIN
print("public/data.enc yazıldı; data.json silindi")
