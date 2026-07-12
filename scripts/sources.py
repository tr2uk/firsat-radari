"""
Fırsat Radarı — kaynak adaptörleri (belediye + ulusal, ücretsiz).

Her fonksiyon normalize edilmiş kayıt listesi döndürür. İki mod:
  - offline=True  -> scripts/fixtures/*.json okur (ağ yok, sadece stdlib). Test/seed için.
  - offline=False -> gerçek API/kaynaktan çeker (requests/openpyxl gerekir).

Ortak şema (frontend ile birebir):
  title, town, district, opp, prop, price(int|None), size(int|None),
  rateable(int|None), status, source, score(None -> build_data hesaplar),
  income(int), date 'YYYY-MM-DD', why, [real(bool), url, contact, deadline]

CANLI çekim için gereken anahtarlar (GitHub Actions secrets):
  CH_API_KEY   -> Companies House (ücretsiz): https://developer.company-information.service.gov.uk/
  EPC_API_KEY  -> EPC (ücretsiz; devlet ucu Mayıs 2026'da kapanıyor, sonrası aggregator)
Land Registry, PlanIt, The Gazette anahtar istemez.
"""
import json, os, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
TODAY = datetime.date.today().isoformat()

# --- Kasaba -> İlçe eşlemesi (genişletilebilir) ---
TOWN_DISTRICT = {
    "Hastings": "Hastings", "St Leonards-on-Sea": "Hastings", "Ore": "Hastings",
    "Silverhill": "Hastings", "Hollington": "Hastings",
    "Bexhill-on-Sea": "Rother", "Battle": "Rother", "Rye": "Rother",
    "Sidley": "Rother", "Ninfield": "Rother", "Robertsbridge": "Rother",
    "Uckfield": "Wealden", "Hailsham": "Wealden", "Crowborough": "Wealden",
    "Heathfield": "Wealden", "Polegate": "Wealden", "Pevensey Bay": "Wealden",
    "Wadhurst": "Wealden", "Mayfield": "Wealden",
    "Eastbourne": "Eastbourne",
    "Lewes": "Lewes", "Newhaven": "Lewes", "Seaford": "Lewes",
    "Peacehaven": "Lewes", "Ringmer": "Lewes",
    "Hove": "Brighton & Hove", "Brighton": "Brighton & Hove", "Portslade": "Brighton & Hove",
}
AUTH_DISTRICT = {"Hastings": "Hastings", "Rother": "Rother", "Wealden": "Wealden",
                 "Eastbourne": "Eastbourne", "Lewes": "Lewes"}


def district_of(town):
    return TOWN_DISTRICT.get(town, "Rother")


def _fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def _postcode(text):
    m = re.search(r"[A-Z]{1,2}\d{1,2}[A-Z]?(\s*\d[A-Z]{2})?", text or "")
    return m.group(0).strip() if m else None


def guess_prop(text):
    t = (text or "").lower()
    if any(k in t for k in ["office", "ofis"]):            return "Ofis"
    if any(k in t for k in ["industrial", "warehouse", "depo", "yard"]): return "Endüstriyel/Depo"
    if any(k in t for k in ["pub", "public house", "restaurant", "cafe"]): return "Pub/Restoran"
    if any(k in t for k in ["hotel", "guest house"]):      return "Otel/Konaklama"
    if any(k in t for k in ["land", "site", "plot", "arsa"]): return "Arsa"
    if any(k in t for k in ["flat", "dwelling", "residential", "house", "c3", "konut"]):
        return "Konut"
    if any(k in t for k in ["shop", "retail", "class e", "store", "showroom"]): return "Perakende/Dükkan"
    return "Karma Kullanım"


def guess_opp(text):
    t = (text or "").lower()
    if "change of use" in t or "change-of-use" in t:  return "Change-of-Use Fırsatı"
    if any(k in t for k in ["demolition", "erection", "dwellings", "development", "outline"]):
        return "Arsa/Geliştirme"
    return "Change-of-Use Fırsatı"


