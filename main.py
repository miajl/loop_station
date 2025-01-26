from PyQt5.QtWidgets import (QApplication, QMainWindow, QHBoxLayout,
                              QVBoxLayout, QWidget, QLabel, QStackedLayout,
                                QPushButton, QFileDialog)
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal
from synth_wrapper import SynthWrapper
from looper import LooperGUI, LoopingTrack
from clock import Clock
import yaml
import sys
import time
import os

ticks_per_second = 1024

# maps key on keyboard to pitch (on initiate this is offset by 60 so 
# 'r' is middle C)
keymap = {'q':-5, # G
          '2':-4, # G#
          'w':-3, # A
          '3':-2, # A#
          'e':-1, # B
          'r':0, # C
          '5':1, # C#
          't':2, # D
          '6':3, # D#
          'y':4, # E
          'u':5, # F
          '8':6, # F#
          'i':7, # G
          '9':8, # G#
          'o':9, # A
          '0':10, # A#
          'p':11, # B
          '[':12, # C
          'z':12, # C
          's':13, # C#
          'x':14, # D
          'd':15, # D#
          'c':16, # E
          'v':17, # F
          'g':18, # F#
          'b':19, # G
          'h':20, # G#
          'n':21, # A
          'j':22, # A#
          'm':23, # B
          ',':24, # C
          'l':25, # C#
          '.':26, # D
          ';':27, # D#
          '/':28 # E
          }

# Maps notes as (white_key, key, pitch) where white_key is a bool that is true 
# if the key is white or false if it is black. Used by piano gui
key_description = [(True, 'q', -5), # G
          (False, '2', -4), # G#
          (True, 'w', -3), # A
          (False, '3', -2), # A#
          (True, 'e', -1), # B
          (True, 'r', 0), # C
          (False, '5', 1), # C#
          (True, 't', 2), # D
          (False, '6', 3), # D#
          (True, 'y', 4), # E
          (True, 'u', 5), # F
          (False, '8', 6), # F#
          (True, 'i', 7), # G
          (False, '9', 8), # G#
          (True, 'o', 9), # A
          (False, '0', 10), # A#
          (True, 'p', 11), # B
          (True, '[, z', 12), # C
          (False, 's', 13), # C#
          (True, 'x', 14), # D
          (False, 'd', 15), # D#
          (True, 'c', 16), # E
          (True, 'v', 17), # F
          (False, 'g', 18), # F#
          (True, 'b', 19), # G
          (False, 'h', 20), # G#
          (True, 'n', 21), # A
          (False, 'j', 22), # A#
          (True, 'm', 23), # B
          (True, ',', 24), # C
          (False, 'l', 25), # C#
          (True, '.', 26), # D
          (False, ';', 27), # D#
          (True, '/', 28) # E
]



class KeyWidget(QLabel):
    '''Widget for each key which shows its label and turns red when pressed
       key_type (bool): True if key is white, False if black
       label (str): Label to be shown on widget'''
    def __init__(self, key_type, label):
        super().__init__()
        self.setAutoFillBackground(True)
        self.plain_palette = QPalette()
        if key_type:
            self.plain_palette.setColor(QPalette.Window, QColor('white'))
            self.plain_palette.setColor(QPalette.WindowText, QColor('black'))
        else:
            self.plain_palette.setColor(QPalette.Window, QColor('black'))
            self.plain_palette.setColor(QPalette.WindowText, QColor('white'))

        self.pressed_palette = QPalette()
        self.pressed_palette.setColor(QPalette.Window, QColor('red'))
        self.setText(label)
        self.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self.setPalette(self.plain_palette)

    def set_key_press(self, pressed):
        '''Sets key color as either pressed (red) or released (black/white)'''
        if pressed:
            self.setPalette(self.pressed_palette)
        else:
            self.setPalette(self.plain_palette)

