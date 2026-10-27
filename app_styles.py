# app_styles.py
from theme import css


def get_stylesheet(accent_color: str, theme: dict) -> str:
    t, b = theme["text"], theme["buttons"]
    return f"""
    QWidget#IslandWidget {{
        background-color: transparent;
        border: none;
    }}

    QLabel {{
        color: {css(t['primary'])};
        font-family: {theme['font_family']};
    }}

    QLabel#TitleLabel {{
        font-size: {t['title_size']}px;
        font-weight: 600;
    }}

    QLabel#SubtitleLabel {{
        font-size: {t['subtitle_size']}px;
        color: {css(t['secondary'])};
    }}

    QLabel#IconLabel {{
        background-color: transparent;
        font-size: 16px;
    }}

    QPushButton#MediaButton {{
        background-color: transparent;
        color: {css(b['text'])};
        border-radius: 14px;
        border: none;
        width: 28px;
        height: 28px;
        padding: 2px;
    }}

    QPushButton#MediaButton:hover {{
        background-color: {css(b['media_hover'])};
    }}

    QPushButton#MediaButton:pressed {{
        background-color: {css(b['media_pressed'])};
    }}

    QLabel#PerfLabel {{
        font-size: 11px;
        color: {css(t['perf'])};
        font-weight: 600;
    }}

    QPushButton#ActionButton {{
        background-color: {css(b['action_bg'])};
        color: {css(b['text'])};
        border-radius: 16px;
        border: 1px solid {css(b['action_border'])};
    }}

    QPushButton#ActionButton:hover {{
        background-color: {css(b['action_bg_hover'])};
        border: 1px solid {css(b['action_border_hover'])};
    }}

    QPushButton#ActionButton:pressed {{
        background-color: {css(b['action_bg_pressed'])};
    }}

    QPushButton#ControlBall {{
        background-color: {css(b['ball_bg'])};
        color: {css(b['text'])};
        border-radius: 20px;
        border: 1.2px solid {css(b['ball_border'])};
        width: 40px;
        height: 40px;
        font-size: 20px;
    }}

    QPushButton#ControlBall:hover {{
        background-color: {css(b['ball_bg_hover'])};
        border: 1.5px solid {css(b['ball_border_hover'])};
    }}

    QPushButton#NavButton {{
        background-color: transparent;
        color: {css(b['nav'])};
        border: none;
        font-size: 16px;
        padding: 0px 5px;
    }}

    QPushButton#NavButton:hover {{
        color: {css(b['nav_hover'])};
    }}

    {theme.get('custom_qss') or ''}
    """
