from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QStackedLayout, QButtonGroup, QRadioButton, QSlider, QSpinBox, QComboBox, QLabel, QPushButton
from PyQt5.QtGui import QColor, QPalette, QPainter, QPen
from PyQt5.QtCore import QRect, QPropertyAnimation, QLine
from enum import Enum
import numpy as np
from synth_wrapper import SynthWrapper, ProgramSelector
from clock import AudioSchedule

class LooperState(Enum):
    DISABLED = 1
    RECORD = 2
    PLAY = 3

    def __str__(self):
        if self.value == self.DISABLED.value:
            return "DISABLED"
        elif self.value == self.RECORD.value:
            return "RECORD"
        elif self.value == self.PLAY.value:
            return "PLAY"
        return "NOT MATCHING"


# class Schedule(object):
#     def __init__(self, index):
#         self.n_commands = 0
#         self.schedule = []

#     def add_note(self, beat, pitch, on_off):

sched_1 = [(0, 0, 1), (0.5, 0, 0), (1, 2, 1), (1.5, 2, 0), (2, 4, 1), (2.5, 4, 0), (3, 5, 1), (3.5, 5, 0)]
sched_2 = [(0, 12, 1), (0.5, 12, 0), (1, 14, 1), (1.5, 14, 0), (2, 16, 1), (2.5, 16, 0), (3, 17, 1), (3.5, 17, 0)]
sched_3 = [(2, 4, 1), (2.5, 4, 0)]
sched_4 = [(3, 5, 1), (3.5, 5, 0)]
scheds = [sched_1, sched_2, sched_3, sched_4]

class LoopingTrack(object):
    def __init__(self, index, synth, clock):
        super(LoopingTrack, self).__init__()
        self.index = index
        self.synth = synth
        self.clock = clock
        self.bpm = 60
        self.bpl = 16 #TODO fix
        self.mode = LooperState.DISABLED
        # self.schedule = AudioSchedule(self.bpm, self.bpl, scheds[index]) # TODO fix
        self.schedule = AudioSchedule(self.bpm, self.bpl, [])
        self.quantize = False
        self.quantize_number = 12 # allows for triplets
        self.new_state_loaded = False

    def change_state(self, new_state):
        if new_state == self.mode:
            return
        if new_state == LooperState.DISABLED:
            self.clock.disable_track(self.index)
            print("disabled")
        elif new_state == LooperState.RECORD:
            self.schedule.schedule_beats = []
            self.clock.reset_track_offset(self.index)
            self.clock.disable_track(self.index)
            # self.clock.set
            # self.recording = True
            print("Record")
        #play
        else:
            print("play")
            self.clock.post_schedule(self.index, self.schedule)
            if self.mode == LooperState.DISABLED:
                self.clock.enable_track(self.index, False)
            # # keep offset when recording
            else:
                self.clock.enable_track(self.index, True)
        self.mode = new_state

    def set_quantize(self, quantize):
        self.quantize = quantize
        print("Quantize", self.quantize)

    def set_bpm(self, bpm):
        self.bpm = bpm
        self.schedule.bpm = bpm
        print("Set bpm of track " + str(self.index))
        print(str(self.bpm))
        self.clock.post_schedule(self.index, self.schedule)

    def set_bpl(self, bpl):
        self.bpl = bpl
        self.schedule.beats_per_loop = bpl
        self.clock.post_schedule(self.index, self.schedule)
        print("Set bpl of track " + str(self.index))
        print(str(self.bpl))
        #TODO post schedule

    def set_schedule(self, schedule):
        self.change_state(LooperState.DISABLED)
        self.schedule = schedule
        

    def set_volume(self, volume):
        self.synth.set_volume(volume)
        print(str(volume))

    def get_program_names(self):
        return self.synth.program_selector.get_program_names()
    
    def set_program(self, index):
        print(str(index))
        self.synth.set_instrument(index)
    
    def set_midi_offset(self, offset):
        self.synth.set_midi_offset(offset)

    def on_keystroke(self, note_idx, up_down):
        if self.mode == LooperState.RECORD:
            beat = self.clock.get_current_beat(self.index, self.bpm)
            # quantize beat quantize number
            if self.quantize:
                beat = np.round(beat * self.quantize_number) / self.quantize_number
            self.schedule.schedule_beats.append((beat, note_idx, up_down))
            print(self.schedule.schedule_beats)
        # if self.mode == LooperState.RECORD:
        #     print("sent command " + str(note_idx) + " " + str(up_down))
            self.synth.do_command(note_idx, up_down)

    def get_state(self):
        state_dic = {}
        state_dic["bpm"] = self.bpm
        state_dic["bpl"] = self.bpl
        state_dic["schedule_beats"] = self.schedule.schedule_beats
        state_dic["program"] = self.synth.program
        state_dic["midi_offset"] = self.synth.midi_offset
        state_dic["volume"] = self.synth.volume
        return state_dic
        
    def load_from_state(self, state_dict):
        self.change_state(LooperState.DISABLED)
        self.bpm = state_dict["bpm"]
        self.bpl = state_dict["bpl"]
        
        self.schedule.bpm = self.bpm
        self.schedule.beats_per_loop = self.bpl
        self.schedule.schedule_beats = state_dict["schedule_beats"]

        self.set_program(state_dict["program"])
        self.set_midi_offset(state_dict["midi_offset"])
        self.set_volume(state_dict["volume"])

        self.new_state_loaded = True