class PianoWidget(QWidget):
    '''Widget which contains all the piano keys'''
    def __init__(self, **kwargs):
        super(PianoWidget, self).__init__(**kwargs)
        wk_layout_container = QWidget()
        white_key_layout = QHBoxLayout(wk_layout_container)
        black_key_layout = QHBoxLayout()
        self.key_widgets = {}

        # This is to get the blakc keys to be nicely spaced like the piano

        white_key_count = 0 # counts the number of white keys between black keys
        black_key_layout.addStretch(1) # add a space because the first key is white
        for (key_type, label, note) in key_description:
            tmp = KeyWidget(key_type, label)
            self.key_widgets[note] = tmp
            if key_type:
                white_key_count += 1 # track number of white keys before next black key
                white_key_layout.addWidget(tmp) # white keys are all equally spaced
            else:
                # If there is one white key between black keys have a smaller
                #  stretch than if there are two
                if white_key_count == 1:
                    black_key_layout.addStretch(1)
                else:
                    black_key_layout.addStretch(4)
                black_key_layout.addWidget(tmp, stretch=2)
                white_key_count = 0 # reset number of white keys
        # last key is a white key so we need additional stretch
        black_key_layout.addStretch(2)

        # This layout is so the black keys only go halfway down the piano
        v_layout_container = QWidget()
        v_layout = QVBoxLayout(v_layout_container)
        v_layout.addLayout(black_key_layout, stretch = 1)
        v_layout.addStretch(1)

        # Stack the white key and black key layout
        stacked_layout = QStackedLayout()
        stacked_layout.addWidget(wk_layout_container)
        stacked_layout.addWidget(v_layout_container)
        stacked_layout.setStackingMode(QStackedLayout.StackAll)

        self.setLayout(stacked_layout)

    def set_key_press(self, note, pressed):
        '''Change color of key to reflect its pressed status'''
        self.key_widgets[note].set_key_press(pressed)

