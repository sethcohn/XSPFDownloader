#!/usr/bin/env python2
################################################################################
# XSPFDownloader will download all vidoes from xspf to be played locally
##
# sudo pip install progressbar2
# sudo pip install unicode-slugify
################################################################################

from DownloaderThread import DownloaderThread
import xspf
import progressbar
import shutil
import os
import sys
import urllib
from urlparse import urljoin
from slugify import slugify

class XSPFDownloader(object):
    __PBAR_WIDGETS = ['Downloading: ', progressbar.Percentage(), ' ', progressbar.Bar(),
                    ' ', progressbar.ETA(), ' ', progressbar.AdaptiveTransferSpeed()]

    __PBAR_PREPARE_WIDGETS = ['Preparing: ', progressbar.Percentage(), ' ', progressbar.Bar(), ' ', progressbar.AdaptiveETA()]

    def __init__(self, target_xspf, threads=15, verbose=True):
        self.__reload(target_xspf)

        self.__target_dir = os.path.realpath(os.path.split(target_xspf)[0])
        self.__targets = []
        self.__total_size = 0
        self.__verbose = verbose
        self.__max_threads = threads

        # Prepare targets list
        self.__prepare_targets()

    def start(self):
        self.__download()
        self.__assert_files()

    @property
    def target_dir(self):
        return self.__target_dir

    def save(self):
        file(self.__target_xspf, "wb").write(self.__x.toXml().replace("\n", "\r\n"))
        self.__reload()

    def __reload(self, target_xspf=None):
        if target_xspf is not None:
            self.__target_xspf = target_xspf
        self.__x = xspf.Xspf.loads(self.__target_xspf)

    def __assert_files(self):
        for t in self.__targets:
            assert os.path.isfile(t.target_file), "File %s was not downloaded" % t.target_file

    def __download(self):
        # Do we have a job here?
        if 0 == len(self.__targets):
            return

        left_threads = self.__targets[:]
        active_threads = []
        pbar = progressbar.ProgressBar(widgets=self.__PBAR_WIDGETS, maxval=self.__total_size)

        # Start progress bar
        if self.__verbose:
            print "Downloading to %s" % (self.__target_dir)
            pbar.start()

        # Start iterate all threads till done.
        while len(left_threads) > 0 or len(active_threads) > 0:
            # First activate all threads
            while len(left_threads) > 0 and len(active_threads) < self.__max_threads:
                t = left_threads.pop()
                t.start()
                active_threads.append(t)

            # Update progress bar
            if self.__verbose:
                pbar.update(self.__total_downloaded())

            # Handling exceptions:
            for t in active_threads:
                if t.exception:
                    raise t.exception

            # Remove finished threads
            active_threads = filter(lambda x: x.is_running, active_threads)

    def __total_presentage(self):
        return sum([i.presentage for i in self.__targets])

    def __total_downloaded(self):
        return sum([i.downloaded for i in self.__targets])

    def __xspf_format_fname(self, filename):
        filename = urllib.quote(filename.encode("utf-8"))
        return "%s" % filename

    def __to_downloader(self, obj, attr, fname):
        # Use original location as url
        url = getattr(obj, attr)

        # Make sure remote location
        if not url.startswith("http://"):
            print "[I] Skipping %s" % url
            return None

        # Build new file name
        ext = os.path.splitext(url)[1]
        target_file = u"%s%s" % (slugify(fname), ext)
        
        # Override the old URL in file with the downloaded one (Relative)
        setattr(obj, attr, self.__xspf_format_fname(target_file))

        # Build full path for the Downloaded file
        target_file = os.path.join(self.__target_dir, target_file)

        # Append to targets
        return DownloaderThread(url, target_file)

    def __prepare_targets(self):
        self.__download_image()

        for i, t in enumerate(self.__x.track):
            fname = u"%02d-%s" % (i+1, t.title)
            d = self.__to_downloader(t, "location", fname)
            if d is not None:
                # Append to targets
                self.__targets.append(d)

        if not len(self.__targets):
            print "[I] Nothing to Download."
            return

        # Preparing All targets
        pbar = progressbar.ProgressBar(widgets=self.__PBAR_PREPARE_WIDGETS, maxval=len(self.__targets))
        if self.__verbose:
            print "Preparing to Download %s" % (self.__x.title)
            pbar.start()

        total_size = 0
        for i, t in enumerate(self.__targets):
            pbar.update(i+1)
            t.prepare()
            total_size += t.total_size

        self.__total_size = total_size

    def __download_image(self):
        d = self.__to_downloader(self.__x, "image", "course")
        if not d:
            return

        d.prepare()
        d.start()
        d.join()
        if d.exception:
            raise d.exception

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Usage: %s <XSPF file>" % sys.argv[0]
        exit(1)

    x = XSPFDownloader(sys.argv[1].decode(sys.getfilesystemencoding()))
    x.start()
    x.save()
