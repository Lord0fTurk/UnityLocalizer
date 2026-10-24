---
version: 3.0
name: Universal Multi-Theme Desktop UI & Safe-Refactor Specification
description: >
  Dilden, projeden ve UI motorundan (QML / PySide6 / PyQt6 / CSS) bağımsız masaüstü
  tasarım sistemi. 3 ana tema modunu (Obsidian, Daylight, Cyber Neon), 4 proje vurgu
  paletini (Accent Presets) ve AI ajanlarının mevcut kodu bozmasını engelleyen
  "Sıfır-Kırılma (Zero-Breakage)" mimari kurallarını içerir.
---

# DESIGN.md — Evrensel Masaüstü Tasarım ve Güvenli Refactor Sistemi

Bu belge, projedeki tüm kullanıcı arayüzü bileşenlerinin görsel dilini, renk katmanlarını ve kod
entegrasyon kurallarını tanımlar. Yapay zeka ajanları arayüz üretirken veya mevcut ekranları
güncellerken bu belgedeki kurallara **istisnasız** uymak zorundadır.

---

## 1. Proje Vurgu Paletleri (Accent Presets)

*(Ajan Notu: Her proje kendi kimliğine uygun tek bir `Accent Preset` seçer. Kullanıcı temayı Siyah, Beyaz veya Neon yapsa bile seçilen projenin ana vurgu rengi korunur.)*

* **Preset A — Cyan / Teal (Varsayılan / Modern Utility):**
  * `accentSolid`: `#06B6D4` | `accentHover`: `#22D3EE` | `accentContrastText`: `#06090E`
  * `accentRgb`: `6, 182, 212`
* **Preset B — Emerald / Mint (Veri / Sistem / Enjeksiyon):**
  * `accentSolid`: `#10B981` | `accentHover`: `#34D399` | `accentContrastText`: `#050A08`
  * `accentRgb`: `16, 185, 129`
* **Preset C — Indigo / Violet (Derin / Geliştirici / Motor):**
  * `accentSolid`: `#6366F1` | `accentHover`: `#818CF8` | `accentContrastText`: `#FFFFFF`
  * `accentRgb`: `99, 102, 241`
* **Preset D — Amber / Orange (Endüstriyel / Araç Kutusu):**
  * `accentSolid`: `#F59E0B` | `accentHover`: `#FBBF24` | `accentContrastText`: `#090602`
  * `accentRgb`: `245, 158, 11`

### Anlamsal Durum Renkleri (Semantic Status Tokens)

* **Success (Aktif / Hazır / Önerilen):**
  * `statusSuccess`: `#10B981` | `statusSuccessSubtle`: `rgba(16, 185, 129, 0.14)` | `statusSuccessBorder`: `rgba(16, 185, 129, 0.40)`
* **Warning (Uyarı / Bekleme):**
  * `statusWarning`: `#F59E0B` | `statusWarningSubtle`: `rgba(245, 158, 11, 0.14)` | `statusWarningBorder`: `rgba(245, 158, 11, 0.40)`
* **Danger (Hata / Kritik / Destek):**
  * `statusDanger`: `#F43F5E` | `statusDangerSubtle`: `rgba(244, 63, 94, 0.14)` | `statusDangerBorder`: `rgba(244, 63, 94, 0.40)`
* **Info (Bilgi Kutusu / Konfigürasyon Özeti):**
  * `statusInfo`: `#38BDF8` | `statusInfoSubtle`: `rgba(56, 189, 248, 0.12)` | `statusInfoBorder`: `rgba(56, 189, 248, 0.35)`

---

## 2. Üçlü Tema Token Matrisi (3-Theme Token Matrix)

Tüm token isimleri QML, JavaScript ve Python uyumluluğu için **`camelCase`** standardındadır (CSS/QSS kullanılıyorsa `--kebab-case` karşılığına dönüştürülür). Hiçbir bileşende sabit hex kodu (`#000000`, `#FFFFFF` vb.) kullanılamaz:

