#!/usr/bin/env python
# coding=utf-8
__version__ = "13.3.0"
# When modifying remember to issue a new tag command in git before committing, then push the new tag
#   git tag -a v13.3.0 -m "v13.3.0"
#   git push origin master --tags
"""
Python script that allows you to download TV shows off the Icelandic RÚV Sarpurinn website.
The script is written in Python 3.5+

See: https://github.com/sverrirs/ruvsarpur
Author: Sverrir Sigmundarson  info@sverrirs.com  https://www.sverrirs.com
"""

# DEBUG: If you get an error such as:
#   UnicodeEncodeError: 'charmap' codec can't encode character '\u2010': character maps to <undefined>
# Set your console to use utf-8 encoding by issuing this statement:
#    chcp 65001
# The output will be a little garbled but at least you will be able to dump utf-8 data to the console 

# Requires the following
#   pip install colorama
#   pip install termcolor
#   pip install python-dateutil
#   pip install requests
#   pip install simplejson
#   pip install fuzzywuzzy
#   pip install python-levenshtein
#      For alternative install http://stackoverflow.com/a/33163704

import sys, os.path, re, time
from os import sep
import traceback   # For exception details
import textwrap # For text wrapping in the console window
from colorama import init, deinit # For colorized output to console windows (platform and shell independent)
from termcolor import colored # For shorthand color printing to the console, https://pypi.python.org/pypi/termcolor
from pathlib import Path # to check for file existence in the file system
import json # To store and load the tv schedule that has already been downloaded
import argparse # Command-line argument parser
import requests # Downloading of data from HTTP
import datetime # Formatting of date objects 
from fuzzywuzzy import fuzz # For fuzzy string matching when trying to find programs by title or description, https://towardsdatascience.com/string-matching-with-fuzzywuzzy-e982c61f8a84
from operator import itemgetter # For sorting the download list items https://docs.python.org/3/howto/sorting.html#operator-module-functions
import ntpath # Used to extract file name from path for all platforms http://stackoverflow.com/a/8384788
import glob # Used to do partial file path matching (when searching for already downloaded files) http://stackoverflow.com/a/2225582/779521
import uuid # Used to generate a ternary backup local filename if everything else fails.
import platform  # To get information about if we are running on windows or not

import urllib.request, urllib.parse # Downloading of data from URLs (used with the JSON parser)
import requests # Downloading of data from HTTP
from requests.adapters import HTTPAdapter # For Retrying
from requests.packages.urllib3.util.retry import Retry # For Retrying

import subprocess # To execute shell commands 
from itertools import (takewhile,repeat) # To count lines for the extremely large IMDB files 

# Disable SSL warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

import utilities

# Lambdas as shorthands for printing various types of data
# See https://pypi.python.org/pypi/termcolor for more info
color_title = lambda x: colored(x, 'cyan', 'on_grey')
color_pid_title = lambda x: colored(x, 'red', 'on_cyan')
color_pid = lambda x: colored(x, 'red')
color_sid = lambda x: colored(x, 'yellow')
color_description = lambda x: colored(x, 'white')

color_error = lambda x: colored(x, 'red')
color_warn = lambda x: colored(x, 'yellow')
color_info = lambda x: colored(x, 'cyan')

color_progress_fill = lambda x: colored(x, 'green')
color_progress_remaining = lambda x: colored(x, 'white')
color_progress_percent = lambda x: colored(x, 'green')

# The name of the directory used to store log files.  The directory will be located in the users home directory
LOG_DIR="{0}/{1}".format(os.path.expanduser('~'),'.ruvsarpur')

# Name of the log file containing the previously recorded shows
PREV_LOG_FILE = 'prevrecorded.log'
# Name of the log file containing the downloaded tv schedule
TV_SCHEDULE_LOG_FILE = 'tvschedule.json'
# Name of the file containing cache to imdb series and movies matches
IMDB_CACHE_FILE = 'imdb-cache.json'

# The available bitrate streams
QUALITY_BITRATE = {
    "Normal"  : { 'code': "1200", 'bits': "1150000", 'chunk_size':1500000},
    "HD720"   : { 'code': "2400", 'bits': "2350000", 'chunk_size':2800000},
    "HD1080"  : { 'code': "3600", 'bits': "3550000", 'chunk_size':4000000}
}

MONTH_NAMES = ['', 'jan', 'feb', 'mar', 'apr', 'maí', 'jún', 'júl', 'ágú', 'sep', 'okt', 'nóv', 'des']

# Parse the formats
#   https://ruv-vod.akamaized.net/opid/5234383T0/3600/index.m3u8
#   https://ruv-vod.akamaized.net/lokad/5240696T0/3600/index.m3u8
RE_VOD_URL_PARTS = re.compile(r'(?P<urlprefix>.*)(?P<rest>\/\d{3,4}\/index\.m3u8)', re.IGNORECASE)

# Parse just the base url from 
#   https://ruv-vod.akamaized.net/lokad/5240696T0/5240696T0.m3u8
# resulting in vodbase being = https://ruv-vod.akamaized.net/lokad/5240696T0
RE_VOD_BASE_URL = re.compile(r'(?P<vodbase>.*)\/(?P<rest>.*\.m3u8)', re.IGNORECASE)

RUV_URL = 'https://ruv-vod.akamaized.net'

# Function to count lines in very large files efficiently, see: https://stackoverflow.com/a/27517681/779521
def countLinesInFile(filename):
    with open(filename, 'rb') as f:
      bufgen = takewhile(lambda x: x, (f.raw.read(1024*1024) for _ in repeat(None)))
      return sum( buf.count(b'\n') for buf in bufgen if buf )

# Checks to see if a file is older than a specific timedelta
# See: https://stackoverflow.com/a/65412797/779521
# Example: 
#     isFileOlderThan(filename, timedelta(seconds=10))
#     isFileOlderThan(filename, timedelta(days=14))
def isFileOlderThan(file, delta): 
    cutoff = datetime.datetime.utcnow() - delta
    mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(file))
    if mtime < cutoff:
        return True
    return False

