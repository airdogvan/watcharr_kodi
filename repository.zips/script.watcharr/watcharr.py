 # This code is heavely inspired from https://github.com/maximeh/script.mwarrpisodes
# Assume all bugs are mine

from __future__ import annotations
import re
import requests
from typing import final, TypeVar, Any, Callable, Optional, cast, Dict



SHOW_ID_ERR = -1

# This is totally stolen from script.xbmc.subtitles plugin !
REGEX_EXPRESSIONS = [
    r"[Ss]([0-9]+)[][._-]*[Ee]([0-9]+)([^\\\\/]*)$",
    r"[\._ \-]([0-9]+)x([0-9]+)([^\\/]*)",  # foo.1x09
    r"[\._ \-]([0-9]+)([0-9][0-9])([\._ \-][^\\/]*)",  # foo.109
    r"([0-9]+)([0-9][0-9])([\._ \-][^\\/]*)",
    r"[\\\\/\\._ -]([0-9]+)([0-9][0-9])[^\\/]*",
    r"Season ([0-9]+) - Episode ([0-9]+)[^\\/]*",  # Season 01 - Episode 02
    r"Season ([0-9]+) Episode ([0-9]+)[^\\/]*",  # Season 01 Episode 02
    r"[\\\\/\\._ -][0]*([0-9]+)x[0]*([0-9]+)[^\\/]*",
    r"[[Ss]([0-9]+)\]_\[[Ee]([0-9]+)([^\\/]*)",  # foo_[s01]_[e01]
    r"[\._ \-][Ss]([0-9]+)[\.\-]?[Ee]([0-9]+)([^\\/]*)",  # foo, s01e01, foo.s01.e01, foo.s01-e01
    r"s([0-9]+)ep([0-9]+)[^\\/]*",  # foo - s01ep03, foo - s1ep03
    r"[Ss]([0-9]+)[][ ._-]*[Ee]([0-9]+)([^\\\\/]*)$",
    r"[\\\\/\\._ \\[\\(-]([0-9]+)x([0-9]+)([^\\\\/]*)$",    
    ]




def sanitize(title: str, replace: str) -> str:
    for char in ["[", "]", "_", "(", ")", ".", "-"]:
        title = title.replace(char, replace)
    return title

F = TypeVar("F", bound=Callable[..., Any])

def logged(func: F) -> F:
    def wrapper(*args: WatchArr, **kwargs: str) -> F:
        mwarr = args[0]
        if not mwarr.is_logged:
            mwarr.login()
        return func(*args, **kwargs)

    return cast(F, wrapper)

def login_session() -> requests.Session:
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(1)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

@final
class WatchArr:
    def __init__(self, userid: str, password: str, watcharr_url: str) -> None:
        self.userid = userid
        self.password = password
        self.url = watcharr_url
        self.title_is_filename = False
        self.shows: Dict[int, Tuple[int, str]] = {}  # Declare self.shows as a dictionary
        self.is_logged = False
        self.req = login_session()



    def __del__(self) -> None:
        self.req.close()

    def __repr__(self) -> str:
        return f"WatchArr('{self.userid}', '{self.password}', {self.url})"        
    
    def login(self) -> None:
#        logger.debug("login")
        login_data = {
            "username": self.userid,
            "password": self.password
        }    


        response = self.req.post(f"{self.url}/auth/", json=login_data)    
        # Quickly check if it seems we are logged on.
        if response.status_code == 200:
