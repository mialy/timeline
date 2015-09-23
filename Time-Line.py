#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os
import sqlite3
import gettext
import codecs
import datetime
from PyQt4 import QtGui, QtCore
from time import time, strftime

class TimerApp(QtGui.QMainWindow):
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
        super(TimerApp, self).__init__()
        self.init_app()

    def init_app(self):
        dbfile = self.get_db_filename()
        self.db = sqlite3.connect(dbfile)
        self.db_cur = self.db.cursor()
        gettext.install("Time-Line", "locale", unicode=True, names=['ngettext'])

        # icons absolute path
        self.ICONS_DIR  = os.path.dirname(os.path.abspath(__file__)) + os.sep
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
            QtGui.QMessageBox.critical(self,
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
        self.btn_state.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
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

        # init stats window instance
        self.window_show_times = WindowShowTimes(self)
        self.window_show_times.setWindowFlags(QtCore.Qt.Window)
        self.window_show_times.setParent(self)
        self.window_show_times.windowIcon()
        self.window_show_times.setWindowModality(QtCore.Qt.WindowModal)

    def on_clicked_menuitem_showtimes(self):
        self.window_show_times.show()

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
            self.btn_state.setToolTip(_("Press button to stop and save the counter."))
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
                self.stop_state(pass_db_update = True)
                QtGui.QMessageBox.critical(self,
                    _("Error"),
                    _("Database error:") + " " + e.args[0]
                )

        else:
            self.stop_state()

    def stop_state(self, pass_db_update = False):
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
            QtGui.QMessageBox.critical(self,
                _("Error"),
                _("Database error:") + " " + e.args[0]
            )

    def on_clicked_btn_add(self):
        text = self.edit_project.text()
        text = self.strip_text(text)

        if len(text) == 0:
            QtGui.QMessageBox.information(self,
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
            ''', {"name":text})
            result = self.db_fetch_assoc(["rowid"])

            if not len(result):
                self.db_cur.execute('''
                    INSERT INTO projects (name)
                    VALUES (:name)
                ''', {"name":text})
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
            isOk = QtGui.QMessageBox.warning(self,
                _("Confirmation"),
                _("Are you sure you want to delete project %s and all his records?") % item,
                QtGui.QMessageBox.No | QtGui.QMessageBox.Yes)

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
            self.stop_state(pass_db_update = True)
            QtGui.QMessageBox.critical(self,
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
        cfg = QtCore.QSettings(QtCore.QSettings.IniFormat,
            QtCore.QSettings.UserScope,
            self.APP_NAME, "application")
        dir = self.strip_text(QtCore.QFileInfo(cfg.fileName()).absolutePath() + "/")

        if not os.path.exists(dir):
            os.makedirs(dir)

        db = dir + self.DB_NAME

        if not os.path.exists(db):
            with open(db, 'a'):
                os.utime(db, None)

        return db

    def get_id_from_cbox(self, index):
        try:
            id = int(self.cbox_list.itemData(index).toPyObject())
        except:
            id = int(self.cbox_list.itemData(index))
        return id

    def load_cbox(self, clear_current = False):
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

class WindowShowTimes(QtGui.QMainWindow):
    def __init__(self, parent = None):
        self.parent = parent
        super(WindowShowTimes, self).__init__(parent)
        self.init_ui()

    def showEvent(self, event):
        self.reset_ui()

    def init_ui(self):
        self.db_cur = self.parent.db_cur
        self.db_fetch_assoc = self.parent.db_fetch_assoc

        self.setWindowTitle(_("Show Times"))

        # project line
        label_project = QtGui.QLabel(_("Project"))
        self.cbox_list = QtGui.QComboBox(self)
        self.cbox_list.setInsertPolicy(QtGui.QComboBox.InsertAlphabetically)
        self.cbox_list.setEditable(True)
        self.cbox_list.setAutoCompletion(True)
        self.load_cbox()

        # dates range line
        range = self.get_default_date_range()
        label_date_range = QtGui.QLabel(_("Select range"))
        label_date_range_to = QtGui.QLabel(_("To"))
        self.date_from = QtGui.QDateTimeEdit()
        self.date_from.setTimeSpec(QtCore.Qt.UTC)
        self.date_from.setCalendarPopup(True)
        self.date_from.setDateTime(range["start"])
        self.date_to = QtGui.QDateTimeEdit()
        self.date_to.setTimeSpec(QtCore.Qt.UTC)
        self.date_to.setCalendarPopup(True)
        self.date_to.setDateTime(range["end"])

        # third & fourth line
        label_options = QtGui.QLabel(_("Options"))
        self.cb_show_each_day = QtGui.QCheckBox(_("Show time per day within range"))
        self.cb_show_each_day.setChecked(True)
        self.cb_show_each_day.clicked.connect(self.on_clicked_cb_show_each_day)
        self.cb_pass_empty = QtGui.QCheckBox(_("Show non-working days"))
        self.cb_pass_empty.setChecked(True)

        # fifth line
        font = QtGui.QFont("Monospace")
        font.setStyleHint(QtGui.QFont.TypeWriter)
        self.output = QtGui.QPlainTextEdit()
        self.output.setFont(font)
        self.output.setReadOnly(True)
        self.output.setFixedHeight(200)
        self.output.hide()

        # bottom line (last)
        self.btn_show_result = QtGui.QPushButton(_("&Show Result"))
        self.btn_show_result.setMinimumSize(0, 25)
        self.btn_show_result.clicked.connect(self.on_clicked_btn_show_result)
        self.btn_close = QtGui.QPushButton(_("&Close"))
        self.btn_close.setMinimumSize(0, 25)
        self.btn_close.clicked.connect(self.on_clicked_btn_close)

        # layout
        grid_date_range = QtGui.QGridLayout()
        grid_date_range.setSpacing(15)
        grid_date_range.addWidget(self.date_from, 0, 1)
        grid_date_range.addWidget(self.date_to, 0, 2)
        q_date_range = QtGui.QWidget(self)
        q_date_range.setLayout(grid_date_range)

        grid = QtGui.QGridLayout()
        grid.setSpacing(15)
        grid.addWidget(label_project, 0, 0)
        grid.addWidget(self.cbox_list, 0, 1, 1, 3)
        grid.addWidget(label_date_range, 1, 0)
        grid.addWidget(label_date_range_to, 1, 2, QtCore.Qt.AlignCenter)
        grid.addWidget(self.date_from, 1, 1)
        grid.addWidget(self.date_to, 1, 3)
        grid.addWidget(label_options, 2, 0)
        grid.addWidget(self.cb_show_each_day, 2, 1, 1, 3)
        grid.addWidget(self.cb_pass_empty, 3, 1, 1, 3)
        grid.addWidget(self.btn_show_result, 4, 1, 1, 1)
        grid.addWidget(self.btn_close, 4, 3)
        grid.addWidget(self.output, 5, 0, 1, 4)

        q_widget = QtGui.QWidget(self)
        q_widget.setLayout(grid)
        self.setCentralWidget(q_widget)

    def reset_ui(self):
        range = self.get_default_date_range()
        self.date_from.setDateTime(range["start"])
        self.date_to.setDateTime(range["end"])
        self.load_cbox(True)
        self.cb_show_each_day.setChecked(True)
        self.cb_pass_empty.setChecked(True)
        self.cb_pass_empty.setEnabled(True)
        self.output.setPlainText("")
        self.output.show()

    def get_default_date_range(self):
        end = QtCore.QDateTime.currentDateTime()
        end.setTimeSpec(QtCore.Qt.UTC)
        end.setTime(QtCore.QTime(23, 59, 59, 999))
        start = end.addDays(-7)
        start.setTime(QtCore.QTime(0, 0, 0, 0))
        ranges = {
            "start": start,
            "end": end
        }
        return ranges

    def on_clicked_cb_show_each_day(self):
        checked = self.cb_show_each_day.isChecked()
        self.cb_pass_empty.setEnabled(True if checked else False)

    def on_clicked_btn_close(self):
        self.close()

    def on_clicked_btn_show_result(self):
        output = ""
        index = int(self.cbox_list.currentIndex())
        project_id = self.parent.get_id_from_cbox(index)
        date_from = self.date_from.dateTime().toTime_t()
        date_to = self.date_to.dateTime().toTime_t()
        show_days = self.cb_show_each_day.isChecked()
        pass_empty_days = self.cb_pass_empty.isChecked()

        self.db_cur.execute('''
            SELECT
                STRFTIME("%Y-%m-%d", date_start, "unixepoch") AS date,
                SUM(duration) AS duration
            FROM times
            WHERE
                project_id = :project_id
                AND date_start <= :date_to
                AND date_end >= :date_from
            GROUP BY date
            ORDER BY date_start
        ''', {
            "project_id": project_id,
            "date_from": date_from,
            "date_to": date_to})
        result = self.db_fetch_assoc(["date", "duration"])
        if result is None:
            return

        total = 0
        dates = {}
        for time in result:
            total += (time['duration'])
            if not show_days:
                continue
            dates[str(time["date"])] = self.secondsToTime(time["duration"])

        if pass_empty_days and show_days:
            for x in range(date_from, date_to, 86400):
                key = str(datetime.datetime.fromtimestamp(x).strftime('%Y-%m-%d'))
                if key in dates:
                    output += str(key) + ": " + str(dates[key]) + "\n"
                else:
                    output += str(key) + ": " + _("none") + "\n"
            output += "-" * 36 + "\n"
        elif show_days:
            for x in sorted(dates):
                output += str(x) + ": " + str(dates[x]) + "\n"
            output += "-" * 36 + "\n"

        output += _("Total time:") + " " + self.secondsToTime(total) + "\n\n"
        output += _("Dates are in UTC") + "\n"
        self.output.setPlainText(output)
        self.output.show()

    def secondsToTime(self, seconds = 0):
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return "%02d:%02d:%02d" % (hours, minutes, seconds)

    def load_cbox(self, clear_current = False):
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

def main():
    codecs.register(lambda name: codecs.lookup('utf-8') if name == 'cp65001' else None)
    app = QtGui.QApplication(sys.argv)
    ex = TimerApp()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
