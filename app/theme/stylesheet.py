"""
Compressly — Claude-inspired dark theme.

Visual language:
  • Very dark warm gray background (#1c1c1c), NOT pure black
  • Surfaces are just 1-2 shades lighter — no heavy card borders
  • Ultra-thin left sidebar with icon-only buttons
  • Salmon/terracotta accent (#d4956a) matching Claude's star logo
  • Clean Inter/Segoe UI typography, generous line-height
  • Rounded inputs with subtle borders
  • No aggressive shadows or gradients

The single most important QSS rule:
  * {{ background-color: transparent; }}
  This makes EVERY widget transparent by default.
  Only named containers (#surface, #sidebar, etc.) paint themselves.
  This eliminates ALL black strips on list items and nested widgets.
"""

from __future__ import annotations

DARK = {
    "bg":           "#1a1a1a",
    "bg2":          "#202020",
    "surface":      "#282828",
    "surface2":     "#2e2e2e",
    "surface3":     "#363636",
    "border":       "rgba(255,255,255,0.10)",
    "border2":      "rgba(255,255,255,0.18)",
    "text":         "#f0ede8",
    "text2":        "#b0ada6",
    "text3":        "#787470",
    "accent":       "#d4956a",
    "accent2":      "#e0a87c",
    "accentBg":     "rgba(212,149,106,0.14)",
    "accentBorder": "rgba(212,149,106,0.35)",
    "green":        "#6ab87e",
    "red":          "#d07060",
    "scrollbar":    "rgba(255,255,255,0.10)",
    "scrollHover":  "rgba(255,255,255,0.20)",
    "inputBg":      "#2e2e2e",
    "inputBorder":  "rgba(255,255,255,0.14)",
    "rowBg":        "rgba(255,255,255,0.04)",
    "rowHover":     "rgba(255,255,255,0.07)",
    "rowBorder":    "rgba(255,255,255,0.08)",
    "dropBorder":   "rgba(255,255,255,0.14)",
    "dropHoverBg":  "rgba(212,149,106,0.10)",
    "dropHoverBorder": "#d4956a",
    "btnBg":        "rgba(255,255,255,0.08)",
    "btnHover":     "rgba(255,255,255,0.13)",
    "btnBorder":    "rgba(255,255,255,0.13)",
    "grooveBg":     "rgba(255,255,255,0.13)",
    "checkBg":      "rgba(255,255,255,0.08)",
    "toastBg":      "#323232",
    "sidebarBg":    "#1a1a1a",
    "sidebarBorder":"rgba(255,255,255,0.08)",
    "navActive":    "rgba(255,255,255,0.10)",
    "navHover":     "rgba(255,255,255,0.06)",
    "navText":      "rgba(255,255,255,0.60)",
    "navTextHover": "rgba(255,255,255,0.90)",
    "navTextActive":"#d4956a",
    "creditColor":  "rgba(255,255,255,0.28)",
    "chipChecked":  "#d4956a",
    "chipText":     "#f0ede8",
}

