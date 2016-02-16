#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import codecs
from PyQt4 import QtGui, QtCore
from timeline.MainWindow import MainWindow


def main():
    codecs.register(
        lambda name: codecs.lookup('utf-8') if name == 'cp65001' else None
    )
    app = QtGui.QApplication(sys.argv)
    ex = MainWindow()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
