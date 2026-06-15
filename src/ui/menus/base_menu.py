from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Union, Optional, Callable
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QMenu, QMenuBar

@dataclass
class Option:
    key: str
    label: str
    icon: Optional[QIcon] = None
    shortcut: Optional[str] = None
    enabled: bool = True
    checkable: bool = False
    checked: bool = False
    separator_before: bool = False
    menu: Optional[RootMenu] = None

class SubMenu:
    def __init__(self, label: str, icon: Optional[QIcon] = None, enabled: bool = True,
                 root_menu: Optional[RootMenu] = None):
        self.label = label
        self.icon = icon
        self.enabled = enabled
        self.children: List[Union[Option, 'SubMenu']] = []
        self.root_menu = root_menu

    def option(self, key: str, label: str, icon=None, shortcut=None, enabled=True,
               checkable=False, checked=False, sep_before=False) -> Option:
        opt = Option(key, label, icon, shortcut, enabled, checkable, checked, sep_before)
        opt.menu = self.root_menu
        self.children.append(opt)
        return opt

    def submenu(self, label: str, icon=None, enabled=True) -> 'SubMenu':
        sub = SubMenu(label, icon, enabled, root_menu=self.root_menu)
        self.children.append(sub)
        return sub

class RootMenu:
    """Base class for a top‑level menu. Subclass and define build()."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.controller = main_window.controller
        self.title = "Menu"
        self.children: List[Union[Option, SubMenu]] = []

    def option(self, key: str, label: str, icon=None, shortcut=None, enabled=True,
               checkable=False, checked=False, sep_before=False) -> Option:
        opt = Option(key, label, icon, shortcut, enabled, checkable, checked, sep_before)
        opt.menu = self
        self.children.append(opt)
        return opt

    def submenu(self, label: str, icon=None, enabled=True) -> SubMenu:
        sub = SubMenu(label, icon, enabled, root_menu=self)
        self.children.append(sub)
        return sub

    def build(self):
        """Override to define menu structure."""
        pass

    def execute(self, key: str):
        """Called when an option is selected. Override to dispatch actions."""
        pass