LIGHT = {
    "bg":           "#fafafa",
    "bg2":          "#f4f4f4",
    "surface":      "#ffffff",
    "surface2":     "#f7f7f7",
    "surface3":     "#eeeeee",
    "border":       "rgba(0,0,0,0.07)",
    "border2":      "rgba(0,0,0,0.13)",
    "text":         "#1a1a1a",
    "text2":        "#5a5a5a",
    "text3":        "#909090",
    "accent":       "#b5714a",
    "accent2":      "#c47d55",
    "accentBg":     "rgba(181,113,74,0.10)",
    "accentBorder": "rgba(181,113,74,0.28)",
    "green":        "#3d7a52",
    "red":          "#a04040",
    "scrollbar":    "rgba(0,0,0,0.10)",
    "scrollHover":  "rgba(0,0,0,0.20)",
    "inputBg":      "#f4f4f4",
    "inputBorder":  "rgba(0,0,0,0.12)",
    "rowBg":        "rgba(0,0,0,0.025)",
    "rowHover":     "rgba(0,0,0,0.045)",
    "rowBorder":    "rgba(0,0,0,0.07)",
    "dropBorder":   "rgba(0,0,0,0.14)",
    "dropHoverBg":  "rgba(181,113,74,0.07)",
    "dropHoverBorder": "#b5714a",
    "btnBg":        "rgba(0,0,0,0.04)",
    "btnHover":     "rgba(0,0,0,0.08)",
    "btnBorder":    "rgba(0,0,0,0.10)",
    "grooveBg":     "rgba(0,0,0,0.10)",
    "checkBg":      "rgba(0,0,0,0.05)",
    "toastBg":      "#ffffff",
    "sidebarBg":    "#f4f4f4",
    "sidebarBorder":"rgba(0,0,0,0.07)",
    "navActive":    "rgba(0,0,0,0.07)",
    "navHover":     "rgba(0,0,0,0.04)",
    "navText":      "rgba(0,0,0,0.50)",
    "navTextHover": "rgba(0,0,0,0.80)",
    "navTextActive":"#b5714a",
    "creditColor":  "rgba(0,0,0,0.30)",
    "chipChecked":  "#b5714a",
    "chipText":     "#1a1a1a",
}

COLORS = DARK


def build_stylesheet(theme: str = "dark") -> str:
    c = LIGHT if theme == "light" else DARK
    return _QSS.format(**c)


