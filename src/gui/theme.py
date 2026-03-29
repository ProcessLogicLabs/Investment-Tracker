"""Centralized theme system with dark/light mode support."""

from dataclasses import dataclass
from PyQt6.QtWidgets import QApplication, QGraphicsDropShadowEffect
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPalette, QColor


@dataclass
class ThemePalette:
    """Semantic color palette for the application."""
    # Surfaces
    window: str
    surface: str
    surface_alt: str
    border: str

    # Text
    text_primary: str
    text_secondary: str
    text_disabled: str
    text_on_primary: str

    # Semantic
    positive: str
    negative: str
    accent: str
    warning: str
    muted: str

    # Derived
    positive_bg: str
    negative_bg: str
    accent_bg: str

    # Table
    header_bg: str
    row_hover: str
    selection_bg: str

    # Chart
    chart_bg: str
    chart_grid: str
    chart_text: str

    # Input
    input_bg: str
    input_border: str

    # Chrome
    toolbar_bg: str
    statusbar_bg: str
    shadow: str


LIGHT = ThemePalette(
    window='#f5f5f5',
    surface='#ffffff',
    surface_alt='#f9f9f9',
    border='#e0e0e0',
    text_primary='#212121',
    text_secondary='#666666',
    text_disabled='#9e9e9e',
    text_on_primary='#ffffff',
    positive='#2e7d32',
    negative='#c62828',
    accent='#1976D2',
    warning='#ff9800',
    muted='#757575',
    positive_bg='rgba(46, 125, 50, 15)',
    negative_bg='rgba(198, 40, 40, 15)',
    accent_bg='#e3f2fd',
    header_bg='#1976D2',
    row_hover='#e8f0fe',
    selection_bg='#bbdefb',
    chart_bg='#ffffff',
    chart_grid='#e0e0e0',
    chart_text='#333333',
    input_bg='#ffffff',
    input_border='#cccccc',
    toolbar_bg='#fafafa',
    statusbar_bg='#f0f0f0',
    shadow='rgba(0, 0, 0, 30)',
)

DARK = ThemePalette(
    window='#1e1e1e',
    surface='#2d2d2d',
    surface_alt='#353535',
    border='#444444',
    text_primary='#e0e0e0',
    text_secondary='#aaaaaa',
    text_disabled='#666666',
    text_on_primary='#ffffff',
    positive='#66bb6a',
    negative='#ef5350',
    accent='#42a5f5',
    warning='#ffa726',
    muted='#9e9e9e',
    positive_bg='rgba(102, 187, 106, 20)',
    negative_bg='rgba(239, 83, 80, 20)',
    accent_bg='#1a3a5c',
    header_bg='#2962FF',
    row_hover='#3a3a3a',
    selection_bg='#1a3a5c',
    chart_bg='#2d2d2d',
    chart_grid='#444444',
    chart_text='#cccccc',
    input_bg='#3a3a3a',
    input_border='#555555',
    toolbar_bg='#2a2a2a',
    statusbar_bg='#252525',
    shadow='rgba(0, 0, 0, 60)',
)


class Typography:
    H1_SIZE = 18
    H2_SIZE = 14
    BODY_SIZE = 11
    CAPTION_SIZE = 9


