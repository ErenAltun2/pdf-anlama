# Bilimsel PDF Anlama

## Proje hakkında

Bilimsel makalelerdeki tabloları, matematiksel formülleri ve figürleri bulup
anlaşılır çıktılara dönüştürmek için hazırlanmış bir Python projesidir. PDF'teki
öğelerin yerleri Docling ile tespit edilir; seçilen tablo, formül ve figür
görüntüleri bir görsel dil modeline (VLM) gönderilerek okunur veya açıklanır.

Proje iki şekilde kullanılabilir:

- **Streamlit arayüzü:** PDF yükleyip tüm belgeyi ya da belirli sayfaları işler;
  kırpılan görüntüyü ve model çıktısını yan yana gösterir.
- **Komut satırı:** Mevcut PDF dosyalarını toplu işler; sonuçları CSV, Markdown
  ve JSON olarak kaydeder.

Tabloları ekranda inceleyip CSV olarak indirebilir, formüllerin LaTeX kodunu
Word denklem alanında kullanabilir, figür açıklamalarını okuyup kopyalayabilirsin.
Bu proje model çıktısı üretir; sonuçların doğruluğunun makale bağlamında ayrıca
kontrol edilmesi gerekir.

## İş akışı

1. PDF sayfaları Docling ile okunur ve belge yapısı JSON olarak kaydedilir.
2. Tablolar, formüller ve figürler; sayfa, konum ve okuma sırasıyla belirlenir.
3. Belirlenen alanlar PDF'ten görüntü olarak kırpılır.
4. VLM tabloları Markdown/HTML'e, formülleri LaTeX'e dönüştürür ve figürleri
   Türkçe açıklar.
5. Sonuçlar doğrulanıp `outputs/results/` altına yazılır ve arayüzde gösterilir.

Streamlit'te belirli sayfalar seçilebilir. Daha önce işlenmiş sayfa ve içerik
türleri kayıt altında tutulur; sonraki çalıştırmada yalnızca yeni sayfalar veya
eksik içerik türleri işlenir. Önceki sonuçlar korunur. Bu kayıtlar
`outputs/results/<id>/processed_pages.json` dosyasındadır.
Yeni sayfalardan aynı içerik türleri isteniyorsa sayfalar birlikte Docling'e
verilir; böylece sayfa başına tekrar başlatma maliyeti azaltılır.

## Kurulum ve çalıştırma

Proje kök dizininde sanal ortamı oluştur (henüz yoksa), etkinleştir ve
bağımlılıkları kur:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### VLM sağlayıcısı

Varsayılan sağlayıcı Gemini'dir. Gemini kullanmak için proje kökünde `.env`
dosyasında `GEMINI_API_KEY` tanımlı olmalıdır. İsteğe bağlı olarak
`GEMINI_MODEL` ile model adı belirlenebilir. Yerel Ollama kullanacaksan
`VLM_PROVIDER=ollama` ve `OLLAMA_MODEL` değerlerini tanımla; Ollama uygulaması
ve belirtilen model bilgisayarda kullanılabilir olmalıdır. `.env` dosyasını
paylaşma veya sürüm kontrolüne ekleme. Gemini istekleri arasında varsayılan
olarak 4 saniye beklenir. İstek hızını artırmak için `.env` dosyasına
`VLM_MIN_GAP_SECONDS=1` yazılabilir; ancak daha kısa aralık API hız sınırına
takılmaya ve otomatik tekrar denemeleri nedeniyle toplam sürenin uzamasına yol
açabilir. Ollama yerel çalıştığı için bu bekleme uygulanmaz.

### Streamlit arayüzü

```powershell
streamlit run src/app.py
```

PDF'i yükle, işlenecek sayfaları ve içerik türlerini seçip **PDF'i işle**
düğmesine bas. Büyük dosyalarda veya çok sayıda görselde işlem, Docling ve VLM
çağrıları nedeniyle zaman alabilir. Arayüzde yüklenebilecek PDF üst sınırı
100 MB'tır.
Windows Uygulama Denetimi Docling'in CUDA kitaplığını `WinError 4551` ile
engellerse uygulama CPU'da yeniden dener; bu durumda işlem daha yavaş olabilir.
İşlem özetinde Docling'in bu PDF için GPU, CPU veya önceden kaydedilmiş JSON
kullanıp kullanmadığı gösterilir.
PDF işlenirken arayüzde de Docling'in seçtiği aygıt görüntülenir. Bu bilgi
PyTorch tabanlı Docling hızlandırıcısını gösterir; OCR için CUDA sağlayıcısı
kullanılamıyorsa durum ayrıca belirtilir.

