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


# === Dayanıklılık: bir kaynak bu tur 0 dönerse son iyi yayından "bayat" taşı ===
EXPECTED_SOURCES = ["Belediye (Canlı)", "Konsey Varlık Kaydı", "Planlama Başvurusu",
                    "Land Registry", "Gazette (Tasfiye)", "Auction Kataloğu"]
STALE_MAX_DAYS = 14
LIVE_DATA_URL = os.environ.get("LIVE_DATA_URL",
                               "https://tr2uk.github.io/firsat-radari/data.json")

def _age_days(d):
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(str(d)[:10])).days
    except Exception:
        return 0

def _load_last_good(offline):
    if offline:
        return None
    import requests
    try:
        r = requests.get(LIVE_DATA_URL, timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("  son-iyi veri çekilemedi:", e)
    return None

def carry_over_stale(items, offline):
    """Bu tur 0 dönen kaynakların kayıtlarını önceki iyi yayından taşır (bayat işaretli)."""
    prev = _load_last_good(offline)
    if not prev or not prev.get("items"):
        return items
    counts = {}
    for it in items:
        counts[it.get("source")] = counts.get(it.get("source"), 0) + 1
    carried = 0
    for src in EXPECTED_SOURCES:
        if counts.get(src, 0) > 0:
            continue  # bu tur canlı veri geldi
        for it in prev["items"]:
            if it.get("source") != src:
                continue
            ss = it.get("stale_since") or str(prev.get("generated", ""))[:10]
            if _age_days(ss) > STALE_MAX_DAYS:
                continue  # çok eski -> budandı
            it = dict(it)
            it["stale"] = True
            it["stale_since"] = ss
            if "önceki taramadan" not in it.get("why", ""):
                it["why"] = it.get("why", "") + " · önceki taramadan (kaynak bu tur yanıt vermedi)."
            items.append(it)
            carried += 1
    if carried:
        print(f"  dayanıklılık: {carried} bayat kayıt taşındı (0 dönen kaynaklar)")
    return items


# === Fırsat skoru — ağırlıklı ve ayarlanabilir kriterler ===
# Bu ağırlıkları kendi stratejine göre değiştir; skor bunları toplar ve 45-92'ye sıkıştırır.
WEIGHTS = {
    "base": 45, "status_distress": 12, "opp_distress": 12, "opp_change_of_use": 8,
    "opp_land": 5, "opp_cheap": 4, "opp_public": 6, "resi_conversion": 8,
    "source_council": 12, "source_gazette": 10, "source_auction": 6,
    "source_planning": 4, "source_land_registry": 3, "below_market": 8,
    "affordable": 5, "deadline_soon": 5, "ch_matched": 5,
}
SCORE_MIN, SCORE_MAX = 45, 92


def _days_to(d):
    try:
        return (datetime.date.fromisoformat(d) - datetime.date.today()).days
    except Exception:
        return None


def score(rec):
    if rec.get("real"):
        rec["score_factors"] = ["gerçek belediye listesi (CANLI)"]
        return None
    W = WEIGHTS; s = W["base"]; why = []
    stl = (rec.get("status", "") or "").lower()
    if any(k in stl for k in ["boş", "kapanıyor", "müzayede", "repossession", "konsey arazisi", "düşük fiyatlı"]):
        s += W["status_distress"]; why.append("boş/distressed/ucuz durum")
    opp = rec.get("opp", "")
    if opp in ("Distressed İşletme", "Atıl/Boş Bina", "Müzayede (Auction)"):
        s += W["opp_distress"]; why.append("distressed fırsat")
    elif opp == "Change-of-Use Fırsatı":
        s += W["opp_change_of_use"]; why.append("change-of-use")
    elif opp == "Arsa/Geliştirme":
        s += W["opp_land"]; why.append("geliştirme arazisi")
    elif opp == "Ucuz Gayrimenkul":
        s += W["opp_cheap"]; why.append("ucuz gayrimenkul")
    elif opp == "Kamu/Belediye Mülkü":
        s += W["opp_public"]; why.append("kamu/belediye")
    text = (rec.get("why", "") + " " + rec.get("title", "")).lower()
    if any(k in text for k in ["konut", "resident", "flat", "c3", "daire", "dwelling"]):
        s += W["resi_conversion"]; why.append("konuta dönüşüm sinyali")
    src_w = {"Konsey Varlık Kaydı": "source_council", "Belediye (Canlı)": "source_council",
             "Gazette (Tasfiye)": "source_gazette", "Auction Kataloğu": "source_auction",
             "Planlama Başvurusu": "source_planning", "Land Registry": "source_land_registry"}.get(rec.get("source", ""))
    if src_w:
        s += W[src_w]; why.append("kaynak: " + rec.get("source", ""))
    p, r = rec.get("price"), rec.get("rateable")
    if p and r and p < r * 12:
        s += W["below_market"]; why.append("piyasa altı")
    if p and p < 150000:
        s += W["affordable"]; why.append("düşük giriş (<£150k)")
    dl = rec.get("deadline")
    if dl and dl.get("date"):
        dd = _days_to(dl["date"])
        if dd is not None and 0 <= dd <= 21:
            s += W["deadline_soon"]; why.append("son tarih yakın")
    if rec.get("ch_number"):
        s += W["ch_matched"]; why.append("CH adres eşleşti")
    # Konsey arazisi içi ayrıştırma (aynı kaynak içinde önceliklendirme)
    if rec.get("source") == "Konsey Varlık Kaydı":
        t = (rec.get("title", "") or "").lower()
        if any(k in t for k in ["land", "site", "plot", "field", "development", "garages"]):
            s += 6; why.append("geliştirmeye açık arazi")
        elif any(k in t for k in ["garage", "convenience", "kiosk", "shelter", "toilet", "store", "hut"]):
            s -= 6; why.append("küçük/sınırlı varlık")
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

    # Dayanıklılık: bu tur 0 dönen kaynakları önceki iyi yayından bayat taşı
    items = carry_over_stale(items, offline)

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
