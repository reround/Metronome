"""
节拍器

特点：可以实时调整
"""

import sys, time, threading
from enum import Enum, auto

import numpy as np
import sounddevice as sd

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import (
    Qt,
    pyqtSlot,
    pyqtSignal,
    QObject,
    QThread,
    QMutex,
    QWaitCondition,
    QMutexLocker,
    QEvent,
    QTimer,
)
from PyQt6.QtGui import QIcon

from Metronome_mainWindow import Ui_MainWindow


class MetroState(Enum):
    PAUSE = auto()  # 暂停
    RUNNING = auto()  # 运行中


class Metronome(QObject):
    sig_beat = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.t = 0  # 已播放样本计数
        self.time_signature = "4/4"  # 拍号（如 4/4）
        self.beat_num: int = 4  # 拍数
        self.current_beat: int = 0  # 当前拍子数
        self.CLICK_HZ = 800  # 拍子声音频率
        self.volume = 0.5  # 音量
        self.FS = 44_100  # 采样率
        self.BPM = 100  # 每分钟拍子数
        self.BEAT_S = 60 / self.BPM  # 每拍持续时间
        self.CLICK_S = 0.10  # 拍子声音持续时间
        self.state = MetroState.PAUSE  # 是否暂停

        # 每拍需要的样本数
        self.BEAT_N = int(self.FS * self.BEAT_S)
        self.CLICK_N = int(self.FS * self.CLICK_S)

    def update_bmp(self, value):
        self.BPM = value  # 每分钟拍子数
        self.BEAT_S = 60 / self.BPM  # 每拍持续时间
        self.BEAT_N = int(self.FS * self.BEAT_S)
        self.CLICK_N = int(self.FS * self.CLICK_S)

    def clear(self):
        self.t = 0
        self.current_beat = 0

    def callback(self, outdata, frames, time_, status):
        # 生成 frames 长度的缓冲区
        buf = np.zeros(frames, dtype="float32")
        for i in range(frames):
            # 一个周期 BEAT_N 个样本
            pos_in_beat = self.t % self.BEAT_N
            # print(f"pos_in_beat:{pos_in_beat}")
            if pos_in_beat < self.CLICK_N:
                buf[i] = self.volume * np.sin(
                    2 * np.pi * self.CLICK_HZ * pos_in_beat / self.FS
                )
            self.t += 1
            if pos_in_beat == 0:
                self.sig_beat.emit()
                # print(f"current_beat:{self.current_beat}")
                self.current_beat += 1
                # 首拍高音
                if self.current_beat % self.beat_num == 1:
                    self.CLICK_HZ = 800
                else:
                    self.CLICK_HZ = 500
            else:
                pass

        outdata[:, 0] = buf  # 单声道

    def start(self):
        with sd.OutputStream(
            channels=1, samplerate=self.FS, callback=self.callback, blocksize=1024
        ):
            self.state = MetroState.RUNNING
            while True:
                if self.state == MetroState.PAUSE:
                    return
                time.sleep(0.1)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # 初始化 UI
        self.setWindowIcon(QIcon("assets/svg/metronome.svg"))
        self.setFixedSize(self.size())  # 锁死/禁止放大缩小

        self.metronome = Metronome()

        self.dial_range = (30, 240)
        self.dial.setRange(self.dial_range[0], self.dial_range[1])  # 数值范围
        self.dial.setSingleStep(1)  # 步进 5
        self.dial.setNotchesVisible(True)  # 显示刻度
        self.dial.setNotchTarget(15.0)  # 刻度疏密
        self.horizontalSlider_volume.setValue(int(self.metronome.volume * 100))
        self.metronome.sig_beat.connect(self.beep)

    def beep(self):
        """
        处理拍子响应
        """
        # 这里可以播放“嘀”声、闪烁灯、打印字符等
        # print("d", end="", flush=True)
        self.dial.setStyleSheet("QDial { background: #a5d6a7; }")
        # 100 ms 后自动变白，不阻塞
        QTimer.singleShot(100, lambda: self.dial.setStyleSheet(""))

    @pyqtSlot(int)
    def on_dial_valueChanged(self, value: int):
        """
        实时变更频率的地方, 以dial数值改变为标准
        """
        self.lineEdit_bmp.setText(str(value))
        self.metronome.update_bmp(self.dial.value())

    @pyqtSlot(str)
    def on_lineEdit_bmp_textChanged(self, value: str):
        try:
            int_value = int(value)
            if int_value < self.dial_range[0] or int_value > self.dial_range[1]:
                int_value = self.dial_range[0]
                self.dial.setValue(int(value))
            self.dial.setValue(int(value))

        except ValueError:
            int_value = self.dial_range[0]
        pass

    @pyqtSlot(int)
    def on_horizontalSlider_volume_valueChanged(self, value: int):
        self.metronome.volume = value / 100

    @pyqtSlot()
    def on_pushButton_start_clicked(self):
        if self.metronome.state == MetroState.PAUSE:
            self.metronome.clear()
            # 线程
            play_beat_th = threading.Thread(target=self.metronome.start)
            play_beat_th.start()
            self.pushButton_start.setText("暂停")
        else:
            self.metronome.state = MetroState.PAUSE
            self.pushButton_start.setText("开始")

    @pyqtSlot(str)
    def on_lineEdit_beat_num_textChanged(self, value: str):
        try:
            self.metronome.beat_num = int(value)
        except ValueError:
            self.metronome.beat_num = 4

    def closeEvent(self, event: QEvent) -> None:
        self.metronome.state = MetroState.PAUSE  # 关闭线程


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
