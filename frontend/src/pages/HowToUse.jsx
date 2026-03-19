import { useState } from "react";

function Section({ title, children }) {
  return (
    <div className="bg-slate-800 rounded-xl p-6 space-y-3">
      <h2 className="text-lg font-bold text-blue-400 border-b border-slate-600 pb-2">{title}</h2>
      {children}
    </div>
  );
}

function Step({ n, title, children }) {
  return (
    <div className="flex gap-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center font-bold text-sm">
        {n}
      </div>
      <div className="flex-1">
        <p className="font-semibold text-white mb-1">{title}</p>
        <div className="text-slate-300 text-sm leading-relaxed space-y-1">{children}</div>
      </div>
    </div>
  );
}

function Note({ type = "info", children }) {
  const styles = {
    info:    "bg-blue-950 border-blue-500 text-blue-200",
    warn:    "bg-amber-950 border-amber-500 text-amber-200",
    success: "bg-green-950 border-green-500 text-green-200",
    danger:  "bg-red-950 border-red-500 text-red-200",
  };
  const icons = { info: "ℹ️", warn: "⚠️", success: "✅", danger: "🚫" };
  return (
    <div className={`border-l-4 rounded-r px-4 py-2 text-sm ${styles[type]}`}>
      {icons[type]} {children}
    </div>
  );
}

function Code({ children }) {
  return (
    <code className="bg-slate-900 text-green-400 px-2 py-0.5 rounded text-xs font-mono">
      {children}
    </code>
  );
}

