import os
from operations.operation import Operation
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from dict2xml import dict2xml

'''
Finish Operation for Building the Cube and Saving All Data
Written by Sai Keshav Sasanapuri, Cecelia Ahrens, and Robert Maron
'''


class FinishOp(Operation):
    main = None

    '''Starts Finish Operation'''

    def on_start(self):
        # The save-folder dialog must be shown on the MAIN thread: on
        # macOS, native file dialogs (NSOpenPanel) abort the app if they
        # are created from a worker thread.
        try:
            destination_dir = QFileDialog.getExistingDirectory(
                self.main, "Choose a folder to save the cube")
        except Exception:
            destination_dir = None
        if destination_dir is None or destination_dir == "":
            # User cancelled: nothing saved, re-enable the controls
            self.main.finishPageTitle.setText("Select a folder to save the cube")
            self.main.finishInfoText.setText("No folder selected — nothing was saved.")
            self.main.finishFinishButton.setEnabled(True)
            self.main.finishRedoButton.setEnabled(True)
            self.main.finishComboBox.setEnabled(True)
            self.main.finishInfoText.setEnabled(True)
            self.main.finishStartOverButton.setEnabled(True)
            return

        self.main.finish_destination_dir = destination_dir

        # start thread, move worker to thread
        self.main.thread = QThread()
        self.main.worker = FinishWorker()
        self.main.worker.moveToThread(self.main.thread)
        self.main.worker.main = self.main
        self.main.thread.started.connect(self.main.worker.run)

        # connect slots
        self.main.worker.finished.connect(self.finished)
        self.main.worker.progress_box.connect(self.updateProgressDialog)

        # start
        self.main.thread.start()

    '''Finish Operation'''

    def finished(self, error):
        self.main.thread.quit()
        if error != '':
            self.main.finishInfoText.setText(error)

    '''Cancel Operation'''

    def cancel(self):
        self.main.thread.quit()

    '''Start or Stop Progress dialog box'''

    def updateProgressDialog(self, message):
        if message == "close":
            self.main.progress_box.stop()
        else:
            self.main.progress_box.start(message)


class FinishWorker(QObject):
    main = None
    finished = pyqtSignal(str)
    progress_box = pyqtSignal(str)

    def run(self):
        # Output directory was chosen on the main thread in on_start()
        destination_dir = self.main.finish_destination_dir
        self.main.finishPageTitle.setText("Saving cube to " + destination_dir)
        self.progress_box.emit("Saving cube")

        # cleaning up object title for saving data
        name = self.main.metadata["title"]
        name = name.replace(' ', "_")
        name = f"{name}_DataCube"

        # generate xml (once)
        metadata_xml = dict2xml({"metadata": self.main.metadata})
        with open(os.path.join(destination_dir, name + "-metadata.xml"), "w") as file:
            file.write(metadata_xml)

        # save exposure profile
        self.main.light_op.saveProfile("MISHA_ExposureProfile", destination_dir)

        # build and save cube and images
        build_result = self.main.cube_builder.build(destination_dir, name)
        if build_result == None:
            self.finished.emit('')
        else:
            self.finished.emit(build_result)
        self.main.finishPageTitle.setText("Cube saved in selected folder")
        self.progress_box.emit("close")
        self.main.finishFinishButton.setEnabled(True)
        self.main.finishRedoButton.setEnabled(True)
        self.main.finishComboBox.setEnabled(True)
        self.main.finishInfoText.setEnabled(True)
        self.main.finishStartOverButton.setEnabled(True)
