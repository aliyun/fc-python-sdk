# -*- coding: utf-8 -*-

import os
import zipfile


def zip_dir(inputDir, output):
    """
    Zip up a directory and preserve symlinks and empty directories
    Derived from: https://gist.github.com/kgn/610907
    : param inputDir: the input directory that need be archived.
    : param output: the output file-like object to store the archived data.
    """
    zipOut = zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED)

    rootLen = len(inputDir)

    def _archive_dir(parentDirectory):
        contents = os.listdir(parentDirectory)
        # store empty directories
        if not contents:
            # http://www.velocityreviews.com/forums/t318840-add-empty-directory-using-zipfile.html
            archiveRoot = parentDirectory[rootLen:].replace('\\', '/').lstrip('/')
            zipInfo = zipfile.ZipInfo(archiveRoot + '/')
            zipOut.writestr(zipInfo, '')
        for item in contents:
            fullPath = os.path.join(parentDirectory, item)
            if os.path.isdir(fullPath) and not os.path.islink(fullPath):
                _archive_dir(fullPath)
            else:
                archiveRoot = fullPath[rootLen:].replace('\\', '/').lstrip('/')
                if os.path.islink(fullPath):
                    # http://www.mail-archive.com/python-list@python.org/msg34223.html
                    zipInfo = zipfile.ZipInfo(archiveRoot)
                    zipInfo.create_system = 3
                    # long type of hex val of '0xA1ED0000L',
                    # say, symlink attr magic...
                    zipInfo.external_attr = 2716663808
                    zipOut.writestr(zipInfo, os.readlink(fullPath))
                else:
                    #print('faint {0} {1} {2}'.format(rootLen, fullPath, archiveRoot))
                    zipOut.write(fullPath, archiveRoot, zipfile.ZIP_DEFLATED)

    _archive_dir(inputDir)

    zipOut.close()