class ControlPanel(QWidget):
    '''Widget which contains the save, load and sync buttons
       load_function (function): a function with single string argument to 
                    be called on loading
       save_function (function): a function with single string argument to
                    be called on saving
       sync_function (function): a function with no arguments to be called 
                    on sync button press'''
    def __init__(self, load_function, save_function, sync_function, metronome_function):
        super(ControlPanel, self).__init__()

        #put buttons in horizontal layout
        self.layout = QHBoxLayout()
        self.load_button = QPushButton("Load File")
        self.load_button.clicked.connect(self.load_file)
        self.layout.addWidget(self.load_button)

        self.save_button = QPushButton("Save Tracks")
        self.save_button.clicked.connect(self.save_file)
        self.layout.addWidget(self.save_button)

        self.sync_button = QPushButton("Sync All Tracks")
        self.sync_button.clicked.connect(sync_function)
        self.layout.addWidget(self.sync_button)
        self.setLayout(self.layout)

        self.metronome_button = QPushButton("Use Metronome")
        self.metronome_button.setCheckable(True)
        self.metronome_button.clicked.connect(metronome_function)

        self.load_function = load_function
        self.save_function = save_function

    #TODO future work add tracks if there are more in the load file
    def load_file(self):
        '''Opens a file dialog to pick a file to load from and calls the
           load function'''
        file_dialog = QFileDialog()
        file_dialog.setWindowTitle("Load File (Select One)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            self.load_function(selected_files[0])

    def save_file(self):
        '''Opens a file dialog to pick a filename to save to and calls the 
           save function'''
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Save File")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)

        if file_dialog.exec():
            self.save_function(file_dialog.selectedFiles()[0])


        
class ThreadSupervisor(QObject):
    '''Calls the main window on_update function'''
    update_signal = pyqtSignal()
    def __init__(self, update_func):
        super(ThreadSupervisor, self).__init__()
    def run(self):
        while(True):
            self.update_signal.emit()
            time.sleep(0.1)


class MainWindow(QMainWindow):
    '''The main window of the GUI, contains all other GUI objects and the main
      on_update function'''
    def __init__(self, n_tracks, **kwargs):
        super(MainWindow, self).__init__(**kwargs)
        self.resize(900, 600)
        self.n_tracks = int(n_tracks) # number of tracks
        self.synths = [] # synths for each looper
        self.down_keys = [] # used to avoid multiple triggers per key event

        # create synths for all the tracks
        for i in range(self.n_tracks):
            self.synths.append(SynthWrapper("./data/FluidR3_GM.sf2",
                                             "./data/fluid_synth_programs.txt"))

        # initialize clock
        self.clock = Clock(self.n_tracks, self.synths, ticks_per_second)

        # initialize loopers
        self.loopers = []
        self.looper_guis = []
        self.widget = QWidget()
        self.layout = QVBoxLayout()

        # initialize control pane widget
        self.control_widget = ControlPanel(self.load_file, self.save_file,
                                            self.sync_tracks)
        self.layout.addWidget(self.control_widget, stretch=0.5)

        # create the loopers and their GUIS
        for i in range(self.n_tracks):
            self.loopers.append(LoopingTrack(i, self.synths[i], self.clock))
            gui = LooperGUI(i, self.n_tracks, self.loopers)
            self.looper_guis.append(gui)
            self.layout.addWidget(gui, stretch = 1)

        # create piano widget
        self.piano_widget = PianoWidget()
        self.layout.addWidget(self.piano_widget, stretch = 1)
        self.widget.setLayout(self.layout)
        self.setCentralWidget(self.widget)

        # Create thread for on_update function
        self.thread = QThread()
        self.thread_supervisor = ThreadSupervisor(self.on_update)
        self.thread_supervisor.moveToThread(self.thread)
        self.thread.started.connect(self.thread_supervisor.run)
        self.thread_supervisor.update_signal.connect(self.on_update)
        self.thread.start()

    def keyPressEvent(self, event):
        '''Sends a key down to each of the loopers if it is the first instance
          of the key down'''
        if event.isAutoRepeat():
            return
        # only go off the first time
        if not event.key() in self.down_keys and event.text() in keymap:            
            self.down_keys.append(event.key())
            for i in range(self.n_tracks):
                self.loopers[i].on_keystroke(keymap[event.text()], True)
                self.piano_widget.set_key_press(keymap[event.text()], True)


    def keyReleaseEvent(self, event):
        '''Sends a key up to each of the loopers if it is the first instance
          of key up after a key down'''
        if event.isAutoRepeat():
            return
        if event.key() in self.down_keys and event.text() in keymap:
            self.down_keys.remove(event.key())

            for i in range(self.n_tracks):
                self.loopers[i].on_keystroke(keymap[event.text()], False)
                self.piano_widget.set_key_press(keymap[event.text()], False)

    def load_file(self, filename):
        '''Loads schedules from yaml file at filename and sends them to the
          looper GUIs'''
        load_file = open(filename, 'r')
        load_dict = yaml.safe_load(load_file)
        for i in range(len(load_dict.keys())):
            if i < self.n_tracks:
                self.loopers[i].load_from_state(load_dict[i])


    def save_file(self, filename):
        '''Saves current looper states in yaml file with given filename'''
        save_file = open(filename, 'w')
        out_dict = {} 
        for i in range(self.n_tracks):
            out_dict[i] = self.loopers[i].get_state()
        yaml.dump(out_dict, save_file)
        save_file.close()

    def sync_tracks(self):
        '''Resets offsets for each track so they all start playing together'''
        self.clock.sync_track_starts()

    def on_update(self):
        '''Triggers on_update for clock and all looper guis'''
        self.clock.on_update()
        for looper_gui in self.looper_guis:
            looper_gui.on_update()






if __name__ == "__main__":
    # pass in how many tracks with command line argument
    app = QApplication([])
    window = MainWindow(sys.argv[1])
    window.show()
    app.exec()