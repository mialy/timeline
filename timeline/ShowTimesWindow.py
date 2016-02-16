#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
from PyQt4 import QtGui, QtCore


class ShowTimesWindow(QtGui.QMainWindow):
    def __init__(self, parent=None):
        self.parent = parent
        super(ShowTimesWindow, self).__init__(parent)
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
        self.cb_show_each_day = QtGui.QCheckBox(
            _("Show time per day within range")
        )
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
        start = end.addDays(-6)
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
        project_id = self.parent.get_id_from_cbox(index, self.cbox_list)
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
                (:project_id <= 0 OR project_id = :project_id)
                AND date_start <= :date_to
                AND date_end >= :date_from
            GROUP BY date
            ORDER BY date_start
        ''', {
            "project_id": project_id,
            "date_from": date_from,
            "date_to": date_to
        })
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
                key = datetime.datetime.fromtimestamp(x).strftime('%Y-%m-%d')
                key = str(key)
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

    def secondsToTime(self, seconds=0):
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return "%02d:%02d:%02d" % (hours, minutes, seconds)

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

        self.cbox_list.insertItem(0, _('< All projects >'), 0)

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

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
