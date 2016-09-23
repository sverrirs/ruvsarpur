# RÚV Sarpur Download
A simple python script that allows you to download TV shows off the Icelandic RÚV Sarpurinn website. 

The script is written in Python 3.5

# Examples
The script can be run simply by typing in 
```
python ruvsarpur.py --help
```

To find shows by title use the `--find` argument
```
python ruvsarpur.py --find "Hvolpa"
```
which returns
```
Found 3 shows
4849074 : Hvolpasveitin (16 of 26)
          pid: 4849074
          sid: 18457
4849075 : Hvolpasveitin (17 of 26)
          pid: 4849075
          sid: 18457
4849077 : Hvolpasveitin (19 of 26)
          pid: 4849077
          sid: 18457
```

To download shows you can either use the sid (series id) or the pid (program id) to select what to download.

Using the sid will download all available episodes in the series
```
python ruvsarpur.py --sid "18457"
```

Using the pid will only download a single episode
```
python ruvsarpur.py --pid "4849075"
```

The script keeps track of the shows that have already been downloaded. You can force it to re-download files by using the `--force` switch
```
python ruvsarpur.py --pid "4849075" --force
```

The script downloads the tv schedule for the last month (that is the default availability of shows on the RÚV website). By default the script will only refresh the schedule once per day. You can force it to re-download the tv schedule by using the `--refresh` switch
```
python ruvsarpur.py --find "Hvolpasveit" --refresh
```

# Requires
The script requires the following packages to be installed 
```
pip install python-dateutil
pip install requests
pip install simplejson
pip install fuzzywuzzy
pip install python-levenshtein
```
If you run into trouble installing the python-levenstein package (it is optional) then check out this solution on StackOverflow http://stackoverflow.com/a/33163704
