import sys
import datetime as dt
import RPi.GPIO as GPIO
import time
import threading
import enum
import qrc_rc
import random

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5 import QtCore, QtGui, QtWidgets, QtTest
from PyQt5 import uic

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(17, GPIO.IN)
GPIO.setup(27, GPIO.IN)
GPIO.setup(22, GPIO.IN)
GPIO.setup(5, GPIO.IN)

#motor setup
GPIO.setup(23, GPIO.OUT,initial=GPIO.LOW)
GPIO.setup(24, GPIO.OUT,initial=GPIO.LOW)

GPIO.output(23, GPIO.LOW)
GPIO.output(24, GPIO.LOW)

form_class = uic.loadUiType("ui_main_page_1104.ui")[0]

style_lbl_pump_on = "border: none;color: rgb(0, 255, 0);"
style_lbl_pump_off = "border: none;color: rgb(80, 80, 80);"
style_frame_pump_on = "border: 5px solid rgb(0, 255, 0);border-radius: 50px;"
style_frame_pump_off = "border: 5px solid rgb(80, 80, 80);border-radius: 50px;"

style_frame_wl_NONE = "border: 5px solid rgb(80, 80, 80);border-radius: 50px;"
style_frame_wl_LL = "border: 5px solid rgb(0, 255, 0);border-radius: 50px;"
style_frame_wl_L = "border: 5px solid rgb(255, 255, 0);border-radius: 50px;"
style_frame_wl_H = "border: 5px solid rgb(255, 85, 0);border-radius: 50px;"
style_frame_wl_HH = "border: 5px solid rgb(255, 0, 0);border-radius: 50px;"

style_lbl_wl_NONE = "border-radius: 25px;border-width: 0px;color: rgb(80, 80, 80);background-color: none;"
style_lbl_wl_LL = "border-radius: 25px;border-width: 0px;color: rgb(0, 255, 0);background-color: none;"
style_lbl_wl_L = "border-radius: 25px;border-width: 0px;color: rgb(255, 255, 0);background-color: none;"
style_lbl_wl_H = "border-radius: 25px;border-width: 0px;color: rgb(255, 85, 0);background-color: none;"
style_lbl_wl_HH = "border-radius: 25px;border-width: 0px;color: rgb(255, 0, 0);background-color: none;"
style_lbl_wl_on = "border-radius: 25px;border-width: 0px;color: rgb(255, 255, 255);background-color: rgb(0, 255, 0);"
style_lbl_wl_off = "border-radius: 25px;border-width: 0px;color: rgb(255, 255, 255);background-color: rgb(255, 0, 0);"

class PIN(enum.Enum):
    HH = 5
    H = 22
    L = 27
    LL = 17
    MOTOR1 = 23
    MOTOR2 = 24

class State(enum.Enum):
    NONE = 0
    LL = 1
    L = 2
    H = 3
    HH = 4
    
def get_water_level_text(state):
    water_levels = ["NONE", "L-LOW", "LOW", "HIGH", "H-HIGH"]
    return water_levels[state.value]

def get_sensor_state():
    state = State.NONE;
    if (GPIO.input(PIN.HH.value) == 1):
        state = State.HH;
    elif (GPIO.input(PIN.H.value) == 1):
        state = State.H;
    elif (GPIO.input(PIN.L.value) == 1):
        state = State.L;
    elif (GPIO.input(PIN.LL.value) == 1):
        state = State.LL;
    return state

class sensorThread(QThread):
    sensor_changed = pyqtSignal(State, State)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.working = True
        
    def __del__(self):
        self.stop()
        self.wait()
    
    def stop(self):
        GPIO.output(PIN.MOTOR1.value, GPIO.LOW)
        GPIO.output(PIN.MOTOR2.value, GPIO.LOW)
        self.working = False
        self.quit()
    
    def run(self):
        state = State.NONE;
        last_state = State.NONE;
        motor_state = State.NONE;
        while self.working:
            state = get_sensor_state()

            if (state != last_state or self.main.update == True):
                #일반동작
                if (self.main.prediction_mode == False):
                    if (last_state == State.L and state == State.H):
                        motor_state = State.H
                    elif (last_state == State.H and state == State.HH):
                        motor_state = State.HH        
                    elif (last_state == State.H and state == State.L):
                        motor_state = State.L          
                    elif (last_state == State.L and state == State.LL):
                        motor_state = State.LL
                    elif (state == State.NONE):
                        motor_state = State.LL
                #예측동작
                else:
                    if (self.main.rainfall_per_h >= 20):
                        motor_state = State.HH
                    elif (self.main.rainfall_per_h >= 15):
                        motor_state = State(min(4, state.value + 2))
                    elif (self.main.rainfall_per_h >= 10):
                        motor_state = State(min(4, state.value + 1))
                    else:
                        motor_state = state
                self.main.update = False
                self.sensor_changed.emit(state, motor_state)
                
            last_state = state

