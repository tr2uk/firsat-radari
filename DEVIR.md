# Fırsat Radarı — Devir Dosyası (Session Handoff)

**Son güncelleme:** 2026-07-12
**Repo:** https://github.com/tr2uk/firsat-radari (PUBLIC) · owner `tr2uk`
**Canlı:** https://tr2uk.github.io/firsat-radari/ (GitHub Pages, Actions workflow kaynağı)
**Yerel klasör:** `~/Downloads/firsat-radari-app` (Masaüstünde DEĞİL — Downloads'a taşındı)
**Son commit:** `fc5b936` · branch `main` · çalışan ağaç TEMİZ (her şey push'lu)

> Ne yapıyor: East Sussex (Hastings/Rother/Wealden/Eastbourne/Lewes) için gayrimenkul
> & işletme "fırsat istihbaratı" panosu. Ücretsiz backend = GitHub Actions cron günde
> bir veriyi çeker, skorlar, şifreler ve statik siteyi Pages'e deployer. Vercel YOK.

---

## 0) HIZLI BAŞLANGIÇ (yeni sohbet buradan devam etsin)

```bash
cd ~/Downloads/firsat-radari-app
source .venv/bin/activate            # requests, openpyxl, cryptography kurulu
# CANLI derleme (data.json üretir):
python scripts/build_data.py --out public/data.json
# Şifrele (data.json -> data.enc, düz metni siler):
SITE_PASSPHRASE='...' python scripts/encrypt_data.py
# Yerel önizleme:
python3 -m http.server -d public 8000   # http://localhost:8000
```

- **Deploy = `git push origin main`** → `ingest.yml` otomatik çalışır (build → alerts →
  ŞİFRELE → Pages deploy). Ayrıca her gün 06:00 UTC cron + elle `workflow_dispatch`.
- `.venv/`, `public/data.json`, `public/data.enc`, `__pycache__/` **gitignore'lu**.
  Şifreli veri (`data.enc`) repoya girmez; **CI her koşuda yeniden üretir** ve Pages
  artefaktıyla yükler. Pages repodan değil, CI çıktısından deploy eder.
- Python 3.9 (sistem). `Bash tool = login zsh`. Yerel canlı testte harici API'ler
  rate-limit/flaky olabilir (aşağıda); CI farklı IP + günlük olduğu için daha sağlıklı.

---

## 1) MİMARİ / DOSYALAR

| Dosya | Görev |
|---|---|
| `scripts/build_data.py` | Tüm kaynakları çalıştırır, **skorlar**, dayanıklılık (bayat taşıma), geocode, `public/data.json` yazar |
| `scripts/sources.py` | Kaynak adaptörleri (`_fetch_*` = CANLI, `_fixture` = offline). `SOURCES` listesi |
| `scripts/encrypt_data.py` | `data.json` → AES-256-GCM `data.enc` (PBKDF2-SHA256, 250k iter); düz metni siler |
| `scripts/alerts.py` | (opsiyonel) e-posta uyarısı; düz `data.json` okur → şifrelemeden ÖNCE çalışmalı |
| `scripts/fixtures/*.json` | Offline seed verisi (ağ yok, sadece stdlib) |
| `public/index.html` | Tek-dosya ön yüz + **parola kapısı** + WebCrypto çözme |
| `.github/workflows/ingest.yml` | CI: derle → alerts → şifrele → Pages deploy |

**Kaynak → `source` etiketi eşlemesi (skorlamada kullanılıyor, DEĞİŞTİRİRKEN DİKKAT):**
`Belediye (Canlı)` (ESCC, `real:True`) · `Konsey Varlık Kaydı` (Rother) ·
`Planlama Başvurusu` (PlanIt) · `Land Registry` · `Gazette (Tasfiye)` · `Auction Kataloğu`

---

## 2) BU OTURUMDA YAPILANLAR (7 commit, kronolojik)

1. **`c1f98ff` İlk sürüm** — repo init, GitHub'a public push, Pages'i workflow kaynağıyla açtık.

2. **`5a89a7e` Veri kaynaklarını canlıya göre düzeltme** (gerçek API şemalarına göre):
   - **Land Registry** → yalnızca FIRSAT: repossession (kat. B) veya `< £130k` ucuz satış;
     normal emsaller atlanıyor.
   - **PlanIt** → `auth=` tek başına HTTP 400 ("Spatial/date/search restrictions required").
     Çözüm: her yetkilinin merkez koordinatında **`lat/lng + krad`** spatial sorgu +
     change-of-use/geliştirme keyword filtresi + 429 rate-limit backoff.
   - **ESCC (Belediye)** → PDF linkleri **göreli** (`/media/…`), kod mutlak URL arıyordu (0
     eşleşme). İç içe `<i>/<small>` etiketleri var → temiz isim `title="Download '…'"`
     attribute'undan; "DEADLINE PASSED" ilanlar eleniyor.
   - **Rother .xlsx** → kayıtta **occupancy/Vacant sütunu YOK**; "vacant" filtresi 440
     satırın hepsini eliyordu. Çözüm: geliştirilebilir arazi alt kümesi
     (land/site/plot/depot/yard/former/garage), üst sınır 30, kasaba adresten ayrıştırılıyor.
   - **Gazette** → PARSER DÜZELTİLDİ+DOĞRULANDI (`text=East Sussex & noticetypes=2450 &
     start-publish-date` → 45 gerçek şirket kaydı). Bug'lar: geçersiz `results-page-size`
     (500 yapıyor), tarih alanı `updated`→`published`. Session+prime+backoff retry eklendi.

3. **`d0ea08d` Rother başlığı** — referans-kod yerine açıklayıcı `Property` adı sütunu.

4. **`e79c7fe` Veri dayanıklılığı (stale carryover)** — bir kaynak 0 dönerse son iyi
   yayından (`LIVE_DATA_URL`) o kaynağın kayıtlarını **≤14 gün** "bayat" taşır
   (`stale:True`, UI'da gri "önceki tarama" rozeti). Offline'da devre dışı.
   `build_data.py`: `EXPECTED_SOURCES`, `STALE_MAX_DAYS=14`, `carry_over_stale()`.

5. **`890ba01` Skor kalibrasyonu + konsey arazisi davranışı**:
   - `WEIGHTS` yeniden (base 45, kaynak-bazlı ağırlıklar, `resi_conversion`), clamp **45–92**.
   - **Rother kayıtları artık `real` DEĞİL → skorlanıyor**; `opp="Arsa/Geliştirme"`,
     `status="Konsey arazisi (boş)"`. Sadece ESCC `real:True` kaldı.
   - UI: fiyatı null skorlu kayıtlar "£0" yerine **"Teklif/müzakere"**; proposal 4. bölüm
     (TR+EN) müzakere satırı; size/price null çökme korumaları.

6. **`58703b3` Konsey arazisi içi ayrıştırma** — `score()` içinde: başlıkta
   land/site/plot/field/development/garages → **+6**; garage/convenience/kiosk/shelter/
   toilet/store/hut → **−6**. Geliştirilebilir araziler öne çıktı (80), küçük varlıklar geriledi.

7. **`fc5b936` Şifre koruması (AES-256-GCM)** — SON DURUM:
   - `encrypt_data.py`: `data.json` → `data.enc` (PBKDF2-SHA256 250k + AES-GCM), düz metni siler.
   - `ingest.yml`: "Veriyi şifrele" adımı (**alerts'ten SONRA, deploy'dan ÖNCE** — çünkü
     `alerts.py` düz `data.json` okur).
   - `index.html`: `loadLive` IIFE → **parola kapısı** (WebCrypto PBKDF2+AES-GCM çözme,
     `sessionStorage`'da parola). `_enrich`/`_buildFilters` korundu.
   - `.gitignore`: `public/data.json` + `public/data.enc`.
   - **Secret `SITE_PASSPHRASE` repoda TANIMLI** (workflow şifreleme adımını geçti).

---

## 3) MEVCUT CANLI DURUM (doğrulanmış)

- **Şifreli:** `data.enc` HTTP 200 (v1/PBKDF2-SHA256/250k/salt/iv/ciphertext); `data.json` **404**.
  Şifresiz site = yalnızca parola kapısı görünür (ekran görüntüsüyle teyit). Yanlış şifre
  GCM doğrulamasında reddediliyor (`OperationError`), doğru şifre panoyu açıyor.
- **Son (şifrelenmeden önceki) per-source & histogram** (CI üretimi, count=67):
  - Belediye (Canlı) **3** · Konsey Varlık Kaydı **30** · Planlama **29** · Land Registry **5**
  - Gazette **0** · Auction **0**
  - Histogram: CANLI 3 · 50→15 · 60→26 · 70→4 · **80→19** · (skor aralığı ~54–80)
- **En iyi 10:** hepsi konsey geliştirilebilir arazisi @80 (Former High School Site, Former
  Railway Track, çeşitli "Land at…" — Bexhill/Rye).

---

## 4) BİLİNEN SORUNLAR / GOTCHA'LAR

- **Gazette API şu an flaky**: `data.json` endpoint aralıklı **500 / IP rate-limit** veriyor
  (aynı sorgu dakikalar içinde 200↔500). PARSER DOĞRU (45 kayıt döndürdüğü kanıtlandı).
  Session+prime+backoff retry var; günlük cron sağlıklı bir günde yakalayacak. → **0 = kod
  değil, upstream.**
- **PlanIt katı rate-limit** (429, ~100s pencere). 5 yetkili spatial sorgu; bazı turlarda 1
  yetkili timeout edebilir (kod diğerlerinden devam eder). Büyük `krad` timeout yapar (küçük tut).
- **Auction** = kasıtlı boş (`_fetch_auctions` → `[]`), opsiyonel entegrasyon noktası.
- **Node 20 deprecation** uyarısı (Actions) — zararsız, otomatik Node 24'e düşüyor.
- **Gömülü DEMO seed**: `index.html` içinde 31 kayıtlık sahte demo veri var (hassas değil);
  kapı açılana dek `DATA` gerçek veriyle değişmez. Gerçek veri yalnızca şifreli `data.enc`'te.
- **Güvenlik sınırı**: istemci-tarafı şifreleme = paylaşılan TEK parola; parolayı bilen
  herkes çözer. Kişi-bazlı erişim/iptal gerekirse sunucu-taraflı auth şart.
- Yerel `data.json`/`data.enc` şu an diskte YOK (encrypt sildi, gitignore'lu). Yeniden
  üretmek için Bölüm 0'daki komutlar.

---

## 5) YAPILACAKLAR / AÇIK İŞLER (öncelik sırasız)

- [ ] **Gazette'i canlı yakala**: cron'un sağlıklı bir günde Gazette kaydı çektiğini doğrula
      (data.enc'i çöz, `Gazette (Tasfiye)` > 0 mı?). Gerekirse retry sayısı/aralığı artır.
- [ ] **CH_API_KEY (opsiyonel)**: Companies House ücretsiz anahtarı repo Settings > Secrets'a
      eklenirse tasfiye→adres zenginleştirmesi açılır (`enrich_gazette`). Yoksa sessizce atlanır.
- [ ] **Stale carryover'ı gerçek kesintide gözlemle**: Gazette bir gün dolu, ertesi gün 0
      dönerse "önceki tarama" rozetli bayat kayıtların taşındığını doğrula.
- [ ] **Auction entegrasyonu** (isteğe bağlı): Clive Emson vb. lot/rehber fiyat/tarih ayrıştırma
      (ToS'a dikkat).
- [ ] **Parola yönetimi**: parola değişince kullanıcıların `sessionStorage` eski parolası
      otomatik başarısız olur (yeniden girerler) — sorun yok, ama istenirse mesaj eklenebilir.
- [ ] **(Düşünülecek) Erişim modeli**: tek parola yeterli mi, yoksa kişi-bazlı mı? Kişi-bazlı
      gerekiyorsa Pages'ten çıkıp hafif bir auth backend gerekir.
- [ ] **Skor eşikleri**: 45–92 clamp ve ağırlıklar Cetin'in stratejisine göre ince ayar
      yapılabilir (hepsi `build_data.py` `WEIGHTS`'te tek yerde).

---

## 6) SECRET'LAR (repo Settings > Secrets > Actions)

| Secret | Durum | Not |
|---|---|---|
| `SITE_PASSPHRASE` | **TANIMLI** (zorunlu) | Şifreleme parolası; yoksa CI şifreleme adımı fail |
| `CH_API_KEY` | opsiyonel | Companies House zenginleştirme |
| `EPC_API_KEY` | opsiyonel | EPC (kullanılmıyor şu an) |
| `RESEND_API_KEY`, `ALERT_FROM`, `ALERT_TO` | opsiyonel | e-posta uyarısı (alerts.py) |

> Kural: parola/secret ISTENMEZ; kullanıcı kendi ekler.

---

## 7) DEPLOY & DOĞRULAMA REÇETESİ

```bash
# push sonrası:
RID=$(gh run list --workflow=ingest.yml -L 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$RID" --exit-status --interval 12
# canlı şifreli veri + düz metin yok kontrolü:
curl -s -o /dev/null -w "enc %{http_code}\n"  "https://tr2uk.github.io/firsat-radari/data.enc"
curl -s -o /dev/null -w "json %{http_code}\n" "https://tr2uk.github.io/firsat-radari/data.json"  # 404 beklenir
```