| Token Adı (`camelCase`) | 1. Obsidian (Varsayılan Siyah) | 2. Daylight (Yumuşak Beyaz) | 3. Cyber Neon (Parlak Oyuncu) |
| :--- | :--- | :--- | :--- |
| **`canvas`** *(Pencere Zemini)* | `#090D14` | `#F1F5F9` *(Buz grisi)* | `#060911` *(Derin uzay siyahı)* |
| **`surfaceSidebar`** *(Yan Panel)* | `#0C111A` | `#E2E8F0` | `#090E1A` |
| **`surfaceCard`** *(Kart Zemini)* | `#111723` | `#FFFFFF` *(Saf beyaz)* | `#0D1322` |
| **`surfaceControl`** *(Input/Buton)*| `#171F2E` | `#F8FAFC` | `#09111E` |
| **`surfaceHover`** *(Hover Zemini)* | `#1E293B` | `#E2E8F0` | `#132038` |
| **`surfaceSubtle`** *(Bilgi Barı)* | `#141C2B` | `#F8FAFC` | `#0B1526` |
| **`borderCard`** *(Kart Sınırı)* | `#1E2636` *(1px nötr)* | `#CBD5E1` *(1px ince gri)* | `rgba(accentRgb, 0.25)` |
| **`borderControl`** *(Kontrol Sınırı)*| `#263042` *(1px nötr)* | `#94A3B8` *(1px net gri)* | `rgba(accentRgb, 0.55)` |
| **`borderFocus`** *(Aktif/Focus)* | `accentSolid` *(1px)* | `accentSolid` *(1.5px)* | `accentHover` *(2px + Glow)* |
| **`textPrimary`** *(Ana Başlık/Metin)*| `#F1F5F9` | `#0F172A` *(Koyu lacivert)*| `#F8FAFC` |
| **`textSecondary`** *(Alt Açıklama)* | `#94A3B8` | `#475569` | `#94A3B8` |
| **`textMuted`** *(Pasif/Etiket)* | `#64748B` | `#64748B` | `#52637A` |
| **`accentSubtle`** *(Seçili Dolgu)* | `rgba(accentRgb, 0.12)` | `rgba(accentRgb, 0.15)` | `rgba(accentRgb, 0.18)` |
| **`accentBorder`** *(Seçili Sınır)* | `rgba(accentRgb, 0.45)` | `rgba(accentRgb, 0.55)` | `rgba(accentRgb, 0.80)` |
| **`effectGlow`** *(Dış Parlama)* | `none` *(Kapalı)* | `0 2px 6px rgba(15,23,42,0.06)`| `0 0 12px rgba(accentRgb, 0.25)` |

---

## 3. Evrensel Bileşen Arketipleri (Component Archetypes)

Bileşenler içerdikleri metne veya dile (i18n) göre değil, **yapısal rollerine** göre stillendirilir:

### 3.1. Sol Navigasyon Öğesi (`NavItem`)

* **Pasif:** Zemin `transparent`, sınır `none`, metin/ikon `textSecondary`.
* **Hover:** Zemin `surfaceHover` (%50 saydam), metin `textPrimary`.
* **Aktif (Seçili):**
  * *Obsidian & Daylight:* Dış çerçeve **yoktur** (`border.width: 0`). Zemin `accentSubtle`, sol kenarda `3px` genişliğinde dikey `accentSolid` çubuk, metin `textPrimary` (`SemiBold`).
  * *Cyber Neon:* Zemin `accentSubtle`, dış çerçeve `1.5px solid accentSolid`, sol kenarda parlak çubuk.

### 3.2. Ana Eylem Butonu (`PrimaryCTA` / Hero Button)

* **Geometri:** Yükseklik `42px - 44px`, köşe yuvarlaklığı **sabit `6px`** (kesinlikle yuvarlak hap yapılmaz).
* **Obsidian & Daylight:** Zemin tam doygun `accentSolid`, metin yüksek kontrastlı `accentContrastText` (`Bold 700`), çerçeve `none`.
* **Cyber Neon:** Zemin `rgba(accentRgb, 0.30)`, çerçeve `1.5px solid accentHover`, metin `textPrimary`.

### 3.3. İkincil ve Araç Butonları (`SecondaryButton` / `ActionButton`)

* **Geometri:** Yükseklik `36px - 38px`, köşe yuvarlaklığı **sabit `6px`**, yatay iç boşluk `14px`.
* **Obsidian & Daylight:** Zemin `surfaceControl`, çerçeve `1px solid borderControl`, metin `textPrimary`. Hover durumunda zemin `surfaceHover` olur.
* **Cyber Neon:** Zemin `surfaceControl`, çerçeve `1px solid borderControl` (`rgba(accentRgb, 0.55)`), metin `textPrimary`.

