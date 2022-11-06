#!/usr/bin/env python
# coding=utf-8
__version__ = "8.1.0"
# When modifying remember to issue a new tag command in git before committing, then push the new tag
#   git tag -a v8.1.0 -m "v8.1.0"
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
import traceback   # For exception details
import textwrap # For text wrapping in the console window
from colorama import init, deinit # For colorized output to console windows (platform and shell independent)
from termcolor import colored # For shorthand color printing to the console, https://pypi.python.org/pypi/termcolor
from pathlib import Path # to check for file existence in the file system
import json # To store and load the tv schedule that has already been downloaded
import argparse # Command-line argument parser
import requests # Downloading of data from HTTP
import datetime, dateutil.relativedelta # Formatting of date objects and adjusting date ranges
from xml.etree import ElementTree  # Parsing of TV schedule XML data
from fuzzywuzzy import fuzz # For fuzzy string matching when trying to find programs by title or description
from operator import itemgetter # For sorting the download list items https://docs.python.org/3/howto/sorting.html#operator-module-functions
import ntpath # Used to extract file name from path for all platforms http://stackoverflow.com/a/8384788
import glob # Used to do partial file path matching (when searching for already downloaded files) http://stackoverflow.com/a/2225582/779521
import uuid # Used to generate a ternary backup local filename if everything else fails.

import urllib.request, urllib.parse # Downloading of data from URLs (used with the JSON parser)
import requests # Downloading of data from HTTP
from requests.adapters import HTTPAdapter # For Retrying
from requests.packages.urllib3.util.retry import Retry # For Retrying
import ssl
import http.client as http_client

import subprocess # To execute shell commands 

# Disable SSL warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Lambdas as shorthands for printing various types of data
# See https://pypi.python.org/pypi/termcolor for more info
color_title = lambda x: colored(x, 'cyan', 'on_grey')
color_pid_title = lambda x: colored(x, 'red', 'on_cyan')
color_pid = lambda x: colored(x, 'red')
color_sid = lambda x: colored(x, 'yellow')
color_description = lambda x: colored(x, 'white')

color_progress_fill = lambda x: colored(x, 'green')
color_progress_remaining = lambda x: colored(x, 'white')
color_progress_percent = lambda x: colored(x, 'green')

# The name of the directory used to store log files.  The directory will be located in the users home directory
LOG_DIR="{0}/{1}".format(os.path.expanduser('~'),'.ruvsarpur')

# Name of the log file containing the previously recorded shows
PREV_LOG_FILE = 'prevrecorded.log'
# Name of the log file containing the downloaded tv schedule
TV_SCHEDULE_LOG_FILE = 'tvschedule.json'

# The available bitrate streams
QUALITY_BITRATE = {
    "Very Low": { 'code': "500", 'bits': "450000", 'chunk_size' : 750000},
    "Low"     : { 'code': "800", 'bits': "750000", 'chunk_size' :1000000},
    "Normal"  : { 'code': "1200", 'bits': "1150000", 'chunk_size':1500000},
    "HD720"   : { 'code': "2400", 'bits': "2350000", 'chunk_size':2800000},
    "HD1080"  : { 'code': "3600", 'bits': "3550000", 'chunk_size':4000000}
}

# Parse the formats
#   https://ruv-vod.akamaized.net/opid/5234383T0/3600/index.m3u8
#   https://ruv-vod.akamaized.net/lokad/5240696T0/3600/index.m3u8
RE_VOD_URL_PARTS = re.compile(r'(?P<urlprefix>.*)(?P<rest>\/\d{3,4}\/index\.m3u8)', re.IGNORECASE)

# Parse just the base url from 
#   https://ruv-vod.akamaized.net/lokad/5240696T0/5240696T0.m3u8
# resulting in vodbase being = https://ruv-vod.akamaized.net/lokad/5240696T0
RE_VOD_BASE_URL = re.compile(r'(?P<vodbase>.*)\/(?P<rest>.*\.m3u8)', re.IGNORECASE)

RUV_URL = 'https://ruv-vod.akamaized.net'

# All the categories that will be downloaded by VOD, the first number determines the graphql query to use, 
# the second value the category name to use in the query.
vod_types_and_categories = [  # Note that this corresponds to the top level list of pages available (Sjonvarp, Utvarp, Krakkaruv, Ungruv)
  (1, 'tv'),
  (2, 'krakkaruv'),
  (2, 'ungruv')
]
             
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
    
