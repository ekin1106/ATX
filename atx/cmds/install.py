#! /usr/bin/env python
# -*- coding: utf-8 -*-

import atexit
import tempfile
import subprocess32 as subprocess
import shutil
import urllib2
import re
import os

import tqdm
import atx.androaxml as apkparse

from atx import logutils
from atx import adb as adbutils
from atx.cmds import utils


log = logutils.getLogger('install')
DEFAULT_REMOTE_PATH = '/data/local/tmp/_atx_tmp.apk'
__apks = dict(
    utf8ime='http://7rfh09.com2.z0.glb.qiniucdn.com/Utf7Ime.apk')


def clean(tmpdir):
    log.info('Remove temp directory')
    shutil.rmtree(tmpdir)


def adb_pushfile(adb, filepath, remote_path):
    filesize = os.path.getsize(filepath)
    pb = tqdm.tqdm(unit='B', unit_scale=True, total=filesize)
    p = adb.cmd('push', filepath, remote_path)

    while True:
        try:
            p.wait(0.5)
        except subprocess.TimeoutExpired:
            pb.n = get_file_size(adb, remote_path)
            pb.refresh()
            # log.info("Progress %dM/%dM", get_file_size(remote_path) >>20, filesize >>20)
            pass
        except (KeyboardInterrupt, SystemExit):
            p.kill()
            raise
        except:
            raise
        else:
            # log.info("Success pushed into device")
            break
    pb.close()


def get_file_size(adb, remote_path):
    output = subprocess.check_output(adb.build_cmd('shell', 'ls', '-l', remote_path))
    m = re.search(r'\s(\d+)', output)
    if not m:
        return 0
    return int(m.group(1))


def adb_remove(adb, path):
    p = adb.cmd('shell', 'rm', path)
    stdout, stderr = p.communicate()
    if stdout or stderr:
        log.warn('%s\n%s', stdout, stderr)


def adb_install(adb, remote_path):
    p = adb.cmd('shell', 'pm', 'install', '-rt', remote_path)
    stdout, _ = p.communicate()
    if stdout.find('Success') == -1:
        raise IOError("Adb install failed: %s" % stdout)


def main(path, serial=None, host=None, port=None, start=False):
    adb = adbutils.Adb(serial, host, port)
    
    # use qiniu paths
    if __apks.get(path):
        path = __apks.get(path)

    if re.match(r'^https?://', path):
        tmpdir = tempfile.mkdtemp(prefix='atx-install-')
        atexit.register(clean, tmpdir)
        log.info("Create temp directory: %s", tmpdir)

        urlpath = path
        target = os.path.join(tmpdir, '_tmp.apk')
        path = target
        log.info("Download from: %s", urlpath)
        utils.http_download(urlpath, target)

    package_name, main_activity = apkparse.parse_apk(path)
    log.info("APK package name: %s", package_name)
    log.info("APK main activity: %s", main_activity)

    log.info("Push file to android device")
    adb_pushfile(adb, path, DEFAULT_REMOTE_PATH)

    log.info("Install ..., will take a few seconds")
    adb_install(adb, DEFAULT_REMOTE_PATH)
    log.info("Clean _tmp.apk")
    adb_remove(adb, DEFAULT_REMOTE_PATH)

    if start:
        log.info("Start app '%s'" % package_name)
        adb.cmd('shell', 'am', 'start', '-n', package_name+'/'+main_activity).wait()
    log.info("Done")