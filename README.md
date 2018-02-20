<p align="center">
  <img src="https://raw.githubusercontent.com/sverrirs/ruvsarpur/master/img/entertainment.png" alt="logo" title="logo">
</p>

# RÚV Sarpur
[`ruvsarpur.py`](#ruvsarpurpy) is a python script that allows you to list, search and download TV shows off the Icelandic RÚV Sarpurinn website. 

[`webvtttosrt.py`](#webvtttosrtpy) is a python script that can convert webvtt and vtt files to the .srt subtitles format. (This format is used by the RÚV website for some episodes).

Project website at https://sverrirs.github.io/ruvsarpur/

> Note: As of version 2.0 this tool includes the ffmpeg video processing kit. If you are on any other platform than Windows 64bit you will need to [download the binary executable of ffmpeg](https://www.ffmpeg.org/download.html) for your operating system from the official website and then specify its path using the `--ffmpeg` command line parameter.


# Demo
<p align="center">
  <img src="https://raw.githubusercontent.com/sverrirs/ruvsarpur/master/img/demo01.gif" alt="Usage Demo" title="Usage Demo">
</p>

# Requirements
Python version 3.x

Both scripts require the following packages to be installed 
```
pip install colorama
pip install termcolor
```

Additionally the `ruvsarpur.py` script requires the following packages
```
pip install python-dateutil
pip install requests
pip install simplejson
pip install fuzzywuzzy
pip install python-levenshtein
```
If you run into trouble installing the python-levenstein package (it is optional) then check out this solution on StackOverflow http://stackoverflow.com/a/33163704

## Contributing
Please use a pull/rebase, e.g. `git pull --rebase origin master` when merging changes from master to your branch to avoid unnecessary merge commits.


# ruvsarpur.py
This is a python script that allows you to list, search and download TV shows off the Icelandic RÚV Sarpurinn website.

## Finding and listing shows
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

## Downloading shows

To download shows you can either use the `sid` (series id) or the `pid` (program id) to select what to download.

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

## Choosing video quality

The script chooses automatically the 'Normal' video quality for all download streams, this is equivilent of SD (standard-definition) or 1200kbps.

By using `--quality` you instruct the script to download either a higher or lower quality video.
```
python ruvsarpur.py --pid 4849075 --quality "HD1080"
```

The available values are:
| Value | Description | kbps |
| ----- | ----- | ----- |
| `"Very Low"` | Very small, for very old mobile devices with small screens (resolution under 320x240) | 500kbps |
| `"Low"` | Small, for older devices, e.g. iPhone 4G (resolution under 640x360) | 800kbps |
| `"Normal"` | Normal quality expected in a standard definition broadcast, works well on most devices. This is the default. | 1200kbps |
| `"HD720"` | 720p good quality, intended for HD-ready devices | 2400kbps |
| `"HD1080"` | 1080p very good quality intended for newer devices marked as Full-HD resolution. This produces very big files. | 3600kbps |


## Advanced uses

Using `--category` argument allows you to filter the tv schedule by category. For example to list only childrens tv shows use the category number 1
```
python ruvsarpur.py --list --category 1
```

The available categories are:
```
1='Börn'
2='Framhaldsþættir'
3='Fréttatengt'
4='Fræðsla'
5='Íþróttir'
6='Íslenskir þættir'
7='Kvikmyndir'
9='Tónlist'
13='Samfélag'
17='Menning'
```

The `--days` argument can be used to filter the list by only listing shows added in the past _N_ number of days. For example, to list only children's shows that were added in the past day use:
```
python ruvsarpur.py --list --category 1 --days 1
```

The the `--new` flag limits the search and downloads to only new shows (e.g. shows that have just aired their first episode in a new multi-episode series). The example below will only list new children's shows on the TV schedule. 
```
python ruvsarpur.py --list --category 1 --new
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


## Scheduling downloads
You can schedule this script to run periodically to download new episodes in a series. To have the script correctly handle downloading re-runs and new seasons then it is recommended to use the `--find` option and specify the series title.

```
python ruvsarpur.py --find "Hvolpasveitin" -o "c:\videos\ruv\hvolpasveit"
```

> When running this in a bat or cmd file in windows ensure you include the following two lines at the top of the bat file
> `@echo off`
> `chcp 1252`
> Otherwise the icelandic character set will not be correctly understood when the batch file is run

You can additionally add the `--days` argument to only include shows from the N number of previous days (e.g. specify 1 if you intend to run this script every day, 7 if you only intend to run it once a week etc)

```
python ruvsarpur.py --sid 18457 --days 7  -o "c:\videos\ruv"
```

### Downloading only a particular season of a series
In the case you only want to download a particular run of a series then you should use the `--sid` option to monitor a particular tv series and `-o` to set the directory to save the video file into.

```
python ruvsarpur.py --sid 18457 -o "c:\videos\ruv\hvolpasveit-season-1"
```  

## Frequently Asked Questions

#### I keep getting a message `SHOW_TITLE not found on server (pid=PID_NUMBER)` when trying to download using your script.
_Cause_: The file is not available on the RÚV servers.

The script performs an optimistic attempt to locate any show that is listed in the broadcasting programme. However the files are not guaranteed to be still available on the RÚV servers. This is the error that is shown in those cases.

## Using OpenVPN to automatically connect to a VPN if necessary
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
