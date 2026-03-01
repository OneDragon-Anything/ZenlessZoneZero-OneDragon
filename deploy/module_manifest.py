# AUTO-GENERATED — DO NOT EDIT
import sys
if not getattr(sys, 'frozen', False):
    import argparse
    import ast
    import atexit
    import base64
    import builtins
    import contextlib
    import copy
    import csv
    import ctypes
    import cv2
    import datetime
    import difflib
    import gettext
    import glob
    import hashlib
    import hmac
    import html
    import importlib
    import importlib.util
    import inspect
    import io
    import json
    import librosa
    import locale
    import logging
    import math
    import matplotlib.font_manager
    import matplotlib.pyplot
    import numpy
    import onnxruntime
    import os
    import os.path
    import platform
    import polib
    import pyautogui
    import pyclipper
    import pyuac
    import pywintypes
    import random
    import re
    import requests
    import shutil
    import signal
    import smtplib
    import socket
    import soundcard
    import string
    import subprocess
    import sys
    import threading
    import time
    import traceback
    import urllib.parse
    import urllib.request
    import uuid
    import vgamepad
    import warnings
    import webbrowser
    import win32clipboard
    import win32con
    import win32ui
    import winreg
    import yaml
    import zipfile
    from PIL import Image, ImageDraw, ImageFont
    from PySide6 import QtCore
    from PySide6.QtCore import Property, QEasingCurve, QEvent, QEventLoop, QMimeData, QObject, QPoint, QPropertyAnimation, QRect, QRectF, QRegularExpression, QSize, QThread, QTimer, QUrl, Qt, Signal
    from PySide6.QtGui import QBrush, QColor, QDesktopServices, QDrag, QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent, QFont, QFontMetrics, QIcon, QImage, QIntValidator, QKeyEvent, QMouseEvent, QPaintEvent, QPainter, QPainterPath, QPen, QPixmap, QResizeEvent, QShowEvent, QSyntaxHighlighter, QTextCharFormat, QWheelEvent, Qt
    from PySide6.QtMultimedia import QMediaPlayer
    from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
    from PySide6.QtWidgets import QAbstractButton, QAbstractItemView, QAbstractScrollArea, QApplication, QComboBox, QCompleter, QDialog, QFileDialog, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGraphicsScene, QGraphicsView, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpacerItem, QSpinBox, QStackedWidget, QStyledItemDelegate, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
    from abc import ABC, abstractmethod
    from collections import defaultdict, deque
    from collections.abc import Callable
    from colorama import Fore, Style, init
    from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
    from contextlib import suppress
    from ctypes import wintypes
    from ctypes.wintypes import DWORD, HANDLE, RECT, SHORT, UINT, WCHAR, WORD
    from cv2.typing import MatLike
    from dataclasses import dataclass, field
    from datetime import datetime, timedelta
    from email.header import Header
    from email.mime.image import MIMEImage
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formataddr
    from enum import Enum, IntEnum, StrEnum
    from functools import cached_property, lru_cache, partial, wraps
    from io import BytesIO
    from logging import DEBUG
    from logging.handlers import TimedRotatingFileHandler
    from mss import mss
    from mss.base import MSSBase
    from packaging import version
    from pathlib import Path
    from pyautogui import screenshot
    from pygetwindow import Win32Window
    from pygit2 import Blob, Oid, Remote, Repository, Walker, discover_repository, init_repository, settings
    from pygit2.enums import CheckoutStrategy, ConfigLevel, ResetMode, SortMode
    from pynput import keyboard, mouse
    from pynput.keyboard import Controller, Key
    from qfluentwidgets import Action, BodyLabel, CaptionLabel, CardWidget, CheckBox, CheckableMenu, ColorDialog, ComboBox, Dialog, DisplayLabel, DoubleSpinBox, EditableComboBox, FlowLayout, FluentIcon, FluentIconBase, FluentStyleSheet, FluentThemeColor, FluentWindow, FlyoutViewBase, HorizontalFlipView, HyperlinkButton, HyperlinkCard, ImageLabel, IndeterminateProgressBar, IndicatorPosition, InfoBar, InfoBarIcon, InfoBarPosition, LargeTitleLabel, LineEdit, ListItemDelegate, ListWidget, MSFluentWindow, MaskDialogBase, MenuAnimationType, MessageBox, MessageBoxBase, NavigationBar, NavigationBarPushButton, NavigationItemPosition, PipsPager, PipsScrollButtonDisplayMode, Pivot, PixmapLabel, PlainTextEdit, PopupTeachingTip, PrimaryPushButton, ProgressBar, ProgressRing, PushButton, PushSettingCard, RoundMenu, ScrollArea, SettingCard, SettingCardGroup, SimpleCardWidget, SingleDirectionScrollArea, SpinBox, SplashScreen, SplitTitleBar, StrongBodyLabel, StyleSheetBase, SubtitleLabel, SwitchButton, TableWidget, TeachingTip, TeachingTipTailPosition, Theme, TitleLabel, ToolButton, ToolTip, ToolTipFilter, ToolTipPosition, TransparentPushButton, TransparentToolButton, VBoxLayout, isDarkTheme, qconfig, qrouter, setFont, setTheme, setThemeColor
    from qfluentwidgets.common.animation import BackgroundAnimationWidget, FluentAnimation, FluentAnimationProperty, FluentAnimationType
    from qfluentwidgets.common.config import qconfig
    from qfluentwidgets.common.overload import singledispatchmethod
    from qfluentwidgets.components.navigation.pivot import PivotItem
    from qfluentwidgets.components.settings.setting_card import FluentStyleSheet, SettingIconWidget
    from qfluentwidgets.components.widgets.frameless_window import FramelessWindow
    from qfluentwidgets.window.stacked_widget import StackedWidget
    from qframelesswindow import FramelessDialog
    from queue import Empty, Queue
    from random import random
    from scipy import signal
    from scipy.signal import butter, correlate, filtfilt
    from scipy.spatial import KDTree
    from shapely.geometry import Polygon
    from sklearn.preprocessing import scale
    from soundcard.mediafoundation import SoundcardRuntimeWarning
    from threading import Event, Lock
    from types import ModuleType
    from typing import Any, Callable, ClassVar, Dict, IO, Iterable, List, Optional, Set, TYPE_CHECKING, Tuple, Type, TypeVar, Union, cast
    from urllib.parse import urlencode
    from yaml import CSafeLoader, SafeLoader
