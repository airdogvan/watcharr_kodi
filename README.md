script.watcharr
=================

Kodi plugin for [Watchrr] https://github.com/sbondCo/Watcharr

This plugin will mark TV shows episodes or movies you've seen as watched on yourinstance of Watcharr .
It will also add the the TV show or movie to your account if it was not already there.


build
=====
If you really want to build it, here is a simple script to do so:
```sh
#!/bin/bash

dest=script.watcharr
version=$(grep "^\s\+version" addon.xml | cut -f2 -d'"')

if [ -d $dest ]; then
    rm -r $dest
fi

mkdir $dest
cp addon.xml $dest/
cp *.txt $dest/
cp icon.png $dest/
cp *.py $dest/
cp -r resources $dest/

if [ -f $dest-$version.zip ]; then
    rm $dest-$version.zip
fi

zip -r $dest-$version.zip $dest
rm -r $dest
````
It will create a zip file that you can install directly within Kodi.

install
=======

Using the GUI of Kodi, choose to install your plugin as a zip file, find your
zip file, and you're done !

download
========
If you can't or don't want to build this plugin, look at the release tab.
You can download the last plugin from there.




