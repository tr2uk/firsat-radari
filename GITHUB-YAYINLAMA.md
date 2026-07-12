# GitHub'da yayınlama — Claude Code için prompt

## Önce (bir kez)
1. GitHub CLI kur: https://cli.github.com  → sonra `gh auth login` (tarayıcıyla giriş yap).
2. Bu zip'i çıkar; terminalde **`firsat-radari-app`** klasörüne gir.
3. Aynı klasörde Claude Code'u başlat ve aşağıdaki promptu yapıştır.

---

## Claude Code'a yapıştırılacak prompt

```
Bulunduğum bu klasörü (firsat-radari-app) GitHub'da yayınla ve GitHub Pages'te
canlıya al. Sırasıyla yap ve her adımın çıktısını bana göster:

1) Git deposu hazırla: `git init -b main`, tüm dosyaları ekle, "İlk sürüm: Fırsat
   Radarı" mesajıyla commit et. (.gitignore zaten var; __pycache__ ve .seen_ids.json
   commit'lenmesin.)

2) GitHub oturumunu doğrula: `gh auth status`. Oturum yoksa DUR ve bana bildir
   (benden token isteme, ben `gh auth login` yapacağım).

3) PUBLIC bir repo oluştur ve push et:
   `gh repo create firsat-radari --public --source=. --remote=origin --push`
   (Ad doluysa sonuna kısa bir ek koy, ör. firsat-radari-es.)

4) owner/repo değerlerini al: `gh repo view --json owner,name`.

5) GitHub Pages'i GitHub Actions kaynağıyla etkinleştir:
   `gh api --method POST repos/<owner>/<repo>/pages -f build_type=workflow`
   Zaten varsa `--method PUT` ile dene; hata verirse görmezden gel.

6) Deploy iş akışını çalıştır ve izle:
   `gh workflow run "Fırsat Radarı — ingest & deploy"` (veya ingest.yml),
   ardından `gh run watch`.
   İş akışı canlı kaynaklara erişemezse otomatik olarak `--offline` fixtures ile
   veri üretir (workflow bunu zaten yapıyor), yani site boş kalmaz.

7) Yayın adresini yazdır: `gh api repos/<owner>/<repo>/pages --jq .html_url`.
   Bana bu canlı URL'yi ve son çalışmanın sonucunu (başarılı/hatalı) özetle.

Kurallar: Herhangi bir adımda hata olursa DUR ve net şekilde açıkla; benden token/secret
isteme. Repo'yu private yapma (ücretsiz Pages için public gerekli).
```

---

## Opsiyonel: canlı veri anahtarları (secrets)

Fixtures yerine tam CANLI veri için (Companies House / EPC / e-posta uyarısı):

```
gh secret set CH_API_KEY       # https://developer.company-information.service.gov.uk (ücretsiz)
gh secret set EPC_API_KEY      # EPC (opsiyonel)
gh secret set RESEND_API_KEY   # e-posta uyarısı (ücretsiz 3.000/ay)
gh secret set ALERT_FROM       # ör. radar@alanadınız.co.uk
gh secret set ALERT_TO         # ör. siz@ornek.com,ekip@ornek.com
```

Anahtar koymadan da çalışır: PlanIt, The Gazette, Land Registry, belediye kaynakları
anahtarsızdır; CH/EPC yoksa o zenginleştirmeler atlanır.

## Sonraki güncellemeler
`main`'e her push, cron her gün 06:00 UTC iş akışını tetikler → veriyi yeniler ve
Pages'i günceller. Elle: `gh workflow run` ya da Actions sekmesi → Run workflow.
