# -*- coding: utf-8 -*-
"""设计令牌：浅色主题。所有界面颜色都从这里取，换肤只改这一个文件。"""

# ---------------------------------------------------------------- 颜色
BG0 = "#F2F5FA"          # 页面底色
BG1 = "#FFFFFF"          # 顶栏 / 状态栏
PANEL = "#FFFFFF"        # 卡片
PANEL_HI = "#F5F8FC"     # 次级面板 / 悬浮
LINE = "#E2E8F0"         # 主描边
LINE_SOFT = "#EDF1F6"    # 分隔线

TEXT = "#15202B"
TEXT_SUB = "#51606F"
MUTED = "#7A8A99"
DIM = "#A9B6C4"

PRIMARY = "#2563EB"      # 主色（按钮、选中）
PRIMARY_DK = "#1D4ED8"
PRIMARY_SOFT = "#EAF1FF"
ACCENT = "#0E9F8A"       # 成功 / 在场
ACCENT_SOFT = "#E6F7F4"
AMBER = "#D97706"        # 待缴费 / 提醒
AMBER_SOFT = "#FFF4E5"
RED = "#E5484D"          # 拒绝 / 异常
RED_SOFT = "#FDECEC"
BLUE = "#2563EB"
BLUE_SOFT = "#EAF1FF"

PLATE_BLUE = "#1A4FD6"
PLATE_YELLOW = "#FFC53D"
PLATE_GREEN = "#22A06B"

# ---------------------------------------------------------------- 字体
FONT_UI = "Microsoft YaHei UI"
FONT_NUM = "Bahnschrift"

# ---------------------------------------------------------------- 尺寸
RADIUS = 14
RADIUS_SM = 10
GAP = 16
PAD = 18


def qss() -> str:
    """全局样式表（浅色）。"""
    return f"""
    * {{
        font-family: "{FONT_UI}";
        outline: none;
    }}
    QMainWindow, QDialog, QWidget#root {{
        background: {BG0};
    }}

    /* ---------------- 卡片 ---------------- */
    QFrame#card {{
        background: {PANEL};
        border: 1px solid {LINE};
        border-radius: {RADIUS}px;
    }}
    QFrame#cardFlat {{
        background: {PANEL_HI};
        border: 1px solid {LINE_SOFT};
        border-radius: {RADIUS_SM}px;
    }}
    QLabel {{
        color: {TEXT};
        background: transparent;
    }}
    QLabel#cardTitle {{
        color: {TEXT_SUB};
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 1px;
    }}
    QLabel#cardHint {{ color: {DIM}; font-size: 11px; }}
    QLabel#muted {{ color: {MUTED}; font-size: 12px; }}
    QLabel#dim {{ color: {DIM}; font-size: 12px; }}
    QLabel#value {{
        color: {TEXT};
        font-family: "{FONT_NUM}";
        font-size: 22px;
        font-weight: 600;
    }}
    QLabel#unit {{ color: {MUTED}; font-size: 12px; }}

    /* ---------------- 按钮 ---------------- */
    QPushButton#primary {{
        background: {PRIMARY};
        color: #FFFFFF;
        border: none;
        border-radius: {RADIUS_SM}px;
        padding: 12px 18px;
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 1px;
    }}
    QPushButton#primary:hover   {{ background: #3B76F6; }}
    QPushButton#primary:pressed {{ background: {PRIMARY_DK}; }}
    QPushButton#primary:disabled {{
        background: #E6EBF2; color: {DIM};
    }}

    QPushButton#ghost {{
        background: {PANEL};
        color: {TEXT};
        border: 1px solid {LINE};
        border-radius: {RADIUS_SM}px;
        padding: 11px 16px;
        font-size: 13px;
        letter-spacing: 1px;
    }}
    QPushButton#ghost:hover   {{ border-color: {PRIMARY}; color: {PRIMARY}; background: {PRIMARY_SOFT}; }}
    QPushButton#ghost:pressed {{ background: #DCE7FF; }}
    QPushButton#ghost:disabled {{ color: {DIM}; border-color: {LINE_SOFT}; background: {PANEL}; }}

    QPushButton#danger {{
        background: transparent;
        color: {RED};
        border: 1px solid #F3C3C5;
        border-radius: {RADIUS_SM}px;
        padding: 11px 16px;
        font-size: 13px;
    }}
    QPushButton#danger:hover {{ background: {RED_SOFT}; border-color: {RED}; }}

    QPushButton#linkBtn {{
        background: transparent; border: none;
        color: {MUTED}; font-size: 12px; padding: 2px 4px;
    }}
    QPushButton#linkBtn:hover {{ color: {PRIMARY}; }}

    /* ---------------- 输入 ---------------- */
    QLineEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit {{
        background: {PANEL_HI};
        border: 1px solid {LINE};
        border-radius: {RADIUS_SM}px;
        color: {TEXT};
        padding: 9px 12px;
        font-size: 13px;
        selection-background-color: #CFE0FF;
        selection-color: {TEXT};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {{
        border-color: {PRIMARY}; background: {PANEL};
    }}

    /* ---------------- 表格 ---------------- */
    QTableWidget {{
        background: transparent;
        border: none;
        color: {TEXT};
        font-size: 13px;
        gridline-color: transparent;
        selection-background-color: {PRIMARY_SOFT};
        selection-color: {TEXT};
    }}
    QTableWidget::item {{
        border-bottom: 1px solid {LINE_SOFT};
        padding: 6px 8px;
    }}
    QTableWidget::item:hover {{ background: {PANEL_HI}; }}
    QHeaderView {{ background: transparent; border: none; }}
    QHeaderView::section {{
        background-color: {PANEL};
        color: {MUTED};
        border: none;
        border-bottom: 1px solid {LINE};
        padding: 8px;
        font-size: 11px;
        letter-spacing: 1px;
        font-weight: 600;
    }}
    QTableCornerButton::section {{ background: transparent; border: none; }}

    /* ---------------- 滚动条 ---------------- */
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #D3DCE7; border-radius: 4px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: #BCC9D7; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* ---------------- 状态栏 ---------------- */
    QStatusBar {{
        background: {BG1};
        border-top: 1px solid {LINE};
        color: {MUTED};
        font-size: 12px;
    }}
    QStatusBar::item {{ border: none; }}

    QToolTip {{
        background: #FFFFFF;
        color: {TEXT};
        border: 1px solid {LINE};
        padding: 6px 8px;
    }}
    QMessageBox {{ background: {PANEL}; }}
    QMessageBox QLabel {{ color: {TEXT}; font-size: 13px; }}
    """