class predictThread(QThread):
    def __init__(self, startTime, parent=None):
        super().__init__(parent)
        self.main = parent
        self.time = startTime
        self.working = True
        
    def __del__(self):
        self.stop()
        self.wait()
        
    def stop(self):
        self.working = False
        self.quit()
        
    def run(self):
        while self.working == True:
            self.time = self.time.addSecs(-1)
            self.main.lineEdit_predict_timer.setText(self.time.toString("hh:mm:ss"))
            if (abs(self.time.secsTo(QTime(0, 0))) <= 0):
                self.main.lineEdit_waterlevel.setText("")
                self.main.lineEdit_predict_timer.setText("")
                self.main.lineEdit_rainfallperhour.setText("")
                self.main.rainfall_per_h = -1
                self.main.update = True
                self.main.prediction_mode = False
                self.working = False
                
                self.main.lbl_predict.setStyleSheet(style_lbl_pump_off)
                self.main.frame_predict.setStyleSheet(style_frame_pump_off)
                self.main.lbl_predict.setText("OFF")
                self.main.btn_predict.setText("예측값 사용")
                self.main.btn_predict_reset.setEnabled(True)
            loop = QtCore.QEventLoop()
            QtCore.QTimer.singleShot(1000, loop.quit)
            loop.exec_()


