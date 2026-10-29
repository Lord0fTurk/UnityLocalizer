pragma Singleton
import QtQuick

QtObject {
    id: theme

    // ── Tema ve Vurgu Seçimleri ─────────────────────────────────────
    // appBackend.settings üzerinden reaktif bağlanır; yoksa varsayılanlar devrededir.
    readonly property string mode: {
        var m = (appBackend && appBackend.settings && appBackend.settings.theme_mode) 
                ? appBackend.settings.theme_mode : "obsidian";
        return (m === "daylight" || m === "cyber_neon") ? m : "obsidian";
    }

    readonly property string preset: {
        var p = (appBackend && appBackend.settings && appBackend.settings.accent_preset)
                ? appBackend.settings.accent_preset : "cyan";
        return (p === "emerald" || p === "indigo" || p === "amber") ? p : "cyan";
    }

    readonly property bool isDark: mode !== "daylight"
    readonly property bool isNeon: mode === "cyber_neon"

    // ── 1. Proje Vurgu Paletleri (Accent Presets - DESIGN.md §1) ─────
    // Daylight uses deeper tones so accent text and icons keep 4.5:1 on white surfaces
    // (the bright dark-theme tones measure only 2.1-2.5:1 there).
    readonly property color accentSolid: {
        switch (preset) {
            case "emerald": return isDark ? "#10B981" : "#047857";
            case "indigo":  return isDark ? "#5558E8" : "#4F46E5";
            case "amber":   return isDark ? "#F59E0B" : "#A04A07";
            case "cyan":
            default:        return isDark ? "#06B6D4" : "#0F6F86";
        }
    }

    readonly property color accentHover: {
        switch (preset) {
            case "emerald": return isDark ? "#34D399" : "#065F46";
            case "indigo":  return isDark ? "#818CF8" : "#4338CA";
            case "amber":   return isDark ? "#FBBF24" : "#8A3F06";
            case "cyan":
            default:        return isDark ? "#22D3EE" : "#155E75";
        }
    }

    readonly property color accentContrastText: {
        if (!isDark) return "#FFFFFF";
        switch (preset) {
            case "emerald": return "#050A08";
            case "indigo":  return "#FFFFFF";
            case "amber":   return "#090602";
            case "cyan":
            default:        return "#06090E";
        }
    }

    readonly property color accentRgb: {
        switch (preset) {
            case "emerald": return Qt.rgba(16/255, 185/255, 129/255, 1);
            case "indigo":  return Qt.rgba(99/255, 102/255, 241/255, 1);
            case "amber":   return Qt.rgba(245/255, 158/255, 11/255, 1);
            case "cyan":
            default:        return Qt.rgba(6/255, 182/255, 212/255, 1);
        }
    }

    // ── Anlamsal Durum Renkleri (Semantic Status Tokens - DESIGN.md §1) ──
    // Success (Aktif / Hazır / Önerilen)
    // Status colors double as text colors, so Daylight gets deeper tones (>= 4.5:1 on white).
    readonly property color statusSuccess:       isDark ? "#10B981" : "#047857"
    readonly property color statusSuccessSubtle: Qt.rgba(16/255, 185/255, 129/255, 0.14)
    readonly property color statusSuccessBorder: Qt.rgba(16/255, 185/255, 129/255, 0.40)

    // Warning (Uyarı / Bekleme)
    readonly property color statusWarning:       isDark ? "#F59E0B" : "#A04A07"
    readonly property color statusWarningSubtle: Qt.rgba(245/255, 158/255, 11/255, 0.14)
    readonly property color statusWarningBorder: Qt.rgba(245/255, 158/255, 11/255, 0.40)

    // Danger (Hata / Kritik / Destek)
    readonly property color statusDanger:        isDark ? "#F43F5E" : "#BE123C"
    readonly property color statusDangerSubtle:  Qt.rgba(244/255, 63/255, 94/255, 0.14)
    readonly property color statusDangerBorder:  Qt.rgba(244/255, 63/255, 94/255, 0.40)

    // Info (Bilgi Kutusu / Konfigürasyon Özeti)
    readonly property color statusInfo:          isDark ? "#38BDF8" : "#0369A1"
    readonly property color statusInfoSubtle:    Qt.rgba(56/255, 189/255, 248/255, 0.12)
    readonly property color statusInfoBorder:    Qt.rgba(56/255, 189/255, 248/255, 0.35)

    // ── 2. Üçlü Tema Token Matrisi (DESIGN.md §2) ───────────────────

    // canvas (Pencere Zemini)
    readonly property color canvas: {
        if (mode === "daylight") return "#F1F5F9";
        if (mode === "cyber_neon") return "#060911";
        return "#090D14";
    }

    // surfaceSidebar (Yan Panel)
    readonly property color surfaceSidebar: {
        if (mode === "daylight") return "#E2E8F0";
        if (mode === "cyber_neon") return "#090E1A";
        return "#0C111A";
    }

    // surfaceCard (Kart Zemini)
    readonly property color surfaceCard: {
        if (mode === "daylight") return "#FFFFFF";
        if (mode === "cyber_neon") return "#0D1322";
        return "#111723";
    }

    // surfaceControl (Input / Buton)
    readonly property color surfaceControl: {
        if (mode === "daylight") return "#F8FAFC";
        if (mode === "cyber_neon") return "#09111E";
        return "#171F2E";
    }

    // surfaceHover (Hover Zemini)
    readonly property color surfaceHover: {
        if (mode === "daylight") return "#E2E8F0";
        if (mode === "cyber_neon") return "#132038";
        return "#1E293B";
    }

    // surfaceSubtle (Bilgi Barı / Özet Satırı - KESİNLİKLE Saf Beyaz Kullanılmaz)
    readonly property color surfaceSubtle: {
        if (mode === "daylight") return "#F8FAFC";
        if (mode === "cyber_neon") return "#0B1526";
        return "#141C2B";
    }

    // borderCard (Kart Sınırı)
    readonly property color borderCard: {
        if (mode === "daylight") return "#CBD5E1";
        if (mode === "cyber_neon") return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, 0.25);
        return "#1E2636";
    }

    // borderControl (Kontrol Sınırı)
    readonly property color borderControl: {
        // Control boundaries need 3:1 against their surroundings (WCAG 1.4.11).
        if (mode === "daylight") return "#6B7C93";
        if (mode === "cyber_neon") return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, 0.55);
        return "#5A6A84";
    }

    // borderFocus (Aktif / Focus)
    readonly property color borderFocus: {
        if (mode === "cyber_neon") return accentHover;
        return accentSolid;
    }

    // textPrimary (Ana Başlık / Metin)
    readonly property color textPrimary: {
        if (mode === "daylight") return "#0F172A";
        if (mode === "cyber_neon") return "#F8FAFC";
        return "#F1F5F9";
    }

    // textSecondary (Alt Açıklama)
    readonly property color textSecondary: {
        if (mode === "daylight") return "#475569";
        return "#94A3B8";
    }

    // textMuted (Pasif / Etiket)
    readonly property color textMuted: {
        if (mode === "daylight") return "#526074";
        if (mode === "cyber_neon") return "#8494AD";
        return "#8190A5";
    }

    // accentSubtle (Seçili Dolgu)
    readonly property color accentSubtle: {
        if (mode === "daylight") return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, 0.16);
        if (mode === "cyber_neon") return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, 0.22);
        return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, 0.18);
    }

    // accentBorder (Seçili Sınır)
    readonly property color accentBorder: {
        if (mode === "daylight") return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, 0.55);
        if (mode === "cyber_neon") return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, 0.80);
        return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, 0.45);
    }

    // effectGlow (Cyber Neon dış parlama rengi - DESIGN.md §2)
    readonly property color glowColor: {
        if (mode === "cyber_neon") return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, 0.35);
        return "transparent";
    }
    readonly property color effectGlow: glowColor

    // Support (Patreon) pink: deeper in Daylight so it stays readable as text.
    readonly property color supportColor: isDark ? "#F472B6" : "#BE185D"
    function supportAlpha(alpha) { return Qt.rgba(244/255, 114/255, 182/255, alpha); }
    function dangerAlpha(alpha)  { return Qt.rgba(244/255, 63/255, 94/255, alpha); }

    // Review status "repaired" (purple) and the surfaces the views used to hard-code.
    readonly property color statusRepaired:        isDark ? "#A855F7" : "#7E22CE"
    readonly property color surfaceDisabled:       isDark ? "#232A3B" : "#CBD5E1"
    readonly property color surfaceDisabledSubtle: isDark ? "#121722" : "#F1F5F9"
    readonly property color surfaceInset:          isDark ? "#080C13" : "#F8FAFC"

    // Swatch colors shown in the accent picker (the dark-theme tone of each preset).
    readonly property var presetSwatches: ({ cyan: "#06B6D4", emerald: "#10B981", indigo: "#5558E8", amber: "#F59E0B" })

    // ── 4. Köşe Yuvarlaklığı ve Geometri Sabitleri (DESIGN.md §4) ────
    readonly property int radiusCard:    10 // Ana Kartlar
    readonly property int radiusControl: 6  // Tüm Butonlar, Inputlar, Bilgi Çubukları (Kesinlikle hap değil)
    readonly property int radiusBadge:   4  // Rozetler ve Etiketler

    // Geriye dönük uyumluluk için alias
    readonly property int radiusButton:  6

    readonly property int heightPrimaryCTA: 44
    readonly property int heightSecondary:  38
    readonly property int heightInput:      38
    readonly property int heightBadge:      24

    // ── 5. Geriye Dönük Uyumluluk Alias'ları (Zero-Breakage - DESIGN.md §5) ──
    readonly property color clrBg:            canvas
    readonly property color bgDark:           canvas
    readonly property color clrSidebar:       surfaceSidebar
    readonly property color clrCard:          surfaceCard
    readonly property color cardBg:           surfaceCard
    readonly property color clrCardHover:     surfaceHover
    readonly property color cardHover:        surfaceHover
    readonly property color clrCardBorder:    borderCard
    readonly property color borderCardCol:    borderCard
    readonly property color clrControl:       surfaceControl
    readonly property color clrInput:         surfaceControl
    readonly property color inputBg:          surfaceControl
    readonly property color clrAccent:        accentSolid
    readonly property color primaryColor:     accentSolid
    readonly property color clrAccent2:       accentHover
    readonly property color clrTxt:           textPrimary
    readonly property color textColor:        textPrimary
    readonly property color clrTxt2:          textSecondary
    readonly property color textSecondaryCol: textSecondary
    readonly property color clrTxtDim:        textMuted
    readonly property color textMutedCol:     textMuted

    // ── Renk Helper Fonksiyonları ───────────────────────────────────
    function accentAlpha(alpha) {
        return Qt.rgba(accentRgb.r, accentRgb.g, accentRgb.b, alpha);
    }

    function rgba(r, g, b, a) {
        return Qt.rgba(r / 255.0, g / 255.0, b / 255.0, a);
    }
}
