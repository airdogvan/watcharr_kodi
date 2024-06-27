# -*- coding: utf-8 -*-

import logging
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon

logger = logging.getLogger(__name__)

_addon = xbmcaddon.Addon()
_icon_path = _addon.getAddonInfo("icon")
_icon = xbmcvfs.translatePath(_icon_path)
_scriptname = _addon.getAddonInfo("name")


def getSettingAsBool(setting: str) -> bool:
    return _addon.getSetting(setting).lower() == "true"


def getSetting(setting: str) -> str:
    return _addon.getSetting(setting).strip()


def getSettingAsInt(setting: str) -> int:
    try:
        value = getSetting(setting)
        if setting == "watched-percent":
            values = ["70", "80", "90"]  # The possible values for "watched-percent"
            return int(values[int(value)])  # Use the index to get the actual value
        else:
            return int(value)
    except ValueError:
        return 0


def notif(msg: str, time: int = 5000) -> None:
    xbmcgui.Dialog().notification("WatchArr", msg, _icon, time)