class MyWindow(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.rainfall_per_h = -1
        self.update = False
        self.prediction_mode = False
        self.state = State.NONE;
        self.motor_state = State.NONE;
        self.setupUi(self)
        self.btn_submit.clicked.connect(self.submit_clicked)
        self.btn_predict.clicked.connect(self.predict_clicked)
        self.btn_submit_reset.clicked.connect(self.submit_reset_clicked)
        self.btn_predict_reset.clicked.connect(self.predict_reset_clicked)
        
        self.listWidget_time.clicked.connect(self.listWidget_time_clicked)
        self.listWidget_rainfall.clicked.connect(self.listWidget_rainfall_clicked)
        
        self.predict_thread = None
        self.sensor_thread = sensorThread(parent=self)
        self.sensor_thread.sensor_changed.connect(self.update_GUI)
        #self.sensor_thread.start()
        
    def closeEvent(self, e):
        self.hide()
        if (self.sensor_thread) :
            self.sensor_thread.stop()
        if (self.predict_thread):
            self.predict_thread.stop()
        GPIO.output(PIN.MOTOR1.value, GPIO.LOW)
        GPIO.output(PIN.MOTOR2.value, GPIO.LOW)
        print("closeEvent() called")
      
    def predict_clicked(self):
        if (not self.prediction_mode):
            if (self.rainfall_per_h < 0) :
                QMessageBox.warning(self, "오류", "계산된 결과 없음")
                return
            
            self.prediction_mode = True
            self.update = True
            startTime = QTime.fromString(self.lineEdit_predict_timer.text(), "hh:mm:ss")
            self.predict_thread = predictThread(parent=self, startTime=startTime)
            self.predict_thread.start()
            
            self.lbl_predict.setStyleSheet(style_lbl_pump_on)
            self.frame_predict.setStyleSheet(style_frame_pump_on)
            self.btn_predict.setText("예측값 사용 중지")
            self.btn_predict_reset.setEnabled(False)
            
            #self.update_GUI(self.state, self.motor_state)
        else:
            if (self.predict_thread):
                self.predict_thread.terminate()
                #self.predict_thread.working = False
                #self.predict_thread.stop()
            
#            self.predict_thread.exit()
            
            self.lbl_predict.setStyleSheet(style_lbl_wl_LL)
            self.frame_predict.setStyleSheet(style_frame_wl_LL)
            self.prediction_mode = False
            self.update = True
            self.lbl_predict.setText("L-LOW");
            self.btn_predict.setText("예측값 사용")
            self.btn_predict_reset.setEnabled(True)
            
    def submit_clicked(self):
        if (self.prediction_mode == True) :
            QMessageBox.warning(self, "오류", "예측모델 동작중")
            return
        
        secs = abs(self.timeEdit_predict.time().secsTo(QTime(0, 0)))
        if (secs <= 0):
            QMessageBox.warning(self, "오류", "시간 입력 오류")
            return
        
        rainfall = self.spinBox_rainfall.value()
        if (rainfall <= 0):
            QMessageBox.warning(self, "오류", "강수량 입력 오류")
            return
        
        self.rainfall_per_h = rainfall / secs * 3600

        print("secs : " + str(secs))
        print("rainfall : " + str(rainfall) + " mm")
        print("rainfall per hour : " + str(self.rainfall_per_h) + " mm")
        
        
        if (self.rainfall_per_h >= 20):
            self.lineEdit_waterlevel.setText("H-High")
        elif (self.rainfall_per_h >= 15):
            self.lineEdit_waterlevel.setText("+2")
        elif (self.rainfall_per_h >= 10):
            self.lineEdit_waterlevel.setText("+1")
        else:
            self.lineEdit_waterlevel.setText("+0")
        
        self.lineEdit_predict_timer.setText(self.timeEdit_predict.time().toString("hh:mm:ss"))
        self.lineEdit_rainfallperhour.setText(str(round(self.rainfall_per_h, 2)) + " mm")
    
    def submit_reset_clicked(self):
        self.timeEdit_predict.setTime(QTime.fromString("00:00:00", "hh:mm:ss"))
        self.spinBox_rainfall.setValue(0)
    
    def predict_reset_clicked(self):
        self.rainfall_per_h = -1
        self.lineEdit_waterlevel.setText("")
        self.lineEdit_predict_timer.setText("")
        self.lineEdit_rainfallperhour.setText("")
        
    def listWidget_time_clicked(self):
        item = self.listWidget_time.currentItem()
        if (item):
            self.timeEdit_predict.setTime(QTime.fromString(item.text(), "hh:mm:ss"))
            
    def listWidget_rainfall_clicked(self):
        item = self.listWidget_rainfall.currentItem()
        if (item):
            self.spinBox_rainfall.setValue(int(item.text()))
        
    @pyqtSlot(State, State)
    def update_GUI(self, state, motor_state):
        self.state = state;
        self.motor_state = motor_state;
        self.lbl_waterlevel.setText(get_water_level_text(state))
        
        if (self.prediction_mode) :
            if (motor_state == State.NONE):
                self.lbl_predict.setText("L-LOW")
            else:
                self.lbl_predict.setText(get_water_level_text(motor_state))
            if (motor_state == State.L):
                self.lbl_predict.setStyleSheet(style_lbl_wl_L)
                self.frame_predict.setStyleSheet(style_frame_wl_L)
            elif (motor_state == State.LL):
                self.lbl_predict.setStyleSheet(style_lbl_wl_LL)
                self.frame_predict.setStyleSheet(style_frame_wl_LL)
            elif (motor_state == State.H):
                self.lbl_predict.setStyleSheet(style_lbl_wl_H)
                self.frame_predict.setStyleSheet(style_frame_wl_H)
            elif (motor_state == State.HH):
                self.lbl_predict.setStyleSheet(style_lbl_wl_HH)
                self.frame_predict.setStyleSheet(style_frame_wl_HH)
            else:
                self.lbl_predict.setStyleSheet(style_lbl_wl_LL)
                self.frame_predict.setStyleSheet(style_frame_wl_LL)
        
        #sensor update
        if (state == State.HH):
            self.progressBar_water.setValue(90)
            self.lbl_wl_HH.setStyleSheet(style_lbl_wl_on)
            self.lbl_wl_H.setStyleSheet(style_lbl_wl_on)
            self.lbl_wl_L.setStyleSheet(style_lbl_wl_on)
            self.lbl_wl_LL.setStyleSheet(style_lbl_wl_on)
            self.lbl_waterlevel.setStyleSheet(style_lbl_wl_HH)
            self.frame_waterlevel.setStyleSheet(style_frame_wl_HH)
        elif (state == State.H):
            self.progressBar_water.setValue(65)
            self.lbl_wl_HH.setStyleSheet(style_lbl_wl_off)
            self.lbl_wl_H.setStyleSheet(style_lbl_wl_on)
            self.lbl_wl_L.setStyleSheet(style_lbl_wl_on)
            self.lbl_wl_LL.setStyleSheet(style_lbl_wl_on)
            self.lbl_waterlevel.setStyleSheet(style_lbl_wl_H)
            self.frame_waterlevel.setStyleSheet(style_frame_wl_H)
        elif (state == State.L):
            self.progressBar_water.setValue(40)
            self.lbl_wl_HH.setStyleSheet(style_lbl_wl_off)
            self.lbl_wl_H.setStyleSheet(style_lbl_wl_off)
            self.lbl_wl_L.setStyleSheet(style_lbl_wl_on)
            self.lbl_wl_LL.setStyleSheet(style_lbl_wl_on)
            self.lbl_waterlevel.setStyleSheet(style_lbl_wl_L)
            self.frame_waterlevel.setStyleSheet(style_frame_wl_L)
        elif (state == State.LL):
            self.progressBar_water.setValue(15)
            self.lbl_wl_HH.setStyleSheet(style_lbl_wl_off)
            self.lbl_wl_H.setStyleSheet(style_lbl_wl_off)
            self.lbl_wl_L.setStyleSheet(style_lbl_wl_off)
            self.lbl_wl_LL.setStyleSheet(style_lbl_wl_on)
            self.lbl_waterlevel.setStyleSheet(style_lbl_wl_LL)
            self.frame_waterlevel.setStyleSheet(style_frame_wl_LL)
        else:
            self.progressBar_water.setValue(1)
            self.lbl_wl_HH.setStyleSheet(style_lbl_wl_off)
            self.lbl_wl_H.setStyleSheet(style_lbl_wl_off)
            self.lbl_wl_L.setStyleSheet(style_lbl_wl_off)
            self.lbl_wl_LL.setStyleSheet(style_lbl_wl_off)
            self.lbl_waterlevel.setStyleSheet(style_lbl_wl_NONE)
            self.frame_waterlevel.setStyleSheet(style_frame_wl_NONE)
        # motor update
        if (motor_state == State.H or motor_state == State.L):
            self.lbl_pump1.setText("ON")
            self.lbl_pump2.setText("OFF")
            self.lbl_pump1.setStyleSheet(style_lbl_pump_on)
            self.lbl_pump2.setStyleSheet(style_lbl_pump_off)
            self.frame_pump1.setStyleSheet(style_frame_pump_on)
            self.frame_pump2.setStyleSheet(style_frame_pump_off)
            GPIO.output(PIN.MOTOR1.value, GPIO.HIGH)
            GPIO.output(PIN.MOTOR2.value, GPIO.LOW)
        elif (motor_state == State.HH):
            self.lbl_pump1.setText("ON")
            self.lbl_pump2.setText("ON")
            self.lbl_pump1.setStyleSheet(style_lbl_pump_on)
            self.lbl_pump2.setStyleSheet(style_lbl_pump_on)
            self.frame_pump1.setStyleSheet(style_frame_pump_on)
            self.frame_pump2.setStyleSheet(style_frame_pump_on)
            GPIO.output(PIN.MOTOR1.value, GPIO.HIGH)
            GPIO.output(PIN.MOTOR2.value, GPIO.HIGH)
        elif (motor_state == State.LL or motor_state == State.NONE):
            self.lbl_pump1.setText("OFF")
            self.lbl_pump2.setText("OFF")
            self.lbl_pump1.setStyleSheet(style_lbl_pump_off)
            self.lbl_pump2.setStyleSheet(style_lbl_pump_off)
            self.frame_pump1.setStyleSheet(style_frame_pump_off)
            self.frame_pump2.setStyleSheet(style_frame_pump_off)
            GPIO.output(PIN.MOTOR1.value, GPIO.LOW)
            GPIO.output(PIN.MOTOR2.value, GPIO.LOW)
            
    
    def sensor(self):
        state = State.NONE;
        last_state = State.NONE;
        motor_state = State.NONE;
        self.update_GUI(state, motor_state)
        while True:
            state = get_sensor_state()
            if (state != last_state or self.update == True):
                #일반동작
                if (self.prediction_mode == False):
                    if (last_state == State.L and state == State.H):
                        motor_state = State.H
                    elif (last_state == State.H and state == State.HH):
                        motor_state = State.HH        
                    elif (last_state == State.H and state == State.L):
                        motor_state = State.L          
                    elif (last_state == State.L and state == State.LL):
                        motor_state = State.LL
                    elif (state == State.NONE):
                        motor_state = State.LL
                #예측동작
                else:
                    if (self.rainfall_per_h >= 20):
                        motor_state = State.HH
                    elif (self.rainfall_per_h >= 15):
                        motor_state = State(min(4, state.value + 2))
                    elif (self.rainfall_per_h >= 10):
                        motor_state = State(min(4, state.value + 1))
                    else:
                        motor_state = state
                self.update = False
                self.update_GUI(state, motor_state)
            last_state = state
            QApplication.processEvents()     


if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = MyWindow()
    myWindow.show()
    myWindow.sensor()
    app.exec_()