"""Dark sci-fi theme helpers for wxPython widgets.

Provides utility functions that create wxPython widgets pre-configured
with the dark colour palette defined in styles.py.
"""

import wx
from .styles import (
    BG_COLOR, PANEL_BG, CANVAS_BG, TEXT_COLOR, ACCENT_COLOR,
    SUCCESS_COLOR, WARNING_COLOR, DANGER_COLOR,
)


def hex_to_wx_colour(hex_str: str) -> wx.Colour:
    """Convert a '#1a1a2e' style hex string to a wx.Colour."""
    hex_str = hex_str.lstrip('#')
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return wx.Colour(r, g, b)


def _bg():   return hex_to_wx_colour(BG_COLOR)
def _panel(): return hex_to_wx_colour(PANEL_BG)
def _canvas(): return hex_to_wx_colour(CANVAS_BG)
def _text(): return hex_to_wx_colour(TEXT_COLOR)
def _accent(): return hex_to_wx_colour(ACCENT_COLOR)


def dark_panel(parent, **kwargs):
    """Create a dark-background wx.Panel."""
    p = wx.Panel(parent, **kwargs)
    p.SetBackgroundColour(_bg())
    p.SetForegroundColour(_text())
    return p


def dark_label(parent, label="", **kwargs):
    """Create a dark-themed wx.StaticText."""
    st = wx.StaticText(parent, label=label, **kwargs)
    st.SetForegroundColour(_text())
    try:
        st.SetBackgroundColour(_bg())
    except Exception:
        pass
    return st


def dark_button(parent, label="", **kwargs):
    """Create a dark-themed wx.Button."""
    btn = wx.Button(parent, label=label, **kwargs)
    return btn


def dark_text(parent, value="", style=0, **kwargs):
    """Create a dark-themed wx.TextCtrl (multi-line or single-line)."""
    tc = wx.TextCtrl(parent, value=value, style=style, **kwargs)
    tc.SetBackgroundColour(_panel())
    tc.SetForegroundColour(_text())
    return tc


def dark_combo(parent, choices=None, style=wx.CB_READONLY, **kwargs):
    """Create a dark-themed wx.ComboBox."""
    if choices is None:
        choices = []
    cb = wx.ComboBox(parent, choices=choices, style=style, **kwargs)
    return cb


def dark_slider(parent, value=0, minValue=0, maxValue=100, **kwargs):
    """Create a dark-themed wx.Slider."""
    sl = wx.Slider(parent, value=value, minValue=minValue,
                   maxValue=maxValue, **kwargs)
    return sl


def dark_spin(parent, value=1, min_val=1, max_val=100, **kwargs):
    """Create a dark-themed wx.SpinCtrl."""
    sp = wx.SpinCtrl(parent, value=str(value),
                     min=min_val, max=max_val, **kwargs)
    return sp


def dark_checkbox(parent, label="", **kwargs):
    """Create a dark-themed wx.CheckBox."""
    cb = wx.CheckBox(parent, label=label, **kwargs)
    cb.SetForegroundColour(_text())
    return cb


def dark_radio(parent, label="", **kwargs):
    """Create a dark-themed wx.RadioButton."""
    rb = wx.RadioButton(parent, label=label, **kwargs)
    rb.SetForegroundColour(_text())
    return rb


def dark_listbox(parent, **kwargs):
    """Create a dark-themed wx.ListBox."""
    lb = wx.ListBox(parent, **kwargs)
    lb.SetBackgroundColour(_panel())
    lb.SetForegroundColour(_text())
    return lb


def dark_listctrl(parent, style=wx.LC_REPORT, **kwargs):
    """Create a dark-themed wx.ListCtrl (report style)."""
    lc = wx.ListCtrl(parent, style=style, **kwargs)
    lc.SetBackgroundColour(_panel())
    lc.SetForegroundColour(_text())
    return lc


def configure_dark_panel(panel: wx.Panel):
    """Apply dark background/foreground to an already-created wx.Panel."""
    panel.SetBackgroundColour(_bg())
    panel.SetForegroundColour(_text())


def get_default_font(size=9, family=wx.FONTFAMILY_DEFAULT):
    """Return a default wx.Font for the application."""
    return wx.Font(size, family, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