### 3.4. Seçili Mod / Durum Butonları (`SegmentedToggle` / `SelectedOption`)

* **Aktif veya seçili olan seçenek:** Zemin `accentSubtle`, çerçeve `1px solid accentBorder`, metin `accentHover` (Daylight temada `accentSolid`), ağırlık `600`.
* **Pasif seçenekler:** `SecondaryButton` ile birebir aynıdır; asla zifiri siyah (`#000000`) veya görünmez bırakılmaz.

### 3.5. Bilgi Çubukları ve Özeti (`InfoBanner` / `ConfigSummaryBar`)

*(Örn: Aktif ayar özeti veya bilgi satırları)*

* **KESİNLİKLE** karanlık temalarda `#FFFFFF` (saf beyaz) zemin kullanılmaz!
* **Zemin:** `surfaceSubtle` veya `statusInfoSubtle`.
* **Çerçeve:** `1px solid borderCard` (veya sol kenarda `3px solid accentSolid`).
* **Metin:** Etiket kısmı `textSecondary`, değer kısmı `textPrimary` (`SemiBold`), köşe yuvarlaklığı `6px`.

### 3.6. Durum Rozetleri ve Etiketler (`StatusBadge` / `CountPill`)

*(Örn: Kartların sağ üst köşesindeki durum, öneri veya sayaç rozetleri)*

* **Geometri:** Yükseklik `22px - 24px`, yatay padding `8px`, köşe yuvarlaklığı `4px` (veya `6px`).
* **Nötr / Sayaç Rozeti:** Zemin `surfaceControl`, çerçeve `1px solid borderControl`, metin `textSecondary` (`11px`, `Medium`). Asla saf beyaz zemin üzerine siyah yazı yapılmaz.
* **Aktif / Pozitif Rozet:** Zemin `statusSuccessSubtle`, çerçeve `1px solid statusSuccessBorder`, metin `statusSuccess` (`#10B981` — parlak ve okunaklı).
* **Önerilen / Vurgu Rozeti:** Zemin `accentSubtle`, çerçeve `1px solid accentBorder`, metin `accentHover` (Daylight temada `accentSolid`).

### 3.7. Metin Girişleri ve Seçim Kutuları (`TextInput`, `PathField`, `ComboBox`)

* **Geometri:** Yükseklik `38px`, köşe yuvarlaklığı `6px`.
* **Normal Durum:** Zemin `surfaceControl`, çerçeve `1px solid borderControl`, metin `textPrimary`, placeholder `textMuted`.
* **Focus (Odaklanmış) Durum:** Çerçeve `1px solid borderFocus`.

---

## 4. Tipografi ve Yerleşim Sabitleri (Typography & Layout Invariants)

* **Sayfa Başlığı (`PageHeader`):** `22px`, `SemiBold (600)`, renk **her zaman `textPrimary`**. Alt açıklama (`PageSubtitle`) `13px`, renk **`textSecondary`**.
* **Kart Başlığı (`CardHeader`):** `15px`, `SemiBold (600)`, renk **her zaman `textPrimary`**. Yanındaki ikon metinle aynı hizada (`16px - 18px`) olmalıdır.
* **Köşe Yuvarlaklığı Kilidi (Strict Radius Scale):**
  * Ana Kartlar (`SectionCard`): `10px`
  * Tüm Butonlar, Inputlar, Bilgi Çubukları: **`6px`** *(20px+ yuvarlak sosis/hap buton kullanımı yasaktır)*
  * Küçük Rozetler ve Dil Kısayolları: `4px`

---

## 5. AI Ajanları İçin Mimari Koruma ve Sıfır-Kırılma Kuralları (CRITICAL GUARDRAILS)

Arayüz kodunu yazarken veya mevcut bir projeyi güncellerken aşağıdaki **7 teknik kuralın** ihlal edilmesi görsel çökmelere yol açacağı için kesinlikle yasaktır:

### Kural 1: Sıfır-Kırılma ve Geriye Dönük Alias Zorunluluğu (Zero-Breakage Protocol)

