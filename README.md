<p align="center">
  <img src="https://raw.githubusercontent.com/sverrirs/ruvsarpur/master/img/entertainment.png" alt="logo" title="logo">
</p>

# RÚV Sarpur
[`ruvsarpur.py`](#ruvsarpurpy) is a python script that allows you to list, search and download TV shows off the Icelandic RÚV Sarpurinn website. The script is operated solely through a windows or linux command prompt.

[`webvtttosrt.py`](#webvtttosrtpy) is a python script that can convert webvtt and vtt files to the .srt subtitles format. (This format is used by the RÚV website for some episodes).

Project website at https://sverrirs.github.io/ruvsarpur/

If you are intending on using this tool outside of Iceland then I recommend a [VPN connection](http://www.expressrefer.com/refer-a-friend/30-days-free/?referrer_id=11147993). Its setup is discussed in more detail in a section near the end of this document

- [RÚV Sarpur](#rúv-sarpur)
- [Demo](#demo)
- [Requirements](#requirements)
- [Finding and listing shows](#finding-and-listing-shows)
  - [Incremental updates](#incremental-updates)
  - [Finding shows by name](#finding-shows-by-name)
- [Downloading shows](#downloading-shows)
- [Choosing video quality](#choosing-video-quality)
- [Advanced uses](#advanced-uses)
- [Scheduling downloads](#scheduling-downloads)
  - [Downloading only a particular season of a series](#downloading-only-a-particular-season-of-a-series)
- [Embedding media information in MP4 metadata tags](#embedding-media-information-in-mp4-metadata-tags)
- [Integration with Plex MediaServer](#integration-with-plex-mediaserver)
  - [Downloading of series and movie posters and splash screens](#downloading-of-series-and-movie-posters-and-splash-screens)
  - [Integration with IMDB for correct series and movie names](#integration-with-imdb-for-correct-series-and-movie-names)
- [Frequently Asked Questions](#frequently-asked-questions)
    - [I get an AttributeError when executing the script](#i-get-an-attributeerror-when-executing-the-script)
    - [I keep getting a message `SHOW_TITLE not found on server (pid=PID_NUMBER)` when trying to download using your script.](#i-keep-getting-a-message-show_title-not-found-on-server-pidpid_number-when-trying-to-download-using-your-script)
- [Using OpenVPN to automatically connect to a VPN if necessary](#using-openvpn-to-automatically-connect-to-a-vpn-if-necessary)
- [webvtttosrt.py](#webvtttosrtpy)
  - [How to use](#how-to-use)
  - [Conversion example](#conversion-example)


# Demo
<p align="center">
  <img src="https://raw.githubusercontent.com/sverrirs/ruvsarpur/master/img/demo01.gif" alt="Usage Demo" title="Usage Demo">
</p>

# Requirements
Python version 3.9 or newer, running the latest version is highly recommended.

Before first use make sure you install all requirements using 

```
pip install -r requirements.txt
```

> If you run into trouble installing the python-levenstein package (it is optional) then check out this solution on StackOverflow http://stackoverflow.com/a/33163704

*This tool includes the ffmpeg video processing kit. If you are on any other platform than Windows 64bit you will need to [download the binary executable of ffmpeg](https://www.ffmpeg.org/download.html) for your operating system from the official website. Then either add the ffmpeg tool to your PATH environment variable or alternatively specify its path explicitly using the `--ffmpeg` command line parameter.*

# Finding and listing shows
After downloading the script can be run by typing in
```
python ruvsarpur.py --help
```

To list all available shows and their information use the `--list` switch. This switch can be used with any other argument to disable downloading and have the script only list matches.
```
python ruvsarpur.py --list
```

The script downloads the tv schedule for the last month (that is the default availability of shows on the RÚV website). By default the script will only refresh the schedule once per day. You can force it to re-download the tv schedule by using the `--refresh` switch
```
python ruvsarpur.py --list --refresh
```

The script stores, by default, all of its config files in the current user home directory in a folder named '.ruvsarpur'. Use the `--portable` command line option to make the script store all configuration files in the current working directory.

```
python ruvsarpur.py --portable --list
```

## Incremental updates
The full refresh of the VOD catalog using the `--refresh` switch can be very time consuming. In cases where the script is run on a frequent intra-day schedule the `--incremental` switch can be added. When this switch is used the script attempts to perform a fast incremental intra-day refresh. 

Setting this switch instructs the refresh mechanism to only download information for items that are new since the last full TV schedule refresh from the same day. If the current date when the refreh is run is newer than the latest refresh date stored then this option has no effect and a full refresh is always performed. 

## Finding shows by name
To find shows by title use the `--find` argument
```
python ruvsarpur.py --list --find "Hvolpa"
```
which returns
```
Found 3 shows
4852061: Hvolpasveitin (11 af 24)
  21810: Sýnt 2016-09-26 18:01

4849078: Hvolpasveitin (20 af 26)
  18457: Sýnt 2016-09-25 08:00

4852060: Hvolpasveitin (10 af 24)
  21810: Sýnt 2016-09-19 18:01
```

The results are formatted in the following pattern
```
{pid} : {show title}
{sid} : {showtime}
```

You can include the optional `--desc` switch to display a short description of each program (if it is available)

```
python ruvsarpur.py --list --find "Hvolpa" --desc
```

# Downloading shows

To download shows you can either use the `sid` (series id), the `pid` (program id) to select what to download. Alternatively it is also possible to use the `--find` switch directly but that may result in the script downloading additional material that may match your search string as well.

Using the `--sid` will download all available episodes in the series
```
python ruvsarpur.py --sid 18457
```

Using the `--pid` will only download a single episode
```
python ruvsarpur.py --pid 4849075
```

Both the `--sid` and `--pid` parameters support multiple ids

```
python ruvsarpur.py --sid 18457 21810
```
```
python ruvsarpur.py --pid 4849075 4852060 4849078
```

Use the `-o` or `--output` argument to control where the video files will be saved to. Please make sure that you don't end your path with a backwards slash.
```
python ruvsarpur.py --pid 4849075 -o "c:\videos\ruv"
```

The script keeps track of the shows that have already been downloaded. You can force it to re-download files by using the `--force` switch
```
python ruvsarpur.py --pid 4849075 --force
```

If recoding history has been lost, files copied between machines or they are incorrectly labelled as previously recorded there is a `--checklocal` switch available. 

When this switch is specified the script will check to see if the video file exists on the user's machine before attempting a re-download. If it doesn't exist then it will start the download, if the file exists it will record it's pid as recorded and skip re-downloading it.
```
python ruvsarpur.py --pid 4849075 --checklocal
```

# Choosing video quality

The script automatically attempts to download videos using the 'HD1080' video quality for all download streams, this is equivilent of Full-HD resolution or 3600kbps. This setting will give you the best possible offline viewing experience and the best video and audio quality when casting to modern TVs.

Note: If you're intending the video files to be exclusively used on mobile phones then using the 'Normal' quality or 1200kbps will in most cases be sufficient and save you a lot of space and bandwidth. Normal is equivilent of SD (standard-definition).

By using `--quality` you instruct the script to download either a higher or lower quality video.
```
python ruvsarpur.py --pid 4849075 --quality "HD720"
```

The available values are:

| Value | Description | kbps |
| ----- | ----- | ----- |
| `"Normal"` | Normal quality expected in a standard definition broadcast, works well on most devices. | 1200kbps |
| `"HD720"` | 720p good quality, intended for HD-ready devices | 2400kbps |
| `"HD1080"` | 1080p very good quality intended for newer devices marked as Full-HD resolution. This produces very big files.  This is the default. | 3600kbps |


# Advanced uses

The `--new` flag limits the search and downloads to only new shows (e.g. shows that have just aired their first episode in a new multi-episode series). The example below will only list new children's shows on the TV schedule. 
```
python ruvsarpur.py --list --new
```

The `--keeppartial` flag can be used to keep partially downloaded files in case of errors, if omitted then the script deletes any incomplete partially downloaded files if an error occurs (this is the default behavior).


Use `--originaltitle` flag to include the original show name (usually the foreign title) in the output file.
```
python ruvsarpur.py --list --find "Hvolpa" --originaltitle
```
which returns
```
Found 2 shows
4852061: Hvolpasveitin (11 af 24) - Paw Patrol 
  21810: Sýnt 2016-09-26 18:01

4849078: Hvolpasveitin (20 af 26) - Paw Patrol
  18457: Sýnt 2016-09-25 08:00
```


# Scheduling downloads
You can schedule this script to run periodically to download new episodes in a series. To have the script correctly handle downloading re-runs and new seasons then it is recommended to use the `--find` option and specify the series title.

```
python ruvsarpur.py --find "Hvolpasveitin" -o "c:\videos\ruv\hvolpasveit"
```

> When running this in a bat or cmd file in windows ensure you include the following two lines at the top of the bat file
> `@echo off`
> `chcp 1252`
> Otherwise the icelandic character set will not be correctly understood when the batch file is run

## Downloading only a particular season of a series
In the case you only want to download a particular run of a series then you should use the `--sid` option to monitor a particular tv series and `-o` to set the directory to save the video file into.

```
python ruvsarpur.py --sid 18457 -o "c:\videos\ruv\hvolpasveit-season-1"
```

# Embedding media information in MP4 metadata tags
The script embedds information from the RÚV source listing into the MP4 video file using the following standard MP4 files metadata tags. 
- title
  - The title of the movie or incase of a tv-show or sports event the episode title.
- comment
  - Contains a special encoding of the program id and series id (pid and sid) to allow for accurate matching by other scripts, format `ruvinfo:pid:sid`
- synopis
  - The movie synopsis/description or in case of a tv-show the episode or series description, for sports events the sports type and the date and if available the teams competing.
- show
  - Only for tv-shows or sports events, the title of the series, i.e. "The Simpsons"
- date
  - Only for movies or documentaries, the year that the movie was released.
- episode_id
  - The episode number or episode name (used for display)
- episode_sort
  - The episode number (within the season), used for sorting and not displayed.
- season_number
  - The season number, used for sorting
- media_type
  - The type of content, one of ['Movie', 'Sports', 'TV Show']

These tags and their contents are supported by most mainstream library management tools and video players, including Plex and iTunes. 


> MP4 media tagging can be completely disabled by using the `--nometadata` switch. It is not recommended to switch metadata embedding off unless you are having problems with this feature.


# Integration with Plex MediaServer
The script offers compatibility with a local installation of the Plex Media server, https://www.plex.tv/ by using the `--plex` switch. With the switch on the script will download, label and organize its downloaded media according to the Plex media server rules to ensure that all tv-series and movies can be read and are stored in compatible Plex library structures.

See more about naming and organization rules for Plex on their website, https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/


## Downloading of series and movie posters and splash screens
When using the `--plex` switch the script will attempt to download available posters and episode thumbnails from the RÚV website as well. This feature is on by default and cannot be turned off as it significantly improves the quality of your media library. 

A full refresh of all metadata, posters and artwork in your library is possible without triggering a re-download of video contents by using the `--novideo` switch. 

```
python ruvsarpur.py --find "Hvolpasveit" -o "c:\videos\ruv\" --novideo
```

Will perform a full refresh of all metadata and artwork for Hvolpasveitin, including downloading posters and episode stills.

## Integration with IMDB for correct series and movie names
The script attempts to match shows and movies to the correct IMDB ID. This is done based on the shows title. For non-english shows this matching can be improved drastically by using the `--imdbfolder` hand having it point to a local copy of the `title.basics.tsv` file that can be obtained from https://www.imdb.com/interfaces/.

The script will warn you to update this file when the local file is older than 6 months.

# Frequently Asked Questions

### I get an AttributeError when executing the script
_Cause_: There may be a new python version dependency for the script (i.e. the script now uses features from a newer Python version than you have installed)

A common symptom is an exception such as 
```
AttributeError: 'str' object has no attribute 'removesuffix'
```

Make sure you always run the most latest Python version on your machine, see https://www.python.org/downloads/. If the problem persists after upgrading Python, please create an [issue](https://github.com/sverrirs/ruvsarpur/issues/new/choose).

### I keep getting a message `SHOW_TITLE not found on server (pid=PID_NUMBER)` when trying to download using your script.
_Cause_: The file is not available on the RÚV servers.

The script performs an optimistic attempt to locate any show that is listed in the broadcasting programme. However the files are not guaranteed to be still available on the RÚV servers. This is the error that is shown in those cases.

# Using OpenVPN to automatically connect to a VPN if necessary
In case you want your script to be run over a [VPN connection](http://www.expressrefer.com/refer-a-friend/30-days-free/?referrer_id=11147993) then it is recommended that you use the `OpenVPN` software. It is widely supported by VPN providers and can be easily used via command line.

Below is an example of how to integrate a VPN connection sequence before running the ruvsarpur.py downloader on Windows

```
echo "Starting VPN connection"
start openvpn.exe --config "vpnconfig.ovpn" --auth-user-pass "userpassword.txt"

echo "Waiting 15 seconds before starting download"
ping 127.0.0.1 -n 15 > nul

python ruvsarpur.py --find "Hvolpasveitin" --days 30 -o "c:\videos\ruv\hvolpasveit"

echo "Terminating VPN connection"
taskkill /FI "IMAGENAME eq openvpn.exe"
taskkill /f /im openvpn.exe
```

_Note that this code **must** be run under Administrator/sudo privileges due to modifications and changes to the system that `openvpn.exe` makes to redirect internet traffic through its VPN connection._

# webvtttosrt.py
is a general purpose python script that can convert webvtt and vtt files to the .srt subtitles format. This tool is useful when you want to merge subtitle files to existing mp4 video files using the [GPAC mp4box utility](https://github.com/gpac/gpac/) or similar tools.

## How to use
This is how you could convert webvtt and vtt subtitle files to SRT and merge them with the source video file using the [GPAC Mp4Box](https://github.com/gpac/gpac/) utility:

1. First download the subtitles file (usually available in the source of the website that contains the web player. Search for ".webvtt" or ".vtt" in the website HTML source)

2. Convert to .srt using the script by issuing
      ```
      python webvtttosrt.py -i subtitles.vtt
      ```

3. Add the srt file to the mp4 video stream (assuming install location for [GPAC](https://github.com/gpac/gpac/))
      ```
      "C:\Program Files\GPAC\mp4box.exe" -add "video.mp4" -add "subtitles.srt":lang=is:name="Icelandic" "merged-video.mp4"
      ```

   if the subtitle font is too small you can make it larger by supplying the ':size=XX' parameter like
     ```
     "C:\Program Files\GPAC\mp4box.exe" -add "video.mp4" -add "subtitles.srt":size=32:lang=is:name="Icelandic" "merged-video.mp4"
     ```

## Conversion example

Given the following WEBVTT subtitle file
```
1-0
00:01:07.000 --> 00:01:12.040 line:10 align:middle
Hey buddy, this is the first
subtitle entry that will be displayed

2-0
00:01:12.160 --> 00:01:15.360 line:10 align:middle
Yeah and this is the second line
<i>living the dream!</i>
```

the script will produce the following SRT conversion
```
1
00:01:07,000 --> 00:01:12,040
Hey buddy, this is the first
subtitle entry that will be displayed

2
00:01:12,160 --> 00:01:15,360
Yeah and this is the second line
<i>living the dream!</i>
```