_QSS = """
/* ═══════════════════════════════════════════════════════════════════════
   GLOBAL RESET — every widget transparent by default.
   This is the ONLY reliable way to prevent black strips.
═══════════════════════════════════════════════════════════════════════ */
* {{
    background-color: transparent;
    color: {text};
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
    selection-background-color: {accent};
    selection-color: white;
}}

/* ═══════════════════════════════════════════════════════════════════════
   WINDOW — the only solid background
═══════════════════════════════════════════════════════════════════════ */
QMainWindow, QDialog {{
    background-color: transparent;
}}
/* Root container — background painted by _RoundedContainer.paintEvent */
QWidget#root {{
    background-color: transparent;
}}

/* ═══════════════════════════════════════════════════════════════════════
   SCROLL AREAS — must stay transparent
═══════════════════════════════════════════════════════════════════════ */
QScrollArea,
QScrollArea > QWidget,
QScrollArea > QWidget > QWidget,
QAbstractScrollArea::viewport {{
    background-color: transparent;
    border: none;
}}

QStackedWidget {{
    background-color: transparent;
    border: none;
}}

/* ═══════════════════════════════════════════════════════════════════════
   CUSTOM TITLE BAR
═══════════════════════════════════════════════════════════════════════ */
QWidget#titleBar {{
    background-color: {bg};
    border-bottom: 1px solid {sidebarBorder};
}}

/* Window control buttons (─ □ ✕) */
QPushButton#winBtn {{
    background-color: transparent;
    border: none;
    border-radius: 0;
    color: {text3};
    font-size: 13px;
    padding: 0;
    min-width: 38px;
    max-width: 38px;
    min-height: 38px;
    max-height: 38px;
}}
QPushButton#winBtn:hover {{
    background-color: {btnHover};
    color: {text};
}}
/* Close button gets a red tint on hover */
QPushButton#winBtn[closeBtn="true"]:hover {{
    background-color: rgba(192,57,43,0.75);
    color: white;
}}

/* ═══════════════════════════════════════════════════════════════════════
   NAMED SURFACES
═══════════════════════════════════════════════════════════════════════ */
QFrame#sidebar {{
    background-color: {sidebarBg};
    border-right: 1px solid {sidebarBorder};
    border-radius: 0;
}}

/* Nav row hover — the whole row, not just the button */
QWidget#navRow:hover {{
    background-color: {navHover};
    border-radius: 8px;
}}
QFrame#topbar {{
    background-color: transparent;
    border-bottom: 1px solid {border};
    border-radius: 0;
}}
QFrame#surface {{
    background-color: {surface};
    border-radius: 12px;
}}
QWidget#surface {{
    background-color: {surface};
    border-radius: 12px;
}}
QFrame#surfaceFlat {{
    background-color: {surface};
    border-radius: 8px;
}}
QFrame#dropZone {{
    background-color: {rowBg};
    border: 1.5px dashed {dropBorder};
    border-radius: 14px;
}}
QFrame#dropZone[hover="true"] {{
    background-color: {dropHoverBg};
    border: 1.5px dashed {dropHoverBorder};
}}

/* Format chips on the empty state */
QLabel#formatChip {{
    color: {text3};
    font-size: 11px;
    font-weight: 500;
    background-color: {rowBg};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 3px 8px;
}}

/* Queue row — needs WA_StyledBackground + this rule */
QWidget#queueRow {{
    background-color: {rowBg};
    border: 1px solid {rowBorder};
    border-radius: 10px;
}}
QWidget#queueRow:hover {{
    background-color: {rowHover};
}}

/* ═══════════════════════════════════════════════════════════════════════
   LIST WIDGET — items transparent; row widget paints itself
═══════════════════════════════════════════════════════════════════════ */
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 0;
}}
QListWidget::item {{
    background-color: transparent;
    border: none;
    padding: 0;
    margin: 0 0 3px 0;
}}
QListWidget::item:selected,
QListWidget::item:hover {{
    background-color: transparent;
    border: none;
}}

/* ═══════════════════════════════════════════════════════════════════════
   TOOLTIP
═══════════════════════════════════════════════════════════════════════ */
QToolTip {{
    background-color: {surface3};
    color: {text};
    border: 1px solid {border2};
    padding: 5px 9px;
    border-radius: 7px;
    font-size: 12px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   TYPOGRAPHY
═══════════════════════════════════════════════════════════════════════ */
QLabel#h1 {{
    font-size: 28px;
    font-weight: 500;
    color: {text};
    letter-spacing: -0.5px;
}}
QLabel#h2 {{
    font-size: 18px;
    font-weight: 500;
    color: {text};
}}
QLabel#h3 {{
    font-size: 14px;
    font-weight: 500;
    color: {text};
}}
QLabel#eyebrow {{
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    color: {text3};
    text-transform: uppercase;
}}
QLabel#muted {{
    color: {text2};
    font-size: 13px;
}}
QLabel#dim {{
    color: {text3};
    font-size: 11px;
}}
QLabel#stat {{
    font-size: 22px;
    font-weight: 600;
    color: {text};
}}
QLabel#accent {{
    color: {accent};
}}
QLabel#success {{
    color: {green};
}}
QLabel#danger {{
    color: {red};
}}

/* ═══════════════════════════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════════════════════════ */
QPushButton {{
    background-color: {btnBg};
    color: {text};
    border: 1px solid {btnBorder};
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 400;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {btnHover};
    border-color: {border2};
}}
QPushButton:pressed {{
    background-color: {surface3};
}}
QPushButton:disabled {{
    color: {text3};
    background-color: transparent;
    border-color: {border};
}}

QPushButton[variant="primary"] {{
    background-color: {accent};
    color: white;
    border: 1px solid transparent;
    font-weight: 500;
}}
QPushButton[variant="primary"]:hover {{
    background-color: {accent2};
}}
QPushButton[variant="primary"]:disabled {{
    background-color: {accentBg};
    color: {text3};
    border: 1px solid {accentBorder};
}}

QPushButton[variant="ghost"] {{
    background-color: transparent;
    border: 1px solid transparent;
    color: {text2};
    padding: 6px 12px;
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {btnBg};
    color: {text};
}}

QPushButton[variant="danger"] {{
    background-color: transparent;
    color: {red};
    border: 1px solid rgba(192,103,90,0.25);
}}
QPushButton[variant="danger"]:hover {{
    background-color: rgba(192,103,90,0.10);
}}

/* Sidebar nav row buttons — full-width, entire row is clickable */
QPushButton#navRow {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    text-align: left;
    padding: 0;
}}
QPushButton#navRow:hover {{
    background-color: {navHover};
}}
QPushButton#navRow:checked {{
    background-color: {navActive};
}}

/* Sidebar toggle chevron */
QPushButton#sidebarToggle {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: {text3};
    font-size: 14px;
    padding: 0;
    min-width: 28px; max-width: 28px;
    min-height: 28px; max-height: 28px;
}}
QPushButton#sidebarToggle:hover {{
    background-color: {navHover};
    color: {text2};
}}

/* Sidebar icon-only buttons (toggle chevron) */
QPushButton#navBtn {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: {text2};
    font-size: 17px;
    padding: 0;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
}}
QPushButton#navBtn:hover {{
    background-color: {navHover};
    color: {text};
}}
QPushButton#navBtn:checked {{
    background-color: {navActive};
    color: {accent};
}}

/* Chip toggles */
QPushButton#chip {{
    background-color: {btnBg};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 12px;
    color: {text2};
    font-size: 12px;
    font-weight: 400;
}}
QPushButton#chip:hover {{
    background-color: {btnHover};
    color: {text};
}}
QPushButton#chip:checked {{
    background-color: {chipChecked};
    color: white;
    border: 1px solid transparent;
    font-weight: 500;
}}

/* ═══════════════════════════════════════════════════════════════════════
   INPUTS
═══════════════════════════════════════════════════════════════════════ */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {inputBg};
    border: 1px solid {inputBorder};
    border-radius: 8px;
    padding: 7px 10px;
    color: {text};
    font-size: 13px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {accent};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0; height: 0; border: none; background: transparent;
}}
QComboBox::drop-down {{
    border: none; width: 22px; background: transparent;
}}
QComboBox QAbstractItemView {{
    background-color: {surface3};
    border: 1px solid {border2};
    border-radius: 8px;
    color: {text};
    padding: 4px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   SLIDERS
═══════════════════════════════════════════════════════════════════════ */
QSlider {{ background: transparent; }}
QSlider::groove:horizontal {{
    height: 4px;
    background: {grooveBg};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {accent};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {text};
    border: 2px solid {accent};
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: white;
    width: 16px; height: 16px;
    margin: -6px 0;
    border-radius: 9px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   PROGRESS BAR
═══════════════════════════════════════════════════════════════════════ */
QProgressBar {{
    background-color: {grooveBg};
    border: none;
    border-radius: 3px;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 3px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   SCROLLBARS
═══════════════════════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0; border: none;
}}
QScrollBar::handle:vertical {{
    background: {scrollbar}; border-radius: 3px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {scrollHover}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0; background: transparent; border: none;
}}
QScrollBar:horizontal {{
    background: transparent; height: 6px; margin: 0; border: none;
}}
QScrollBar::handle:horizontal {{
    background: {scrollbar}; border-radius: 3px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {scrollHover}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0; background: transparent; border: none;
}}

/* ═══════════════════════════════════════════════════════════════════════
   CHECKBOX
═══════════════════════════════════════════════════════════════════════ */
QCheckBox {{ spacing: 8px; color: {text}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid {border2};
    background-color: {checkBg};
}}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

/* ═══════════════════════════════════════════════════════════════════════
   TOAST
═══════════════════════════════════════════════════════════════════════ */
QFrame#toast {{
    background-color: {toastBg};
    border: 1px solid {border2};
    border-radius: 10px;
}}
QFrame#toast[level="success"] {{ border: 1px solid rgba(90,158,111,0.40); }}
QFrame#toast[level="error"]   {{ border: 1px solid rgba(192,103,90,0.40); }}
"""
