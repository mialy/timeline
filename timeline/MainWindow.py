#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import sqlite3
import gettext
from PyQt4 import QtGui, QtCore
from time import time, strftime
from timeline.ShowTimesWindow import ShowTimesWindow


class MainWindow(QtGui.QMainWindow):
    # consts
    DB_NAME = "records.db"
    APP_NAME = "Time-Line"
    ICONS_DIR = "icons/"

    # properties
    running = False
    time_start = time()
    time_end = time()
    time_mid = time()
    qtimer = QtCore.QTimer()
    db = None
    db_cur = None
    current_timer_rowid = 0

    def __init__(self):
        super(MainWindow, self).__init__()
        self.init_app()

    def init_app(self):
        dbfile = self.get_db_filename()
        self.db = sqlite3.connect(dbfile)
        self.db_cur = self.db.cursor()

        if sys.version_info.major < 3:
            gettext.install("Time-Line", "locale", unicode=True,
                            names=['ngettext'])
        else:
            gettext.install("Time-Line", "locale", names=['ngettext'])

        # icons absolute path
        self.ICONS_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep
        self.ICONS_DIR += "icons" + os.sep

        # init db tables
        self.db_cur.execute('''
            PRAGMA encoding="UTF-8";
        ''')

        try:
            self.db_cur.execute('''
                CREATE TABLE IF NOT EXISTS test (
                    name VARCHAR(255)
                )
            ''')
            self.db.commit()

            self.db_cur.execute('''
                DROP TABLE IF EXISTS test
            ''')
            self.db.commit()
        except sqlite3.Error as e:
            self.init_ui()
            QtGui.QMessageBox.critical(
                self,
                _("Error"),
                _("Database error:") + " " + e.args[0]
            )
            return

        self.db_cur.execute('''
            CREATE TABLE IF NOT EXISTS times (
                project_id INTEGER,
                date_start INTEGER,
                date_end INTEGER,
                duration INTEGER
            )
        ''')
        self.db.commit()

        self.db_cur.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                name VARCHAR(255)
            )
        ''')
        self.db.commit()

        self.db_cur.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                name VARCHAR(255),
                value VARCHAR(255)
            )
        ''')
        self.db.commit()

        self.init_ui()

    def __del__(self):
        if hasattr(self, "db"):
            self.db.close()

    def init_ui(self):
        # labels
        label_new_project = QtGui.QLabel(_("New project"))
        label_project = QtGui.QLabel(_("Project"))

        # edit field
        self.edit_project = QtGui.QLineEdit()

        # combobox
        self.cbox_list = QtGui.QComboBox(self)
        self.cbox_list.setInsertPolicy(QtGui.QComboBox.InsertAlphabetically)
        self.cbox_list.setEditable(True)
        self.cbox_list.setAutoCompletion(True)
        self.load_cbox()

        cbox_is_empty = self.cbox_list.count() <= 0
        self.cbox_list.setDisabled(cbox_is_empty)
        self.cbox_list.activated.connect(self.on_change_cbox_list)

        # buttons
        self.btn_state = QtGui.QPushButton(_("Start"), self)
        self.btn_state.setCheckable(True)
        self.btn_state.setDisabled(cbox_is_empty)
        self.btn_state.setToolTip(_("Press button to start the counter."))
        self.btn_state.setIcon(QtGui.QIcon(self.ICONS_DIR + "play.png"))
        self.btn_state.clicked.connect(self.on_clicked_btn_state)
        self.btn_state.setSizePolicy(
            QtGui.QSizePolicy.Expanding,
            QtGui.QSizePolicy.Fixed
        )
        self.btn_state.setMinimumSize(0, 35)

        self.btn_add = QtGui.QPushButton(_("Add"), self)
        self.btn_add.clicked.connect(self.on_clicked_btn_add)

        self.btn_del = QtGui.QPushButton(_("Delete"), self)
        self.btn_del.clicked.connect(self.on_clicked_btn_del)
        self.btn_del.setDisabled(cbox_is_empty)

        # timer display
        self.lcd_timer = QtGui.QLCDNumber(self)
        self.lcd_timer.setDigitCount(8)
        self.lcd_timer.display(self.get_time_delta())

        # layout
        grid = QtGui.QGridLayout()
        grid.setSpacing(15)
        grid.addWidget(label_new_project, 0, 0)
        grid.addWidget(self.edit_project, 0, 1)
        grid.addWidget(self.btn_add, 0, 2)
        grid.addWidget(label_project, 1, 0)
        grid.addWidget(self.cbox_list, 1, 1)
        grid.addWidget(self.btn_del, 1, 2)
        grid.addWidget(self.btn_state, 3, 0, 1, 0)
        grid.addWidget(self.lcd_timer, 2, 0, 1, 0)

        # menubar
        menuitem_stats = QtGui.QAction(_("Show &Times..."), self)
        menuitem_stats.setShortcut('Ctrl+T')
        menuitem_stats.triggered.connect(self.on_clicked_menuitem_showtimes)

        menuitem_exit = QtGui.QAction(_("&Exit"), self)
        menuitem_exit.setShortcut('Ctrl+Q')
        menuitem_exit.triggered.connect(QtGui.qApp.quit)

        self.menubar = self.menuBar()
        menuitem_file = self.menubar.addMenu(_("&File"))
        menuitem_file.addAction(menuitem_stats)
        menuitem_file.addSeparator()
        menuitem_file.addAction(menuitem_exit)

        # main window
        q_widget = QtGui.QWidget(self)
        q_widget.setLayout(grid)
        self.setCentralWidget(q_widget)
        self.setFixedSize(320, 240)
        self.setWindowTitle(_("Time-Line"))
        self.setWindowIcon(QtGui.QIcon(self.ICONS_DIR + "timer.png"))
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.show()

    def on_clicked_menuitem_showtimes(self):
        window_show_times = ShowTimesWindow(self)
        window_show_times.setWindowFlags(QtCore.Qt.Window)
        window_show_times.setParent(self)
        window_show_times.windowIcon()
        window_show_times.setWindowModality(QtCore.Qt.WindowModal)
        window_show_times.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        window_show_times.show()

    # save selected project into db for next run
    def on_change_cbox_list(self):
        index = self.cbox_list.currentIndex()

        self.db_cur.execute('''
            SELECT value
            FROM settings
            WHERE name = :name COLLATE NOCASE
            LIMIT 1
        ''', {"name": "last_project"})
        result = self.db_fetch_assoc(["rowid"])

        if result:
            self.db_cur.execute('''
                UPDATE settings
                SET value = :value
                WHERE name = :name
            ''', {
                "name": "last_project",
                "value": self.get_id_from_cbox(index)
            })
            self.db.commit()
        else:
            self.db_cur.execute('''
                INSERT INTO settings (
                    name,
                    value
                ) VALUES (:name, :value)
            ''', {
                "name": "last_project",
                "value": int(index)
            })
            self.db.commit()

    def on_clicked_btn_state(self):
        if not self.running:
            self.running = True
            self.btn_state.setIcon(QtGui.QIcon(self.ICONS_DIR + "stop.png"))
            self.btn_state.setText(_("Stop"))
            self.btn_state.setToolTip(
                _("Press button to stop and save the counter.")
            )
            self.time_start = time()
            self.time_end = time()
            self.time_mid = time()
            self.qtimer.timeout.connect(self.update_timer)
            self.qtimer.start(1000)
            self.btn_state.setChecked(True)

            index = self.cbox_list.currentIndex()
            times = self.get_times_list()

            try:
                current_timer_rowid = 0
                self.db_cur.execute('''
                    INSERT INTO times (
                        project_id,
                        date_start,
                        date_end,
                        duration
                    ) VALUES (:p_id, :date_start, :date_end, :duration)
                ''', {
                    "p_id": self.get_id_from_cbox(index),
                    "date_start": times["start"],
                    "date_end": times["end"],
                    "duration": times["duration"]
                })
                self.db.commit()
                self.current_timer_rowid = self.db_cur.lastrowid
            except sqlite3.Error as e:
                self.stop_state(pass_db_update=True)
                QtGui.QMessageBox.critical(
                    self,
                    _("Error"),
                    _("Database error:") + " " + e.args[0]
                )

        else:
            self.stop_state()

    def stop_state(self, pass_db_update=False):
        self.running = False
        self.btn_state.setIcon(QtGui.QIcon(self.ICONS_DIR + "play.png"))
        self.btn_state.setText(_("Start"))
        self.btn_state.setToolTip(_("Press button to start the counter."))
        self.qtimer.stop()
        self.btn_state.setChecked(False)

        if pass_db_update:
            return

        times = self.get_times_list()

        try:
            self.db_cur.execute('''
                UPDATE times
                SET
                    date_end = :date_end,
                    duration = :duration
                WHERE rowid = :id
            ''', {
                "date_end": times["end"],
                "duration": times["duration"],
                "id": self.current_timer_rowid
            })
            self.db.commit()
        except sqlite3.Error as e:
            QtGui.QMessageBox.critical(
                self,
                _("Error"),
                _("Database error:") + " " + e.args[0]
            )

    def on_clicked_btn_add(self):
        text = self.edit_project.text()
        text = self.strip_text(text)

        if len(text) == 0:
            QtGui.QMessageBox.information(
                self,
                _("Info"),
                _("Please Enter a project name.")
            )
            return

        index = self.cbox_list.findText(text, QtCore.Qt.MatchFixedString)
        if index >= 0:
            self.cbox_list.setCurrentIndex(index)
        else:
            # check if item exist in DB
            self.db_cur.execute('''
                SELECT rowid
                FROM projects
                WHERE name = :name COLLATE NOCASE
                LIMIT 1
            ''', {"name": text})
            result = self.db_fetch_assoc(["rowid"])

            if not len(result):
                self.db_cur.execute('''
                    INSERT INTO projects (name)
                    VALUES (:name)
                ''', {"name": text})
                self.db.commit()
                self.cbox_list.addItem(text, self.db_cur.lastrowid)

            self.load_cbox(True)
            index = self.cbox_list.findText(text, QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.cbox_list.setCurrentIndex(index)
                self.btn_state.setDisabled(False)
                self.btn_del.setDisabled(False)
                self.cbox_list.setDisabled(False)

        self.edit_project.setText("")

    def on_clicked_btn_del(self):
        item = "<b>" + self.cbox_list.currentText() + "</b>"
        index = self.cbox_list.currentIndex()
        id = self.get_id_from_cbox(index)
        if id >= 0:
            isOk = QtGui.QMessageBox.warning(
                self,
                _("Confirmation"),
                _("Are you sure you want to delete project %s and all his "
                  "records?") % item,
                QtGui.QMessageBox.No | QtGui.QMessageBox.Yes
            )

            if isOk == QtGui.QMessageBox.No:
                return

            # remove elements from DB
            self.db_cur.execute('''
                DELETE FROM times
                WHERE project_id = :id
            ''', {"id": id})
            self.db.commit()

            self.db_cur.execute('''
                DELETE FROM projects
                WHERE rowid = :id
            ''', {"id": id})
            self.db.commit()

            self.cbox_list.removeItem(index)

        cbox_is_empty = self.cbox_list.count() <= 0

        if cbox_is_empty:
            self.stop_state()

        self.btn_state.setDisabled(cbox_is_empty)
        self.btn_del.setDisabled(cbox_is_empty)
        self.cbox_list.setDisabled(cbox_is_empty)

    def update_timer(self):
        self.time_end = time()
        self.lcd_timer.display(self.get_time_delta())

        if (self.time_end - self.time_mid) < 60:
            return

        self.time_mid = time()
        times = self.get_times_list()

        try:
            self.db_cur.execute('''
                UPDATE times
                SET
                    date_end = :date_end,
                    duration = :duration
                WHERE rowid = :id
            ''', {
                "date_end": times["end"],
                "duration": times["duration"],
                "id": self.current_timer_rowid
            })
            self.db.commit()
        except sqlite3.Error as e:
            self.stop_state(pass_db_update=True)
            QtGui.QMessageBox.critical(
                self,
                _("Error"),
                _("Database error:") + " " + e.args[0]
            )

    def get_time_delta(self):
        time = int(self.time_end - self.time_start)
        hours, remainder = divmod(time, 3600)
        minutes, seconds = divmod(remainder, 60)
        time = "%02d:%02d:%02d" % (hours, minutes, seconds)
        return time

    def get_times_list(self):
        start = int(self.time_start)
        end = int(self.time_end)
        duration = int(end - start)
        return {
            "start": start,
            "end": end,
            "duration": duration
        }

    def db_fetch_assoc(self, cols):
        out = []

        for row in self.db_cur.fetchall():
            data = dict()
            for i, col in enumerate(row):
                data[cols[i]] = col
            out.append(data)

        return out

    def get_db_filename(self):
        cfg = QtCore.QSettings(
            QtCore.QSettings.IniFormat,
            QtCore.QSettings.UserScope,
            self.APP_NAME, "application"
        )
        dir = QtCore.QFileInfo(cfg.fileName()).absolutePath() + "/"
        dir = self.strip_text(dir)

        if not os.path.exists(dir):
            os.makedirs(dir)

        db = dir + self.DB_NAME

        if not os.path.exists(db):
            with open(db, 'a'):
                os.utime(db, None)

        return db

    def get_id_from_cbox(self, index, list=None):
        list = list if list is not None else self.cbox_list

        try:
            id = int(list.itemData(index).toPyObject())
        except:
            id = int(list.itemData(index))
        return id

    def load_cbox(self, clear_current=False):
        if clear_current:
            self.cbox_list.clear()

        # get current projects list
        self.db_cur.execute('''
            SELECT
                rowid AS id,
                name AS name
            FROM projects
            ORDER BY name COLLATE NOCASE ASC
        ''')
        self.projects = self.db_fetch_assoc(["id", "name"])

        if hasattr(self, "projects") and len(self.projects) > 0:
            for cols in self.projects:
                self.cbox_list.addItem(cols["name"], cols["id"])

        # get previous selected project, if available
        self.db_cur.execute('''
            SELECT value
            FROM settings
            WHERE name = :name COLLATE NOCASE
            LIMIT 1
        ''', {"name": "last_project"})
        result = self.db_fetch_assoc(["value"])

        if len(result):
            id = int(result[0]["value"])
            index = self.cbox_list.findData(id)
            self.cbox_list.setCurrentIndex(index)

    def strip_text(self, text):
        try:
            text = unicode(text).strip()
        except Exception:
            text = text.strip()

        return text

    def closeEvent(self, event):
        if self.running:
            self.stop_state()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
