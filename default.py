# -*- coding: utf-8 -*-
 # This code is heavely inspired from https://github.com/maximeh/script.mwarrpisodes

import os
import sys
import threading
import logging
from typing import Callable
import re

import xbmc
import xbmcvfs
import xbmcaddon

import utils
import kodilogging

from watcharr import WatchArr, SHOW_ID_ERR


watcharr_url = ""

_addon = xbmcaddon.Addon()
_kodiversion = float(xbmcaddon.Addon("xbmc.addon").getAddonInfo("version")[0:4])
_cwd = _addon.getAddonInfo("path")
_language = _addon.getLocalizedString
_resource_path = os.path.join(_cwd, "resources", "lib")
_resource = xbmcvfs.translatePath(_resource_path)


# Set the path for the log file
log_file = os.path.join(_cwd, "debug.txt")

# Configure custom logging to write to the log file
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', filename=log_file)

logger = logging.getLogger(__name__)

kodilogging.config()
logger = logging.getLogger(__name__)


class MEMonitor(xbmc.Monitor):
    def __init__(self, *args: int, **kwargs: Callable) -> None:
        xbmc.Monitor.__init__(self)
        self.action = kwargs["action"]

    def onSettingsChanged(self) -> None:
        logger.debug("User changed settings")
        self.action()


class MEProperties:
    def __init__(self) -> None:
        self.showid = self.episode = self.season = 0
        self.title = ""
        self.total_time = sys.maxsize
        self.last_pos = 0
        self.type = ""
        self.tmdb_id = ""       


class MEPlayer(xbmc.Player):
    def __init__(self) -> None:
##        logger.debug("MEPlayer - init")
        xbmc.Player.__init__(self)
        self._tracker = threading.Thread(target=self._track_position)
        self._reset()
        self.info_tag_video = None

    def _reset(self) -> None:
##        logger.debug("_reset called")
        self.resetTracker()
        if hasattr(self, "mwarr"):
            del self.mwarr
        self.monitor = MEMonitor(action=self._reset)
        self.props = MEProperties()
        self._playback_lock = threading.Event()
        self.mwarr: WatchArr = MEPlayer.initWatchArr()
        if not self.mwarr.is_logged:
            logger.debug("not is_logged")
        if not self.mwarr.is_logged:
            return
        logger.debug("mwarrPlayer - account is logged successfully.")

    def resetTracker(self) -> None:
        if hasattr(self, "_playback_lock"):
            self._playback_lock.clear()
        if not hasattr(self, "_tracker"):
            return
        if self._tracker.is_alive():
            self._tracker.join()
        self._tracker = threading.Thread(target=self._track_position)

    @classmethod
    def initWatchArr(cls) -> WatchArr:        
        username = utils.getSetting("Username")
        password = utils.getSetting("Password")
        watcharr_url = utils.getSetting("Address")
        watcharr_url = watcharr_url + "/api"
        logger.debug("Settings = %s, %s, %s", username, password, watcharr_url)

        login_notif = _language(32912)
        if not username or not password:
            utils.notif(login_notif, time=2500)
            return WatchArr("", "")
        
        login_notif = _language(32913)
        if not watcharr_url:
            utils.notif(login_notif, time=2500)
            return WatchArr("", "")
        
        mwarr = WatchArr(username, password, watcharr_url)
        mwarr.login()
        if mwarr.is_logged:
            login_notif = f"{username} {_language(32911)}"
        utils.notif(login_notif, time=2500)

        if mwarr.is_logged and (not mwarr.populate_shows()):
            utils.notif(_language(32927), time=2500)
        return mwarr

    def _track_position(self) -> None:
        while self._playback_lock.is_set() and not self.monitor.abortRequested():
            try:
                self.props.last_pos = self.getTime()
            except:
                self._playback_lock.clear()
            xbmc.sleep(250)
        logger.debug("Tracker time (ended) = %d", self.props.last_pos)


        # Update the show dict to check if it has already been added somehow.
        self.mwarr.populate_shows()

        # Add the show if it's not already in our account
        if self.props.showid in self.mwarr.shows.values():
            logger.debug("Show is already in the account.")
            return

    # For backward compatibility
    def onPlayBackStarted(self) -> None:
        # Get the currently playing file
        file = self.getPlayingFile()
        # Create a ListItem for the file
