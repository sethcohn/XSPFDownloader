#!/usr/bin/env python2
################################################################################
# DownloaderThread is one thread for download system
################################################################################

import threading
import urllib2
import socket
import os
import httplib
from urlparse import urlparse
from contextlib import closing

class DownloaderThread(threading.Thread):
    def __init__(self, target_url, target_file, chunk_size=8192, max_retries=5, timeout=5):
        # Init download variables
        self.__target_url = target_url
        self.__target_file = target_file
        self.__chunk_size = chunk_size
        self.__max_retries = max_retries
        self.__timeout = 5
        self.__running = True
        self.__started = False
        self.__prepared = False
        self.__target_size = 0
        self.__file_size = 0
        self.__downloaded_size = 0

        # Init Thread
        super(DownloaderThread, self).__init__()
        self.daemon = True

        # Wrap run for exceptions
        self.__exception = None
        self.__real_run = self.run
        self.run = self.__run_wrapper

    def run(self):
        """ Main of the thread """
        assert self.__prepared, "Downloader was not prepared"

        if not self.__running:
            return

        self.__started = True
        self.__download_with_retries()
        self.__running = False

    def kill(self):
        """ Signal the thread to stop working and wait until done """
        if not self.__running or not self.isAlive():
            return

        self.__running = False
        self.join()

    def prepare(self):
        """ Prepare the download thread by getting target size and local size """

        # Read Real url and Target size
        self.__target_url, self.__target_size = self.__read_file_size(self.__target_url)

        # Check if local file exists
        self.__file_size = 0
        if os.path.isfile(self.__target_file):
            self.__file_size = os.stat(self.__target_file).st_size

        self.__missing_size = self.__target_size - self.__file_size
        if 0 == self.__missing_size:
            # Skip downlodaing of this file
            self.__started = True
            self.__running = False

        self.__downloaded_size = self.__file_size
        assert self.__missing_size >= 0, "Negative bytes to download???"
        self.__prepared = True

    def __read_file_size(self, url):
        """ Sends HEAD request to retrieve file size """

        # Read headers
        p = urlparse(url)
        conn = httplib.HTTPConnection(p.netloc)
        conn.request("HEAD", p.path)
        res = conn.getresponse()

        # Check for redirect
        loc = res.getheader("Location")
        if loc:
            return self.__read_file_size(loc)

        return (url, int(res.getheader("Content-Length")))

    @property
    def is_running(self):
        if not self.__started:
            return True

        return self.isAlive()

    @property
    def target_file(self):
        return self.__target_file

    @property
    def presentage(self):
        assert self.__prepared, "Downloader was not prepared"
        return (self.downloaded * 100) / self.__total_size

    @property
    def downloaded(self):
        return self.__downloaded_size
    
    @property
    def total_size(self):
        assert self.__prepared, "Downloader was not prepared"
        return self.__target_size

    @property
    def exception(self):
        return self.__exception

    def __run_wrapper(self, **kargs):
        try:
            return self.__real_run(**kargs)
        except Exception, e:
            self.__exception = e
            self.__running = False

    def __download_with_retries(self):
        """ Download with retry loop """

        tries = 0
        while True:
            try:
                tries += 1
                return self.__download_file()
            except (socket.timeout, urllib2.HTTPError) as e:
                if tries <= self.__max_retries:
                    continue
                raise

    def __download_file(self):
        """ Download operation """

        # Open a request
        req = urllib2.Request(self.__target_url)
        req.headers['Range'] = 'bytes=%d-%d' % (self.__downloaded_size, self.__target_size)

        with closing(urllib2.urlopen(url=req, timeout=self.__timeout)) as resp:
            # Open the file for writing and invoke read_chunks.
            with file(self.__target_file, "wb") as f:
                # Go to end of file
                f.seek(0, 2)

                # Start writing
                self.__read_chunks(resp, f)

    def __read_chunks(self, resp, f):
        """
            This file will download all resp content
            into f file object
        """

        total_size = self.__target_size

        while self.__running and self.downloaded != total_size:
            # Read the chunk
            chunk = resp.read(self.__chunk_size)
            if not chunk:
                break

            # Write to file
            f.write(chunk)

            # Calc the presentage
            self.__downloaded_size += len(chunk)