# =========================================================================
# 1) BELEDİYE — ESCC güncel kiralık/satılık + Rother varlık kaydı (boş varlıklar)
# =========================================================================
def council_assets(offline=True):
    out = []
    # -- ESCC güncel listeler (gerçek belgeler) --
    escc = _fixture("escc_listings.json") if offline else _fetch_escc_listings()
    for r in escc:
        out.append({
            "title": r["name"], "town": r["town"], "district": district_of(r["town"]),
            "opp": "Kamu/Belediye Mülkü", "prop": "Ofis",
            "price": None, "size": None, "rateable": None,
            "status": "Kiralık (ESCC)", "source": "Belediye (Canlı)",
            "score": None, "income": 0, "date": TODAY,
            "why": "Doğrudan East Sussex County Council mülkü; belediyeden edinim en avantajlı yol. Kira/şartlar konsey belgesinde.",
            "real": True, "url": r["url"], "contact": "property.estates@eastsussex.gov.uk",
        })
    # -- Rother varlık kaydı: yalnızca BOŞ (occupancy=Vacant) varlıkları fırsat olarak yüzeye çıkar --
    rother = _fixture("rother_assets.json") if offline else _fetch_rother_assets()
    for r in rother:
        if "vacant" not in str(r.get("occupancy", "")).lower():
            continue
        prop = "Arsa" if "land" in r["address"].lower() else "Karma Kullanım"
        out.append({
            "title": r["address"], "town": r["town"], "district": district_of(r["town"]),
            "opp": "Kamu/Belediye Mülkü", "prop": prop,
            "price": None, "size": None, "rateable": None,
            "status": "Boş", "source": "Konsey Varlık Kaydı",
            "score": None, "income": 0, "date": TODAY,
            "why": "Rother varlık kaydında BOŞ görünen belediye mülkü. Elden çıkarma/peppercorn/CAT için değerlendirilebilir.",
            "real": True,
            "url": "https://rdcpublic.blob.core.windows.net/website-uploads/2025/06/Rother-Asset-List-Estates.xlsx",
            "contact": "taris.demann@rother.gov.uk",
        })
    return out


def _fetch_escc_listings():
    """CANLI: ESCC 'Property for sale or rent' sayfasındaki PDF listelerini ayrıştırır."""
    import requests
    from html.parser import HTMLParser
    url = "https://www.eastsussex.gov.uk/your-council/about/property/sale-rent"
    html = requests.get(url, timeout=30).text
    items = []
    for m in re.finditer(r'href="(https://www\.eastsussex\.gov\.uk/media/[^"]+\.pdf)"[^>]*>([^<]+)</a>', html):
        link, name = m.group(1), m.group(2).strip()
        town = "Eastbourne" if "eastbourne" in name.lower() or "pacific" in name.lower() else "Lewes"
        items.append({"name": name, "town": town, "kind": "escc", "url": link})
    return items


def _fetch_rother_assets():
    """CANLI: Rother varlık kaydı .xlsx (adres, holding, occupancy)."""
    import requests, io, openpyxl
    url = "https://rdcpublic.blob.core.windows.net/website-uploads/2025/06/Rother-Asset-List-Estates.xlsx"
    wb = openpyxl.load_workbook(io.BytesIO(requests.get(url, timeout=60).content), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(c).lower() if c else "" for c in rows[0]]
    def col(*names):
        for i, h in enumerate(hdr):
            if any(n in h for n in names): return i
        return None
    ia, io_, ioc = col("address", "description"), col("holding", "tenure"), col("occup", "status")
    out = []
    for r in rows[1:]:
        addr = r[ia] if ia is not None else None
        if not addr: continue
        out.append({"address": str(addr), "town": "Bexhill-on-Sea",
                    "holding": str(r[io_]) if io_ is not None else "",
                    "occupancy": str(r[ioc]) if ioc is not None else ""})
    return out


# =========================================================================
# 2) PLANLAMA — PlanIt API (ücretsiz, anahtarsız): change-of-use / geliştirme sinyalleri
# =========================================================================
def planning(offline=True, authorities=("Hastings", "Rother", "Wealden", "Eastbourne", "Lewes")):
    recs = _fixture("planit.json") if offline else _fetch_planit(authorities)
    out = []
    for r in recs:
        desc = r.get("description", "")
        town = _town_from_address(r.get("address", "")) or AUTH_DISTRICT.get(r.get("area_name", ""), "Hastings")
        out.append({
            "title": (desc[:70] + "…") if len(desc) > 72 else (desc or r.get("name", "Planlama başvurusu")),
            "town": town, "district": AUTH_DISTRICT.get(r.get("area_name", ""), district_of(town)),
            "opp": guess_opp(desc), "prop": guess_prop(desc),
            "price": None, "size": None, "rateable": None,
            "status": "Planlama aşaması", "source": "Planlama Başvurusu",
            "score": None, "income": 0, "date": r.get("start_date", TODAY),
            "why": "Planlama başvurusu: " + (desc or "") + " — dönüşüm/geliştirme fırsatı sinyali.",
            "url": r.get("url", "https://www.planit.org.uk/"),
        })
    return out


def _town_from_address(addr):
    for t in TOWN_DISTRICT:
        if t.split("-")[0].lower() in (addr or "").lower():
            return t
    return None


