#!/usr/bin/env python3
"""
Yeni fırsatlar için e-posta uyarısı (Resend — ücretsiz: 3.000 e-posta/ay).

Bir önceki çalıştırmaya göre YENİ eklenen kayıtları bulur ve özet e-posta gönderir.
Ücretsiz kalır; WhatsApp gibi metered kanallar yerine e-posta önerilir.

Ortam değişkenleri (GitHub Actions secrets):
  RESEND_API_KEY, ALERT_FROM (ör. radar@alanadınız.co.uk), ALERT_TO (virgülle çoklu)
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "public", "data.json"))
SEEN = os.path.join(HERE, ".seen_ids.json")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    payload = load(DATA, {"items": []})
    items = payload.get("items", [])
    seen = set(load(SEEN, []))
    new = [i for i in items if str(i.get("id")) not in seen]

    # yüksek öncelik / son tarihi yakınları öne al
    new.sort(key=lambda x: (x.get("score") or 0), reverse=True)

    if not new:
        print("Yeni fırsat yok."); return

    lines = []
    for i in new[:25]:
        price = f"£{i['price']:,}" if i.get("price") else "Konseyden"
        lines.append(f"• [{i.get('score') or 'CANLI'}] {i['title']} — {i['town']} ({i['source']}) {price}\n  {i.get('url','')}")
    body = "Fırsat Radarı — yeni fırsatlar:\n\n" + "\n".join(lines)

    key = os.environ.get("RESEND_API_KEY")
    to = [x.strip() for x in os.environ.get("ALERT_TO", "").split(",") if x.strip()]
    frm = os.environ.get("ALERT_FROM", "radar@example.com")
    if key and to:
        import requests
        r = requests.post("https://api.resend.com/emails",
                          headers={"Authorization": f"Bearer {key}"},
                          json={"from": frm, "to": to,
                                "subject": f"Fırsat Radarı: {len(new)} yeni fırsat", "text": body},
                          timeout=30)
        print("Resend:", r.status_code)
    else:
        print("RESEND_API_KEY/ALERT_TO yok — e-posta atlanıyor. Önizleme:\n", body[:800])

    with open(SEEN, "w", encoding="utf-8") as f:
        json.dump([str(i.get("id")) for i in items], f)


if __name__ == "__main__":
    main()
