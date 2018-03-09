# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'sk8_gyro_dialog.ui'
#
# Created by: PyQt5 UI code generator 5.10
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_GyroDialog(object):
    def setupUi(self, GyroDialog):
        GyroDialog.setObjectName("GyroDialog")
        GyroDialog.setWindowModality(QtCore.Qt.ApplicationModal)
        GyroDialog.resize(551, 96)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(GyroDialog.sizePolicy().hasHeightForWidth())
        GyroDialog.setSizePolicy(sizePolicy)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(GyroDialog)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(GyroDialog)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.progressBar = QtWidgets.QProgressBar(GyroDialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.progressBar.sizePolicy().hasHeightForWidth())
        self.progressBar.setSizePolicy(sizePolicy)
        self.progressBar.setProperty("value", 0)
        self.progressBar.setObjectName("progressBar")
        self.verticalLayout.addWidget(self.progressBar)
        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(GyroDialog)
        QtCore.QMetaObject.connectSlotsByName(GyroDialog)

    def retranslateUi(self, GyroDialog):
        _translate = QtCore.QCoreApplication.translate
        GyroDialog.setWindowTitle(_translate("GyroDialog", "Gyro bias calibration"))
        self.label.setText(_translate("GyroDialog", "Keep device still, collecting samples for gyro bias calculation..."))