def _fetch_planit(authorities):
    import requests
    recs = []
    for auth in authorities:
        url = "https://www.planit.org.uk/api/applics/json"
        params = {"auth": auth, "pg_sz": 40, "sort": "-start_date"}
        try:
            data = requests.get(url, params=params, timeout=30,
                                 headers={"User-Agent": "FirsatRadari/1.0"}).json()
            recs += data.get("records", [])
        except Exception as e:
            print("PlanIt hata", auth, e)
    return recs


# =========================================================================
# 3) DISTRESSED İŞLETME — The Gazette (tasfiye/winding-up ilanları)
# =========================================================================
def gazette(offline=True):
    recs = _fixture("gazette.json") if offline else _fetch_gazette()
    out = []
    for r in recs:
        town = r.get("town", "Hastings")
        out.append({
            "title": "Tasfiye ilanı — " + r.get("company", "İşletme"),
            "town": town, "district": district_of(town),
            "opp": "Distressed İşletme", "prop": "Karma Kullanım",
            "price": None, "size": None, "rateable": None,
            "status": "Kapanıyor", "source": "Gazette (Tasfiye)",
            "score": None, "income": 0, "date": r.get("date", TODAY),
            "why": "The Gazette tasfiye ilanı; işletme borç/tasfiye sürecinde. Mekân yakında boşalabilir, pazarlığa açık olabilir.",
            "url": r.get("url", "https://www.thegazette.co.uk/all-notices/content/129"),
        })
    return out


def _fetch_gazette():
    """CANLI: The Gazette insolvency JSON feed'i (TN/BN postcode filtreli)."""
    import requests
    url = "https://www.thegazette.co.uk/all-notices/notice/data.json"
    params = {"noticetypes": "2450", "results-page-size": 50, "text": "East Sussex"}
    try:
        data = requests.get(url, params=params, timeout=30,
                            headers={"User-Agent": "FirsatRadari/1.0", "Accept": "application/json"}).json()
    except Exception as e:
        print("Gazette hata", e); return []
    out = []
    for e in data.get("entry", []):
        title = e.get("title", "")
        out.append({"company": title, "town": "Hastings",
                    "date": (e.get("updated", TODAY) or TODAY)[:10],
                    "url": (e.get("id") or "https://www.thegazette.co.uk/")})
    return out


# =========================================================================
# 4) UCUZ/DISTRESSED KONUT — HM Land Registry Price Paid (OGL, ücretsiz): repossession (kategori B)
# =========================================================================
def land_registry(offline=True):
    recs = _fixture("land_registry.json") if offline else _fetch_land_registry()
    out = []
    for r in recs:
        town = r.get("town", "Hastings")
        cat = r.get("category", "A")
        prop = {"F": "Konut", "T": "Konut", "S": "Konut", "D": "Konut", "O": "Karma Kullanım"}.get(
            r.get("property_type", "F"), "Konut")
        out.append({
            "title": f"{r.get('paon','')} {r.get('street','')}".strip() + (" (repossession emsali)" if cat == "B" else " (son satış emsali)"),
            "town": town, "district": district_of(town),
            "opp": "Distressed İşletme" if cat == "B" else "Ucuz Gayrimenkul",
            "prop": prop, "price": r.get("price"), "size": None, "rateable": None,
            "status": "Repossession" if cat == "B" else "Son satış",
            "source": "Land Registry", "score": None, "income": 0,
            "date": r.get("date", TODAY),
            "why": ("Land Registry repossession kaydı — düşük fiyatlı edinim sinyali."
                    if cat == "B" else "Land Registry son satış emsali; fiyat referansı."),
            "url": "https://landregistry.data.gov.uk/",
        })
    # emsalleri (kategori A) skorlamada tutmak için bırakıyoruz ama repossession'ları öne çıkarıyoruz
    return out


def _fetch_land_registry():
    """CANLI: Price Paid SPARQL — son işlemler (kategori B öncelikli), TN/BN bölgesi."""
    import requests
    q = """
    PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
    PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>
    SELECT ?paon ?street ?town ?price ?date ?cat WHERE {
      ?t lrppi:pricePaid ?price ; lrppi:transactionDate ?date ;
         lrppi:propertyAddress ?a ; lrppi:transactionCategory ?c .
      ?a lrcommon:town ?town . OPTIONAL { ?a lrcommon:paon ?paon } OPTIONAL { ?a lrcommon:street ?street }
      BIND(REPLACE(STR(?c),".*/","") AS ?cat)
      FILTER(?town IN ("HASTINGS","BEXHILL-ON-SEA","EASTBOURNE","LEWES","RYE"))
      FILTER(?date > "2026-05-01"^^<http://www.w3.org/2001/XMLSchema#date>)
    } ORDER BY DESC(?date) LIMIT 60
    """
    try:
        r = requests.get("https://landregistry.data.gov.uk/landregistry/query",
                         params={"query": q}, headers={"Accept": "application/sparql-results+json"}, timeout=60)
        rows = r.json()["results"]["bindings"]
    except Exception as e:
        print("Land Registry hata", e); return []
    out = []
    for b in rows:
        out.append({"paon": b.get("paon", {}).get("value", ""), "street": b.get("street", {}).get("value", ""),
                    "town": b.get("town", {}).get("value", "").title(), "price": int(float(b["price"]["value"])),
                    "date": b["date"]["value"][:10], "property_type": "F",
                    "category": "B" if b.get("cat", {}).get("value", "").upper().startswith("B") else "A"})
    return out


