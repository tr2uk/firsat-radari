#!/usr/bin/env python3
"""
Fırsat Radarı — veri derleyici (backend).

Tüm kaynak adaptörlerini çalıştırır, normalize eder, skorlar, (opsiyonel) geocode eder
ve public/data.json üretir. Frontend bu dosyayı okur.

Kullanım:
  python build_data.py --offline        # fixtures ile; ağ yok; test/seed
  python build_data.py                   # CANLI: gerçek API/kaynaklar (requests gerekir)
  python build_data.py --out ../public/data.json

CANLI mod ortam değişkenleri (opsiyonel): CH_API_KEY, EPC_API_KEY
"""
import argparse, json, os, datetime, sys
import sources as S

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.normpath(os.path.join(HERE, "..", "public", "data.json"))


# === Fırsat skoru — ağırlıklı ve ayarlanabilir kriterler ===
# Bu ağırlıkları kendi stratejine göre değiştir; skor bunları toplar ve 50-97'ye sıkıştırır.
WEIGHTS = {
    "base": 50,
    "vacant_or_distressed_status": 12,   # durum: Boş / Kapanıyor / Müzayede / Repossession
    "opp_distress": 10,                  # fırsat tipi: Distressed / Atıl / Müzayede
    "opp_public_or_cou": 6,              # Kamu-Belediye / Change-of-Use
    "opp_land": 4,                       # Arsa / Geliştirme
    "source_edge": 6,                    # kaynak: Gazette / Konsey / Belediye
    "source_auction": 4,                 # kaynak: Auction
    "source_planning": 3,                # kaynak: Planlama
    "below_market": 8,                   # fiyat < rateable * 12
    "affordable": 4,                     # fiyat < £150k (düşük giriş)
    "deadline_soon": 5,                  # son tarih <= 21 gün
    "ch_matched": 4,                     # tasfiye + kayıtlı ofis adresi eşleşti
}
SCORE_MIN, SCORE_MAX = 50, 97


def _days_to(d):
    try:
        return (datetime.date.fromisoformat(d) - datetime.date.today()).days
    except Exception:
        return None


def score(rec):
    """Ağırlıklı fırsat skoru (0-100). Gerçek belediye (real) kayıtlar skorsuz -> frontend 'CANLI' gösterir.
    Şeffaflık için katkı veren faktörler rec['score_factors'] içine yazılır."""
    if rec.get("real"):
        rec["score_factors"] = ["gerçek belediye kaydı (CANLI)"]
        return None
    W = WEIGHTS
    s = W["base"]
    why = []
    st = rec.get("status", "") or ""
    if any(k in st for k in ["Boş", "Kapanıyor", "Müzayede", "Repossession"]):
        s += W["vacant_or_distressed_status"]; why.append("boş/distressed durum")
    opp = rec.get("opp", "")
    if opp in ("Distressed İşletme", "Atıl/Boş Bina", "Müzayede (Auction)"):
        s += W["opp_distress"]; why.append("distressed fırsat tipi")
    elif opp in ("Kamu/Belediye Mülkü", "Change-of-Use Fırsatı"):
        s += W["opp_public_or_cou"]; why.append("kamu/change-of-use")
    elif opp == "Arsa/Geliştirme":
        s += W["opp_land"]; why.append("geliştirme arsası")
    src = rec.get("source", "")
    if src in ("Gazette (Tasfiye)", "Konsey Varlık Kaydı", "Belediye (Canlı)"):
        s += W["source_edge"]; why.append("ayrıcalıklı kaynak")
    elif src == "Auction Kataloğu":
        s += W["source_auction"]; why.append("müzayede kaynağı")
    elif src == "Planlama Başvurusu":
        s += W["source_planning"]; why.append("planlama sinyali")
    p, r = rec.get("price"), rec.get("rateable")
    if p and r and p < r * 12:
        s += W["below_market"]; why.append("piyasa altı gösterge")
    if p and p < 150000:
        s += W["affordable"]; why.append("düşük giriş (<£150k)")
    dl = rec.get("deadline")
    if dl and dl.get("date"):
        dd = _days_to(dl["date"])
        if dd is not None and 0 <= dd <= 21:
            s += W["deadline_soon"]; why.append("son tarih yakın")
    if rec.get("ch_number"):
        s += W["ch_matched"]; why.append("tasfiye+kayıtlı ofis eşleşti")
    rec["score_factors"] = why
    return max(SCORE_MIN, min(SCORE_MAX, s))


def geocode(rec, offline):
    """postcodes.io ile ücretsiz UK geocode (yalnızca CANLI mod). Frontend zaten kasaba bazlı çizer."""
    if offline:
        return
    import requests, re
    text = (rec.get("title", "") + " " + rec.get("town", ""))
    m = re.search(r"[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d?[A-Z]{0,2}", text)
    if not m:
        return
    try:
        pc = m.group(0).replace(" ", "")
        d = requests.get(f"https://api.postcodes.io/postcodes/{pc}", timeout=15).json()
        if d.get("status") == 200:
            rec["lat"] = d["result"]["latitude"]
            rec["lng"] = d["result"]["longitude"]
    except Exception:
        pass


def build(offline=True):
    items = []
    for fn in S.SOURCES:
        try:
            got = fn(offline=offline)
            print(f"  {fn.__name__}: {len(got)} kayıt")
            items += got
        except Exception as e:
            print(f"  {fn.__name__}: HATA {e}", file=sys.stderr)

    # Companies House ile tasfiye kayıtlarını kayıtlı ofis adresi/konuma bağla
    try:
        S.enrich_gazette(items, offline=offline, api_key=os.environ.get("CH_API_KEY"))
    except Exception as e:
        print("  companies_house enrich: HATA", e, file=sys.stderr)

    # id + skor + link + geocode
    for i, rec in enumerate(items, start=1):
        rec["id"] = 1000 + i
        rec["score"] = score(rec)
        rec.setdefault("income", 0)
        rec.setdefault("link", rec.get("url", ""))
        geocode(rec, offline)

    return {
        "generated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "count": len(items),
        "source": "offline-fixtures" if offline else "live",
        "items": items,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="fixtures ile çalış (ağ yok)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    print(f"Fırsat Radarı ingestion ({'OFFLINE' if args.offline else 'CANLI'})…")
    payload = build(offline=args.offline)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✓ {payload['count']} kayıt -> {args.out}")


if __name__ == "__main__":
    main()