function Tab({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-t border-b-2 transition-colors ${
        active
          ? "border-blue-500 text-blue-400 bg-slate-800"
          : "border-transparent text-slate-400 hover:text-white"
      }`}
    >
      {label}
    </button>
  );
}

export default function HowToUse() {
  const [osTab, setOsTab] = useState("mac"); // mac | windows

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">
      <div>
        <h1 className="text-2xl font-bold">Nasıl Kullanılır?</h1>
        <p className="text-slate-400 text-sm mt-1">
          Sistemi sıfırdan kurma ve kullanma rehberi — ilk kez açıyorsan buradan başla.
        </p>
      </div>

      {/* ── GENEL BAKIŞ ─────────────────────────────────────────────── */}
      <Section title="Sisteme Genel Bakış">
        <p className="text-slate-300 text-sm leading-relaxed">
          Bu sistem, 3D yazıcının tablasına koyduğun parçayı <strong>kamera ile tespit eder</strong>,
          koordinatlarını hesaplar, <strong>otomatik kaplama G-code'u üretir</strong> ve yazıcıya
          gönderir. Pompa aynı anda çözeltiyi parça üzerine basar.
        </p>
        <div className="bg-slate-900 rounded-lg p-4 font-mono text-xs text-slate-300 space-y-1">
          <p><span className="text-green-400">USB Kamera</span>  →  PC (bu yazılım)</p>
          <p><span className="text-blue-400">3D Yazıcı</span>   →  PC (USB / serial kablo)</p>
          <p><span className="text-amber-400">Arduino Uno</span> →  PC (USB kablo, pompa step motor kontrolü)</p>
        </div>
        <Note type="warn">
          Başlamadan önce <strong>3 USB kablosunun</strong> takılı olması gerekiyor:
          kamera, yazıcı ve Arduino.
        </Note>
      </Section>

      {/* ── İLK KURULUM ─────────────────────────────────────────────── */}
      <Section title="1. Adım — İlk Kurulum (Bir Kez Yapılır)">
        <div className="flex gap-2 mb-4">
          <Tab label="macOS / Linux" active={osTab === "mac"} onClick={() => setOsTab("mac")} />
          <Tab label="Windows"       active={osTab === "win"} onClick={() => setOsTab("win")} />
        </div>

        {osTab === "mac" ? (
          <div className="space-y-3 text-sm text-slate-300">
            <p>Terminal aç, proje klasörüne git:</p>
            <div className="bg-slate-900 rounded p-3 font-mono text-green-400 text-xs space-y-1">
              <p>cd ~/Desktop/Bitirme</p>
              <p>chmod +x start.sh</p>
              <p>./start.sh</p>
            </div>
            <p>Script ilk çalışmada Python sanal ortamını ve tüm paketleri otomatik kurar (~5 dakika internet hızına göre değişir).</p>
          </div>
        ) : (
          <div className="space-y-3 text-sm text-slate-300">
            <p>Dosya Gezgini'nde proje klasörünü aç ve <Code>start.bat</Code> dosyasına çift tıkla.</p>
            <Note type="info">
              Windows güvenlik uyarısı çıkarsa "Daha fazla bilgi" → "Yine de çalıştır" seç.
            </Note>
            <p>Script ilk çalışmada Python sanal ortamını ve tüm paketleri otomatik kurar.</p>
          </div>
        )}

        <Note type="success">
          Kurulum tamamlandığında tarayıcı otomatik açılır → <Code>http://localhost:5173</Code>
        </Note>
      </Section>

      {/* ── KAMERA İNDEKSİ ─────────────────────────────────────────── */}
      <Section title="2. Adım — Kamera İndeksi Nedir?">
        <p className="text-slate-300 text-sm leading-relaxed">
          Bilgisayarın takılı kameraları 0, 1, 2… şeklinde numaralandırılır.
          <strong> Genellikle 0 doğrudur</strong> — bu laptop'un dahili kamerasıdır.
          Sisteme bağladığın USB kamera farklı bir numara alabilir.
        </p>
        <div className="bg-slate-900 rounded-lg p-4 text-sm space-y-2">
          <div className="flex items-center gap-3">
            <span className="w-8 text-center font-bold text-blue-400">0</span>
            <span className="text-slate-300">Laptop'un dahili kamerası (varsa)</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="w-8 text-center font-bold text-green-400">1</span>
            <span className="text-slate-300">İlk takılan USB kamera ← büyük ihtimalle bu</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="w-8 text-center font-bold text-amber-400">2</span>
            <span className="text-slate-300">İkinci USB kamera (varsa)</span>
          </div>
        </div>
        <Note type="info">
          <strong>Nasıl anlarım?</strong> Ayarlar sayfasında indeksi değiştir → Kaydet.
          Dashboard'daki canlı görüntü değişirse doğru indeksi buldun.
          Dahili kamera yoksa direkt 0 dene, görüntü gelmezse 1 dene.
        </Note>
      </Section>

      {/* ── SERIAL PORT ─────────────────────────────────────────────── */}
      <Section title="3. Adım — Serial Port Nedir, Hangisini Seçeceğim?">
        <p className="text-slate-300 text-sm leading-relaxed">
          USB kabloyla bağladığın her cihaz (yazıcı, Arduino) işletim sisteminde bir
          <strong> sanal seri port</strong> olarak görünür. Portun adı işletim sistemine göre farklıdır:
        </p>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-900 rounded-lg p-4 space-y-2">
            <p className="text-blue-400 font-semibold text-sm">macOS / Linux</p>
            <div className="text-xs font-mono text-slate-300 space-y-1">
              <p><span className="text-green-400">/dev/tty.usbserial-XXXX</span></p>
              <p className="text-slate-500">→ FTDI çipli yazıcılar</p>
              <p><span className="text-green-400">/dev/tty.usbmodem-XXXX</span></p>
              <p className="text-slate-500">→ Arduino / native USB</p>
              <p><span className="text-green-400">/dev/ttyUSB0</span></p>
              <p className="text-slate-500">→ Linux (yazıcı)</p>
              <p><span className="text-green-400">/dev/ttyACM0</span></p>
              <p className="text-slate-500">→ Linux (Arduino)</p>
            </div>
          </div>
          <div className="bg-slate-900 rounded-lg p-4 space-y-2">
            <p className="text-amber-400 font-semibold text-sm">Windows</p>
            <div className="text-xs font-mono text-slate-300 space-y-1">
              <p><span className="text-amber-400">COM3</span></p>
              <p className="text-slate-500">→ genellikle Arduino</p>
              <p><span className="text-amber-400">COM4</span></p>
              <p className="text-slate-500">→ genellikle 3D yazıcı</p>
              <p className="text-slate-400 text-xs mt-2">
                Aygıt Yöneticisi → Bağlantı Noktaları (COM ve LPT) kısmından görebilirsin.
              </p>
            </div>
          </div>
        </div>

        <Note type="warn">
          <strong>Hangisi hangisi?</strong> Cihazı takıp çıkar, listede kaybolan port o cihaza aittir.
          "Yenile" butonuna basarak listeyi güncelleyebilirsin.
        </Note>

        <div className="bg-slate-900 rounded-lg p-4 space-y-2 text-sm">
          <p className="font-semibold text-slate-200">Kısa kontrol yöntemi (macOS):</p>
          <div className="font-mono text-xs text-green-400 space-y-1">
            <p># Yazıcıyı tak, terminale yaz:</p>
            <p>ls /dev/tty.*</p>
            <p># Çıkan port → yazıcı portun</p>
            <p># Arduino'yu tak, tekrar çalıştır → yeni gelen port Arduino</p>
          </div>
        </div>
      </Section>

      {/* ── ARUCO ───────────────────────────────────────────────────── */}
      <Section title="4. Adım — ArUco Marker Kalibrasyon">
        <p className="text-slate-300 text-sm leading-relaxed">
          Sistem kameranın gördüğü pikseli yazıcı tablasındaki gerçek milimetre koordinatına
          çevirebilmek için <strong>4 adet ArUco marker</strong> kullanır. Bu kareler,
          tablaya yapıştırılmış referans noktalarıdır.
        </p>

        <div className="space-y-3">
          <Step n="1" title="Marker'ları yazdır">
            <p>Terminalde çalıştır:</p>
            <Code>python scripts/generate_aruco.py</Code>
            <p className="mt-1">→ <Code>aruco_markers.png</Code> oluşur. Bunu yazdır.</p>
            <Note type="info">300 DPI'da yazdırırsan her marker ~30×30mm olur. Ölçü önemli değil ama tutarlı olsun.</Note>
          </Step>

          <Step n="2" title="Marker'ları tablaya yapıştır">
            <p>4 köşeye sırayla yapıştır:</p>
            <div className="bg-slate-900 rounded p-3 font-mono text-xs text-slate-300 mt-1">
              <p>Marker 0 → Sol Ön</p>
              <p>Marker 1 → Sağ Ön</p>
              <p>Marker 2 → Sağ Arka</p>
              <p>Marker 3 → Sol Arka</p>
            </div>
          </Step>

          <Step n="3" title="Marker pozisyonlarını ölç ve gir">
            <p>Her marker'ın merkezinin yazıcı koordinatını cetvel ile ölç (mm cinsinden).
            Ayarlar sayfasındaki "ArUco Marker Pozisyonları" kutularına gir.</p>
          </Step>

          <Step n="4" title="Kalibre Et butonuna bas">
            <p>Ayarlar → "Kalibre Et" butonuna bas. Kamera marker'ları görmüşse
            <Code>Kalibrasyon başarılı</Code> yazısı çıkar.</p>
            <Note type="warn">Kamera tam tepeden bakmalı, marker'lar görünür olmalı.</Note>
          </Step>
        </div>
      </Section>

      {/* ── KAPLAMA AKIŞI ───────────────────────────────────────────── */}
      <Section title="5. Adım — Kaplama İşlemi (Her Kullanımda)">
        <div className="space-y-4">
          <Step n="1" title="Parçayı tablaya yerleştir">
            <p>Parçayı çift taraflı bantla tablaya sabitle. Tam ortada olmasına gerek yok — sistem nerede olduğunu bulur.</p>
          </Step>

          <Step n="2" title="Pompa şırıngasını hazırla">
            <p>Şırıngaya çözeltiyi doldur, havasını al, sisteme bağla.</p>
          </Step>

          <Step n="3" title="Dashboard → Tara butonuna bas">
            <p>Kamera görüntüsünde parça yeşil konturla çizilir. Log satırında boyutlarını göreceksin.</p>
            <Note type="warn">Kalibrasyon yapılmamışsa kontur mm'ye çevrilemez, G-code üretilemez.</Note>
          </Step>

          <Step n="4" title="Kaplama parametrelerini ayarla (isteğe bağlı)">
            <p>Sağ panelden:</p>
            <ul className="list-disc list-inside space-y-0.5 ml-2">
              <li><strong>Çizgi aralığı</strong> — kaplama çizgileri arası mesafe (ince → daha fazla çözelti)</li>
              <li><strong>Z-offset</strong> — nozzle ile parça yüzeyi arası mesafe</li>
              <li><strong>Feed rate</strong> — kaplama hareketi hızı (yavaş → daha eşit kaplama)</li>
              <li><strong>Bant kalınlığı</strong> — parçanın altındaki bant kalınlığı (Z sıfıra eklenir)</li>
              <li><strong>Pattern</strong> — zigzag / paralel / spiral</li>
            </ul>
          </Step>

          <Step n="5" title="Önizle butonuna bas">
            <p>G-code üretilir. Alt bölümde kaplama yolu görselleştirilir. Satır sayısı ve tahmini süre log'da görünür.</p>
          </Step>

          <Step n="6" title="Pompayı başlat">
            <p>Sağ panelden pompa hızını ayarla → "Başlat"a bas. Çözelti akmaya başlar.</p>
          </Step>

          <Step n="7" title="Başlat butonuna bas">
            <p>G-code yazıcıya gönderilir. İlerleme çubuğunu takip et. İşlem bitince nozzle park pozisyonuna çekilir.</p>
            <Note type="danger">
              Acil durumda "Durdur" butonuna bas → M112 gönderilir, yazıcı anında durur.
            </Note>
          </Step>
        </div>
      </Section>

      {/* ── SSS ─────────────────────────────────────────────────────── */}
      <Section title="Sık Sorulan Sorular">
        {[
          {
            q: "Kamera görüntüsü gelmiyor, ne yapayım?",
            a: "Ayarlar → Kamera İndeksini 0 yerine 1 dene → Kaydet. Hâlâ gelmiyorsa USB kablosunu çıkar takarak dene.",
          },
          {
            q: "Port listesinde cihazım görünmüyor?",
            a: "Cihaz sürücüsü yüklü olmayabilir. Arduino için 'CH340 driver', Ender 3 için 'CP2102 driver' gerekebilir. Google'da arayabilirsin.",
          },
          {
            q: "Kalibrasyon başarısız diyor?",
            a: "Kamera 4 marker'ın tamamını görmüyor olabilir. Kameranın açısını kontrol et, ışık yeterliyse markerler net görünmeli.",
          },
          {
            q: "Tara dedim ama kontur çıkmadı?",
            a: "Parçanın arka plandan yeterince ayrışmıyor olabilir. Parçanın altına beyaz kağıt koy veya ışığı artır.",
          },
          {
            q: "'Yazıcıya bağlanılamadı' hatası?",
            a: "Yanlış port seçilmiş olabilir. Başka bir COM/tty portundan dene. Yazıcının açık olduğundan emin ol.",
          },
          {
            q: "G-code gönderdim ama yazıcı hareket etmiyor?",
            a: "G28 (home) komutu çalışıyor olabilir, bu uzun sürer. Log'da 'done' görünene kadar bekle. Yazıcının USB ile değil SD kartla bağlı olmadığını kontrol et.",
          },
        ].map(({ q, a }) => (
          <details key={q} className="bg-slate-900 rounded-lg group">
            <summary className="px-4 py-3 cursor-pointer text-sm font-medium text-slate-200 hover:text-white list-none flex justify-between items-center">
              {q}
              <span className="text-slate-500 group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <p className="px-4 pb-3 text-sm text-slate-400">{a}</p>
          </details>
        ))}
      </Section>
    </div>
  );
}
