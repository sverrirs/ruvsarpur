#!/usr/bin/env python
# coding=utf-8
__version__ = "1.2.0"
"""
Python script that allows you to download TV shows off the Icelandic RÚV Sarpurinn website.
The script is written in Python 3.5

See: https://github.com/sverrirs/ruvsarpur
Author: Sverrir Sigmundarson  info@sverrirs.com  https://www.sverrirs.com
"""

# Requires the following
#   pip install colorama
#   pip install termcolor
#   pip install python-dateutil
#   pip install requests
#   pip install simplejson
#   pip install fuzzywuzzy
#   pip install python-levenshtein
#      For alternative install http://stackoverflow.com/a/33163704


import sys, pprint, os.path, re
import textwrap # For text wrapping in the console window
from colorama import init, deinit # For colorized output to console windows (platform and shell independent)
from termcolor import colored, cprint # For shorthand color printing to the console, https://pypi.python.org/pypi/termcolor
from pathlib import Path # to check for file existence in the file system
import json # To store and load the tv schedule that has already been downloaded
import argparse # Command-line argument parser
import requests # Downloading of data from HTTP
import datetime, dateutil.relativedelta # Formatting of date objects and adjusting date ranges
from xml.etree import ElementTree  # Parsing of TV schedule XML data
from fuzzywuzzy import fuzz # For fuzzy string matching when trying to find programs by title or description
from operator import itemgetter, attrgetter # For sorting the download list items https://docs.python.org/3/howto/sorting.html#operator-module-functions
import ntpath # Used to extract file name from path for all platforms http://stackoverflow.com/a/8384788

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
PREV_LOG_FILE = "{0}/{1}".format(LOG_DIR,'prevrecorded.log')
# Name of the log file containing the downloaded tv schedule
TV_SCHEDULE_LOG_FILE = "{0}/{1}".format(LOG_DIR, 'tvschedule.json')

# The urls that should be tried when attempting to discover the actual video file on the server
EP_URLS = [
            'http://smooth.ruv.cache.is/lokad/{0}R{1}.mp4',
            'http://smooth.ruv.cache.is/opid/{0}R{1}.mp4'
          ]
             
# Print console progress bar
# http://stackoverflow.com/a/34325723
def printProgress (iteration, total, prefix = '', suffix = '', decimals = 1, barLength = 100, color = True):
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
      bar             = color_progress_fill('█' * filledLength) + color_progress_remaining('-' * (barLength - filledLength))
      sys.stdout.write('\r %s |%s| %s %s' % (prefix, bar, color_progress_percent(percents+'%'), suffix)),
    else:
      bar             = '█' * filledLength + '-' * (barLength - filledLength)
      sys.stdout.write('\r %s |%s| %s %s' % (prefix, bar, percents+'%', suffix)),
      
    if iteration == total:
        sys.stdout.write('\n')
    sys.stdout.flush()
    
# Downloads a file using Requests
# From: http://stackoverflow.com/a/16696317
def download_file(url, local_filename ):
    # NOTE the stream=True parameter
    r = requests.get(url, stream=True)
    
    # If the status is not success then terminate
    if( r.status_code != 200 ):
      return None
    
    total_size = int(r.headers['Content-Length'])
    total_size_mb = str(int(total_size/1024.0/1024.0))
    completed_size = 0
        
    print("{0} | Total: {1} MB".format(color_title(ntpath.basename(local_filename)), total_size_mb))
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

# Attempts to locate the video file for a certain program id on the server
# when the file is located it is downloaded and then the logic stops, if nothing is 
# found then this function returns None
def find_and_download_file(pid, local_filename ):

  for url in EP_URLS:
    for r in range(30):
      url_formatted = url.format(pid, r)
      if( not download_file(url_formatted, local_filename) is None ):
        return local_filename
    
  print( "{0} not found on server (pid={1})".format(color_title(ntpath.basename(local_filename)), pid))
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
    
