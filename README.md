# Fırsat Radarı — East Sussex (gerçek veri, ücretsiz, Vercel'siz)

Belediye ve ulusal kaynaklardan **gerçek veri** çeken, **tamamen ücretsiz** ve **Vercel kullanmayan** bir fırsat-istihbarat sistemi. Backend = GitHub Actions (zamanlanmış ingestion). Host = GitHub Pages (statik). Veri = günlük üretilen `public/data.json`.

En avantajlı edinim genelde **belediyeden** olduğu için kaynaklar belediye-önceliklidir (surplus/varlık kaydı, peppercorn/Community Asset Transfer, High Street Rental Auction) + planlama, tasfiye, Land Registry ve müzayede sinyalleriyle zenginleştirilir.

## Mimari (hepsi ücretsiz, Vercel yok)

```
GitHub Actions (cron, "backend")  ──►  scripts/build_data.py  ──►  public/data.json
        │  (her gün 06:00 UTC)                                          │
        └──►  scripts/alerts.py  ──►  Resend e-posta (yeni fırsatlar)   │
                                                                        ▼
                              GitHub Pages (statik host)  ◄──  public/index.html (frontend)
```

- **Backend / zamanlama:** GitHub Actions — ücretsiz, ayda 2.000+ dk. Cron burada çalışır (Vercel'e gerek yok).
- **Host:** GitHub Pages — ücretsiz, ticari kullanıma uygun statik hosting.
- **Veritabanı:** başlangıçta **yok** — veri minik olduğu için düz `data.json` yeterli ($0). İleride istersen Neon/Cloudflare D1 (ücretsiz kademe) eklenebilir.
- **Geocode:** postcodes.io (ücretsiz) — Google Maps API'ye ve kotasına gerek yok.
- **Uyarı:** Resend (ücretsiz 3.000 e-posta/ay). WhatsApp gibi metered kanallar opsiyonel.

> Alternatif host: **Cloudflare Pages** (yine ücretsiz, ticari OK). İş mantığı aynı kalır.

## Klasör yapısı

```
public/
  index.html        # Frontend — data.json'u okur (yoksa gömülü demo verisine düşer)
  data.json         # build_data.py çıktısı (günlük üretilir)
scripts/
  build_data.py     # Orkestratör: tüm kaynakları çalıştırır, skorlar, data.json yazar
  sources.py        # Kaynak adaptörleri (belediye, planlama, gazette, land registry, auction…)
  alerts.py         # Yeni fırsatlar için Resend e-posta
  requirements.txt  # requests, openpyxl (yalnız CANLI mod)
  fixtures/*.json   # Offline test/seed verisi (ağsız çalıştırma)
.github/workflows/
  ingest.yml        # cron → build → GitHub Pages'e dağıt
```

## Kaynaklar

| Kaynak | Ne verir | Ücret | Anahtar |
|---|---|---|---|
| ESCC "Property for sale/rent" | Belediye kiralık/satılık (gerçek) | Ücretsiz | Hayır |
| Rother varlık kaydı (.xlsx) | Belediye mülkleri + **boş** olanlar | Ücretsiz | Hayır |
| PlanIt API | Planlama başvuruları (change-of-use/geliştirme) | Ücretsiz | Hayır |
| The Gazette | Tasfiye/winding-up (distressed işletme) | Ücretsiz | Hayır |
| HM Land Registry Price Paid | Son satış + repossession (OGL) | Ücretsiz | Hayır |
| Müzayede (Clive Emson vb.) | BMV lotlar | Ücretsiz | Hayır* |
| Companies House | Şirket/insolvency zenginleştirme | Ücretsiz | **CH_API_KEY** |
| EPC | Enerji sertifikası | Ücretsiz** | **EPC_API_KEY** |

\* Müzayede sitelerinde ToS'a uyun; mümkünse resmi feed/işbirliği. \*\* EPC ücretsiz devlet ucu Mayıs 2026'da kapanıyor; sonrası aggregator gerekebilir.

## Kurulum (10 dakika)

1. Bu klasörü bir **GitHub deposu** yap (yeni repo → dosyaları yükle).
2. **Settings → Pages → Build and deployment → Source: GitHub Actions** seç.
3. (Opsiyonel) **Settings → Secrets and variables → Actions** altına ekle: `CH_API_KEY`, `EPC_API_KEY`, `RESEND_API_KEY`, `ALERT_FROM`, `ALERT_TO`.
4. **Actions** sekmesinden "Fırsat Radarı — ingest & deploy" iş akışını **Run workflow** ile tetikle.
5. Yayınlanan Pages adresini aç — üstteki rozet **CANLI**'ya döner, kartlar `data.json`'dan gelir.

## Offline test (ağsız)

```bash
python3 scripts/build_data.py --offline --out public/data.json
# public/index.html'i tarayıcıda aç (yerel sunucu ile):
python3 -m http.server -d public 8000   # http://localhost:8000
```

## Maliyet

Bu haliyle **£0/ay**: GitHub Actions + GitHub Pages + postcodes.io + Resend ücretsiz kademe; veri minik olduğu için DB gerekmiyor. Metered olan tek şeyler (Google Maps API, Twilio WhatsApp) **kullanılmıyor**. Sürpriz fatura riski yok.

## Yeni kaynak eklemek

`scripts/sources.py` içine `def yeni_kaynak(offline=True): -> list[dict]` ekle (ortak şemaya uy), sonra `SOURCES` listesine koy. Offline için `scripts/fixtures/yeni_kaynak.json` bırak.

## Yasal notlar

Açık/resmî veri (OGL) serbest. Portal (Rightmove/Zoopla) **scrape etme** — ToS + veritabanı hakkı + GDPR riski. Kişisel veri işlersen ICO kaydı + GDPR. Deal aracılığı (sourcing) yaparsan redress + AML + PI gerekir.

## Sonraki adımlar

- Companies House anahtarıyla tasfiye kayıtlarını mülk/adresle eşleştir.
- Fırsat skorunu kendi kriterlerinle ağırlıklandır (`scripts/build_data.py → score`).
- İstersen Cloudflare Worker + Neon ekleyip dinamik sorgu/API'ye geç.
