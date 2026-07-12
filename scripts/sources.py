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
    # -- Rother varlık kaydı: offline'da BOŞ (occupancy=Vacant); canlıda geliştirilebilir
    #    konsey arazisi (kind=dev-land, çünkü kayıtta occupancy sütunu yok). --
    rother = _fixture("rother_assets.json") if offline else _fetch_rother_assets()
    for r in rother:
        occ = str(r.get("occupancy", "")).lower()
        is_vacant = "vacant" in occ
        is_devland = r.get("kind") == "dev-land"
        if not (is_vacant or is_devland):
            continue
        prop = "Arsa" if "land" in r["address"].lower() else "Karma Kullanım"
        out.append({
            "title": r["address"], "town": r["town"], "district": district_of(r["town"]),
            "opp": "Kamu/Belediye Mülkü", "prop": prop,
            "price": None, "size": None, "rateable": None,
            "status": "Boş" if is_vacant else "Konsey arazisi",
            "source": "Konsey Varlık Kaydı",
            "score": None, "income": 0, "date": TODAY,
            "why": ("Rother varlık kaydında BOŞ görünen belediye mülkü. Elden çıkarma/peppercorn/CAT için değerlendirilebilir."
                    if is_vacant else
                    "Rother varlık kaydındaki konsey mülkiyetindeki geliştirilebilir arazi/parsel. Elden çıkarma/CAT/geliştirme için değerlendirilebilir."),
            "real": True,
            "url": "https://rdcpublic.blob.core.windows.net/website-uploads/2025/06/Rother-Asset-List-Estates.xlsx",
            "contact": "taris.demann@rother.gov.uk",
        })
    return out


def _fetch_escc_listings():
    """CANLI: ESCC 'Property for sale or rent' sayfasındaki PDF listelerini ayrıştırır.
    Not: linkler GÖRELİ (/media/…pdf); isimlerde '[2.2 MB] [pdf]' son eki ve
    bazen 'OFFER DEADLINE PASSED' etiketi bulunur — temizlenir/elenir."""
    import requests
    base = "https://www.eastsussex.gov.uk"
    url = base + "/your-council/about/property/sale-rent"
    html = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 FirsatRadari"}).text
    items = []
    seen = set()
    # <a … href="/media/…​.pdf" …>…</a> — link başka attribute'lardan SONRA gelir ve
    # metinde iç içe <i>/<small> etiketleri vardır. Temiz isim title="Download '…'"
    # attribute'undadır; süresi geçmiş teklifler metinde 'DEADLINE PASSED' içerir.
    for m in re.finditer(r'<a\b[^>]*\bhref="([^"]*?/media/[^"]+\.pdf)"[^>]*>(.*?)</a>', html, re.S):
        link, inner, tag = m.group(1), m.group(2), m.group(0)
        if not link.startswith("http"):
            link = base + link
        if link in seen:
            continue
        seen.add(link)
        tm = re.search(r"title=\"Download\s*'([^']+)'\"", tag)
        if tm:
            name = tm.group(1).strip().title()
        else:
            name = re.sub(r"\s*\[[^\]]*\]\s*", " ", re.sub(r"<[^>]+>", " ", inner)).strip()
        if "deadline passed" in re.sub(r"<[^>]+>", " ", inner).lower():
            continue  # süresi geçmiş teklifleri gösterme
        low = (name + " " + link).lower()
        if "pacific" in low or "eastbourne" in low or "sovereign" in low:
            town = "Eastbourne"
        elif "hastings" in low:
            town = "Hastings"
        elif "bexhill" in low:
            town = "Bexhill-on-Sea"
        else:
            town = "Lewes"
        items.append({"name": name, "town": town, "kind": "escc", "url": link})
    return items