#            logger.debug("Login successful")
            token = response.json().get('token')
            self.req.headers.update({'Authorization': f'{token}'})
            self.is_logged = True
        return

       
    @logged
    def populate_shows(self) -> bool:
        self.shows.clear()

        # Populate shows with the list of show_ids in our account       
        response = self.req.get(f"{self.url}/watched")
        response_json = response.json()
        if not response_json:
            return False

        # Iterate over the items in the response
        for item in response_json:
            # Check if the 'content' field exists and if it has a 'tmdbId' field
            if 'content' in item and 'tmdbId' in item['content']:
                # Get the 'tmdbId' and 'id' fields
                tmdbId = item['content']['tmdbId']
                id = item['id']
                title = item['content']['title']

                # Use the 'tmdbId' as the key and the 'id' as the value in self.shows
                self.shows[tmdbId] = (id, title)


        return True
        

    @logged
    def find_show_id(self, show_title: str, season: int, episode: int, type: str) -> Optional[int]:
        # Try to find the ID of the show in our account first        
        self.populate_shows()

        for _, (show_id, title) in self.shows.items():
            if show_title == title:
                return show_id
        else:
            # If not found in our shows, get the tmdb ID from title
            show_id = self.search_tmdb_for_media(show_title, season, episode,type)
            if show_id:
                return show_id
        

        return None


  
   # This is totally stolen from script.xbmc.subtitles plugin !

    def get_info(self, file_name: str) -> tuple[str, int, int, str]:
        title = ""
        season = SHOW_ID_ERR
        episode = SHOW_ID_ERR
        self.title_is_filename = False

        for regex in REGEX_EXPRESSIONS:
            response_file = re.findall(regex, file_name)
            if response_file:
                season = int(response_file[0][0])
                episode = int(response_file[0][1])
            else:
                continue
            title = re.split(regex, file_name)[0]
            title = sanitize(title, " ")
            title = title.strip()
            self.title_is_filename = True
            if season and episode:
                media_id = self.search_tmdb_for_media(title, season, episode, 'tv')
            else:
                media_id = self.search_tmdb_for_media(title, season, episode, 'movie')


        return title.title(), season, episode, media_id 
     
    
    def search_tmdb_for_media(self, title, season, episode, media_type) -> int:

        url = f"https://api.themoviedb.org/3/search/{media_type}?api_key=f090bb54758cabf231fb605d3e3e0468&query={title}"
        response = requests.get(url)
        data = response.json()

        if not data['results']:
            return None

        # If media type is 'tv', filter results to shows with the specified season and episode
        if media_type == 'tv':
            results = []
            for result in data['results']:
                if result['name'] == title:  # Add this line
                    url = f"https://api.themoviedb.org/3/tv/{result['id']}/season/{season}/episode/{episode}?api_key=f090bb54758cabf231fb605d3e3e0468"
                    response = requests.get(url)
                    if response.status_code == 200:
                        results.append(result)
        else:
            results = data['results']

        if not results:
            return None

        # Sort results by year (for TV shows) or release date (for movies) and popularity
        results.sort(key=lambda result: (result.get('first_air_date') or result.get('release_date'), result['popularity']), reverse=True)

        # Select the best match
        best_match = results[0]
        max_popularity = max(result['popularity'] for result in results)
        if best_match['popularity'] == max_popularity and best_match['vote_count'] >=10 and (best_match.get('first_air_date') or best_match.get('release_date')) == max((result.get('first_air_date') or result.get('release_date')) for result in results):
            if media_type == 'tv':
                #First add show to internal db
                internal_id = self.add_to_internal(best_match['id'], media_type, 'WATCHING', True )
                #Then add episode 
                self.add_to_internal(internal_id, media_type, 'WATCHING', False, season, episode )
                return internal_id if internal_id is not None else None
            else:
                return best_match['id']


        # If the most popular result is not the most recent, return the most recent

        # Filter out results with less than 10 votes
        filtered_results = [result for result in results if result['vote_count'] >= 10]
        # Find the maximum popularity among the filtered results
        max_popularity = max(result['popularity'] for result in filtered_results)
        # Filter the results again to only include items with maximum popularity
        most_popular_results = [result for result in filtered_results if result['popularity'] == max_popularity]
        # Find the most recent date among the most popular results
        max_date = max((result.get('first_air_date') or result.get('release_date')) for result in most_popular_results)
        # Find the best match among the most popular results
        best_match = next(result for result in most_popular_results if (result.get('first_air_date') or result.get('release_date')) == max_date)

        if media_type == 'tv':
            #First add show to internal db
            internal_id = self.add_to_internal(best_match['id'], media_type, 'WATCHING', True )
            #Then add episode 
            self.add_to_internal(internal_id, media_type, 'WATCHING', False, season, episode )
            return internal_id if internal_id is not None else None
        else:
            #It's a movie
            return best_match['id']

        
        return None

    def add_to_internal(self, media_id, media_type, status, bool=False, season=None, episode=None) -> int:
        # If bool is false use internal id, if not use tmdb id
        # media_id will be watchedId if false, contentId otherwise

        # If show doesn't exist in internal db must first add it
        if bool and media_type == 'tv': #Just make double sure it's not movie
            url = f"{self.url}/watched"
            data = {
                "contentId": media_id,
                "contentType": media_type,
                "status": status
            }
            response = requests.post(url, json=data, headers=self.req.headers)
            if response.status_code == 200:
                return response.json()['id']

            return None
        else:
            # Presumably new show has beed added, now add episode
            if media_type == 'tv':#Just make double sure it's not movie
                url = f"{self.url}/watched/episode"
                data = {
                        "watchedId": media_id,
                        "seasonNumber": season,
                        "episodeNumber": episode,
                        "status": status
                        }
                response = requests.post(url, json=data, headers=self.req.headers)
                if response.status_code == 200:
                    response_json = response.json()
                    return response_json.get('id')  # This will return None if 'id' is not in the response

                return None             


            
    @logged
    def set_show_watched(self, show_id: int, season: int, episode: int, type: str) -> bool:
        if type == 'tv':
            watched_data = {
                "watchedId": show_id,
                "seasonNumber": season,
                "episodeNumber": episode,
                "status": "FINISHED"
            }
            data = self.req.post(
                f"{self.url}/watched/episode",
                json = watched_data,
                headers= self.req.headers
            )
        else:
            watched_data = {
                "contentId": show_id,
                "contentType": "movie",
                "status": "FINISHED"
            }
            data = self.req.post(
                f"{self.url}/watched",
                json = watched_data,
                headers= self.req.headers
            )
        if data.status_code != 200:
            return False
        return True    
    
    