class ThemeManager(QObject):
    """Singleton that manages application theming."""
    theme_changed = pyqtSignal()

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._mode = 'auto'
        self._palette = LIGHT

    @property
    def palette(self) -> ThemePalette:
        return self._palette

    @property
    def is_dark(self) -> bool:
        return self._palette is DARK

    def set_mode(self, mode: str):
        self._mode = mode
        self._save_preference()
        self._resolve_palette()
        self._apply()
        self.theme_changed.emit()

    def apply_initial(self):
        self._load_preference()
        self._resolve_palette()
        self._apply()

    def _load_preference(self):
        try:
            from ..database.operations import SettingsOperations
            self._mode = SettingsOperations.get('theme_mode', 'auto')
        except Exception:
            self._mode = 'auto'

    def _save_preference(self):
        try:
            from ..database.operations import SettingsOperations
            SettingsOperations.set('theme_mode', self._mode)
        except Exception:
            pass

    def _detect_system_dark(self) -> bool:
        app = QApplication.instance()
        if app:
            palette = app.style().standardPalette()
            bg = palette.color(QPalette.ColorRole.Window)
            return bg.lightness() < 128
        return False

    def _resolve_palette(self):
        if self._mode == 'dark':
            self._palette = DARK
        elif self._mode == 'light':
            self._palette = LIGHT
        else:
            self._palette = DARK if self._detect_system_dark() else LIGHT

    def _apply(self):
        app = QApplication.instance()
        if app:
            app.setStyleSheet(self.generate_stylesheet())

    def generate_stylesheet(self) -> str:
        p = self._palette
        return f"""
        /* === GLOBAL === */
        QMainWindow, QDialog {{
            background-color: {p.window};
            color: {p.text_primary};
        }}
        QWidget {{
            color: {p.text_primary};
        }}

        /* === TAB BAR === */
        QTabWidget::pane {{
            border: 1px solid {p.border};
            border-radius: 4px;
            background: {p.surface};
        }}
        QTabBar::tab {{
            padding: 8px 20px;
            margin-right: 2px;
            border: none;
            border-bottom: 3px solid transparent;
            color: {p.text_secondary};
            background: transparent;
            font-size: {Typography.BODY_SIZE}pt;
        }}
        QTabBar::tab:selected {{
            color: {p.accent};
            border-bottom: 3px solid {p.accent};
            font-weight: bold;
        }}
        QTabBar::tab:hover:!selected {{
            color: {p.text_primary};
            background: {p.accent_bg};
            border-bottom: 3px solid {p.border};
        }}

        /* === TABLES === */
        QTableWidget {{
            background-color: {p.surface};
            alternate-background-color: {p.surface_alt};
            gridline-color: {p.border};
            border: 1px solid {p.border};
            border-radius: 4px;
            selection-background-color: {p.selection_bg};
            selection-color: {p.text_primary};
        }}
        QTableWidget::item {{
            padding: 4px 8px;
        }}
        QTableWidget::item:hover {{
            background-color: {p.row_hover};
        }}
        QHeaderView::section {{
            background-color: {p.header_bg};
            color: {p.text_on_primary};
            padding: 8px 8px;
            border: none;
            border-right: 1px solid rgba(255, 255, 255, 40);
            font-weight: bold;
            font-size: {Typography.BODY_SIZE}pt;
        }}
        QHeaderView::section:last {{
            border-right: none;
        }}

        /* === TOOLBAR === */
        QToolBar {{
            background: {p.toolbar_bg};
            border-bottom: 1px solid {p.border};
            spacing: 4px;
            padding: 4px 8px;
        }}
        QToolBar QToolButton {{
            padding: 6px 12px;
            border-radius: 4px;
            border: 1px solid transparent;
            color: {p.text_primary};
            font-size: {Typography.BODY_SIZE}pt;
        }}
        QToolBar QToolButton:hover {{
            background: {p.accent_bg};
            border: 1px solid {p.border};
        }}
        QToolBar QToolButton:pressed {{
            background: {p.selection_bg};
        }}
        QToolBar::separator {{
            width: 1px;
            background: {p.border};
            margin: 4px 4px;
        }}

        /* === MENU BAR === */
        QMenuBar {{
            background: {p.toolbar_bg};
            border-bottom: 1px solid {p.border};
            padding: 2px;
        }}
        QMenuBar::item {{
            padding: 4px 10px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background: {p.accent_bg};
        }}
        QMenu {{
            background: {p.surface};
            border: 1px solid {p.border};
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px;
            border-radius: 3px;
        }}
        QMenu::item:selected {{
            background: {p.accent_bg};
        }}
        QMenu::separator {{
            height: 1px;
            background: {p.border};
            margin: 4px 8px;
        }}

        /* === SCROLL BARS === */
        QScrollBar:vertical {{
            background: {p.window};
            width: 10px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background: {p.muted};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p.accent};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {p.window};
            height: 10px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.muted};
            border-radius: 5px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {p.accent};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* === INPUTS === */
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
            background: {p.input_bg};
            border: 1px solid {p.input_border};
            border-radius: 4px;
            padding: 5px 8px;
            color: {p.text_primary};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
        QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {{
            border: 2px solid {p.accent};
        }}
        QComboBox::drop-down {{
            border: none;
            padding-right: 8px;
        }}
        QComboBox QAbstractItemView {{
            background: {p.surface};
            border: 1px solid {p.border};
            selection-background-color: {p.accent_bg};
            color: {p.text_primary};
        }}

        /* === BUTTONS === */
        QPushButton {{
            padding: 7px 16px;
            border-radius: 4px;
            border: 1px solid {p.border};
            background: {p.surface};
            color: {p.text_primary};
            font-size: {Typography.BODY_SIZE}pt;
        }}
        QPushButton:hover {{
            background: {p.accent_bg};
            border-color: {p.accent};
        }}
        QPushButton:pressed {{
            background: {p.selection_bg};
        }}
        QPushButton:default {{
            background: {p.accent};
            color: {p.text_on_primary};
            border: none;
        }}
        QPushButton:default:hover {{
            background: {p.header_bg};
        }}
        QPushButton:flat {{
            border: none;
            background: transparent;
        }}
        QPushButton:flat:hover {{
            background: {p.accent_bg};
        }}

        /* === GROUP BOXES === */
        QGroupBox {{
            font-weight: bold;
            font-size: {Typography.BODY_SIZE}pt;
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 16px;
            background: {p.surface};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 2px 10px;
            color: {p.accent};
        }}

        /* === PROGRESS BAR === */
        QProgressBar {{
            background: {p.surface_alt};
            border: none;
            border-radius: 4px;
            text-align: center;
            color: {p.text_secondary};
        }}
        QProgressBar::chunk {{
            border-radius: 4px;
        }}

        /* === STATUS BAR === */
        QStatusBar {{
            background: {p.statusbar_bg};
            border-top: 1px solid {p.border};
            color: {p.text_secondary};
            font-size: {Typography.CAPTION_SIZE}pt;
        }}
        QStatusBar QLabel {{
            color: {p.text_secondary};
            font-size: {Typography.CAPTION_SIZE}pt;
        }}

        /* === SEPARATORS === */
        QFrame[frameShape="4"] {{
            color: {p.border};
            max-height: 1px;
        }}

        /* === CHECKBOX === */
        QCheckBox {{
            color: {p.text_primary};
            spacing: 8px;
        }}

        /* === TOOLTIPS === */
        QToolTip {{
            background: {p.surface};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
        }}

        /* === SCROLL AREA === */
        QScrollArea {{
            border: none;
            background: transparent;
        }}

        /* === LABELS === */
        QLabel {{
            color: {p.text_primary};
        }}

        /* === CALENDAR POPUP === */
        QCalendarWidget {{
            background: {p.surface};
        }}
        QCalendarWidget QAbstractItemView {{
            background: {p.surface};
            color: {p.text_primary};
            selection-background-color: {p.accent};
            selection-color: {p.text_on_primary};
        }}
        """

    def get_matplotlib_params(self) -> dict:
        p = self._palette
        return {
            'figure.facecolor': p.chart_bg,
            'axes.facecolor': p.chart_bg,
            'axes.edgecolor': p.border,
            'axes.labelcolor': p.chart_text,
            'text.color': p.chart_text,
            'xtick.color': p.chart_text,
            'ytick.color': p.chart_text,
            'grid.color': p.chart_grid,
            'grid.alpha': 0.3,
            'figure.edgecolor': p.chart_bg,
        }

    def get_chart_colors(self) -> list:
        return ['#FFD700', '#4169E1', '#32CD32', '#FF6B6B', '#9B59B6', '#E67E22']


def theme() -> ThemeManager:
    """Shorthand to get the ThemeManager singleton."""
    return ThemeManager.instance()


def make_shadow(parent=None) -> QGraphicsDropShadowEffect:
    """Create a drop shadow effect using current theme."""
    shadow = QGraphicsDropShadowEffect(parent)
    shadow.setBlurRadius(12)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(0, 0, 0, 30 if not theme().is_dark else 60))
    return shadow