##        list_item = xbmcgui.ListItem(path=file)
        # Get the InfoTagVideo for the ListItem
        if _kodiversion >= 17.9:
            return
        # This call is only for Krypton and below
        self.onAVStarted()

    # Only available in Leia (18) and up
    def onAVStarted(self) -> None:
        self.props = MEProperties()  # Reset the properties
        self._playback_lock.set()
        self.props.total_time = self.getTotalTime()
        self._tracker.start()

        filename_full_path = self.getPlayingFile()
        if xbmc.getInfoLabel("VideoPlayer.VideoResolution"):
            # Check if a TV show is playing
            if xbmc.getInfoLabel("VideoPlayer.TVshowtitle"):
                self.props.title = xbmc.getInfoLabel("VideoPlayer.TVshowtitle")
                self.props.season = int(xbmc.getInfoLabel("VideoPlayer.Season"))
                self.props.episode = int(xbmc.getInfoLabel("VideoPlayer.Episode"))
                self.props.type = "tv"
            else:
                temp_title = xbmc.getInfoLabel("VideoPlayer.Title")
                self.props.type = "movie"

        if self.props.type == "tv":
            self.props.season = None
            try:
                self.props.season = int(xbmc.getInfoLabel("VideoPlayer.Season"))
            except ValueError:
                self.props.season = 0
            logger.debug("Player - Season: %02d", self.props.season)

            self.props.episode = None
            try:
                self.props.episode = int(xbmc.getInfoLabel("VideoPlayer.Episode"))
            except ValueError:
                self.props.episode = 0
            logger.debug("Player - Episode: %02d", self.props.episode)
        else:
            temp_title = xbmc.getInfoLabel("VideoPlayer.Title")
            # If the title is a simple title, use it as is
            if re.match(r"^[a-zA-Z0-9 ]+$", temp_title) and not re.search(r"\d{4}", temp_title):
                title = temp_title
                self.props.title = title
            else:
                # Special case: if the title contains periods, replace periods with spaces
                if '.' in temp_title:
                    temp_title = temp_title.replace('.', ' ')
                # Break down the title into separate groups
                groups = re.findall(r"([a-zA-Z0-9.]+|\d{4}|[^a-zA-Z0-9.]+)", temp_title)
                
                # Find the index of the group containing the year
                year_index = next(i for i, group in enumerate(groups) if re.match(r"\d{4}", group))

                # Initialize the title as an empty string
                title = ""

                # Iterate over the groups in reverse order, starting from the group before the year
                # Exclude the last non-alphanumeric group before the year
                for i in range(year_index-2, -1, -1):
                    group = groups[i]
                    # If the group is alphanumeric (contains only letters, numbers, or spaces), add it to the start of the title
                    if re.match(r"[a-zA-Z0-9 ]+", group):
                        # Only add a space if the next group is not a space
                        if i > 0 and groups[i-1].strip():
                            title = group.strip() + " " + title
                        else:
                            title = group.strip() + title
                    # If the group is not alphanumeric, stop adding groups to the title
                    else:
                        break

                # Strip leading and trailing spaces from the title
                title = title.strip()
                self.props.title = title


        if self.props.title == "":
            filename = os.path.basename(filename_full_path)
            self.props.title, self.props.season, self.props.episode, self.props.tmdb_id  = self.mwarr.get_info(
                                                                                            filename
                                                                                            )


        logger.debug(
            "Title: '%s' - Season: %02d - Ep: %02d ",
            self.props.title,
            self.props.season,
            self.props.episode
        )
        ## This is redundant and should probably be removed
        if not self.props.season and not self.props.episode:
            self.props.type = "movie"
        else:
            self.props.type = "tv"
       

        self.props.showid = self.mwarr.find_show_id(self.props.title, self.props.season, self.props.episode, self.props.type)
        if self.props.showid == SHOW_ID_ERR:
            utils.notif(f"{self.props.title} {_language(32923)}", time=3000)
            self.resetTracker()
            return
        logger.debug(
            "Player - Found : '%s' - %02d (S%02d E%02d",
            self.props.title,
            self.props.showid,
            self.props.season,
            self.props.episode
        )

        utils.notif(self.props.title, time=2000)

    def onPlayBackStopped(self) -> None:
        # User stopped the playback
        self.onPlayBackEnded()

    def onPlayBackEnded(self) -> None:
        self.resetTracker()


        logger.debug(
            "last_pos / total_time : %d / %d",
            self.props.last_pos,
            self.props.total_time,
        )

        actual_percent = (self.props.last_pos / self.props.total_time) * 100
        logger.debug(
            "last_pos / total_time : %d / %d = %d%%",
            self.props.last_pos,
            self.props.total_time,
            actual_percent,
        )

        min_percent = min(utils.getSettingAsInt("watched-percent"), 95)
        logger.debug("min_percent = %d", min_percent)
        if actual_percent < min_percent:
            return


        # Playback is finished, set the items to watched
        found = 32923
        if utils.getSettingAsBool("auto-add"):

            if self.mwarr.set_show_watched(
                self.props.showid, self.props.season, self.props.episode, self.props.type
            ):
                found = 32924
            utils.notif(
                f"{self.props.title} ({self.props.season:02} - {self.props.episode:02}) {_language(found)}"
            )


if __name__ == "__main__":
    player = MEPlayer()
    if not player.mwarr.is_logged:
        sys.exit(0)

    logger.debug(
        "[%s] - Version: %s Started",
        _addon.getAddonInfo("name"),
        _addon.getAddonInfo("version"),
    )

    while not player.monitor.abortRequested():
        if player.monitor.waitForAbort(1):
            # Abort was requested while waiting. We should exit
            break

    player.resetTracker()
    sys.exit(0)
