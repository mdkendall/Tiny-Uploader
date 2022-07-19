#!/usr/bin/env python
import re
import sys
from time import sleep

import serial

import tasmotizer_esptool as esptool
import json

from datetime import datetime

from PyQt5.QtCore import QUrl, Qt, QThread, QObject, pyqtSignal, pyqtSlot, QSettings, QTimer, QSize, QIODevice
from PyQt5.QtGui import QPixmap
from PyQt5.QtNetwork import QNetworkRequest, QNetworkAccessManager, QNetworkReply
from PyQt5.QtSerialPort import QSerialPortInfo, QSerialPort
from PyQt5.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton, QComboBox, QWidget, QCheckBox, QRadioButton, \
    QButtonGroup, QFileDialog, QProgressBar, QLabel, QMessageBox, QDialogButtonBox, QGroupBox, QFormLayout, QStatusBar

import banner
import firmwareURL

from gui import HLayout, VLayout, GroupBoxH, GroupBoxV, SpinBox, dark_palette
from utils import NoBinFile, NetworkError

__version__ = '0.1'

class ESPWorker(QObject):
    error = pyqtSignal(Exception)
    waiting = pyqtSignal()
    done = pyqtSignal()

    def __init__(self, port, actions, **params):
        super().__init__()
        self.command = [
                      '--chip', 'esp32',
                      '--port', port,
                      '--baud', '921600'
            ]

        self._actions = actions
        self._params = params
        self._continue = False

    @pyqtSlot()
    def run(self):
        esptool.sw.setContinueFlag(True)

        try:
            if 'backup' in self._actions:
                command_backup = ['read_flash', '0x00000', self._params['backup_size'],
                                  'backup_{}.bin'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))]
                esptool.main(self.command + command_backup)

                auto_reset = self._params['auto_reset']
                if not auto_reset:
                    self.wait_for_user()

            if esptool.sw.continueFlag() and 'write' in self._actions:
                file_path = self._params['file_path']
                command_write = ['write_flash', '--flash_mode', 'dout', '0x00000', file_path]

                if 'erase' in self._actions:
                    command_write.append('--erase-all')
                esptool.main(self.command + command_write)

        except (esptool.FatalError, serial.SerialException) as e:
            self.error.emit(e)
        self.done.emit()

    def wait_for_user(self):
        self._continue = False
        self.waiting.emit()
        while not self._continue:
            sleep(.1)

    def continue_ok(self):
        self._continue = True

    def abort(self):
        esptool.sw.setContinueFlag(False)