### Komut satırından PDF işleme

Tek PDF:

```powershell
python src/run.py "data/pdf/1602.03837.pdf" --extract tables,equations,figures --format csv,md
```

Birden fazla PDF veya dosya deseni:

```powershell
python src/run.py "data/pdf/*.pdf" --extract tables --format csv,md --limit 3
```

`--extract` seçenekleri `tables`, `equations` ve `figures`; `--format` ise
`csv`, `md` ve `json` değerlerini kabul eder. `result.json` her çalıştırmada
kaydedilir; `csv` ve `md` ek dışa aktarma dosyalarını belirler. PDF dosyaları
`data/pdf/` klasöründe bulunmalıdır.

## Docker Hub ve Docker Compose ile çalıştırma

Yayımlanmış imaj `erenaltun/pdf-anlama:latest` olarak etiketlenir. İmajı
Docker Hub'a yüklemeden önce Docker Hub'da `erenaltun/pdf-anlama` adında bir
**public** repository oluştur. Ardından proje kökünde:

```powershell
docker login
docker build -t erenaltun/pdf-anlama:latest .
docker push erenaltun/pdf-anlama:latest
```

Arkadaşının kullanımı için `compose.yaml` ve `.env.example` dosyalarını
paylaş. Arkadaşının makinesinde Docker Desktop (Windows/macOS) veya Docker
Engine ve Docker Compose eklentisi kurulu olmalıdır. Gemini ile kullanacaksa
`.env.example` dosyasını `.env` olarak kopyalayıp **kendi** anahtarını
girmelidir:

```powershell
Copy-Item .env.example .env
```

`.env` dosyasını açıp `GEMINI_API_KEY` satırına kendi Gemini anahtarını
ekledikten sonra, `compose.yaml` dosyasının bulunduğu klasörde:

```powershell
docker compose up -d
```

Compose, imajı Docker Hub'dan çeker ve arayüzü `http://localhost:8501`
adresinde başlatır. İşlem durumunu görmek için `docker compose ps`, günlükleri
izlemek için `docker compose logs -f` kullanılabilir. Durdurmak için
`docker compose down` komutunu çalıştır. Sonuçlar adlandırılmış Docker
volume'unda saklanır; normal `down` komutu bu volume'u silmez. Sonuçları
volume ile birlikte silmek istenirse `docker compose down -v` kullanılır.

API anahtarı Docker imajına dahil edilmez; Compose çalışma anında `.env`
değerlerini konteynere aktarır. Gemini anahtarı olmadan arayüz açılabilir,
ancak Gemini ile içerik işleme başlatılamaz. `.env` dosyasını paylaşmayın veya
Docker Hub'a yüklemeyin.

Yeni bir imaj yayımlandığında arkadaşın güncel sürümü almak için:

```powershell
docker compose pull
docker compose up -d
```

Ollama kullanımı için `.env` içinde `VLM_PROVIDER=ollama` yapın ve `OLLAMA_HOST`
değerini Docker konteynerinden erişilebilir Ollama adresine ayarlayın.
Docker Desktop üzerinde host makinedeki Ollama servisi için varsayılan adres
`http://host.docker.internal:11434` olarak verilmiştir. Ollama'nın çalışır
durumda ve belirtilen modelin indirilmiş olması gerekir.

Bu imaj Streamlit arayüzünü çalıştırır. GPU hızlandırması Docker host'undaki
NVIDIA sürücüsü, container runtime ve Docling/ONNX yapılandırmasına bağlıdır;
yalnızca Docker Compose ile GPU kullanımının garanti edildiği
varsayılmamalıdır.

## Sonuçlar nerede saklanır?