# Downloads a file using Requests
# From: http://stackoverflow.com/a/16696317
def download_file(url, local_filename, display_title, keeppartial = False ):
  try:
    # NOTE the stream=True parameter
    r = requests.get(url, stream=True)
    
    # If the status is not success then terminate
    if( r.status_code != 200 ):
      return None
    
    total_size = int(r.headers['Content-Length'])
    total_size_mb = str(int(total_size/1024.0/1024.0))
    completed_size = 0
        
    print("{0} | Total: {1} MB".format(color_title(display_title), total_size_mb))
    printProgress(completed_size, total_size, prefix = 'Downloading:', suffix = 'Starting', barLength = 25)
    
    with open(local_filename, 'wb') as f:
      for chunk in r.iter_content(chunk_size=1024): 
        if chunk: # filter out keep-alive new chunks
          f.write(chunk)
          completed_size += 1024
          printProgress(completed_size, total_size, prefix = 'Downloading:', suffix = 'Working ', barLength = 25)
    
    # Write a final completed line for the progress bar to signify that the operation is done
    printProgress(completed_size, completed_size, prefix = 'Downloading:', suffix = 'Complete', barLength = 25, color = False)
    
    # Write one extra line break after operation finishes otherwise the subsequent prints will end up in the same line
    sys.stdout.write('\n')
    return local_filename
  except:
    print(os.linesep) # Double new line as otherwise the error message is squished to the download progress
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
def download_m3u8_playlist_using_ffmpeg(ffmpegexec, playlist_url, playlist_fragments, local_filename, display_title, keeppartial, video_quality):
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

  printProgress(total_chunks, total_chunks, prefix = 'Downloading:', suffix = 'Complete', barLength = 25, color = False)
  # Write one extra line break after operation finishes otherwise the subsequent prints will end up in the same line
  sys.stdout.write('\n')

  # If the process returned ok then return the local name otherwise a None to signify an error
  if ret.returncode == 0:
    return local_filename
  return None
  
def download_xml(url):
    r = requests.get(url)
    # If the status is not success then terminate
    if( r.status_code != 200 ):
      return None
          
    # https://docs.python.org/2/library/xml.etree.elementtree.html
    tree = ElementTree.fromstring(r.content)
        
    return tree
    
def getShowDetailsText(entry_xml):
  
  # Get the most basic show details text
  details_basic = entry_xml.find('description')
  details_orgtitle_el = entry_xml.find('original-title')
  
  if( not details_basic is None):
    return details_basic.text
  elif( not details_orgtitle_el is None):
    return details_orgtitle_el.text
    
  # Nothing was found
  return None
    
