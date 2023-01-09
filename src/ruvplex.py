#!/usr/bin/env python
# coding=utf-8
__version__ = "1.0.0"
"""
Python script that parses embedded pid and sid information for files in a plex library 
in an attempt to augment the PLEX entries with detailed show and movie information from the RUV website if possible

Interfaces with a local instance of PLEX via REST requests and the RUV API to retrieve show and series information

The script works in the following way
- Given a path to a library of video files
- Scans every folder in this library and attempts to find video files with the embedded metadata in the comment field starting with 'ruvids:' 
- If the folder being scanned does not contain a file '.ruvplex' then a lookup is attempted
- RUV api is queried for the ruvids found in that folder
- The PLEX api is queried to attempt to find the series in question using the foreign title or title of the series or episode or movie
- Plex API is queried to attempt to match the library entry automatically using the internal Plex matching logic API calls
- Plex API is used to update the entry information with relevant data from the RUV API to override descriptions, ratings, original titles etc for each of the entries.
- Script finally writes a .ruvplex file containing information about the show that was matched to the folder and continues to next item

The script is written in Python 3.x

See: https://github.com/sverrirs/ruvsarpur
Author: Sverrir Sigmundarson  info@sverrirs.com  https://www.sverrirs.com
"""

import sys, os.path, re, time
import traceback   # For exception details
import textwrap # For text wrapping in the console window
from colorama import init, deinit # For colorized output to console windows (platform and shell independent)
from termcolor import colored # For shorthand color printing to the console, https://pypi.python.org/pypi/termcolor
from pathlib import Path # to check for file existence in the file system
import json # To manipulate JSON data from the PLEX instance
import argparse # Command-line argument parser
import requests # Downloading of data from HTTP
import datetime, dateutil.relativedelta # Formatting of date objects and adjusting date ranges
from datetime import date # To generate the current year for sport seasons when no show time exists

import urllib.request, urllib.parse # Downloading of data from URLs (used with the JSON parser)
import requests # Downloading of data from HTTP
from requests.adapters import HTTPAdapter # For Retrying
from requests.packages.urllib3.util.retry import Retry # For Retrying
import ssl
import http.client as http_client

import ruvsarpur # Access to the functions defined in the main tool
import ffmpeg    # Wrapper for the ffmpeg exe and ffmpeg probe tool
import platform  # To get information about if we are running on windows or not

JSON_HTTP_Headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36', 'Accept': 'application/json'}

color_error = lambda x: colored(x, 'red')

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

def parseArguments():
  parser = argparse.ArgumentParser()
  
  parser.add_argument("-i", "--input",
                                   help="The path to the library folder root that should be scanned",
                                   type=str)

  parser.add_argument("--plexurl", help="Url path to a local plex instance, if omitted then http://127.0.0.1:32400 will be used as a default", 
                                   type=str,
                                   default="http://127.0.0.1:32400")

  parser.add_argument("--force",   help="Forces a lookup for all shows found in the library", action="store_true")
  
  parser.add_argument("--ffprobe", help="Full path to the ffprobe executable file", 
                                   type=str)

  return parser.parse_args()

#
# Locates the ffprobe executable and returns a full path to it
def findffprobe(path_to_ffprobe_install=None, working_dir=None):
  if not path_to_ffprobe_install is None and os.path.isfile(path_to_ffprobe_install):
    return path_to_ffprobe_install

  # Attempts to search for it under the bin folder
  bin_dist = os.path.join(working_dir, "..","bin","ffprobe.exe" if platform.system() == 'Windows' else 'ffprobe')
  if os.path.isfile(bin_dist):
    return str(Path(bin_dist).resolve())
  
  # Throw an error
  raise ValueError('Could not locate FFMPEG install, please use the --ffmpeg switch to specify the path to the ffmpeg executable on your system.')

#
# Queries the /myplex/account endpoint for the PLEX server and ensures that a valid JSON response is returned
def verifyPlexInstanceReachable(plexurl):
  request = __create_retry_session().get(f"{str(plexurl).rstrip('/')}/myplex/account", stream=False, timeout=5, verify=False, headers=JSON_HTTP_Headers)
  if request is None or not request.status_code == 200 or len(request.text) <= 0:
    raise ValueError(f"Could not locate PLEX server at {plexurl}, please verify that the server is installed and running at the address given in --plexurl")

# The main entry point for the script
def runMain():
  try:
    init() # Initialize the colorama library
    
    today = datetime.date.today()

    # Get the current working directory (place that the script is executing from)
    working_dir = sys.path[0]
    
    # Construct the argument parser for the commandline
    args = parseArguments()

    # Get ffprobe exec
    ffprobeexec = findffprobe(args.ffprobe, working_dir)

    # Verify that the plex instance can be found
    verifyPlexInstanceReachable(args.plexurl)

    # Verify that the directory given is valid and exists

    # Loop through the directory and all subdirectoies and attempt to locate mp4 files to process
    
    

  finally:
    deinit() #Deinitialize the colorama library

# If the script file is called by itself then execute the main function
if __name__ == '__main__':
  runMain()