def _fetch_rother_assets():
    """CANLI: Rother varlık kaydı .xlsx.
    GERÇEK başlıklar: 'Property Custom Reference', 'Property',
    'Property Street Address', 'RDC Holding', 'Leasehold Term'.
    Occupancy/Vacant sütunu YOK — bu yüzden 'boş' filtresi uygulanamaz; onun
    yerine geliştirilebilir/elden çıkarılabilir KONSEY ARAZİSİ alt kümesini
    (land/site/plot/depot/yard/former/garage) fırsat olarak yüzeye çıkarırız.
    Kasaba, adresin sonundaki postcode'dan önce yazan kelimeden ayrıştırılır."""
    import requests, io, openpyxl
    url = "https://rdcpublic.blob.core.windows.net/website-uploads/2025/06/Rother-Asset-List-Estates.xlsx"
    content = requests.get(url, timeout=60, headers={"User-Agent": "FirsatRadari/1.0"}).content
    ws = openpyxl.load_workbook(io.BytesIO(content), read_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    hdr = [str(c).lower().strip() if c else "" for c in rows[0]]
    def col(*names):
        for i, h in enumerate(hdr):
            if any(n in h for n in names): return i
        return None
    i_name = col("property street address", "address")  # tam adres (postcode'lu)
    i_alt = col("property")                              # kısa ad
    i_hold = col("holding", "tenure")
    if i_name is None:
        i_name = i_alt
    DEV_KW = ("land", "site", "plot", "depot", "yard", "former", "garage")
    known = sorted(TOWN_DISTRICT.keys(), key=len, reverse=True)
    out = []
    for r in rows[1:]:
        addr = str(r[i_name]).replace("\xa0", " ").strip() if i_name is not None and r[i_name] else ""
        name = str(r[i_alt]).replace("\xa0", " ").strip() if i_alt is not None and r[i_alt] else ""
        if not addr and not name:
            continue
        blob = (name + " " + addr).lower()
        if not any(k in blob for k in DEV_KW):
            continue  # yalnızca geliştirilebilir arazi/elden çıkarma adayları
        # kasaba tespiti
        town = "Bexhill-on-Sea"
        for t in known:
            if t.split("-")[0].lower() in blob:
                town = t
                break
        out.append({"address": (name or addr), "town": town,
                    "holding": str(r[i_hold]) if i_hold is not None and r[i_hold] else "",
                    "occupancy": "", "kind": "dev-land"})
        if len(out) >= 30:  # panoyu boğmamak için üst sınır
            break
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
    """CANLI: PlanIt applics API (anahtarsız).
    ÖNEMLİ: 'auth' TEK BAŞINA 400 döndürür — API 'Spatial, date or search
    restrictions required' der. Bu yüzden her yetkilinin merkez koordinatı
    etrafında lat/lng + krad (yarıçap km) ile SPATIAL sorgu yaparız (küçük
    yarıçap = hızlı; büyük yarıçap zaman aşımına uğrar). Rate-limit (429)
    olursa 'try again in Ns' okunup bir kez beklenip tekrar denenir."""
    import requests, time, re as _re
    url = "https://www.planit.org.uk/api/applics/json"
    CENTRES = {
        "Hastings": (50.8543, 0.5735),
        "Rother": (50.8407, 0.4674),       # Bexhill-on-Sea
        "Wealden": (50.8620, 0.2650),      # Hailsham/Hellingly
        "Eastbourne": (50.7687, 0.2842),
        "Lewes": (50.8730, 0.0090),
    }
    KW = ["change of use", "change-of-use", "conversion", "convert", "prior approval",
          "demolition", "erection", "dwelling", "redevelop", "residential", "flat"]
    recs, seen = [], set()
    for auth in authorities:
        if auth not in CENTRES:
            continue
        lat, lng = CENTRES[auth]
        params = {"lat": lat, "lng": lng, "krad": 6, "pg_sz": 20, "sort": "-start_date"}
        for attempt in range(2):
            try:
                r = requests.get(url, params=params, timeout=30,
                                 headers={"User-Agent": "FirsatRadari/1.0"})
                if r.status_code == 429:
                    m = _re.search(r"(\d+)", r.json().get("error", ""))
                    wait = min((int(m.group(1)) + 2) if m else 60, 130)
                    print(f"PlanIt rate-limit ({auth}); {wait}s bekleniyor")
                    time.sleep(wait)
                    continue
                data = r.json()
            except Exception as e:
                print("PlanIt hata", auth, e)
                break
            if "error" in data:
                print("PlanIt error", auth, data["error"])
                break
            for rec in data.get("records", []):
                uid = rec.get("uid") or rec.get("url")
                if uid in seen:
                    continue
                desc = (rec.get("description") or "").lower()
                if not any(k in desc for k in KW):
                    continue  # yalnızca dönüşüm/geliştirme sinyali taşıyanlar
                seen.add(uid)
                recs.append(rec)
            break
        time.sleep(3)  # kibar aralık — rate-limit'i azaltır
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
    """CANLI: The Gazette kurumsal tasfiye (insolvency) ilanları.
    GERÇEK şema: data.json -> {'entry': [ {title, published, updated, id, content}, … ]}.
    Notlar: 'results-page-size' GEÇERSİZ bir param (HTTP 500 yapar) — kullanma;
    sayfa boyu sabit 10, sayfalama 'results-page' iledir. noticetypes=2450 kurumsal
    insolvency; bölgeyi 'text' ve son tarihi 'start-publish-date' kısıtlar."""
    import requests, datetime as _dt, time
    base = "https://www.thegazette.co.uk/all-notices/notice"
    url = base + "/data.json"
    since = (_dt.date.today() - _dt.timedelta(days=365)).isoformat()
    s = requests.Session()
    s.headers.update({"User-Agent": "FirsatRadari/1.0", "Accept": "application/json"})

    def _get(params, tries):
        """The Gazette data.json aralıklı 500 verir; oturum cookie'si (JSESSIONID)
        ve backoff retry ile daha güvenilir olur."""
        for i in range(tries):
            try:
                r = s.get(url, params=params, timeout=45)
                if r.status_code == 200:
                    return r.json()
                if r.status_code >= 500:
                    try:  # cookie/oturum tazele
                        s.get(base, params={"text": "East Sussex"}, timeout=30)
                    except Exception:
                        pass
            except Exception as e:
                print("Gazette hata", e)
            time.sleep(3 + 2 * i)
        return None

    entries = []
    for page in (1, 2, 3):  # ~30 en yeni kayıt
        params = {"text": "East Sussex", "noticetypes": "2450",
                  "start-publish-date": since, "results-page": page}
        d = _get(params, tries=5 if page == 1 else 2)
        if d is None:
            if page == 1:
                print("Gazette: data.json 500/timeout (upstream); 0 kayıt döndürülüyor")
            break
        ent = d.get("entry", [])
        if isinstance(ent, dict):
            ent = [ent]
        if not ent:
            break
        entries += ent
    known = sorted(TOWN_DISTRICT.keys(), key=len, reverse=True)
    out = []
    seen = set()
    for e in entries:
        title = (e.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        # ilan içeriğinden (kayıtlı adres) kasaba tahmini
        content = re.sub(r"<[^>]+>", " ", e.get("content", "") or "")
        blob = (title + " " + content).lower()
        town = "Hastings"
        for t in known:
            if t.split("-")[0].lower() in blob:
                town = t
                break
        date = (e.get("published") or e.get("updated") or TODAY)[:10]
        out.append({"company": title, "town": town, "date": date,
                    "url": (e.get("id") or "https://www.thegazette.co.uk/")})
    return out


# =========================================================================
# 4) UCUZ/DISTRESSED KONUT — HM Land Registry Price Paid (OGL, ücretsiz): repossession (kategori B)
# =========================================================================
def land_registry(offline=True, cheap_threshold=130000):
    """Yalnızca fırsatlar: repossession (kategori B) veya < cheap_threshold ucuz satışlar.
    Normal fiyatlı emsaller atlanır (panoyu boğmasın)."""
    recs = _fixture("land_registry.json") if offline else _fetch_land_registry()
    out = []
    for r in recs:
        cat = r.get("category", "A")
        price = r.get("price")
        if cat != "B" and not (price and price < cheap_threshold):
            continue
        town = r.get("town", "Hastings")
        prop = {"F":"Konut","T":"Konut","S":"Konut","D":"Konut","O":"Karma Kullanım"}.get(r.get("property_type","F"),"Konut")
        is_repo = (cat == "B")
        out.append({
            "title": f"{r.get('paon','')} {r.get('street','')}".strip() + (" (repossession)" if is_repo else " (düşük fiyatlı satış)"),
            "town": town, "district": district_of(town),
            "opp": "Distressed İşletme" if is_repo else "Ucuz Gayrimenkul",
            "prop": prop, "price": price, "size": None, "rateable": None,
            "status": "Repossession" if is_repo else "Düşük fiyatlı",
            "source": "Land Registry", "score": None, "income": 0,
            "date": r.get("date", TODAY),
            "why": ("Land Registry repossession kaydı — düşük fiyatlı edinim sinyali." if is_repo
                    else "Land Registry'de bölge ortalaması altında satış — potansiyel ucuz edinim."),
            "url": "https://landregistry.data.gov.uk/",
        })
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