def getShowtimes():
  today = datetime.date.today()
  # Subtract a whole month from the today date
  last_month = today - dateutil.relativedelta.relativedelta(months=1)
  
  # Construct the URL for the last month and download the TV schedule
  url = "http://muninn.ruv.is/files/xml/ruv/{0}/{1}/$download".format(last_month.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
  
  schedule = {}
  schedule['date'] = today

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
              
      # Save the entry into the main schedule
      schedule[entry['pid']] = entry
      
  return schedule
  
def printTvShowDetails(args, show):
  if( not 'pid' in show ):
    return
      
  print( color_pid(show['pid'])+ ": "+color_title(show['title']))
  print( color_sid(show['sid'].rjust(7)) + ": Sýnt "+show['showtime'][:-3] )
  if( args.desc and 'desc' in show ):
    for desc_line in textwrap.wrap(show['desc'], width=60):
      print( "           "+color_description(desc_line) )
  print("")
  
def parseArguments():
  parser = argparse.ArgumentParser()
  
  parser.add_argument("-o", "--output", help="The path to the folder where the downloaded files should be stored",
                                        type=str)
  parser.add_argument("--sid", help="The series id for the tv series that should be downloaded",
                               type=str)
  parser.add_argument("--pid", help="The program id for a specific program entry that should be downloaded",
                               type=str) 

  parser.add_argument("-c", "--category", 
                            choices=[1,2,3,4,5,6,7,9,13,17],
                            help="Limit the results to only shows in particular categories. Categories are: 1='Börn',2='Framhaldsþættir',3='Fréttatengt',4='Fræðsla',5='Íþróttir',6='Íslenskir þættir',7='Kvikmyndir',9='Tónlist',13='Samfélag',17='Menning'",
                            type=int)
  
  parser.add_argument("-f", "--find", help="Searches the TV schedule for a program matching the text given",
                               type=str)  
                               
  parser.add_argument("--days", help="Searches only shows shown in the past N number of days. E.g. if --days 1 then only shows shown yesterday will be searched.",
                               type=int)  

  parser.add_argument("--refresh", help="Refreshes the TV schedule data", action="store_true")
  
  parser.add_argument("--force", help="Forces the program to re-download shows", action="store_true")
  
  parser.add_argument("--list", help="Only lists the items found but nothing is downloaded", action="store_true")
  
  parser.add_argument("--desc", help="Displays show description text when available", action="store_true")
  
  parser.add_argument("-d", "--debug", help="Prints out extra debugging information while script is running", action="store_true")
  
  return parser.parse_args()
 
# Saves a list of program ids to a file
def savePreviouslyRecordedShows(pids):
  #make sure that the directory exists
  os.makedirs(os.path.dirname(PREV_LOG_FILE), exist_ok=True)

  with open(PREV_LOG_FILE, 'w+') as thefile:
    for item in pids:
      thefile.write("%s\n" % item)

# Gets a list of program ids from a file
def getPreviouslyRecordedShows():
  rec_file = Path(PREV_LOG_FILE)
  if rec_file.is_file():
    lines = [line.rstrip('\n') for line in rec_file.open('r+')]
    return lines
  else:
    return []

def saveCurrentTvSchedule(schedule):
  # Format the date field
  schedule['date'] = schedule['date'].strftime('%Y-%m-%d')

  #make sure that the log directory exists
  os.makedirs(os.path.dirname(TV_SCHEDULE_LOG_FILE), exist_ok=True)

  with open(TV_SCHEDULE_LOG_FILE, 'w+', encoding='utf-8') as out_file:
    out_file.write(json.dumps(schedule, ensure_ascii=False, sort_keys=True, indent=2*' '))
  
def getExistingTvSchedule():
  tv_file = Path(TV_SCHEDULE_LOG_FILE)
  if tv_file.is_file():
    with tv_file.open('r+',encoding='utf-8') as in_file:
      existing = json.load(in_file)
    
    # format the date field
    existing['date'] = datetime.datetime.strptime(existing['date'], '%Y-%m-%d')
    
    return existing
  else:
    return None
    
def sanitizeFileName(local_filename):

  #These are symbols that are not "kosher" on a NTFS filesystem.
  local_filename = re.sub(r"[\"/:<>|?*\n\r\t\x00]", " ", local_filename)
  return local_filename

def createLocalFileName(show):
  # Create the local filename, if not multiple episodes then
  # append the date and pid to the filename to avoid conflicts
  if( 'ep_num' in show ):
    local_filename = "{0}.mp4".format(show['title'])
  else:
    local_filename = "{0} - {1} ({2}).mp4".format(show['title'], 
                                                 show['showtime'][:10],
                                                 show['pid'])
                                                 
  return sanitizeFileName(local_filename)
    
# The main entry point for the script
def runMain():
  try:
    init() # Initialize the colorama library
    
    today = datetime.date.today()
    
    # Construct the argument parser for the commandline
    args = parseArguments()
    
    # Check to see if date is set and construct the limit date
    filter_older_than_date = datetime.date.min
    if( args.days is not None and args.days > 0 and args.days < 30 ):
      # Subtract a whole month from the today date
      filter_older_than_date = today - dateutil.relativedelta.relativedelta(days=args.days)
    
    # Get information about already downloaded episodes
    previously_recorded = getPreviouslyRecordedShows()

    # Get an existing tv schedule if possible
    if( not args.refresh ):
      schedule = getExistingTvSchedule()
    
    if( args.refresh or schedule is None or schedule['date'].date() < today ):
      print("Updating TV Schedule")
      schedule = getShowtimes()
      
    # Save the tv schedule as the most current one
    saveCurrentTvSchedule(schedule)
    
    if( args.debug ):
      for key, schedule_item in schedule.items():
        printTvShowDetails(args, schedule_item)
      
    # Now determine what to download
    download_list = []
    
    for key, schedule_item in schedule.items():
    
      # Skip any items that aren't show items
      if( not 'pid' in schedule_item ):
        continue
      
      # If excluded by date then don't consider (2016-09-04 08:46:00)
      if( args.days is not None ):
        show_date = datetime.datetime.strptime(schedule_item['showtime'], '%Y-%m-%d %H:%M:%S')
        if( show_date.date() < filter_older_than_date ):      
          if( args.debug ):
            print("Excluded show '"+schedule_item['title']+"' "+schedule_item['pid']+ " due to date limit ("+schedule_item['showtime']+")")
          continue
          
      # Check if category exclusion
      if( args.category and (not 'catid' in schedule_item or not int(schedule_item['catid']) == args.category )):
        if( args.debug ):
            print("Excluded show '"+schedule_item['title']+"' "+schedule_item['pid']+ " is not in category '"+str(args.category)+"'")
        continue
      
      # if the series id is set then find all shows belonging to that series
      if( args.sid is not None ):
        if( 'sid' in schedule_item and args.sid == schedule_item['sid'] ):
          download_list.append(schedule_item)
      elif( args.pid is not None ):
        if( 'pid' in schedule_item and args.pid == schedule_item['pid'] ):
          download_list.append(schedule_item)
      elif( args.find is not None ):
        if( 'title' in schedule_item and fuzz.partial_ratio( args.find, schedule_item['title'] ) > 80 ):
          download_list.append(schedule_item)
      else:
        # By default if there is no filtering then we simply list everything in the schedule
        download_list.append(schedule_item)
      
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
      print("")
      # Get a valid name for the save file
      local_filename = createLocalFileName(item)
      
      # Print out item number
      print( "{0} of {1}".format(curr_item, total_items))
      curr_item += 1 # Count the file
      
      # If excluded then don't download
      if( not args.force and item['pid'] in previously_recorded ):
        print("'{0}' already recorded (pid={1})".format(color_title(local_filename), item['pid']))
        continue
        
      # If the output directory is set then check if it exists and create it if it is not
      # pre-pend it to the file name then
      if( args.output is not None ):
        if not os.path.exists(args.output):
          os.makedirs(args.output)
          
        # Now prepend the directory to the filename
        local_filename = os.path.join(args.output, local_filename)
      
      # Download the file
      result = find_and_download_file(item['pid'], local_filename)
      if( not result is None ):
        # Store the id as already recorded 
        previously_recorded.append(item['pid'])

        # Now save the list of already recorded shows back to file and exit
        savePreviouslyRecordedShows(previously_recorded)
    
  finally:
    deinit() #Deinitialize the colorama library
    

# If the script file is called by itself then execute the main function
if __name__ == '__main__':
  runMain()