- `outputs/baseline/`: Docling'in belge yapısı JSON'u. Ana akış bunu tekrar Docling çalıştırmamak için kullanır.
- `outputs/crops/`: Modelin okuduğu tablo, formül ve figür görüntüleri. İşleme sırasında oluşturulur; arayüz kaynak görüntüyü ve figür dışa aktarımlarını buradan gösterir.
- `outputs/cache/`: VLM yanıtlarının yeniden kullanılabilir önbelleği. Silinebilir; sonraki çalıştırmada aynı istekler modele yeniden gönderilir.
- `outputs/results/<id>/`: `result.json`, sayfa işleme kaydı ve dışa aktarılan sonuçlar. Arayüz önceki sonuçları buradan gösterir; silinirse önceki sonuçlar kaybolur ve sayfa seçimine bağlı işleme kaydı sıfırlanır.

`crops` ve `results` kaynak kodu değil, uygulamanın ürettiği çalışma verileridir.
İlk kullanımda kırpıntılar ve sonuçlar kendiliğinden oluşturulur. Sonuçları
silmek önceki kayıtları ve arayüzdeki görselleri kaldırır. `data/` altında
indirilen veya kullanıcı tarafından sağlanan PDF'ler bulunabilir. Bu yerel
dosyalar otomatik olarak temizlenmez.

## Kod klasörleri

- `src/app.py`: Streamlit arayüzü ve uygulamanın başlangıç noktası.
- `src/run.py`: Komut satırı ve arayüzün kullandığı ana PDF işleme hattı.
- `src/extraction/`: `extract_items.py` Docling çıktısında tablo/formül/figür konumlarını bulur; `extract_table.py`, `extract_equation.py` ve `describe_figure.py` bu kırpıntıları modele okutur.
- `src/cropping/crop_items.py`: Bulunan öğelerin PDF sayfasındaki alanlarını kırpar.
- `src/integrations/vlm_client.py`: Gemini/Ollama bağlantısı, istek sınırlama ve yanıt önbelleği.
- `src/models/schemas.py`: Sonuçların veri modelleri ve doğrulaması.
- `src/exporting/export.py`: Sonuçları Markdown, CSV, LaTeX ve figür dosyalarına aktarır.
- `scripts/download_examples/`: İsteğe bağlı arXiv örnek PDF'lerini indirme.
- `scripts/preprocessing/`: İsteğe bağlı toplu Docling ön işlemi.
- `scripts/inspect_results/`: Kaydedilmiş sonuçları terminalde inceleme.
- `tests/`: Elle çalıştırılan kontroller ve örnek PDF üreticisi.

`tests/test_table.py`, API çağrısı yapmayan hızlı mantık kontrolüdür.
`tests/test_vlm.py` ve `tests/test_cache.py` gerçek model isteği yapabilir.
`tests/test_run.py` hata denemeleri için örnek PDF'ler üretir; görselli örnek
için `outputs/crops/1602.03837/p3_fig_2.png` bulunmalıdır.

## İsteğe bağlı kontroller

Arayüzü kullanmak için aşağıdaki kontrollerin tamamını çalıştırmak gerekmez.
Tablo ayrıştırma mantığını hızlıca kontrol etmek için:

```powershell
python -m tests.test_table
```

Test çıktısındaki tüm satırlar `PASS` olmalıdır. Sağlayıcı bağlantısını
doğrulamak için `python -m tests.test_vlm` çalıştırılabilir. Bu komut gerçek bir
istek gönderir. `python -m tests.test_cache` de gerçek model isteği yapabilir.

`python -m tests.test_run` yalnızca örnek PDF'leri hazırlar. Bunları ana hatla
işlemek istersen:

```powershell
python src/run.py "data/test/*.pdf" --format csv,md
```

Oluşan sonuçları `outputs/results/` altında incele.

İsteğe bağlı Docling toplu ön işlemini çalıştırmak için:

```powershell
python scripts/preprocessing/run_docling_baseline.py
```

Kaydedilmiş sonucun okuma sırasını görmek için:

```powershell
python scripts/inspect_results/show_order.py 1602.03837
```

Örnek arXiv PDF ve LaTeX arşivlerini indirmek için:

```powershell
python scripts/download_examples/download_arxiv.py
```