class TimeSweep(QWidget):
    def __init__(self, looper, color, **kwargs):
        super(TimeSweep, self).__init__(**kwargs)
        palette = QPalette()
        palette.setColor(palette.Window, QColor("white"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        self.width = self.frameGeometry().width()
        self.height = self.frameGeometry().height()
        self.line = QLine(0, 0, 0, self.height)

        self.looper = looper

        self.started = False
    
    def start_anim(self):
        self.started = True
        # self.animation.start()

    def stop_anim(self):
        self.started = False
        self.repaint()

    def resizeEvent(self, event):
        self.width = self.frameGeometry().width()
        self.height = self.frameGeometry().height()
        QWidget.resizeEvent(self, event)
        self.on_update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.started:
            painter.setPen(QPen(QColor('black'), 5))
            painter.drawLine(self.line)
        else:
            painter.eraseRect(0, 0, self.width, self.height)
    
    def on_update(self):
        if self.started:
            current_beat = (self.looper.clock.get_current_beat(self.looper.index, self.looper.bpm)) % self.looper.bpl
            # print(current_beat)
            x_pos = current_beat * self.width / self.looper.bpl
            self.line.setLine(x_pos, 0, x_pos, self.height)
            self.repaint()

# class NoteRow(QWidget):
#     def __init__(self, color, **kwargs):
#         super(NoteRow, self).__init__(**kwargs)
#         palette = QPalette()
#         palette.setColor(palette.Window, QColor("white"))
#         self.setPalette(palette)
#         self.setAutoFillBackground(True)
#         self.notes = []
#         self.width = self.frameGeometry().width()
#         self.height = self.frameGeometry().height()
#         self.color = color
#         # self.painter = QPainter(self)
#         self.duration = -1
#         self.notes_changed = 0

#     def set_duration(self, duration):
#         self.duration = duration
    
#     def plot_note(self, note_start, note_end):
#         # left, top, width, height
#         note = QRect(note_start * self.width / self.duration, 0, (note_end - note_start) * self.width / self.duration, self.height)
#         self.notes.append((note_start, note_end, note))
    
#     def clear_all_notes(self):
#         pass

#     def plot_all_notes(self):
#         pass

#     def paintEvent(self, event):
#         print("This note is trying to paint")
#         painter = QPainter(self)
#         painter.setPen(QPen(QColor(self.color), 5))
#         if len(self.notes) > 0:
#             for _, _, note in self.notes:
#                 painter.drawRect(note)
#         else:
#             painter.eraseRect(0, 0, self.width, self.height)

#     # def resizeEvent(self, event):
#     #     self.clear_all_notes()
#     #     self.plot_all_notes()
#     #     self.width = self.frameGeometry().width()
#     #     self.height = self.frameGeometry().height()
#     #     QWidget.resizeEvent(self, event)
#     #     self.on_update()

#     def on_update(self):
#         if self.notes_changed:
#             print("we got here but aren't painting")
#             self.repaint()
#             self.notes_changed = 0

lowest_note = -5
highest_note =  28

# class NoteVisualizer(QWidget):
#     def __init__(self, color, **kwargs):
#         super(NoteVisualizer, self).__init__(**kwargs)
#         self.note_rows = {}
#         vlayout = QVBoxLayout()

#         for i in range(lowest_note, highest_note+1):
#             tmp = NoteRow(color)
#             self.note_rows[i] = tmp
#             vlayout.addWidget(tmp)

#         # self.setLayout(vlayout)

#     def plot_schedule(self, schedule):
#         command_pairs = {}
#         for beat, pitch, on_off in schedule.schedule_beats:
#             if pitch not in command_pairs.keys():
#                 command_pairs[pitch] = []
#                 # first is a note off (carry note over from end of loop)
#                 if not on_off:
#                     command_pairs[pitch].append((0, 1))
#             command_pairs[pitch].append((beat, on_off))
#         print(command_pairs)
#         for pitch in command_pairs.keys():
#             on_note = -1
#             looking_for = 1 # whether to find the next on (1) or off not (0)
#             self.note_rows[pitch].set_duration(schedule.beats_per_loop)
#             for (beat, on_off) in command_pairs[pitch]:
#                 if looking_for and on_off:
#                     on_note = beat
#                     looking_for = 0
#                 elif not looking_for and not on_off:
#                     print("plotting note at pitch " + str(pitch) + " start " + str(on_note) + " end " + str(beat))
#                     self.note_rows[pitch].plot_note(on_note, beat)
#                     looking_for = 1
            
#             self.note_rows[pitch].notes_changed = 1

#     def on_update(self):
#         for nr in self.note_rows.values():
#             nr.on_update()
                    
            

default_bpm = 60
default_bpl = 16

class LooperGUI(QWidget):
    def __init__(self, index, n_loopers, loopers):
        super(LooperGUI, self).__init__()

        palette = QPalette()
        palette.setColor(palette.Window, QColor.fromHsvF(index / n_loopers, 1, 1))
        self.setPalette(palette)
        self.setAutoFillBackground(True)


        self.index = index
        self.looper = loopers[index]
        self.loopers = loopers
        hlayout = QHBoxLayout()
        
        # Mode buttons
        mode_button_layout = QVBoxLayout()
        self.mode_buttons = QButtonGroup()

        disable_button = QRadioButton("Disable")
        disable_button.setChecked(True)
        disable_button.toggled.connect(self.mode_change)
        self.mode_buttons.addButton(disable_button, LooperState.DISABLED.value)
        mode_button_layout.addWidget(disable_button)

        record_button = QRadioButton("Record")
        record_button.toggled.connect(self.mode_change)
        self.mode_buttons.addButton(record_button, LooperState.RECORD.value)
        mode_button_layout.addWidget(record_button)

        play_button = QRadioButton("Play")
        play_button.toggled.connect(self.mode_change)
        self.mode_buttons.addButton(play_button, LooperState.PLAY.value)
        mode_button_layout.addWidget(play_button)

        hlayout.addLayout(mode_button_layout)

        # BPM BPL Instrument
        bpm_bpl_sync_layout = QVBoxLayout()
        self.bpm_spin_box = QSpinBox(minimum=1, maximum=300, value=default_bpm)
        self.bpm_spin_box.editingFinished.connect(self.set_bpm)
        self.bpm_spin_box.setPrefix("Beats per Minute: ")
        bpm_bpl_sync_layout.addWidget(self.bpm_spin_box)
        self.bpl_spin_box = QSpinBox(minimum=1, maximum=64, value=default_bpl)
        self.bpl_spin_box.editingFinished.connect(self.set_bpl)
        self.bpl_spin_box.setPrefix("Beats per Loop: ")
        bpm_bpl_sync_layout.addWidget(self.bpl_spin_box)
        sync_combobox = QComboBox()
        sync_combobox.addItem("No Sync")
        self.sync_tracks = []
        for i in range(n_loopers):
            if i != index:
                sync_combobox.addItem("Sync to Track " + str(i + 1))
                self.sync_tracks.append(i)

        bpm_bpl_sync_layout.addWidget(sync_combobox)
        sync_combobox.currentIndexChanged.connect(self.set_sync)
        hlayout.addLayout(bpm_bpl_sync_layout)


        # Volume
        slider_layout = QVBoxLayout()
        self.volume_slider = QSlider(minimum = 0, maximum = 100, value = 60)
        self.volume_slider.valueChanged.connect(self.looper.set_volume)
        slider_layout.addWidget(self.volume_slider)
        slider_layout.addWidget(QLabel(text = "Volume"))
        hlayout.addLayout(slider_layout)

        # Instrument, pitch offset, quantize
        i_po_q_layout = QVBoxLayout()
        self.instrument_combobox = QComboBox()
        self.instrument_combobox.currentIndexChanged.connect(self.looper.set_program)
        for program_name in self.looper.get_program_names():
            self.instrument_combobox.addItem(program_name)
        i_po_q_layout.addWidget(self.instrument_combobox)
        self.po_spin_box = QSpinBox(minimum=21, maximum=108, value=60)
        self.po_spin_box.editingFinished.connect(self.set_midi_offset)
        self.po_spin_box.setPrefix("R Key MIDI value: ")
        i_po_q_layout.addWidget(self.po_spin_box)
        self.quantize_button = QPushButton("Quantize Notes")
        self.quantize_button.setCheckable(True)
        self.quantize_button.clicked.connect(self.toggle_quantize)
        i_po_q_layout.addWidget(self.quantize_button)
        hlayout.addLayout(i_po_q_layout)

        wrapper_layout = QHBoxLayout()
        wrapper_layout.addLayout(hlayout, stretch=1)

        # Note Visualizer
        # self.note_visualizer = NoteVisualizer(QColor.fromHsvF(index / n_loopers, 1, 1))
        self.sweep = TimeSweep(self.looper, QColor.fromHsvF(index / n_loopers, 1, 1))
        vis_sweep_layout = QStackedLayout()
        # vis_sweep_layout.addWidget(self.note_visualizer)
        vis_sweep_layout.addWidget(self.sweep)
        vis_sweep_layout.setStackingMode(QStackedLayout.StackAll)

        wrapper_layout.addLayout(vis_sweep_layout, stretch=1)


        self.setLayout(wrapper_layout)

    def mode_change(self, state):
        if state:
            mode_id = self.mode_buttons.checkedId()
            mode = LooperState(mode_id)
            self.looper.change_state(mode)
            if mode != LooperState.DISABLED:
                self.sweep.start_anim()
            else:
                self.sweep.stop_anim()

            # if mode != LooperState.RECORD:
            #     self.note_visualizer.plot_schedule(self.looper.schedule)

    def set_bpm(self):
        self.looper.set_bpm(self.bpm_spin_box.value())
        self.sweep.bpm = self.bpm_spin_box.value()

    def set_bpl(self):
        self.looper.set_bpl(self.bpl_spin_box.value())
        self.sweep.bpl = self.bpl_spin_box.value()

    def set_midi_offset(self):
        self.looper.set_midi_offset(self.po_spin_box.value())

    def toggle_quantize(self):
        self.looper.set_quantize(self.quantize_button.isChecked())

    def set_sync(self, index):
        if index != 0:
            sync_track = self.sync_tracks[index - 1]
            self.looper.set_bpm(self.loopers[sync_track].bpm)
            self.bpm_spin_box.setValue(self.loopers[sync_track].bpm)
            self.looper.set_bpl(self.loopers[sync_track].bpl)
            self.bpl_spin_box.setValue(self.loopers[sync_track].bpl)
            self.looper.clock.sync(self.index, sync_track)

    def on_update(self):
        self.sweep.on_update()
        # self.note_visualizer.on_update()
        if self.looper.new_state_loaded:
            self.looper.new_state_loaded = False

            self.bpm_spin_box.setValue(self.looper.bpm)
            self.bpl_spin_box.setValue(self.looper.bpl)

            # self.note_visualizer.plot_schedule(self.looper.schedule)
            self.instrument_combobox.setCurrentIndex(self.looper.synth.program)
            self.po_spin_box.setValue(self.looper.synth.midi_offset)
            self.volume_slider.setValue(self.looper.synth.volume)