# =========================================================================
# 5) MÜZAYEDE — bölgesel auction lotları (Clive Emson vb.)
# =========================================================================
def auctions(offline=True):
    recs = _fixture("auctions.json") if offline else _fetch_auctions()
    out = []
    for r in recs:
        town = r.get("town", "Bexhill-on-Sea")
        out.append({
            "title": r.get("lot", "Müzayede lotu"), "town": town, "district": district_of(town),
            "opp": "Müzayede (Auction)", "prop": guess_prop(r.get("type", "") + " " + r.get("lot", "")),
            "price": r.get("guide_price"), "size": None, "rateable": None,
            "status": "Müzayedede", "source": "Auction Kataloğu",
            "score": None, "income": 0, "date": TODAY,
            "why": "Bölgesel müzayede lotu; rehber fiyat düşük, hızlı işlem. Aşağı-piyasa (BMV) edinim fırsatı.",
            "url": r.get("url", "https://www.cliveemson.co.uk/"),
            "deadline": {"label": "Müzayede tarihi", "date": r.get("auction_date", TODAY)},
        })
    return out


def _fetch_auctions():
    """CANLI: Clive Emson bölge kataloğu (HTML) — lot/rehber fiyat/tarih ayrıştırma.
    Not: site ToS'una uyun; mümkünse resmi feed/işbirliği tercih edin."""
    return []  # örnek: entegrasyon noktası


# =========================================================================
# 6) ZENGİNLEŞTİRME — Companies House (kayıtlı ofis adresi/konum) ile tasfiye eşleme
# =========================================================================
def companies_house_lookup(name, offline=True, api_key=None):
    """Şirket adından kayıtlı ofis adresi/konumu döndürür (ücretsiz CH API)."""
    if offline:
        return _fixture("companies_house.json").get(name)
    import requests
    key = api_key or os.environ.get("CH_API_KEY")
    if not key:
        return None
    try:
        r = requests.get("https://api.company-information.service.gov.uk/search/companies",
                         params={"q": name, "items_per_page": 1}, auth=(key, ""), timeout=20)
        items = r.json().get("items", [])
    except Exception as e:
        print("Companies House hata", e); return None
    if not items:
        return None
    it = items[0]
    ro = it.get("registered_office_address", {}) or it.get("address", {}) or {}
    addr = it.get("address_snippet") or ", ".join(
        v for v in [ro.get("address_line_1"), ro.get("locality"), ro.get("postal_code")] if v)
    return {"company_number": it.get("company_number"), "address": addr,
            "postcode": ro.get("postal_code", ""), "town": ro.get("locality", "")}


def _closest_town(loc):
    loc = (loc or "").lower()
    if "bexhill" in loc: return "Bexhill-on-Sea"
    if "st leonard" in loc: return "St Leonards-on-Sea"
    for t in TOWN_DISTRICT:
        if t.split("-")[0].lower() in loc:
            return t
    return None


def enrich_gazette(records, offline=True, api_key=None):
    """Gazette (tasfiye) kayıtlarını Companies House kayıtlı ofis adresi/konumuyla eşler.
    Böylece 'hangi işletme, hangi mekân' netleşir ve konum haritaya oturur."""
    for rec in records:
        if rec.get("source") != "Gazette (Tasfiye)":
            continue
        name = rec.get("title", "").replace("Tasfiye ilanı — ", "").strip()
        info = companies_house_lookup(name, offline=offline, api_key=api_key)
        if not info:
            continue
        town = _closest_town(info.get("town"))
        if town:
            rec["town"] = town
            rec["district"] = district_of(town)
        if info.get("address"):
            rec["ch_address"] = info["address"]
            rec["why"] = rec["why"] + f" Kayıtlı ofis: {info['address']}."
        if info.get("company_number"):
            rec["ch_number"] = info["company_number"]
            rec["url"] = f"https://find-and-update.company-information.service.gov.uk/company/{info['company_number']}"
    return records


# Offline seed'de kullanılacak kaynak kümesi
SOURCES = [council_assets, planning, gazette, land_registry, auctions]