class ProcessDialog(QDialog):
    def __init__(self, port, **kwargs):
        super().__init__()

        self.setWindowTitle('Preparing firmware...')
        self.setFixedWidth(400)

        self.exception = None

        esptool.sw.progress.connect(self.update_progress)

        self.nam = QNetworkAccessManager()
        self.nrBinFile = QNetworkRequest()
        self.bin_data = b''

        self.setLayout(VLayout(5, 5))
        self.actions_layout = QFormLayout()
        self.actions_layout.setSpacing(5)

        self.layout().addLayout(self.actions_layout)

        self._actions = []
        self._action_widgets = {}

        self.port = port

        self.auto_reset = kwargs.get('auto_reset', False)

        self.file_path = kwargs.get('file_path')
        if self.file_path and self.file_path.startswith('http'):
            self._actions.append('download')

        self.backup = kwargs.get('backup')
        if self.backup:
            self._actions.append('backup')
            self.backup_size = kwargs.get('backup_size')

        self.erase = kwargs.get('erase')
        if self.erase:
            self._actions.append('erase')

        if self.file_path:
            self._actions.append('write')

        self.create_ui()
        self.start_process()

    def create_ui(self):
        for action in self._actions:
            pb = QProgressBar()
            pb.setFixedHeight(35)
            self._action_widgets[action] = pb
            self.actions_layout.addRow(action.capitalize(), pb)

        self.btns = QDialogButtonBox(QDialogButtonBox.Abort)
        self.btns.rejected.connect(self.abort)
        self.layout().addWidget(self.btns)

        self.sb = QStatusBar()
        self.layout().addWidget(self.sb)

    def appendBinFile(self):
        self.bin_data += self.bin_reply.readAll()

    def saveBinFile(self):
        if self.bin_reply.error() == QNetworkReply.NoError:
            self.file_path = self.file_path.split('/')[-1]
            with open(self.file_path, 'wb') as f:
                f.write(self.bin_data)
            self.run_esp()
        else:
            raise NetworkError

    def updateBinProgress(self, recv, total):
        self._action_widgets['download'].setValue(recv//total*100)

    def download_bin(self):
        self.nrBinFile.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        self.nrBinFile.setUrl(QUrl(self.file_path))
        self.bin_reply = self.nam.get(self.nrBinFile)
        self.bin_reply.readyRead.connect(self.appendBinFile)
        self.bin_reply.downloadProgress.connect(self.updateBinProgress)
        self.bin_reply.finished.connect(self.saveBinFile)

    def show_connection_state(self, state):
        self.sb.showMessage(state, 0)

    def run_esp(self):
        params = {
            'file_path': self.file_path,
            'auto_reset': self.auto_reset,
            'erase': self.erase
        }

        if self.backup:
            backup_size = f'0x{2 ** self.backup_size}00000'
            params['backup_size'] = backup_size

        self.esp_thread = QThread()
        self.esp = ESPWorker(
            self.port,
            self._actions,
            **params
        )
        esptool.sw.connection_state.connect(self.show_connection_state)
        self.esp.waiting.connect(self.wait_for_user)
        self.esp.done.connect(self.accept)
        self.esp.error.connect(self.error)
        self.esp.moveToThread(self.esp_thread)
        self.esp_thread.started.connect(self.esp.run)
        self.esp_thread.start()

    def start_process(self):
        if 'download' in self._actions:
            self.download_bin()
            self._actions = self._actions[1:]
        else:
            self.run_esp()

    def update_progress(self, action, value):
        self._action_widgets[action].setValue(value)

    @pyqtSlot()
    def wait_for_user(self):
        dlg = QMessageBox.information(self,
                                      'User action required',
                                      'Please power cycle the device, wait a moment and press OK',
                                      QMessageBox.Ok | QMessageBox.Cancel)
        if dlg == QMessageBox.Ok:
            self.esp.continue_ok()
        elif dlg == QMessageBox.Cancel:
            self.esp.abort()
            self.esp.continue_ok()
            self.abort()

    def stop_thread(self):
        self.esp_thread.wait(2000)
        self.esp_thread.exit()

    def accept(self):
        self.stop_thread()
        self.done(QDialog.Accepted)

    def abort(self):
        self.sb.showMessage('Aborting...', 0)
        QApplication.processEvents()
        self.esp.abort()
        self.stop_thread()
        self.reject()

    def error(self, e):
        self.exception = e
        self.abort()

    def closeEvent(self, e):
        self.stop_thread()


class Tasmotizer(QDialog):

    def __init__(self):
        super().__init__()
        self.settings = QSettings('tasmotizer.cfg', QSettings.IniFormat)

        self.port = ''

        self.nam = QNetworkAccessManager()

        self.esp_thread = None

        self.setWindowTitle(f'Tiny Uploader {__version__}')
        self.setMinimumWidth(480)

        self.mode = 0  # BIN file
        self.file_path = ''

        self.create_ui()

        self.refreshPorts()

    def create_ui(self):
        vl = VLayout(5)
        self.setLayout(vl)

        # Banner
        banner = QLabel()
        banner.setPixmap(QPixmap(':/banner.png'))
        vl.addWidget(banner)

        # Port groupbox
        gbPort = GroupBoxH('Select port', 3)
        self.cbxPort = QComboBox()
        pbRefreshPorts = QPushButton('Refresh')
        gbPort.addWidget(self.cbxPort)
        gbPort.addWidget(pbRefreshPorts)
        gbPort.layout().setStretch(0, 4)
        gbPort.layout().setStretch(1, 1)

        # Buttons
        self.pbUpload = QPushButton('Upload firmware!')
        self.pbUpload.setFixedHeight(50)
        self.pbUpload.setStyleSheet('background-color: #223579;')

        hl_btns = HLayout([50, 3, 50, 3])
        hl_btns.addWidgets([self.pbUpload])

        vl.addWidgets([gbPort])
        vl.addLayout(hl_btns)

        pbRefreshPorts.clicked.connect(self.refreshPorts)
        self.pbUpload.clicked.connect(self.start_process)

    def refreshPorts(self):
        self.cbxPort.clear()
        ports = reversed(sorted(port.portName() for port in QSerialPortInfo.availablePorts()))
        for p in ports:
            port = QSerialPortInfo(p)
            self.cbxPort.addItem(port.portName(), port.systemLocation())


    def start_process(self):
        try:
            if self.mode == 0:
                self.file_path = firmwareURL.URL

            process_dlg = ProcessDialog(
                self.cbxPort.currentData(),
                file_path=self.file_path,
                backup=False,
                backup_size=0,
                erase=True,
                auto_reset=True
            )
            result = process_dlg.exec_()
            if result == QDialog.Accepted:
                message = 'Programming successful\n\nYour device is restarting. This may take some time.'
                QMessageBox.information(self, 'Done', message)
            elif result == QDialog.Rejected:
                if process_dlg.exception:
                    QMessageBox.critical(self, 'Error', str(process_dlg.exception))
                else:
                    QMessageBox.critical(self, 'Process aborted', 'The process has been aborted by the user.')

        except NoBinFile:
            QMessageBox.critical(self, 'Image path missing', 'Select a binary to write, or select a different mode.')
        except NetworkError as e:
            QMessageBox.critical(self, 'Network error', e.message)


def main():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DisableWindowContextHelpButton)
    app.setQuitOnLastWindowClosed(True)
    app.setStyle('Fusion')
    app.setPalette(dark_palette)
    app.setStyleSheet('QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }')

    mw = Tasmotizer()
    mw.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