def getShowTimes(days_back = 0):
  today = datetime.date.today()
  if( days_back <= 0 ):
    # Default is getting all of last month, so subtract a whole month from the today date
    from_date = today - dateutil.relativedelta.relativedelta(months=1)
  else:
    from_date = today - dateutil.relativedelta.relativedelta(days=days_back)
  
  # Construct the URL for the last month and download the TV schedule
  #http://muninn.ruv.is/files/xml/ruv/2017-06-15/2017-07-09/
  #url = "http://muninn.ruv.is/files/xml/ruv/{0}/{1}/$download".format(from_date.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
  url = "http://muninn.ruv.is/files/xml/ruv/{0}/{1}/".format(from_date.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
    
  schedule = {}
  print("{0} | Since: {1}".format(color_title('Downloading TV schedule'), from_date.strftime('%Y-%m-%d')))
  schedule_xml = download_xml(url)
  if( schedule_xml is None):
    print("Could not download TV schedule, exiting")
    sys.exit(-1)
  
  # Iterate over every day in the tv schedule and collect the shows being shown
  # index this in a keyed dictionary
  
  for child in schedule_xml:
    if( not child.tag == "service" ):
      continue
    
    for entry_xml in child.iter('event'):
      entry = {}
      
      entry['title'] = entry_xml.find('title').text
      entry['pid'] = entry_xml.get('event-id')
      entry['showtime'] = entry_xml.get('start-time')
      entry['duration'] = entry_xml.get('duration')
      entry['sid'] = entry_xml.get('serie-id')
      
      # Get the show details text
      entry_details = getShowDetailsText(entry_xml)
      if( not entry_details is None ):
        entry['desc'] = entry_details

      # Get the original title of the show
      entry_org_title = entry_xml.find('original-title')
      if( not entry_org_title is None ):
        entry['original-title'] = entry_org_title.text

      # If the series id is nothing then it is not a show (e.g. dagskrárlok)
      if( not entry['sid'] ):
        continue
      
      cat = entry_xml.find('category')
      if(  not cat is None  ):
        entry['catid'] = cat.get('value')
        entry['cat'] = cat.text
      
      ep = entry_xml.find('episode')
      if( not ep is None ):
        entry['ep_num'] = ep.get('number')
        entry['ep_total'] = ep.get('number-of-episodes')
        if( int(entry['ep_total']) > 1 ):
          # Append the episode number to the show title if it is a real multi-episode show
          entry['title'] += " ("+entry['ep_num']+" af "+entry['ep_total']+")"
        #else:
          # If it isn't a multi episode show then append the date to the title (to avoid overwriting files)
          #entry['title'] += " ("+sanitizeFileName(entry['showtime'][:16], "") +")"
              
      # Save the entry into the main schedule
      schedule[entry['pid']] = entry
      
  return schedule
  
def printTvShowDetails(args, show):
  if( not 'pid' in show ):
    return

  # Mark all VOD sourced shows
  vodmark = ' - '+ color_sid('VOD') if 'vod_dlcode' in show else ''

  print( color_pid(show['pid'])+ ": "+color_title(createShowTitle(show, args.originaltitle)) + vodmark)
  print( color_sid(show['sid'].rjust(7)) + ": Sýnt "+show['showtime'][:-3] )
  if( args.desc and 'desc' in show ):
    for desc_line in textwrap.wrap(show['desc'], width=60):
      print( "           "+color_description(desc_line) )
  print("")
  
def parseArguments():
  parser = argparse.ArgumentParser()
  
  parser.add_argument("-o", "--output", help="The path to the folder where the downloaded files should be stored",
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
  local_filename = re.sub(r"[\"/:<>|?*\n\r\t\x00]", sep, local_filename)
  return local_filename

def createShowTitle(show, include_original_title=False, use_plex_formatting=False):
  show_title = show['title']

  # Always include original title if using plex formatting, but we only want the series title, without the (1 af xxx)
  if( use_plex_formatting ):
    
    # If plex we always want to get out of the default title as the default includes the (1 af 2) suffix
    show_title = show['series_title']

    # Append the original if it is available (usually that contains more accurate season info than the icelandic title)
    if( 'original-title' in show and not show['original-title'] is None ):
      show_title = "{0} - {1}".format(show['series_title'], show['original-title'])
  
  # If not plex then adhere to the original title flag if set
  elif( include_original_title and 'original-title' in show and not show['original-title'] is None ):
    return "{0} - {1}".format(show['title'], show['original-title'])
    
  return show_title

def createLocalFileName(show, include_original_title=False, use_plex_formatting=False):
  # Create the show title
  show_title = createShowTitle(show, include_original_title, use_plex_formatting)

  if( use_plex_formatting ):
    original_title = ' ({0})'.format(show['original-title']) if 'original-title' in show and not show['original-title'] is None else ""
    series_title = show['series_title']
    
    if 'is_movie' in show and show['is_movie'] is True: 
      # Dealing with a movie for sure, it may be episodic and therefore should use the "partX" notation
      # described here: https://support.plex.tv/articles/naming-and-organizing-your-movie-media-files/#toc-3
      # Examples:
      #   \show_title\series_title (original-title) - part1.mp4
      #   \show_title\series_title (original-title) - part2.mp4
      if( 'ep_num' in show and 'ep_total' in show and int(show['ep_total']) > 1):
        return "{0}/{1}{2} - part{3}.mp4".format(sanitizeFileName(show_title), sanitizeFileName(series_title), sanitizeFileName(original_title), show['ep_num'].zfill(2))
      else:
        # Just normal single file movie
        return "{0}/{1}{2}.mp4".format(sanitizeFileName(show_title), sanitizeFileName(series_title), sanitizeFileName(original_title))
    elif( 'ep_num' in show and 'ep_total' in show and int(show['ep_total']) > 1):
      # This is an episode 
      # Plex formatting creates a local filename according to the rules defined here
      # https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/
      # Note: We do not santitize the 
      # Examples:
      #   \show_title\Season 01\series_title (original-title) - s01e01.mp4
      # or 
      #    \show_title\Season 01\series_title (original-title) - showtime [pid].mp4
      return "{0}/Season 01/{1}{2} - s01e{3}.mp4".format(sanitizeFileName(show_title), sanitizeFileName(series_title), sanitizeFileName(original_title), show['ep_num'].zfill(2))
    else:
      return "{0}/{1}{2} - {3} - [{4}].mp4".format(sanitizeFileName(show_title), sanitizeFileName(series_title), sanitizeFileName(original_title), sanitizeFileName(show['showtime'][:10]), sanitizeFileName(show['pid']))
      
  else:
    # Create the local filename, if not multiple episodes then
    # append the date and pid to the filename to avoid conflicts
    if( 'ep_num' in show ):
      local_filename = "{0}.mp4".format(show_title)
    else:
      local_filename = "{0} - {1} ({2}).mp4".format(show_title, show['showtime'][:10], show['pid'])

  # Clean up any possible characters that would interfere with the local OS filename rules
  return sanitizeFileName(local_filename)

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
#  NOTE: Currently this only works  under Windows, need to change the discovery mechanism for linux/osx
def findffmpeg(path_to_ffmpeg_install=None, working_dir=None):
  if not path_to_ffmpeg_install is None and os.path.isfile(path_to_ffmpeg_install):
    return path_to_ffmpeg_install

  # Attempts to search for it under the bin folder
  bin_dist = os.path.join(working_dir, "..","bin","ffmpeg.exe")
  if os.path.isfile(bin_dist):
    return str(Path(bin_dist).resolve())
  
  # Throw an error
  raise ValueError('Could not locate FFMPEG install, please use the --ffmpeg switch to specify the path to the ffmpeg executable on your system.')

# Regex to extract the necessary VOD data from the files url
RE_CAPTURE_VOD_EPNUM_FROM_TITLE = re.compile(r'(?P<ep_num>\d+) af (?P<ep_total>\d+)', re.IGNORECASE)

#
# Downloads the full front page VOD schedule and for each episode in there fetches all available episodes
# uses the new RUV GraphQL queries
def getVodSchedule(panelType, categoryName):

  graphql_data = '?operationName=getFrontpage&variables={\"type\":\"'+categoryName+'\",\"limit\":600}&extensions={\"persistedQuery\":{\"version\":1,\"sha256Hash\":\"f640a5b54c853d6a071f7c3b27bf8c056854ab3200c1d35b0a624eb203dfc501\"}}'
  data = requestsVodDataRetrieveWithRetries(graphql_data)

  schedule = {}
  if data is None or len(data) < 1:
    return schedule
  
  if not data or not 'data' in data or not 'Featured' in data['data'] or not 'panels' in data['data']['Featured'] or len(data['data']['Featured']['panels']) <= 0:
    return schedule

  panels_iter_fields = data['data']['Featured']['panels']
  panels = []
  completed_programs = 0
  total_programs = 0
  for panel in panels_iter_fields:
    total_programs += len(panel['programs'])
    panels.append(panel)

  print("{0} | Total: {1} Series in {2}".format(color_title('Downloading VOD schedule'), total_programs, categoryName))
  printProgress(completed_programs, total_programs, prefix = 'Reading:', suffix = '', barLength = 25)

  # Now iterate first through every group and for every thing in the group request all episodes for that 
  # item (there is no programmatic way of distinguishing between how many episodes there are)
  for panel in panels:

    # Is the program a movie or an episode? Movies can also have multiple episodes (i.e. multi-part movies)
    # HEIMILDARMYNDIR, KVIKMYNDIR, ÁTT ÞÚ EFTIR AÐ SJÁ ÞESSAR?
    isMovie =  True if 'kvikmyndir' in panel['slug'] or 'att-thu-eftir-ad-sja-thessar' in panel['slug'] or 'heimildarmyndir' in panel['slug'] else False

    for program in panel['programs']:
      completed_programs += 1
      if program is None or not 'id' in program:
        continue

      # Add all details for the given program to the schedule
      try:
        schedule.update(getVodSeriesSchedule(program['id'], program, isMovie))
      except Exception as ex:
          print( "Unable to retrieve schedule for VOD program '{0}', no episodes will be available for download from this program.".format(program['title']))
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
# Given a series id and program data, downloads all 
# episodes available for that series
# isMovies parameter indicates if the programs belong to the list of known movie categories and should be treated as such
def getVodSeriesSchedule(sid, data, isMovies):
  
  graphdata = '?operationName=getEpisode&variables={"programID":'+str(sid)+'}&extensions={"persistedQuery":{"version":1,"sha256Hash":"f3f957a3a577be001eccf93a76cf2ae1b6d10c95e67305c56e4273279115bb93"}}'
  data = requestsVodDataRetrieveWithRetries(graphdata)

  schedule = {}
  if data is None or len(data) < 1:
    return schedule
  
  if not data or not 'data' in data or not 'Program' in data['data'] or len(data['data']['Program']) <= 0:
    return schedule

  prog = data['data']['Program']

  series_title = prog['title']
  foreign_title = prog['foreign_title']
  total_episodes = len(prog['episodes'])

  for episode in prog['episodes']:
    entry = {}

    entry['episode'] = episode
    entry['episode_title'] = episode['title']
    entry['series_title'] = series_title
    entry['title'] = series_title
    entry['pid'] = str(episode['id'])
    entry['showtime'] = episode['firstrun']
    entry['duration'] = str(episode['duration']) if 'duration' in episode else ''
    entry['sid'] = str(sid)
    entry['desc'] = episode['description'] if 'duration' in episode and len(episode['description']) > 10 else prog['short_description']
    entry['original-title'] = foreign_title

    entry['catid'] = "0"
    entry['cat'] = "VOD"

    entry['is_movie'] = isMovies

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

    # Create the episode numbers programatically to ensure consistency if we're dealing with multi-episode program
    if not entry['ep_total'] is None and int(entry['ep_total']) > 1:
      entry['title'] = '{0} ({1} af {2})'.format(entry['title'], entry['ep_num'], entry['ep_total'])

    # If this is not a movie but a re-occuring episode then append the title (which is usually the date shown)
    # e.g. the news, kastljos, weather
    if entry['ep_total'] is None and not episode['firstrun'] is None and len(episode['firstrun']) > 1:
      entry['title'] = '{0} ({1})'.format(entry['title'], episode['firstrun'])

    schedule[entry['pid']] = entry

    # Decrease the episode count
    total_episodes = total_episodes - 1

  return schedule

def getGroup(regex, group_name, haystack):
  for match in re.finditer(regex, haystack):
    match_value = match.group(group_name).strip()
    if len(match_value) > 0:
      return match_value
  return None
    
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
    if( not args.refresh ):
      schedule = getExistingTvSchedule(tv_schedule_file_name)
    
    if( args.refresh or schedule is None or schedule['date'].date() < today ):
      schedule = {}

      # Downloading the full VOD available schedule as well
      for typeValue, catName in vod_types_and_categories:
        try:
          schedule.update(getVodSchedule(typeValue, catName))
        except Exception as ex:
          print( "Unable to retrieve schedule for VOD category '{0}', no episodes will be available for download from this category.".format(catName))
          continue
      
    # Save the tv schedule as the most current one, save it to ensure we format the today date
    saveCurrentTvSchedule(schedule,tv_schedule_file_name)

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
      print("Nothing found to download")
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
      local_filename = createLocalFileName(item, args.originaltitle, args.plex)
      
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
      # First download the URL for the listing
      ep_graphdata = '?operationName=getProgramType&variables={"id":'+str(item['sid'])+',"episodeId":["'+str(item['pid'])+'"]}&extensions={"persistedQuery":{"version":1,"sha256Hash":"9d18a07f82fcd469ad52c0656f47fb8e711dc2436983b53754e0c09bad61ca29"}}'
      data = requestsVodDataRetrieveWithRetries(ep_graphdata)     
      if data is None or len(data) < 1:
        print("Error: Could not retrieve episode download url, unable to download VOD details, skipping "+item['title'])
        continue
      
      if not data or not 'data' in data or not 'Program' in data['data'] or not 'episodes' in data['data']['Program'] or len(data['data']['Program']['episodes']) < 1:
        print("Error: Could not retrieve episode download url, VOD did not return any data, skipping "+item['title'])
        continue

      try:
        ep_data = data['data']['Program']['episodes'][0] # First and only item
        vod_url_full = ep_data['file']
        item['vod_url_full'] = vod_url_full

        # If no VOD code can be found then this cannot be downloaded
        if vod_url_full is None:
          print("Error: Could not locate VOD download URL in VOD data, skipping "+item['title'])
          continue

        # Get the base of the VOD url
        item['vod_url'] = getGroup(RE_VOD_BASE_URL, 'vodbase', vod_url_full)

      except:
        print("Error: Could not retrieve episode download url due to parsing error in VOD data, skipping "+item['title'])
        continue

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
      result = download_m3u8_playlist_using_ffmpeg(ffmpegexec, playlist_data['url'], playlist_data['fragments'], local_filename, display_title, args.keeppartial, args.quality)
      if( not result is None ):
        # if everything was OK then save the pid as successfully downloaded
        appendNewPidAndSavePreviouslyRecordedShows(item['pid'], previously_recorded, previously_recorded_file_name) 
    
  finally:
    deinit() #Deinitialize the colorama library
    

# If the script file is called by itself then execute the main function
if __name__ == '__main__':
  runMain()