# Print console progress bar
# http://stackoverflow.com/a/34325723
def printProgress (iteration, total, prefix = '', suffix = '', decimals = 1, barLength = 100, color = True):
  try:
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        barLength   - Optional  : character length of bar (Int)
    """
    formatStr       = "{0:." + str(decimals) + "f}"
    percents        = formatStr.format(100 * (iteration / float(total)))
    filledLength    = int(round(barLength * iteration / float(total)))
    if( color ):
      bar             = color_progress_fill('=' * filledLength) + color_progress_remaining('-' * (barLength - filledLength))
      sys.stdout.write('\r %s |%s| %s %s' % (prefix, bar, color_progress_percent(percents+'%'), suffix)),
    else:
      bar             = '=' * filledLength + '-' * (barLength - filledLength)
      sys.stdout.write('\r %s |%s| %s %s' % (prefix, bar, percents+'%', suffix)),
          
    sys.stdout.flush()
  except: 
    pass # Ignore all errors when printing progress


# Performs an optimistic lookup for the movie or show data based on its original title 
# returns back enhancement information that can be used in PLEX to improve matching to official resources
# Response from this API are, JSON on the form:
#     {
#       "d": [ list of results ],
#       "q": the original query,
#       "v": some number
# }
# Each result in d has the format
# {
#     "i": {
#           "height": 1000,
#           "imageUrl": "https://m.media-amazon.com/images/M/MV5BODljM2M4NDItZjZkZi00MTZkLTljMjEtMWE1NGU5NDJjMGVhL2ltYWdlL2ltYWdlXkEyXkFqcGdeQXVyMTMxODk2OTU@._V1_.jpg",
#           "width": 675
#            },
#      "id": "tt0310793",     # <= IMDB ID
#      "l": "Toni Erdmann",   # <= The movie title
#      "q": "feature",        # <= type of resource, one of [feature, TV series, video, short, TV short], might be missing, example: https://v2.sg.media-imdb.com/suggestion/b/blade%20runner.json
#      "qid": "movie",        # <= slugified version of the "q" result
#      "rank": 11288,         # <= Result relevance ranking, sorted in ascending order
#      "s": "Sandra Hüller, Peter Simonischek",    # <= Main actors
#      "y": 2016              # <= Year released
#      "v": [                 # <= List of trailers/teasers/videos applicable for the item
#              {
#                "i": {
#                  "height": 360,
#                  "imageUrl": "https://m.media-amazon.com/images/M/MV5BNDQ5MTU4MDQtOTdkNS00NWQwLWE5ODMtZWQ4Y2QwYzIzMDE0XkEyXkFqcGdeQXVyNzU1NzE3NTg@._V1_.jpg",
#                  "width": 480
#                },
#                "id": "vi2814050585",        # <= use this with "https://www.imdb.com/video/vi2814050585?playlistId=tt0310793"
#                "l": "Bowling for Columbine",
#                "s": "2:07"
#              }
#            ],
#}
def lookupItemInIMDB(item_title, item_year, item_type, sample_duration_sec, total_episode_num, isIcelandic, imdb_orignal_titles):
  if item_title is None or len(item_title) < 1:
    return None

  # Determine the feature type to favor
  imdb_item_types = ['feature'] # Default

  # According to the oscars website > A short film is defined as an original motion picture that has a running time of 40 minutes or less, including all credits.
  # We use 45min as a safety buffer as there can be filler content before and after the films official length on the VOD.
  if item_type == 'movie':
    imdb_item_types = ['short'] if sample_duration_sec > 0 and sample_duration_sec < 2700 else ['feature', 'tv movie']
  elif item_type == 'documentary':
    imdb_item_types = ['short'] if sample_duration_sec > 0 and sample_duration_sec < 2700 else ['feature', 'tv special']
  elif item_type == 'tvshow':
    # We should distinguis between multi season series and mini series, 
    # One definition > Limited series last longer, usually between 6 and 12 episodes, while a miniseries is typically 4-6 episodes, sometimes broadcast in blocks of two to create more of an event for the viewer.
    #   > A miniseries always has a predetermined number of episodes while a series is developed to continue for several seasons.
    imdb_item_types = ['mini-series', 'tv mini-series'] if total_episode_num > 1 and total_episode_num <= 6 else ['tv series']
  
  try:
    r = __create_retry_session().get(f"https://v2.sg.media-imdb.com/suggestion/x/{urllib.parse.quote(item_title)}.json?includeVideos=1")
    if( r.status_code != 200 ): 
      return None # If the status is not success then terminate
  except:
    # If we have a failure in the IMDB api we do not want to fail RUV, just silently ignore this
    return None

  data = r.json()

  # If no results then exit
  if not 'd' in data or data['d'] is None or len(data['d']) < 1:
    return None

  # We remove all matches that do not have a covery photo, unlikely that it is going to be a great match
  # also remove matches that do not have any actors starring in it
  matches = [obj for obj in data['d'] if 'i' in obj and 'q' in obj and 's' in obj and len(obj['s']) > 2 and str(obj['id']).startswith('tt')]
  num_matches = len(matches)
  if num_matches <= 0:
    return None

  # Augment the remaining matches with their original titles from the titles cache if it is available
  if not imdb_orignal_titles is None and len(imdb_orignal_titles) > 0:
    for m in matches:
      org_title = imdb_orignal_titles[m['id']] if m['id'] in imdb_orignal_titles else None
      if not org_title is None:
        m['lo'] = org_title

  result = None
  found_via = "Nothing"
  item_title_lower = item_title.lower()

  # If there is an single exact name match for primary title, we pick that
  if 1 == sum(('l' in obj and item_title_lower == obj['l'].lower()) for obj in matches):
    result = next((obj for obj in matches if 'l' in obj and item_title_lower == obj['l'].lower()), None)
    found_via = "Exact primary title"

  if result is None and 1 == sum(('lo' in obj and item_title_lower == obj['lo'].lower()) for obj in matches):
    result = next((obj for obj in matches if 'lo' in obj and item_title_lower == obj['lo'].lower()), None)
    found_via = "Exact original title"

  # Special case for icelandic movies, they are extremly likely to be the first result if searched by the icelandic name
  #if isIcelandic and item_type == 'movie':
  #  result = matches[0]
  #  found_via = "First match (Icelandic Movie)"

  # If there is a single slightly fuzzy name match, we pick that
  if result is None and 1 == sum(('l' in obj and fuzz.ratio( item_title_lower, obj['l'].lower() ) > 85) for obj in matches):
    result = next((obj for obj in matches if 'l' in obj and fuzz.ratio( item_title_lower, obj['l'].lower() ) > 85), None)
    found_via = "Similar primary title, single match"
  
  # If there is a single slightly fuzzy name match, we pick that
  if result is None and 1 == sum(('lo' in obj and fuzz.ratio( item_title_lower, obj['lo'].lower() ) > 85) for obj in matches):
    result = next((obj for obj in matches if 'lo' in obj and fuzz.ratio( item_title_lower, obj['lo'].lower() ) > 85), None)
    found_via = "Similar original title, single match"

  # Attempt to find a match in the list with a similar name and type
  if result is None:
    result = next((obj for obj in matches if 'l' in obj and fuzz.ratio( item_title_lower, obj['l'].lower() ) > 85 and 'q' in obj and str(obj['q']).lower() in imdb_item_types), None)
    found_via = "Similar primary title and type, first match"

  # Attempt to find a match in the list with a similar name and type
  if result is None:
    result = next((obj for obj in matches if 'lo' in obj and fuzz.ratio( item_title_lower, obj['lo'].lower() ) > 85 and 'q' in obj and str(obj['q']).lower() in imdb_item_types), None)
    found_via = "Similar original title and type, first match"

  # Still no match, attempt to find one with a matching year if it is specified
  if result is None and not item_year is None: 
    result = next((obj for obj in matches if 'q' in obj and str(obj['q']).lower() in imdb_item_types and 'y' in obj and item_year in str(obj['y'])), None)
    found_via = "Same type and year, first match"

  # If there is only a single element in the list then it is likely to be it, for Icelandic movies this is very often the case
  if result is None and num_matches == 1:
    result = next((obj for obj in matches if 'q' in obj and str(obj['q']).lower() in imdb_item_types), None)
    found_via = "Only result"

  # If not a movie or short film then exit
  if result is None:
    return None

  # If no IMDB id then exit
  if not 'id' in result or result['id'] is None:
    return None

  ret_obj = {
    "id": result['id'] if 'id' in result else None,
    "title": result['l'] if 'l' in result else None,
    "actors": result['s'] if 's' in result else None,
    "year": result['y'] if 'y' in result else None,
    "image" : result['i']['imageUrl'] if 'i' in result and 'imageUrl' in result['i'] else None,
    "foundvia": found_via
  }

  if 'v' in result and type(result['v']) is list and len(result['v']) > 0 and "id" in result["v"][0]:
    ret_obj["video"] = {
                          "id": result["v"][0]["id"],
                          "title": result["v"][0]["l"] if "l" in result["v"][0] else None,
                          "length": result["v"][0]["s"] if "s" in result["v"][0] else None
                        }

  return ret_obj

# Downloads the image poster for a movie
# See naming guidelines: https://support.plex.tv/articles/200220677-local-media-assets-movies/#toc-2
def downloadMoviePoster(local_filename, display_title, item, output_path):
  poster_url = item['portrait_image'] if 'portrait_image' in item and not item['portrait_image'] is None else item['series_image'] if 'series_image' in item and not item['series_image'] is None else None
  if poster_url is None:
    return

  poster_dir = Path(local_filename).parent.absolute()

  # If the poster dir is the root directory we do not want to save the poster there
  if Path(poster_dir).samefile(str(output_path)):
    return

  # Note RUV currently always has JPEGs
  poster_filename = f"{poster_dir}{sep}poster.jpg"

  download_file(poster_url, poster_filename, f"Movie artwork for {item['title']}")
  

# Downloads the image and season posters for episodic content
def downloadTVShowPoster(local_filename, display_title, item, output_path):
  episode_poster_url = item['episode_image'] if 'episode_image' in item and not item['episode_image'] is None else None
  series_poster_url = item['portrait_image'] if 'portrait_image' in item and not item['portrait_image'] is None else item['series_image'] if 'series_image' in item and not item['series_image'] is None else None

  # Download the episode poster
  if not episode_poster_url is None:
    episode_poster_name = local_filename.split(".mp4")[0]
    episode_poster_filename = f"{episode_poster_name}.jpg"
    download_file(episode_poster_url, episode_poster_filename, f"Episode artwork for {item['title']}")

  # Download the series poster  
  if not series_poster_url is None: 
    series_poster_dir = Path(local_filename).parent.parent.absolute() # Go up one directory (i.e. not in Season01 but in the main series folder)

    # If the poster dir is the root directory we do not want to save the poster there
    if not Path(series_poster_dir).samefile(str(output_path)):
      series_poster_filename = f"{series_poster_dir}{sep}poster.jpg"
      # Do not override a poster that is already there
      if not Path(series_poster_filename).exists():
        download_file(series_poster_url, series_poster_filename, f"Series artwork for {item['series_title']}")
    
# Downloads all available subtitle files
def downloadSubtitlesFiles(subtitles, local_video_filename, video_display_title, video_item):
  for subtitle in subtitles:

    # See naming guidelines https://support.plex.tv/articles/200471133-adding-local-subtitles-to-your-media/
    subtitle_filename = "{0}.{1}.vtt".format( local_video_filename.split(".mp4")[0], subtitle['name'])
    download_file(subtitle['value'], subtitle_filename, "{1}: Subtitles for: {0}".format(Path(local_video_filename).stem, subtitle['name']))

# Downloads a file using Requests
# From: http://stackoverflow.com/a/16696317
def download_file(url, local_filename, display_title, keeppartial = False ):
  try:
    # NOTE the stream=True parameter
    r = __create_retry_session().get(url, stream=True)
    
    # If the status is not success then terminate
    if( r.status_code != 200 ):
      return None
    
    with open(local_filename, 'wb') as f:
      for chunk in r.iter_content(chunk_size=1024): 
        if chunk: # filter out keep-alive new chunks
          f.write(chunk)
    
    return local_filename
  except Exception as ex:
    print(os.linesep) # Double new line as otherwise the error message is squished to the download progress
    print(ex)
    traceback.print_stack()
    if( not keeppartial ):
      print( "Interrupted: Deleting partial file '{0}'".format(ntpath.basename(local_filename)))
      try:
        os.remove(local_filename)
      except:
        print( "Could not delete partial file. Please remove the file manually '{0}'".format(local_filename))
        raise
    raise

# Creates a new retry session for the HTTP protocol
# See: https://www.peterbe.com/plog/best-practice-with-retries-with-requests
def __create_retry_session(retries=5):
  session = requests.Session()
  retry = Retry(
    total=retries,
    read=retries,
    connect=retries,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504))
  adapter = HTTPAdapter(max_retries=retry)
  session.mount('http://', adapter)
  session.mount('https://', adapter)
  return session

# Attempts to discover the correct playlist file
def find_m3u8_playlist_url(item, display_title, video_quality):
  
  # use default headers
  headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'}

  # Store the program id
  pid = item['pid']

  # June 2022 : New alternate simpler VOD url format
  #    https://ruv-vod.akamaized.net/lokad/5237328T0/3600/index.m3u8

  if not 'vod_url' in item or not 'vod_url_full' in item:
    print( "{0} is not available through VOD (pid={1})".format(color_title(display_title), pid))
    return None

  # Plan
  # 1. Download the file from the vod_url_full and check it's contents
  #    the contents actually tell us if we are dealing with the old stream format which has multiple lines containing the different streams, 
  #    ex. 
  #       #EXT-X-STREAM-INF:CLOSED-CAPTIONS=NONE,BANDWIDTH=530000,RESOLUTION=426x240,CODECS="mp4a.40.2,avc1.640015",AUDIO="audio-aacl-50"
  #       asset-audio=50000-video=450000.m3u8?tlm=hls&streams=2022/02/06/2400kbps/5209577T0.mp4.m3u8:2400,2022/02/06/500kbps/5209577T0.mp4.m3u8:500,2022/02/06/800kbps/5209577T0.mp4.m3u8:800,2022/02/06/1200kbps/5209577T0.mp4.m3u8:1200,2022/02/06/3600kbps/5209577T0.mp4.m3u8:3600&AliasPass=ruv-vod-app-dcp-v4.secure.footprint.net
  #
  #    or if it is the new simpler format that only refers the index file
  #    ex. 
  #       #EXT-X-STREAM-INF:BANDWIDTH=4406504,CODECS="avc1.640028,mp4a.40.2",RESOLUTION=1920x1080,FRAME-RATE=25.000,AUDIO="2@48000-mp4a-0"
  #       3600/index.m3u8

  url_first_file = item['vod_url_full']

  try:
    # Perform the first get
    request = __create_retry_session().get(url_first_file, stream=False, timeout=5, verify=False, headers=headers)
    if request is None or not request.status_code == 200 or len(request.text) <= 0:
      print( "{0} not found on server (first file, pid={1}, url={2})".format(color_title(display_title), pid, url_first_file))
      return None

    # Assume the new format
    url_formatted = '{0}/{1}/index.m3u8'.format(item['vod_url'], QUALITY_BITRATE[video_quality]['code']) 

    # Check if this actually is the old format
    if request.text.find('.m3u8?tlm=hls&streams') > 0:
      url_formatted = '{0}/asset-audio=50000-video={1}.m3u8'.format(item['vod_url'], QUALITY_BITRATE[video_quality]['bits'])       

    # Do the second request to get the actual stream data in the correct format
    request = __create_retry_session().get(url_formatted, stream=False, timeout=5, verify=False, headers=headers)
    if request is None or not request.status_code == 200 or len(request.text) <= 0:
      print( "{0} not found on server (second file, pid={1}, url={2})".format(color_title(display_title), pid, url_formatted))
      return None

    # Count the number of fragments in the file, used to estimate download time
    fragments = [line.strip() for line in request.text.splitlines() if len(line) > 1 and line[0] != '#']

    # We found a playlist file, let's return the url and the fragments
    return {'url': url_formatted, 'fragments':len(fragments)}

  except Exception as ex:
    print( "Error while discovering playlist for {1} from '{0}'".format(url_formatted, color_title(display_title)))
    print( ex )
    traceback.print_stack()
    return None

# FFMPEG download of the playlist
def download_m3u8_playlist_using_ffmpeg(ffmpegexec, playlist_url, playlist_fragments, local_filename, display_title, keeppartial, video_quality, disable_metadata, videoInfo):
  prog_args = [ffmpegexec]

  # Don't show copyright header
  prog_args.append("-hide_banner")

  # Don't show excess logging (only things that cause the exe to terminate)
  prog_args.append("-loglevel")
  prog_args.append("verbose") 
  
  # Force showing progress indicator text
  prog_args.append("-stats") 

  # Overwrite any prompts with YES
  prog_args.append("-y")

  # Add the input url
  prog_args.append('-i')
  prog_args.append(playlist_url)

  # conversion configuration
  prog_args.append('-c')
  prog_args.append('copy')
  prog_args.append('-bsf:a')
  prog_args.append('aac_adtstoasc')

  # Create the metadata for the output file (note: This must appear after the input source, above, is defined)
  # see https://kdenlive.org/en/project/adding-meta-data-to-mp4-video/ and https://kodi.wiki/view/Video_file_tagging
  if not disable_metadata:

    # Ensure that the local filename ends with a .mp4
    if not local_filename.endswith('.mp4'):
      local_filename += '.mp4'

    # Determine the description for the file
    ep_description = ''

    # Find the series description and favour the longer description
    series_description = videoInfo['desc'] if videoInfo['desc'] is not None else videoInfo['series_desc'] if 'series_desc' in videoInfo  else None
    if 'series_sdesc' in videoInfo and videoInfo['series_sdesc'] is not None:
      if( series_description is None or (videoInfo['series_sdesc'] is not None and len(videoInfo['series_sdesc']) > len(series_description))):
        series_description = videoInfo['series_sdesc']

    # Description for movies, we want the longer version of
    if videoInfo['is_movie'] or videoInfo['is_docu']:
      ep_description = series_description
    
    # Description for epsiodic content (do not use the series description)
    if len(ep_description) <= 0 and 'description' in videoInfo['episode'] and len(videoInfo['episode']['description']) > 4 :
      ep_description = videoInfo['episode']['description']

    # If there is no description then we use the series as a fallback
    if len(ep_description) < 4:
      ep_description = series_description

    if videoInfo['is_sport']:
      ep_description = f"{ep_description.rstrip('.')}. Sýnt {str(videoInfo['showtime'])[8:10]}.{str(videoInfo['showtime'])[5:7]}.{str(videoInfo['showtime'])[:4]} kl.{(videoInfo['showtime'][11:16]).replace(':','.')}"

    prog_args.append("-metadata")
    prog_args.append("{0}={1}".format('title', sanitizeFileName(videoInfo['title'] if videoInfo['is_movie'] or videoInfo['is_docu'] or videoInfo['is_sport'] else videoInfo['episode_title']) )) #The title of this video. (String)	
    prog_args.append("-metadata")
    #prog_args.append("{0}={1}".format('comment', sanitizeFileName(videoInfo['desc']) ))  #A (content) description of this video.
    prog_args.append("{0}={1}".format('comment', 'ruvinfo:{0}:{1}'.format(str(videoInfo['pid']), str(videoInfo['sid']))))  #The program id and series id for the video, prefixed with ruvinfo for easier parsing
    prog_args.append("-metadata")
    prog_args.append("{0}={1}".format('synopsis', sanitizeFileName(ep_description) ))  #A synopsis, a longer description of this video

    if (not videoInfo['is_movie'] and not videoInfo['is_docu']) or videoInfo['is_sport']:
      prog_args.append("-metadata")
      prog_args.append("{0}={1}".format('show', sanitizeFileName(videoInfo['series_title']) )) #The name of the TV show,

    if (videoInfo['is_movie'] or videoInfo['is_docu']) and 'imdb' in videoInfo and not videoInfo['imdb'] is None:
      if 'year' in videoInfo['imdb'] and not videoInfo['imdb']['year'] is None:
        prog_args.append("-metadata")
        prog_args.append("{0}={1}".format('date', videoInfo['imdb']['year'] )) # The year of the movie or documentary as reported by IMDB

    if not videoInfo['is_movie'] and not videoInfo['is_docu']:
      prog_args.append("-metadata")
      prog_args.append("{0}={1}".format('episode_id', videoInfo['ep_num']))  #Either the episode name or episode number, for display.
      prog_args.append("-metadata")
      prog_args.append("{0}={1}".format('episode_sort', int(videoInfo['ep_num'])))  #This element is for sorting only, but never displayed. It allows numerical sorting of episode names that are strings, but not (necessarily) numbers. The valid range is limited to 0 to 255 only,
      prog_args.append("-metadata")
      prog_args.append("{0}={1}".format('season_number', int(videoInfo['season_num'])))  #The season number, in the range of 0 to 255 only

    prog_args.append("-metadata")
    prog_args.append("{0}={1}".format('media_type', "Movie" if videoInfo['is_movie'] or videoInfo['is_docu'] else 'Sports' if videoInfo['is_sport'] else "TV Show"))  #The genre this video belongs to. (String)	

    # Add the RUV specific identifier metadata, this can be used by other tooling to identify the entry
    # Note: These tags get dropped by ffmpeg unless the use_metadata_tag switch is used, but when that is used the 
    #       standard tags above stop working, so the solution is to encode this data into the comment field instead. 
    #       shitty solution but the easiest to maintain compatibility
    #prog_args.append("-movflags")
    #prog_args.append("use_metadata_tags") # Necessary to turn on custom MP4 video tags (without it ffmpeg doesn't write tags it doesn't understand)
    #prog_args.append("-metadata")
    #prog_args.append("{0}={1}".format('ruvpid', str(videoInfo['pid'])))  #Program identifier
    #prog_args.append("-metadata")
    #prog_args.append("{0}={1}".format('ruvsid', str(videoInfo['sid'])))  #Season identifier
    
  # Finally the output file path
  prog_args.append(local_filename)

  # Force a UTF8 environment for the subprocess so that files with non-ascii characters are read correctly
  # for this to work we must not use the universal line endings parameter
  my_env = os.environ
  my_env['PYTHONIOENCODING'] = 'utf-8'

  # Some counting for progress bars
  total_chunks = playlist_fragments
  completed_chunks = 0
  total_size = QUALITY_BITRATE[video_quality]['chunk_size'] * total_chunks
  total_size_mb = str(int(total_size/1024.0/1024.0))

  print("{0} | Estimated: {1} MB".format(color_title(display_title), total_size_mb))
  printProgress(completed_chunks, total_chunks, prefix = 'Downloading:', suffix = 'Starting', barLength = 25)

  # Run the app and collect the output
  # print(prog_args)
  ret = subprocess.Popen(prog_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, env=my_env)
  try:
    while True:
      try:
        line = ret.stdout.readline()
        if not line:
          break
        line = line.strip()
        if ' Opening \'{0}'.format(RUV_URL) in line:
          completed_chunks += 1
          printProgress(min(completed_chunks, total_chunks), total_chunks, prefix = 'Downloading:', suffix = 'Working ', barLength = 25)
      except UnicodeDecodeError:
        continue # Ignore all unicode errors, don't care!

    # Ensure that the return code was ok before continuing
    # Check if child process has terminated. Set and return returncode attribute. Otherwise, returns None.
    retcode = ret.poll()
    while retcode is None:
      retcode = ret.poll()
  except KeyboardInterrupt:
    ret.terminate()
    raise

  printProgress(total_chunks, total_chunks, prefix = 'Downloading:', suffix = 'Complete -> {0}'.format(local_filename), barLength = 25, color = False)
  # Write one extra line break after operation finishes otherwise the subsequent prints will end up in the same line
  sys.stdout.write('\n')

  # If the process returned ok then return the local name otherwise a None to signify an error
  if ret.returncode == 0:
    return local_filename
  return None
  
def printTvShowDetails(args, show):
  if( not 'pid' in show ):
    return

  # Mark all VOD sourced shows
  vodmark = ' - '+ color_sid('VOD') if 'vod_dlcode' in show else ''

  print( color_pid(show['pid'])+ ": "+color_title(createShowTitle(show, args.originaltitle)) + vodmark)
  print( color_sid(show['sid'].rjust(7)) + ": Sýnt "+show['showtime'][:-3] )
  if( args.desc and 'desc' in show and show['desc'] is not None ):
    for desc_line in textwrap.wrap(show['desc'], width=60):
      print( "           "+color_description(desc_line) )
  print("")
  
def parseArguments():
  parser = argparse.ArgumentParser()
  
  parser.add_argument("-o", "--output", help="The path to the folder where the downloaded files should be stored",
                                        type=str)
  
  parser.add_argument("--suffix", help="Optional suffix to append to the output filename (useful if for some reason some files are named the same), NOTE make sure the suffix starts with a space character!",
                                  default="",
                                  type=str)

  parser.add_argument("--sid", help="The series ids for the tv series that should be downloaded",
                               type=str, nargs="+")
  parser.add_argument("--pid", help="The program ids for the program entries that should be downloaded",
                               type=str, nargs="+")

  parser.add_argument("-q", "--quality", help="The desired quality of the downloaded episode, default is 'Normal' which is Standard-Definition",
                                         choices=list(QUALITY_BITRATE.keys()),
                                         default="HD1080",
                                         type=str)
  
  parser.add_argument("-f", "--find", help="Searches the TV schedule for a program matching the text given",
                               type=str) 

  parser.add_argument("--refresh", help="Refreshes the TV schedule data", action="store_true")

  parser.add_argument("--imdbfolder", help="Folder storing the downloaded and unzipped title.basics.tsv database snapshot from IMDB, see https://www.imdb.com/interfaces/", 
                                      type=str)

  parser.add_argument("--incremental", help="Performs fast incremental intra-day refreshes. Setting this switch instructs the refresh mechanism to only download information for items that are new since the last full TV schedule refresh from the same day. This option has no effect and a full refresh is performed if the date of this refresh is newer than the latest refresh data. ", action="store_true")

  parser.add_argument("--plex", help="Creates Plex Media Server compatible file names and folder structures. See https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/", action="store_true")

  parser.add_argument("--force", help="Forces the program to re-download shows", action="store_true")
  
  parser.add_argument("--list", help="Only lists the items found but nothing is downloaded", action="store_true")
  
  parser.add_argument("--desc", help="Displays show description text when available", action="store_true")

  parser.add_argument("--keeppartial", help="Keep partially downloaded files if the download is interrupted (default is to delete partial files)", action="store_true")

  parser.add_argument("--checklocal", help="Checks to see if a local file with the same name already exists. If it exists then it is not re-downloaded but it's pid is stored in the recorded log (useful if moving between machines or if recording history is lost)'", action="store_true")
  
  parser.add_argument("-d", "--debug", help="Prints out extra debugging information while script is running", action="store_true")

  parser.add_argument("-p","--portable", help="Saves the tv schedule and the download log in the current directory instead of {0}".format(LOG_DIR), action="store_true")

  parser.add_argument("--new", help="Filters the list of results to only show recently added shows (shows that have just had their first episode aired)", action="store_true")

  parser.add_argument("--originaltitle", help="Includes the original title of the show in the filename if it was found (this is usually the foreign title of the series or movie)", action="store_true")

  parser.add_argument("--nometadata", help="Disables embedding mp4 metadata about the movie or the TV show, default is on. Only disable this if you are having problems with this feature.", action="store_true")

  parser.add_argument("--novideo", help="Disables downloading of video content, restricts behavior to only downloading metadata, posters and subtitles.", action="store_true")

  #parser.add_argument("--preferenglishsubs", help="Prefers downloading entries that have burnt in English subtitles available. This is true for some special schedule items. By default this is off.", action="store_true")

  parser.add_argument("--ffmpeg",       help="Full path to the ffmpeg executable file", 
                                        type=str)

  return parser.parse_args()
 
# Appends the config directory to config file names
def createFullConfigFileName(portable, file_name):
  if portable :
    return "./{0}".format(file_name)
  else:
    return "{0}/{1}".format(LOG_DIR,file_name)

# Saves a list of program ids to a file
def appendNewPidAndSavePreviouslyRecordedShows(new_pid, previously_recorded_pids, rec_file_name):

  # Store the new pid in memory first
  previously_recorded_pids.append(new_pid)

  # Make sure that the directory exists and then write the full list of pids to it
  os.makedirs(os.path.dirname(rec_file_name), exist_ok=True)

  with open(rec_file_name, 'w+') as theFile:
    for item in previously_recorded_pids:
      theFile.write("%s\n" % item)

# Gets a list of program ids from a file
def getPreviouslyRecordedShows(rec_file_name):
  rec_file = Path(rec_file_name)
  if rec_file.is_file():
    lines = [line.rstrip('\n') for line in rec_file.open('r+')]
    return lines
  else:
    return []

def saveCurrentTvSchedule(schedule,tv_file_name):
  today = datetime.date.today()

  # Format the date field
  schedule['date'] = today.strftime('%Y-%m-%d')

  #make sure that the log directory exists
  os.makedirs(os.path.dirname(tv_file_name), exist_ok=True)

  with open(tv_file_name, 'w+', encoding='utf-8') as out_file:
    out_file.write(json.dumps(schedule, ensure_ascii=False, sort_keys=True, indent=2*' '))

def saveImdbCache(imdb_cache, imdb_cache_file_name):
  os.makedirs(os.path.dirname(imdb_cache_file_name), exist_ok=True)

  with open(imdb_cache_file_name, 'w+', encoding='utf-8') as out_file:
    out_file.write(json.dumps(imdb_cache, ensure_ascii=False, sort_keys=True, indent=2*' '))
  
def getExistingJsonFile(file_name):
  try:
    tv_file = Path(file_name)
    if tv_file.is_file():
      with tv_file.open('r+',encoding='utf-8') as in_file:
        existing = json.load(in_file)
      
      return existing
    else:
      return None
  except Exception as ex:
    print(f"Could not open '{file_name}', {ex})")
    return None

def getExistingTvSchedule(tv_file_name):
  try:
    tv_file = Path(tv_file_name)
    if tv_file.is_file():
      with tv_file.open('r+',encoding='utf-8') as in_file:
        existing = json.load(in_file)
      
      # format the date field
      existing['date'] = datetime.datetime.strptime(existing['date'], '%Y-%m-%d')
      
      return existing
    else:
      return None
  except:
    print("Could not open existing tv schedule, downloading new one (invalid file at "+tv_file_name+")")
    return None
    
def sanitizeFileName(local_filename, sep=" "):
  #These are symbols that are not "kosher" on a NTFS filesystem.
  local_filename = re.sub(r"[\.\,\';\"/:<>|?*\n\r\t\x00]", sep, local_filename)
  return local_filename.strip()

# Removes a substring from end of string, see https://stackoverflow.com/a/3663505/779521
def rchop(s, suffix):
  if not type(suffix) is list:
    suffix = [suffix]
  for suff in suffix:
    if suffix and s.endswith(suff):
        return s[:-len(suff)]
  return s

def createShowTitle(show, include_original_title=False, use_plex_formatting=False):
  show_title = sanitizeFileName(show['title'])

  # Always include original title if using plex formatting, but we only want the series title, without the (1 af xxx)
  if( use_plex_formatting ):
    
    # If plex we always want to get out of the default title as the default includes the (1 af 2) suffix
    show_title = sanitizeFileName(show['series_title'])

    # Append the original if it is available (usually that contains more accurate season info than the icelandic title)
    if( 'original-title' in show and not show['original-title'] is None ):
      show_title = "{0} - {1}".format(sanitizeFileName(show['series_title']), rchop(sanitizeFileName(show['original-title']), [' I', ' II', ' III', ' IV', ' V', ' VI', ' VII', ' VIII', ' IX']))
  
  # If not plex then adhere to the original title flag if set
  elif( include_original_title and 'original-title' in show and not show['original-title'] is None ):
    return "{0} - {1}".format(sanitizeFileName(show['title']), sanitizeFileName(show['original-title']))
    
  return show_title

RE_CAPTURE_YEAR_FROM_DESCRIPTION = re.compile(r' frá (?P<year>\d{4})', re.IGNORECASE)

def createLocalFileName(show, include_original_title=False, use_plex_formatting=False, file_name_suffix=""):
  # Create the show title
  show_title = createShowTitle(show, include_original_title, use_plex_formatting)

  if( use_plex_formatting ):
    original_title = ' ({0})'.format(sanitizeFileName(show['original-title'])) if 'original-title' in show and not show['original-title'] is None else ""
    series_title = show['series_title']

    imdb_id_part = ''
    imdb_year_part = ''

    if 'imdb' in show and not show['imdb'] is None and 'id' in show['imdb'] and len(show['imdb']['id']) > 0:
      imdb = show['imdb']
      # Enrich the format if a match is found
      imdb_id_part = f" {{imdb-{imdb['id']}}}" if not imdb['id'] is None else ''
      imdb_year_part = f" ({imdb['year']})" if not imdb['year'] is None else ''

    if ('is_movie' in show and show['is_movie'] is True) or ('is_docu' in show and show['is_docu'] is True): 
      # Dealing with a movie for sure, it may be episodic and therefore should use the "partX" notation
      # described here: https://support.plex.tv/articles/naming-and-organizing-your-movie-media-files/#toc-3
      # Examples:
      #   \show_title\series_title (original-title) - part1.mp4
      #   \show_title\series_title (original-title) - part2.mp4
      if( 'ep_num' in show and 'ep_total' in show and int(show['ep_total']) > 1):
        return f"{sanitizeFileName(show_title)}{file_name_suffix}{sep}{sanitizeFileName(series_title)}{original_title}{file_name_suffix}{imdb_year_part}{imdb_id_part} - part{str(show['ep_num']).zfill(2)}"
      else:
        # Just normal single file movie
        return f"{sanitizeFileName(show_title)}{file_name_suffix}{sep}{sanitizeFileName(series_title)}{original_title}{file_name_suffix}{imdb_year_part}{imdb_id_part}"
    elif( 'is_sport' in show and show['is_sport']):
      # Special handling for sporting events
      # Example
      #   \show_title\Season 2022\title - showtime[:10].mp4 unless the showtime is already present in the title of the episode
      sport_show_title = sanitizeFileName(show['title'])
      
      formatted_showtime = f"{str(show['showtime'])[8:10]}.{str(show['showtime'])[5:7]}.{str(show['showtime'])[:4]}"
      if (
         not show['showtime'][:10] in sport_show_title and 
         not str(show['showtime'][:10]).replace('-','.') in sport_show_title and # Icelandic dates usually include dots and not dashes
         not formatted_showtime in sport_show_title  # Icelandic dates are usually on the form dd.mm.yyyy not yyyy.mm.dd
        ):
        sport_show_title = f"{sport_show_title} ({formatted_showtime})"
      return f"{sanitizeFileName(show_title)}{sep}Season 01{sep}{sport_show_title.replace(':','.')}{file_name_suffix}"
    elif( 'ep_num' in show and 'ep_total' in show and int(show['ep_total']) > 1):
      # This is an episode 
      # Plex formatting creates a local filename according to the rules defined here
      # https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/
      # Note: We do not santitize the 
      # Examples:
      #   \show_title\Season 01\series_title (original-title) - s01e01.mp4
      # or 
      #    \show_title\Season 01\series_title (original-title) - showtime [pid].mp4
      return "{0}{sep}Season {4}{sep}{1}{2} - s{4}e{3}{file_name_suffix}{imdb_id_part}".format(sanitizeFileName(show_title), sanitizeFileName(series_title), original_title, str(show['ep_num']).zfill(2), str(show['season_num'] if 'season_num' in show else 1).zfill(2), sep=sep, imdb_id_part=imdb_id_part, file_name_suffix=file_name_suffix)
    else:
      return "{0}{sep}{1}{2} - {3} - [{4}]{file_name_suffix}{imdb_id_part}".format(sanitizeFileName(show_title), sanitizeFileName(series_title), original_title, sanitizeFileName(show['showtime'][:10]), sanitizeFileName(show['pid']), sep=sep, imdb_id_part=imdb_id_part, file_name_suffix=file_name_suffix)
      
  else:
    # Create the local filename, if not multiple episodes then
    # append the date and pid to the filename to avoid conflicts
    if( 'ep_num' in show ):
      local_filename = "{0}{1}".format(show_title, file_name_suffix)
    else:
      local_filename = "{0} - {1} ({2}){3}".format(show_title, show['showtime'][:10], show['pid'], file_name_suffix)

  # Clean up any possible characters that would interfere with the local OS filename rules
  return "{0}.mp4".format(sanitizeFileName(local_filename))

def isLocalFileNameUnique(local_filename):
  # Check to see if the filename specified already exists, must be a complete path
  ###########################
  # Using glob as I allow partial renaming of the file as long as the original part is left untouched
  # Meaning you can rename files to "Original Show Name (2 of 4) HERE IS MY CUSTOM EXTRA NAME.mp4"
  fileSearchString = local_filename.split(".mp4")[0]+"*.mp4"
  retval = glob.glob(fileSearchString)
  return not retval

#
# Locates the ffmpeg executable and returns a full path to it
def findffmpeg(path_to_ffmpeg_install=None, working_dir=None):
  if not path_to_ffmpeg_install is None and os.path.isfile(path_to_ffmpeg_install):
    return path_to_ffmpeg_install

  # Attempts to search for it under the bin folder
  bin_dist = os.path.join(working_dir, "..","bin","ffmpeg.exe" if platform.system() == 'Windows' else 'ffmpeg')
  if os.path.isfile(bin_dist):
    return str(Path(bin_dist).resolve())
  
  # Attempt to find ffmpeg in the environment
  try:
      return utilities.get_ffmpeg_location()
  except Exception:
      pass # Ignoring the exception
  
  # Throw an error
  raise ValueError('Could not locate FFMPEG install, please use the --ffmpeg switch to specify the path to the ffmpeg executable on your system.')

# Regex to extract the necessary VOD data from the files url
RE_CAPTURE_VOD_EPNUM_FROM_TITLE = re.compile(r'(?P<ep_num>\d+) af (?P<ep_total>\d+)', re.IGNORECASE)

#
# Downloads the full front page VOD schedule and for each episode in there fetches all available episodes
# uses the new RUV GraphQL queries
def getVodSchedule(existing_schedule, args_incremental_refresh=False, imdb_cache=None, imdb_orignal_titles=None):

  # Start with getting all the series available on RUV through their API, this gives us basic information about each of the series
  # https://api.ruv.is/api/programs/tv/all
  # as of 2024-01-15 this API is now 
  # https://api.ruv.is/api/programs/featured/tv

  # Now for each series we request the series information, to obtain more than the basic info, 
  # note: today there is a single episode returned which cannot be used when dealing with multi episode series, we should request all episodes as a second call
  # https://api.ruv.is/api/programs/get_ids/32978

  ruv_api_url_all = 'https://api.ruv.is/api/programs/featured/tv'
  r = __create_retry_session().get(ruv_api_url_all)  
  api_data = r.json()

  # Now the api returns everything categorised into panels
  all_panel_data= api_data['panels'] if 'panels' in api_data else None

  data = []
  # Combine all 
  for panel_data in all_panel_data:
    if 'programs' in panel_data:
      data.extend(panel_data['programs'])

  # Remove all duplicate series from the list
  data = list({item['id']:item for item in data}.values())

  schedule = {}  

  # If we are dealing with incremental refresh then start by storing our existing schedule
  if args_incremental_refresh:
    schedule = existing_schedule

  if r.status_code != 200  or data is None or len(data) < 1:
    return schedule
  
  if not data or len(data) <=0:
    return schedule

  # Filter out all programs that do not have any vod files to download and have an id field
  panels = [p for p in data if 'web_available_episodes' in p and 'id' in p and p['web_available_episodes'] > 0]

  completed_programs = 0
  total_programs = len(panels)
  
  print("{0} | Total: {1} series available".format(color_title('Downloading VOD schedule'), total_programs))
  printProgress(completed_programs, total_programs, prefix = 'Reading:', suffix = '', barLength = 25)

  # Now iterate first through every group and for every thing in the group request all episodes for that 
  # item (there is no programmatic way of distinguishing between how many episodes there are)
  for program in panels:
    completed_programs += 1

    #if str(program['id']) != '32957': 
    #  continue

    # If incremental, then check if we already have this series if we don't we want to add it, 
    # if we have the series check if the web_available_episodes match if not then we want to re-add it
    if args_incremental_refresh:
      existing_vod_episodes_count = sum(type(schedule[p]) is dict and schedule[p]['sid'] == str(program['id']) for p in schedule)
      if( program['web_available_episodes'] <= existing_vod_episodes_count and existing_vod_episodes_count > 0 ):
        continue
      else:
        existing_vs_new_diff = program['web_available_episodes'] - existing_vod_episodes_count
        printProgress(completed_programs, total_programs, prefix = 'Detected {0} new entries for {1}:'.format(existing_vs_new_diff, color_sid(program['title'])), suffix ='', barLength = 25)

    # Add all details for the given program to the schedule
    try:
      # We want to not override existing items in the schedule dictionary in case they are downloaded again
      program_schedule = getVodSeriesSchedule(program['id'], program, imdb_cache, imdb_orignal_titles)
      # This joining of the two dictionaries below is necessary to ensure that 
      # the existing items are not overwritten, therefore schedule is appended to the new list, existing items overwriting any new items.
      #schedule = dict(list(program_schedule.items()) + list(schedule.items())) 
      schedule.update(program_schedule) # Want to override existing keys again!
    except Exception as ex:
        print( "Unable to retrieve schedule for VOD program '{0}', no episodes will be available for download from this program.".format(program['title']))
        print(traceback.format_exc())
        continue
    printProgress(completed_programs, total_programs, prefix = 'Reading:', suffix ='', barLength = 25)

  return schedule

def requestsVodDataRetrieveWithRetries(graphdata):
  retries_left = 3

  while True:
    retries_left = retries_left - 1
    r = requests.get(
      url='https://www.ruv.is/gql/'+graphdata, 
      headers={'content-type': 'application/json', 'Referer' : 'https://www.ruv.is/sjonvarp', 'Origin': 'https://www.ruv.is' })
    data = json.loads(r.content.decode())

    if 'data' in data:
      return data

    if retries_left <= 0:
      return None

    if not 'errors' in data:
      print("Unexpected data in VOD download reply, "+str(data))
      return None

    # OK we will try again, but first we sleep a little bit to throttle the requests
    time.sleep(3)

#
# Replaces image size macro in cover art URLs with a high res version
# example: 
# From:
#    https://d38kdhuogyllre.cloudfront.net/fit-in/$$IMAGESIZE$$x/filters:quality(65)/hd_posters/878lr8-89tmhg.jpg
# To: 
#    https://d38kdhuogyllre.cloudfront.net/fit-in/2048x/filters:quality(65)/hd_posters/878lr8-89tmhg.jpg
def formatCoverArtResolutionMacro(rawsrc):
  if rawsrc is None or len(rawsrc) < 1:
    return None

  return str(rawsrc).replace('$$IMAGESIZE$$','2048')

#
# Given a series id and program data, downloads all episodes available for that series
def getVodSeriesSchedule(sid, _, imdb_cache, imdb_orignal_titles):
  schedule = {}  

  # Perform two lookups, first to the API as this gives us a more complete information about the series, but unfortunately no episode data
  ruv_api_url_sid = 'https://api.ruv.is/api/programs/program/{0}/all'.format(sid)

  r = __create_retry_session().get(ruv_api_url_sid)  
  prog = r.json()  
  if r.status_code != 200 or prog is None or not 'episodes' in prog or len(prog['episodes']) < 1:
    return schedule
  
  # Fix the image and portrait image fields as they come pre-formatted from the API
  prog['image'] = prog['image'].replace('/480x/', '/$$IMAGESIZE$$x/') if 'image' in prog and not prog['image'] is None else None
  prog['portrait_image'] = prog['portrait_image'].replace('/480x/', '/$$IMAGESIZE$$x/') if 'portrait_image' in prog and not prog['portrait_image'] is None else None
  prog['description'] = ' '.join(prog['description']) if type(prog['description']) is list else prog['description'] # The API returns the description as a list, join all lines into a single string

  # We flatten the categories out into only a list of the slugs so it is easier to match
  prog['cat_slugs'] = []
  prog['cat_names'] = []
  for pcat in prog['categories']:
    prog['cat_slugs'].append(pcat['slug'])
    prog['cat_names'].append(pcat['title'])

  # Check if the categories have known names
  isMovie = True if 'kvikmyndir' in prog['cat_slugs'] and not 'leiknir-thaettir' in prog['cat_slugs'] else False
  isDocumentary = True if 'heimildarmyndir' in prog['cat_slugs'] else False
  isSport = True if 'ithrottir' in prog['cat_slugs'] else False
  isEnglishSubtitlesEntry = True if 'with English subtitles' in prog['title'] else False

  # Determine the type
  series_type = "documentary" if isDocumentary else "movie" if isMovie else "tvshow" if not isSport or 'leiknir-thaettir' in prog['cat_slugs'] else None

  # Only trim out the season number if we are not dealing with movies, otherwise we will trim off the number in movies such as "Die Hard 1" and "Die Hard 2" and they'll just be "Die Hard"
  series_title = prog['title'] if isMovie else trimSeasonNumberSuffix(prog['title'])
  series_title_wseason = prog['title']
  series_description = prog['short_description']
  series_shortdescription = prog['description'] if prog['description'] is not None else series_description
  series_image = formatCoverArtResolutionMacro(prog['image']) if 'image' in prog else None
  portrait_image = formatCoverArtResolutionMacro(prog['portrait_image']) if 'portrait_image' in prog else None
  foreign_title = prog['foreign_title']
  total_episodes = len(prog['episodes'])
  imdb_result = None

  # Is it icelandic?
  isIcelandic = str(series_description).lower().startswith('íslensk')

  # First check to see if the series sid is present in the imdb_cache file
  # if it is then we already have our imdb data, if not then we have to look it up
  if not imdb_cache is None and str(sid) in imdb_cache:
    imdb_cache_entry = imdb_cache[str(sid)]
    imdb_result = imdb_cache_entry['imdb']

  # 
  # Attempt to find the entry in IMDB if possible, but only for foreign titles, i.e. movies and shows that 
  # have a foreign title set
  if imdb_result is None and not series_type is None and len(series_type) > 0 and not 'born' in prog['cat_slugs'] :
    # Attempt to extract the year from the description field
    series_year = getGroup(RE_CAPTURE_YEAR_FROM_DESCRIPTION, 'year', series_shortdescription)

    # Sample the duration of the first episode, this is used to determine if a movie is a short or not
    sample_duration_sec = prog['episodes'][0]['duration'] if 'duration' in prog['episodes'][0] else 0

    # Determine if multiepisodic and how many episodes there are
    detected_num = getGroup(RE_CAPTURE_VOD_EPNUM_FROM_TITLE, 'ep_total', prog['episodes'][0]['title'] if not prog['episodes'][0]['title'] is None else series_title )
    total_episode_num = max(int(prog['web_available_episodes']), int(detected_num) if not detected_num is None else 1 ) if 'multiple_episodes' in prog and prog['multiple_episodes'] else 1
    
    imdb_result = None
    # first check the foreign title, this is most likely to result in a match
    if imdb_result is None and not foreign_title is None:
      imdb_result = lookupItemInIMDB(foreign_title, series_year, series_type, sample_duration_sec, total_episode_num, isIcelandic, imdb_orignal_titles)

    # Icheck the local title AND ONLY IF THIS IS A MOVIE.
    # this condition will be mostly true for icelandic movies and documentaries, this is also true when RUV incorrectly enters their data
    #  and places the english name in the series and the icelandic name in the foreign title!, which is very common.
    if imdb_result is None and not series_title is None and isMovie:
      imdb_result = lookupItemInIMDB(series_title, series_year, series_type, sample_duration_sec, total_episode_num, isIcelandic, imdb_orignal_titles)

    # If the imdb result was found then store it in the corrections file for later reuse
    if not imdb_result is None:
      imdb_cache[str(sid)] = {
        'series_id': sid,
        'original-title': foreign_title, 
        'series_title': series_title, 
        'imdb': imdb_result
      }

  for episode in prog['episodes']:
    entry = {}

    entry['imdb'] = imdb_result

    entry['series_title'] = series_title
    entry['series_desc'] = series_description
    entry['series_sdesc'] = series_shortdescription
    entry['series_image'] = series_image
    entry['portrait_image'] = portrait_image

    # Fix the episode description if needed
    episode['description'] = ' '.join(episode['description']) if type(episode['description']) is list else episode['description']
    # Fix episode title
    if episode['title'] is None: 
      #episode['title'] = series_title
      episode['title'] = ''

    entry['episode'] = episode
    entry['episode_title'] = episode['title']
    entry['episode_image'] = formatCoverArtResolutionMacro(episode['image'])
    entry['title'] = series_title
    entry['pid'] = str(episode['id'])
    entry['showtime'] = episode['firstrun']
    entry['duration'] = str(episode['duration']) if 'duration' in episode else ''
    entry['duration_friendly'] = episode['duration_friendly']
    entry['sid'] = str(sid)

    entry['desc'] = episode['description'] if 'description' in episode and len(episode['description']) > 10 else prog['short_description']
    entry['original-title'] = foreign_title

    # The file
    entry['file'] = episode['file']

    # Must format subtitles differently
    entry['subtitles_url'] = episode['subtitles_url']
    entry['subtitles'] = []
    for name in episode['subtitles']:
      if not episode['subtitles'][name] is None:
        entry['subtitles'].append({
          'name': name,
          'value': episode['subtitles'][name]
        })

    entry['has_subtitles'] = True if not entry['subtitles_url'] is None and len(entry['subtitles_url']) > 1 else False

    entry['eventid'] = episode['event']
    entry['rating'] = episode['rating']
    entry['slug'] = episode['slug']

    entry['is_movie'] = isMovie
    entry['is_sport'] = isSport
    entry['is_docu'] = isDocumentary

    entry['english_subtitled'] = isEnglishSubtitlesEntry

    entry['categories'] = prog['cat_names']
    entry['multiple_episodes'] = prog['multiple_episodes']
    entry['web_available_episodes'] = prog['web_available_episodes']

    entry['ep_num'] = str(episode['number']) if 'number' in episode else getGroup(RE_CAPTURE_VOD_EPNUM_FROM_TITLE, 'ep_num', episode['title'])
    if not entry['ep_num'] is None:
      entry['ep_num'] = str(entry['ep_num'])
    else:
      entry['ep_num'] = str(total_episodes)
    
    entry['ep_total'] = getGroup(RE_CAPTURE_VOD_EPNUM_FROM_TITLE, 'ep_total', episode['title'])
    if not entry['ep_total'] is None:
      entry['ep_total'] = str(entry['ep_total'])
    else: 
      entry['ep_total'] = str(len(prog['episodes']))

    # Attempt to parse out the season number, start with 1 as the default
    entry['season_num'] = '1'
    if str(series_title_wseason).endswith(' 2') or str(series_title_wseason).endswith(' II') or str(foreign_title).endswith(' II') or 'önnur þáttaröð' in str(entry['desc']).lower():
      entry['season_num'] = '2'
    elif str(series_title_wseason).endswith(' 3') or str(series_title_wseason).endswith(' III') or str(foreign_title).endswith(' III') or 'þriðja þáttaröð' in str(entry['desc']).lower():
      entry['season_num'] = '3'
    elif str(series_title_wseason).endswith(' 4') or str(series_title_wseason).endswith(' IV') or str(foreign_title).endswith(' IV') or 'fjórða þáttaröð' in str(entry['desc']).lower():
      entry['season_num'] = '4'
    elif str(series_title_wseason).endswith(' 5') or str(series_title_wseason).endswith(' V') or str(foreign_title).endswith(' V') or 'fimmta þáttaröð' in str(entry['desc']).lower():
      entry['season_num'] = '5'
    elif str(series_title_wseason).endswith(' 6') or str(series_title_wseason).endswith(' VI') or str(foreign_title).endswith(' VI') or 'sjötta þáttaröð' in str(entry['desc']).lower():
      entry['season_num'] = '6'
    elif str(series_title_wseason).endswith(' 7') or str(series_title_wseason).endswith(' VII') or str(foreign_title).endswith(' VII') or 'sjöunda þáttaröð' in str(entry['desc']).lower():
      entry['season_num'] = '7'
    elif str(series_title_wseason).endswith(' 8') or  str(series_title_wseason).endswith(' VIII') or str(foreign_title).endswith(' VIII') or 'áttunda þáttaröð' in str(entry['desc']).lower():
      entry['season_num'] = '8'
    elif str(series_title_wseason).endswith(' 9') or str(series_title_wseason).endswith(' IX') or str(foreign_title).endswith(' IX') or 'níunda þáttaröð' in str(entry['desc']).lower():
      entry['season_num'] = '9'
    elif str(series_title_wseason).endswith(' 10') or str(series_title_wseason).endswith(' XX') or str(foreign_title).endswith(' XX') or 'tíunda þáttaröð' in str(entry['desc']).lower():
      entry['season_num'] = '10'

    # Create the episode numbers programatically to ensure consistency if we're dealing with multi-episode program
    if not entry['ep_total'] is None and int(entry['ep_total']) > 1:
      entry['title'] = '{0} ({1} af {2})'.format(entry['title'], entry['ep_num'], entry['ep_total'])

    # If this is not a movie but a re-occuring episode then append the title (which is usually the date shown)
    # e.g. the news, kastljos, weather
    if entry['ep_total'] is None and not episode['firstrun'] is None and len(episode['firstrun']) > 1:
      entry['title'] = '{0} ({1})'.format(entry['title'], episode['firstrun'])

    # Special season handling for sporting events
    # Special title handling for sporting events
    if isSport:
      # Ensure that the year is in the title, because PLEX doesn't handle seasons that are longer than 3 digits, i.e. we cannot use 'Season 2022' there will just be garbage created, i.e. 'Season 230'
      if not str(entry['showtime'])[:4] in entry['series_title']:
        entry['series_title'] = f"{series_title} {str(entry['showtime'])[:4]}"

      # If the episode name is the date then we only append the timeportion
      if( entry['episode_title'] == f"{str(entry['showtime'])[8:10]}.{str(entry['showtime'])[5:7]}.{str(entry['showtime'])[:4]}"):
        entry['title'] = f"{entry['series_title']} ({entry['episode_title']}) kl.{(str(entry['showtime'])[11:16]).replace(':','.')}"  
      else: # we add the date as well
        # Add the subtitle into the final title of the episode, i.e. to include dates or the teams playing, use the full show time at the end with the HH:mm
        entry['title'] = f"{entry['series_title']} ({entry['episode_title']}) {str(entry['showtime'])[8:10]}.{str(MONTH_NAMES[int(entry['showtime'][5:7])])} kl.{(str(entry['showtime'])[11:16]).replace(':','.')}"

      # We cannot use seasons numbers that are longer than 999 as there are only three digits allowed for season numbers
      entry['sport_season'] = entry['showtime'][:4] if 'showtime' in entry and not entry['showtime'] is None and len(entry['showtime']) > 4 else str(date.today().year)

    schedule[entry['pid']] = entry

    # Decrease the episode count
    total_episodes = total_episodes - 1

  return schedule

#
# Removes any season number related suffixes for a given series title
# Ex. Monsurnar 1 => Monsurnar   
#     Hvolpasveitin IV => Hvolpasveitin
def trimSeasonNumberSuffix(series_title):
  prefixes = [' I', ' II', ' III', ' IV', ' V', ' VI', ' VII', ' VIII', ' IX', ' X', ' XI', ' XII', ' 1', ' 2', ' 3', ' 4', ' 5', ' 6', ' 7', ' 8', ' 9', ' 10', ' 11', ' 12']
  for prefix in prefixes:
    new_series_title = series_title.removesuffix(prefix)
    if len(new_series_title) < len(series_title):
      return new_series_title
    series_title = new_series_title

  return series_title
    


def getGroup(regex, group_name, haystack):
  for match in re.finditer(regex, haystack):
    match_value = match.group(group_name).strip()
    if len(match_value) > 0:
      return match_value
  return None

# Attempts to load the IMDB enhancment files from the given imdb path
# this is optional and if the files are not present then this enhancement information will not be available
def loadImdbOriginalTitles(args_imdbfolder):
  imdb_title_cache = {}

  if not args_imdbfolder or args_imdbfolder is None:
    print(color_warn(f"The '--imdbfolder' argument is not set, this will impact IMDB matching for non-english content, consider setting this parameter and downloading the 'title.basics.tsv' file from https://www.imdb.com/interfaces/"))
    return imdb_title_cache

  if not os.path.exists(args_imdbfolder):
    print(color_error(f"The IMDB path {args_imdbfolder} does not exist, no additional information from IMDB will be available, to enable download the title.basics.tsv file from https://www.imdb.com/interfaces/"))
    return imdb_title_cache

  imdb_basics_file_path = os.path.join(args_imdbfolder, "title.basics.tsv")
  if not os.path.isfile(imdb_basics_file_path):
    print(color_error(f"Unable to locate the basics database file at {imdb_basics_file_path}, no additional information from IMDB will be available, to enable download the title.basics.tsv file from https://www.imdb.com/interfaces/"))
    return imdb_title_cache

  # Check the age of the file on disk and print out a warning if it is more than 6 months old
  if isFileOlderThan(imdb_basics_file_path, datetime.timedelta(days=183)):
    print(color_warn(f"The '{imdb_basics_file_path}' file is older than 6 months, consider downloading a newer 'title.basics.tsv' file from https://www.imdb.com/interfaces/"))
  
#  title.basics.tsv.gz - Contains the following information for titles:
#    tconst (string) - alphanumeric unique identifier of the title
#    titleType (string) – the type/format of the title (e.g. movie, short, tvseries, tvepisode, video, etc)
#    primaryTitle (string) – the more popular title / the title used by the filmmakers on promotional materials at the point of release
#    originalTitle (string) - original title, in the original language
#    isAdult (boolean) - 0: non-adult title; 1: adult title
#    startYear (YYYY) – represents the release year of a title. In the case of TV Series, it is the series start year
#    endYear (YYYY) – TV Series end year. ‘\N’ for all other title types
#    runtimeMinutes – primary runtime of the title, in minutes
#    genres (string array) – includes up to three genres associated with the title

  print(color_info("Processing IMDB data files")+ f" | Folder {args_imdbfolder}")

  printProgress(0, 100, prefix = 'Estimating size:', suffix = 'Working', barLength = 25)
  total_lines = countLinesInFile(imdb_basics_file_path)
  curr_line = 0

  with open(imdb_basics_file_path, encoding="utf8") as f:
    for line in f:
      curr_line += 1

      if( curr_line == 1 or curr_line % 10000 == 0):
        printProgress(curr_line, total_lines, prefix = 'Reading Original Titles:', suffix = f" | item {curr_line:,} of {total_lines:,}", barLength = 25)

      (tconst, titleType, primaryTitle, originalTitle, isAdult, startYear, endYear, runtimeMinutes, genres) = line.split('\t')      

      # Skip all lines that have an invalid IDENTIFIER or have '\N' missing indicator in critical fields
      if not tconst.startswith('tt') or originalTitle == '\\N' or primaryTitle == '\\N' or startYear == '\\N':
        continue

      if int(startYear) <= 1930 or not isAdult == '0':
        continue

      if primaryTitle == originalTitle:
        continue

      imdb_title_cache[tconst] = originalTitle

  printProgress(total_lines, total_lines, prefix = 'Reading Original Titles:', suffix = f" | Processed {total_lines:,} items           ", barLength = 25)
  print()

  return imdb_title_cache
    
# The main entry point for the script
def runMain():
  try:
    init() # Initialize the colorama library
    
    today = datetime.date.today()

    # Get the current working directory (place that the script is executing from)
    working_dir = sys.path[0]
    
    # Construct the argument parser for the commandline
    args = parseArguments()

    # Get ffmpeg exec
    ffmpegexec = findffmpeg(args.ffmpeg, working_dir)

    # Create the full filenames for the config files
    previously_recorded_file_name = createFullConfigFileName(args.portable,PREV_LOG_FILE)
    tv_schedule_file_name = createFullConfigFileName(args.portable,TV_SCHEDULE_LOG_FILE)
    
    # Get information about already downloaded episodes
    previously_recorded = getPreviouslyRecordedShows(previously_recorded_file_name)

    # Get an existing tv schedule if possible
    schedule = getExistingTvSchedule(tv_schedule_file_name)
    
    if( args.refresh or schedule is None  ):
    
      # Only load the IMDB data if we are refreshing the schedule
      imdb_orignal_titles = loadImdbOriginalTitles(args.imdbfolder)
      imdb_cache_file_name = createFullConfigFileName(args.portable, IMDB_CACHE_FILE)
      imdb_cache = getExistingJsonFile(imdb_cache_file_name)
      if( imdb_cache is None ):
        imdb_cache = {}

      # Only clear out the schedule if we are not dealing with an incremental update
      # or if the dates don't match anymore 
      if not args.incremental or schedule['date'].date() < today or args.force:
        schedule = {}
      
      # Downloading the full VOD available schedule as well, signal an incremental update if the schedule object has entries in it
      schedule = getVodSchedule(schedule, len(schedule) > 0, imdb_cache, imdb_orignal_titles) 
    
      # Save the tv schedule as the most current one, save it to ensure we format the today date
      if len(schedule) > 1 :
        saveCurrentTvSchedule(schedule, tv_schedule_file_name)

      if len(imdb_cache) > 0:
        saveImdbCache(imdb_cache, imdb_cache_file_name)

    if( args.debug ):
      for key, schedule_item in schedule.items():
        printTvShowDetails(args, schedule_item)
      
    # Now determine what to download
    download_list = []
    
    for key, schedule_item in schedule.items():
    
      # Skip any items that aren't show items
      if key == 'date' or not 'pid' in schedule_item:
        continue
      
      candidate_to_add = None
      # if the series id is set then find all shows belonging to that series
      if( args.sid is not None ):
        if( 'sid' in schedule_item and schedule_item['sid'] in args.sid):
          candidate_to_add = schedule_item
      elif( args.pid is not None ):
        if( 'pid' in schedule_item and schedule_item['pid'] in args.pid):
          candidate_to_add = schedule_item
      elif( args.find is not None ):
        if( 'title' in schedule_item and fuzz.partial_ratio( args.find, createShowTitle(schedule_item, args.originaltitle) ) > 85 ):
          candidate_to_add = schedule_item
        elif( 'title' in schedule_item and fuzz.partial_ratio( args.find, schedule_item['title'] ) > 85 ):
          candidate_to_add = schedule_item
        elif( 'original-title' in schedule_item and not schedule_item['original-title'] is None and fuzz.partial_ratio( args.find, schedule_item['original-title'] ) > 85 ):
          candidate_to_add = schedule_item
      else:
        # By default if there is no filtering then we simply list everything in the schedule
        candidate_to_add = schedule_item

      # If the only new episode filter is set then only include shows that have recently started airing
      if( args.new ):
        # If the show is not a repeat show or hasn't got more than a single episode in total then it isn't considered a show so exclude it
        if( not 'ep_num' in schedule_item or not 'ep_total' in schedule_item or int( schedule_item['ep_total']) < 2 or int(schedule_item['ep_num']) > 1 ):
          candidate_to_add = None # If the show is beyond ep 1 then it cannot be considered a new show so i'm not going to add it

      # Now process the adding of the show if all the filter criteria were satisified
      if( candidate_to_add is not None ):
          download_list.append(candidate_to_add)
      
    total_items = len(download_list)
    if( total_items <= 0 ):
      print(f"Nothing found to download for {color_title(args.find) if args.find is not None else color_sid(args.sid) if args.sid is not None else color_pid(args.pid) if args.pid is not None else color_title('[No search term entered]')}")
      sys.exit(0)
      
    print( "Found {0} show(s)".format(total_items, ))
      
    # Sort the download list by show name and then by showtime
    download_list = sorted(download_list, key=itemgetter('pid', 'title'))
    download_list = sorted(download_list, key=itemgetter('showtime'), reverse=True)
    
    # Now a special case for the list operation
    # Simply show a list of all the episodes found and then terminate
    if( args.list ):
      for item in download_list:
        printTvShowDetails(args, item)
      sys.exit(0)
    
    curr_item = 1
    for item in download_list:
      # Get a valid name for the save file
      local_filename = createLocalFileName(item, args.originaltitle, args.plex, args.suffix)
      
      # Create the display title for the current episode (used in console output)
      display_title = "{0} of {1}: {2}".format(curr_item, total_items, createShowTitle(item, args.originaltitle)) 
      curr_item += 1 # Count the file

      # If the output directory is set then check if it exists and create it if it is not
      # pre-pend it to the file name then
      if( args.output is not None ):
        if not os.path.exists(args.output):
          os.makedirs(args.output, exist_ok=True)
        # Now prepend the directory to the filename
        local_filename = os.path.join(args.output, local_filename)

      # Check to see if the directory structure up to the final filename exists (in case the original local_filename included directories)
      if not os.path.exists(local_filename):
        Path(local_filename).parent.mkdir(parents=True, exist_ok=True)

      #############################################
      # First download the URL for the listing if needed
      if not 'file' in item or item['file'] is None or len(item['file']) < 1 or not str(item['file']).startswith(RUV_URL):
        ep_graphdata = '?operationName=getProgramType&variables={"id":'+str(item['sid'])+',"episodeId":["'+str(item['pid'])+'"]}&extensions={"persistedQuery":{"version":1,"sha256Hash":"9d18a07f82fcd469ad52c0656f47fb8e711dc2436983b53754e0c09bad61ca29"}}'
        data = requestsVodDataRetrieveWithRetries(ep_graphdata)     
        if data is None or len(data) < 1:
          print("Error: Could not retrieve episode download url, unable to download VOD details, skipping "+item['title'])
          continue
        
        if not data or not 'data' in data or not 'Program' in data['data'] or not 'episodes' in data['data']['Program'] or len(data['data']['Program']['episodes']) < 1:
          print("Error: Could not retrieve episode download url, VOD did not return any data, skipping "+item['title'])
          continue

        ep_data = data['data']['Program']['episodes'][0] # First and only item
        vod_url_full = ep_data['file']
      else:
        vod_url_full = item['file']

      try:
        item['vod_url_full'] = vod_url_full

        # Store any references to subtitle files if available
        if not 'subtitles' in item and item['subtitles'] is None:
          item['subtitles'] = ep_data['subtitles'] if 'subtitles' in ep_data else None

        # If no VOD code can be found then this cannot be downloaded
        if vod_url_full is None:
          print("Error: Could not locate VOD download URL in VOD data, skipping "+item['title'])
          continue

        # Get the base of the VOD url
        item['vod_url'] = getGroup(RE_VOD_BASE_URL, 'vodbase', vod_url_full)

      except:
        print("Error: Could not retrieve episode download url due to parsing error in VOD data, skipping "+item['title'])
        continue

      if not args.novideo:
        # If the file has already been registered as downloaded then don't attempt to re-download
        if( not args.force and item['pid'] in previously_recorded ):
          print("'{0}' already recorded (pid={1})".format(color_title(display_title), item['pid']))
          continue

        # Before we attempt to download the file we should make sure we're not accidentally overwriting an existing file
        if( not args.force and not args.checklocal):
          # So, check for the existence of a file with the same name, if one is found then attempt to give
          # our new file a different name and check again (append date and time), if still not unique then 
          # create file name with guid, if still not unique then fail!
          if( not isLocalFileNameUnique(local_filename) ):
            # Check with date
            local_filename = "{0}_{1}.mp4".format(local_filename.split(".mp4")[0], datetime.datetime.now().strftime("%Y-%m-%d"))
            if( not isLocalFileNameUnique(local_filename)):
              local_filename = "{0}_{1}.mp4".format(local_filename.split(".mp4")[0], str(uuid.uuid4()))
              if( not isLocalFileNameUnique(local_filename)):      
                print("Error: unabled to create a local file name for '{0}', check your output folder (pid={1})".format(color_title(display_title), item['pid']))
                continue

        # If the checklocal option is enabled then we don't want to try to download unless force is set
        if( not args.force and args.checklocal and not isLocalFileNameUnique(local_filename) ):
          # Store the id as already recorded and save to the file 
          print("'{0}' found locally and marked as already recorded (pid={1})".format(color_title(display_title), item['pid']))
          appendNewPidAndSavePreviouslyRecordedShows(item['pid'], previously_recorded, previously_recorded_file_name)
          continue

        #############################################
        # We will rely on ffmpeg to do the playlist download and merging for us
        # the tool is much better suited to this than manually merging as there
        # are always some corruption issues in the merged stream if done in code
        
        # Get the correct playlist url
        playlist_data = find_m3u8_playlist_url(item, display_title, args.quality)
        if playlist_data is None:
          print("Error: Could not download show playlist, not found on server. Try requesting a different video quality.")
          continue

        #print(playlist_data
        # Now ask FFMPEG to download and remux all the fragments for us
        result = download_m3u8_playlist_using_ffmpeg(ffmpegexec, playlist_data['url'], playlist_data['fragments'], local_filename, display_title, args.keeppartial, args.quality, args.nometadata, item)
        if( not result is None ):
          # if everything was OK then save the pid as successfully downloaded
          appendNewPidAndSavePreviouslyRecordedShows(item['pid'], previously_recorded, previously_recorded_file_name) 

      # Attempt to download artworks if available but only when plex is selected
      if args.novideo:
        print("Downloading only artworks and subtitle files")

      if args.plex : 
        if( item['is_movie'] or item['is_docu']):
          downloadMoviePoster(local_filename, display_title, item, Path(args.output))
        else: 
          downloadTVShowPoster(local_filename, display_title, item, Path(args.output))

      # Attempt to download any subtitles if available 
      if not item['subtitles'] is None and len(item['subtitles']) > 0:
        try:
          downloadSubtitlesFiles(item['subtitles'], local_filename, display_title, item)
        except Exception as ex:
          print("Error: Could not download subtitle files for item, "+item['title'])
          print(ex)
          traceback.print_stack()
          continue
    
  finally:
    deinit() #Deinitialize the colorama library
    

# If the script file is called by itself then execute the main function
if __name__ == '__main__':
  runMain()