Mevcut bir projede `Theme.qml` (veya merkezi stil dosyası) güncellenirken, projedeki diğer ekranların kullandığı **eski değişken isimleri (property/token) ASLA SİLİNMEZ**.

* Önce tüm proje dosyalarında (`*.qml`, `*.py`, `*.qss`) `Theme.` araması yaparak kullanılan tüm mevcut renk özelliklerini tespit et.
* Yeni `camelCase` tokenları (`canvas`, `surfaceCard`, `textPrimary` vb.) ekledikten sonra, eski değişken isimlerini yeni tokenlara bağlayan birer **alias (takma ad)** olarak dosyada tut:
  * Örnek: `readonly property color bgDark: canvas`
  * Örnek: `readonly property color cardBg: surfaceCard`
  * Örnek: `readonly property color textColor: textPrimary`
  * Örnek: `readonly property color subTextColor: textSecondary`
* Hiçbir QML bileşenine `undefined` renk gitmesine izin verme (QML'de `undefined` renk metinleri `#000000` siyaha, kutuları `#FFFFFF` beyaza çevirerek arayüzü bozar).

### Kural 2: Tam Kapsamlı Sayfa Denetimi (Full-Page Audit)

Sadece ana pencereyi veya sol menüyü (`Sidebar`) güncelleyip bırakma. Projedeki **tüm alt sayfaları, sekmeleri, diyalog pencerelerini ve özel bileşenleri** tek tek tarayarak sabit (hardcoded) kalmış `#000000`, `#FFFFFF` veya eski tema referanslarını yeni token sistemine geçir.

### Kural 3: Kapsayıcı Saydamlık Tuzağı (`opacity` vs `Qt.rgba`)

İçinde metin (`Text` / `Label`) veya ikon barındıran hiçbir arka plan kutusuna (`Rectangle`) saydamlık vermek için `opacity: 0.15` gibi değerler **KULLANMA** (bu işlem içindeki yazıyı da saydamlaştırıp okunmaz hale getirir). Saydamlığı her zaman yalnızca `color` özelliğine `Qt.rgba(r, g, b, a)` veya `#AARRGGBB` formatında uygula.

### Kural 4: Native Kontrol Ezme Kuralı (`background` + `contentItem` Zorunluluğu)

QML `QtQuick.Controls` (`Button`, `ComboBox`, `TextField`, `TabButton`) bileşenlerinde özel `background: Rectangle {}` tanımlandığında, işletim sisteminin varsayılan siyah metin renginin devreye girmemesi için **`contentItem`** (metin rengi `textPrimary` veya `accentContrastText`) da **mutlaka açıkça tanımlanmalıdır**.

### Kural 5: Qt Mnemonic (`&`) Karakter Koruması

Qt/QML `Button`, `AbstractButton` ve `Label` bileşenleri metin içindeki tek `&` karakterini klavye kısayolu (alt çizgi `_`) olarak yorumlar (Örn: `"Apply & Inject"` -> `"Apply _Inject"`). Bunu engellemek için:

* Metin içinde `&` geçiyorsa çift ampersand (`"Apply && Inject"`) kullan veya
* Özel `Button` bileşeninin `contentItem` kısmında standart `Text` bileşeni kullanarak kısayol ayrıştırmasını devre dışı bırak.

### Kural 6: Kör Edici Beyaz ve Görünmez Siyah Yasağı (Contrast Lock)

* **Obsidian** ve **Cyber Neon** temalarında hiçbir kart, rozet (`Badge`), bilgi kutusu (`Banner`) veya buton arka planı `#FFFFFF` (saf beyaz) veya `#000000` (saf siyah) olamaz.
* Koyu arka plan (`#090D14` / `#111723`) üzerindeki hiçbir başlık veya açıklama metni koyu gri/siyah (`#000000` - `#333333`) olamaz; başlıklar her zaman `textPrimary` (`#F1F5F9`), alt metinler `textSecondary` (`#94A3B8`) olmalıdır.

### Kural 7: Çoklu Dil (i18n) ve Metin Bağımsızlığı

Stil kuralları bileşenin içindeki metne (örn: `if (text === "Recommended")`) bağlanamaz; bileşen özelliğine (`property string variant: "primary" | "secondary" | "badge"`) bağlanır. Farklı dillerde metin uzunlukları değişeceği için butonlarda sabit `width` yerine `implicitWidth + padding` kullanılır.