from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QStackedLayout, QButtonGroup, QRadioButton, QSlider, QSpinBox, QComboBox, QLabel, QPushButton
from PyQt5.QtGui import QColor, QPalette, QPainter, QPen
from PyQt5.QtCore import QRect, QPropertyAnimation, QLine
from enum import Enum
import numpy as np
from synth_wrapper import SynthWrapper, ProgramSelector
from clock import AudioSchedule

class LooperState(Enum):
    '''Enum which tracks the state of the looper, whether it is disabled,
    recording or playing'''
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

default_bpm = 60
default_bpl = 16

class LoopingTrack(object):
    '''The back end of the looping track'''
    def __init__(self, index, synth, clock):
        super(LoopingTrack, self).__init__()
        self.index = index
        self.synth = synth
        self.clock = clock
        self.bpm = default_bpm
        self.bpl = default_bpl
        self.mode = LooperState.DISABLED
        self.schedule = AudioSchedule(self.bpm, self.bpl, [])
        self.quantize = False
        self.quantize_number = 12 # allows for triplets
        self.new_state_loaded = False # tracks whether to update the clock
        self.notes_changed = False # updates notes to check to repaint
        self.synced_to_me = [] # list of tracks synced to this track

    def change_state(self, new_state):
        '''changes state to new_state'''
        # if state hasn't changed
        if new_state == self.mode:
            return
        if new_state == LooperState.DISABLED:
            self.clock.disable_track(self.index)
        elif new_state == LooperState.RECORD:
            #clear schedule, reset and disable clock
            self.schedule.schedule_beats = []
            self.clock.reset_track_offset(self.index)
            self.clock.disable_track(self.index)
        # play state
        else:
            # post schedule to be played
            self.clock.post_schedule(self.index, self.schedule)
            # start from beginning if previous state was disabled
            if self.mode == LooperState.DISABLED:
                self.clock.enable_track(self.index, False)
            # keep offset when last mode was recording
            else:
                self.clock.enable_track(self.index, True)
        self.mode = new_state

    def set_quantize(self, quantize):
        '''whether to quantize notes as we record them'''
        self.quantize = quantize

    def set_bpm(self, bpm):
        '''update bpm and post new schedule'''
        self.bpm = bpm
        self.schedule.bpm = bpm
        self.clock.post_schedule(self.index, self.schedule)

        for looper in self.synced_to_me:
            looper.set_bpm(bpm)
            looper.new_state_loaded = True # update the gui

    def set_bpl(self, bpl):
        '''update beats per loop and post new schedule'''
        self.bpl = bpl
        self.schedule.beats_per_loop = bpl
        self.clock.post_schedule(self.index, self.schedule)
        for looper in self.synced_to_me:
            looper.set_bpl(bpl)
            looper.new_state_loaded = True # update the gui

    def set_schedule(self, schedule):
        '''set schedule from loaded file, disable track'''
        self.change_state(LooperState.DISABLED)
        self.schedule = schedule

    def set_volume(self, volume):
        '''sets synth volume'''
        self.synth.set_volume(volume)

    def get_program_names(self):
        '''gets current program name from synth'''
        return self.synth.program_selector.get_program_names()
    
    def set_program(self, index):
        '''sets synth to program at index'''
        self.synth.set_instrument(index)
    
    def set_midi_offset(self, offset):
        '''sets the midi value of the r key'''
        self.synth.set_midi_offset(offset)

    def on_keystroke(self, note_idx, up_down):
        '''plays and records note if in record mode'''
        if self.mode == LooperState.RECORD:
            beat = self.clock.get_current_beat(self.index, self.bpm)
            # quantize beat quantize number
            if self.quantize:
                beat = np.round(beat * self.quantize_number) / self.quantize_number
            # add note to schedule
            self.schedule.schedule_beats.append((beat, note_idx, up_down))
            # send command to synth
            self.synth.do_command(note_idx, up_down)


    def get_state(self):
        '''export state to dict to be saved to file'''
        state_dic = {}
        state_dic["bpm"] = self.bpm
        state_dic["bpl"] = self.bpl
        state_dic["schedule_beats_beats"] = [beat for beat, _, _ in self.schedule.schedule_beats]
        state_dic["schedule_beats_pitches"] = [pitch for _, pitch, _ in self.schedule.schedule_beats]
        state_dic["schedule_beats_onoff"] = [onoff for _, _, onoff in self.schedule.schedule_beats]
        state_dic["program"] = self.synth.program
        state_dic["midi_offset"] = self.synth.midi_offset
        state_dic["volume"] = self.synth.volume
        return state_dic
        
    def load_from_state(self, state_dict):
        '''import state from dict from save file'''
        self.change_state(LooperState.DISABLED)
        self.bpm = state_dict["bpm"]
        self.bpl = state_dict["bpl"]
        
        self.schedule.bpm = self.bpm
        self.schedule.beats_per_loop = self.bpl
        self.schedule.schedule_beats = [(beat, pitch, onoff) for beat, pitch, onoff in zip(state_dict["schedule_beats_beats"], state_dict["schedule_beats_pitches"], state_dict["schedule_beats_onoff"])]

        self.set_program(state_dict["program"])
        self.set_midi_offset(state_dict["midi_offset"])
        self.set_volume(state_dict["volume"])

        self.new_state_loaded = True

lowest_note = -5
highest_note =  28

class NoteVisualizer(QWidget):
    '''Creates the visualization of the notes and the cursor of the current position'''
    def __init__(self, looper, color, **kwargs):
        super(NoteVisualizer, self).__init__(**kwargs)
        palette = QPalette()
        palette.setColor(palette.Window, QColor("white"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self.color = color

        self.width = self.frameGeometry().width()
        self.height = self.frameGeometry().height()

        # line for sweeping 
        self.line = QLine(0, 0, 0, self.height)

        self.looper = looper

        # whether to move the cursor
        self.started = False

        self.notes = []
    
    def start_anim(self):
        '''start the cursor sweep'''
        self.started = True

    def stop_anim(self):
        '''stop the cursor sweep'''
        self.started = False
        # clear the note sweep and turn notes gray
        self.repaint()

    def pitch_to_height(self, pitch):
        '''convert note pitch to rectangle height'''
        top_offset = (highest_note - pitch) / (highest_note + 1 - lowest_note)
        return (top_offset * self.height, 1 / (highest_note + 1 - lowest_note) * self.height)
    
    def add_note(self, pitch, note_start, note_end):
        '''add note with pitch, start and end'''
        top, height = self.pitch_to_height(pitch)
        note = QRect(note_start * self.width/self.looper.bpl,
                      top,
                     (note_end - note_start) * self.width / self.looper.bpl,
                       height)
        self.notes.append(note)

    def clear_notes(self):
        '''clear notes'''
        self.notes = []

    def plot_schedule(self):
        '''plots current schedule of notes'''
        # clear existing notes
        self.clear_notes()
        # separate notes by pitch
        command_pairs = {}
        for beat, pitch, on_off in self.looper.schedule.schedule_beats:
            if pitch not in command_pairs.keys():
                command_pairs[pitch] = []
                # first is a note off (carry note over from end of loop)
                if not on_off:
                    command_pairs[pitch].append((0, 1))
            command_pairs[pitch].append((beat, on_off))

        # for each pitch make rectangle from note on and note off events
        for pitch in command_pairs.keys():
            on_note = -1 # to track the note on beat
            looking_for = 1 # whether to find the next on (1) or off not (0)
            for (beat, on_off) in command_pairs[pitch]:
                # looking for note on and note is note on
                if looking_for and on_off:
                    on_note = beat
                    looking_for = 0
                # we already have the note on and the note is a note off
                elif not looking_for and not on_off:
                    self.add_note(pitch, on_note, beat)
                    looking_for = 1

    def resizeEvent(self, event):
        '''get new width and height on resize'''
        self.width = self.frameGeometry().width()
        self.height = self.frameGeometry().height()
        QWidget.resizeEvent(self, event)
        self.on_update()

    def paintEvent(self, event):
        '''paints cursor and notes'''
        if self.looper.mode == LooperState.RECORD:
            self.plot_schedule()
        painter = QPainter(self)
        # if cursor is moving, paint cursor and notes in color
        if self.started:  
            painter.setPen(QPen(self.color, 2))
            painter.setBrush(self.color)
            for note in self.notes:
                painter.drawRect(note)
            painter.setPen(QPen(QColor('black'), 2))
            painter.drawLine(self.line)
        # otherwise paint notes in gray
        else:
            painter.eraseRect(0, 0, self.width, self.height)
            painter.setPen(QPen(QColor('gray'), 2))
            painter.setBrush(QColor('gray'))
            for note in self.notes:
                painter.drawRect(note)
    
    def on_update(self):
        # paint new cursor position every time
        if self.started:
            current_beat = (self.looper.clock.get_current_beat(self.looper.index, self.looper.bpm)) % self.looper.bpl
            x_pos = current_beat * self.width / self.looper.bpl
            self.line.setLine(x_pos, 0, x_pos, self.height)
            self.repaint()
            


class LooperGUI(QWidget):
    '''Front end of the looper'''
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
        # bpm spin box
        self.bpm_spin_box = QSpinBox(minimum=1, maximum=300, value=default_bpm)
        self.bpm_spin_box.editingFinished.connect(self.set_bpm)
        self.bpm_spin_box.setPrefix("Beats per Minute: ")
        bpm_bpl_sync_layout.addWidget(self.bpm_spin_box)
        # bpl spin box
        self.bpl_spin_box = QSpinBox(minimum=1, maximum=64, value=default_bpl)
        self.bpl_spin_box.editingFinished.connect(self.set_bpl)
        self.bpl_spin_box.setPrefix("Beats per Loop: ")
        bpm_bpl_sync_layout.addWidget(self.bpl_spin_box)
        # sync combobox
        self.sync_combobox = QComboBox()
        self.sync_combobox.addItem("No Sync")
        # get list of all tracks we can sync to
        self.sync_tracks = []
        for i in range(n_loopers):
            if i != index:
                self.sync_combobox.addItem("Sync to Track " + str(i + 1))
                self.sync_tracks.append(i)
        bpm_bpl_sync_layout.addWidget(self.sync_combobox)
        self.sync_combobox.currentIndexChanged.connect(self.set_sync)
        hlayout.addLayout(bpm_bpl_sync_layout)
        self.synced_to = -1
        self.synced_to_idx = -1

        # Volume
        slider_layout = QVBoxLayout()
        self.volume_slider = QSlider(minimum = 0, maximum = 100, value = 60)
        self.volume_slider.valueChanged.connect(self.looper.set_volume)
        slider_layout.addWidget(self.volume_slider)
        slider_layout.addWidget(QLabel(text = "Volume"))
        hlayout.addLayout(slider_layout)

        # Instrument, pitch offset, quantize
        i_po_q_layout = QVBoxLayout()
        # instrument
        self.instrument_combobox = QComboBox()
        self.instrument_combobox.currentIndexChanged.connect(self.looper.set_program)
        for program_name in self.looper.get_program_names():
            self.instrument_combobox.addItem(program_name)
        i_po_q_layout.addWidget(self.instrument_combobox)
        # pitch offset
        self.po_spin_box = QSpinBox(minimum=21, maximum=108, value=60)
        self.po_spin_box.editingFinished.connect(self.set_midi_offset)
        self.po_spin_box.setPrefix("R Key MIDI value: ")
        i_po_q_layout.addWidget(self.po_spin_box)
        # quantize button
        self.quantize_button = QPushButton("Quantize Notes")
        self.quantize_button.setCheckable(True)
        self.quantize_button.clicked.connect(self.toggle_quantize)
        i_po_q_layout.addWidget(self.quantize_button)
        hlayout.addLayout(i_po_q_layout)

        # splits the row in half between buttons and the note visualizer
        wrapper_layout = QHBoxLayout()
        wrapper_layout.addLayout(hlayout, stretch=1)

        # Note Visualizer
        self.note_visualizer = NoteVisualizer(self.looper, QColor.fromHsvF(index / n_loopers, 1, 1))

        wrapper_layout.addWidget(self.note_visualizer, stretch=1)

        self.setLayout(wrapper_layout)

    def mode_change(self, state):
        '''change mode to state'''
        if state:
            mode_id = self.mode_buttons.checkedId()
            mode = LooperState(mode_id)
            self.looper.change_state(mode)
            if mode == LooperState.DISABLED:
                self.note_visualizer.plot_schedule()
                self.note_visualizer.stop_anim()
            elif mode == LooperState.RECORD:
                self.note_visualizer.clear_notes()
                self.note_visualizer.start_anim()
            else: #play
                self.note_visualizer.start_anim()
                self.note_visualizer.plot_schedule()

    def set_bpm(self):
        '''set bpm, update looper and visualizer'''
        self.looper.set_bpm(self.bpm_spin_box.value())
        self.note_visualizer.plot_schedule()
        self.note_visualizer.bpm = self.bpm_spin_box.value()
        self.note_visualizer.repaint()
        self.unsync()

    def set_bpl(self):
        '''set beats per loop, update looper and visualizer'''
        self.looper.set_bpl(self.bpl_spin_box.value())
        self.note_visualizer.plot_schedule()
        self.note_visualizer.bpl = self.bpl_spin_box.value()
        self.note_visualizer.repaint()
        self.unsync()

    def set_midi_offset(self):
        '''set midi value of \'r\' key, update synth'''
        self.looper.set_midi_offset(self.po_spin_box.value())

    def toggle_quantize(self):
        '''set whether to quantize recorded notes'''
        self.looper.set_quantize(self.quantize_button.isChecked())

    def unsync(self):
        if self.synced_to_idx >= 0:
            self.synced_to.synced_to_me.remove(self.looper)
            self.synced_to_idx = -1
            self.sync_combobox.setCurrentIndex(0)

    def set_sync(self, index):
        '''sets whether to sync to another track'''
        # unsync from previous sync track
        if self.synced_to_idx >= 0 and self.synced_to != self.sync_tracks[index -1]:
            self.synced_to.synced_to_me.remove(self.looper)
        
        # sync to new one
        if index != 0:
            self.synced_to_idx = self.sync_tracks[index - 1]
            self.synced_to = self.loopers[self.synced_to_idx]
            # add self to synced to tracks list
            self.synced_to.synced_to_me.append(self.looper)
            # update own bpm, beats per loop, update schedule
            self.looper.set_bpm(self.synced_to.bpm)
            self.bpm_spin_box.setValue(self.synced_to.bpm)
            self.looper.set_bpl(self.synced_to.bpl)
            self.bpl_spin_box.setValue(self.synced_to.bpl)
            self.looper.clock.sync(self.index, self.synced_to_idx)
            self.note_visualizer.plot_schedule()
        # no sync
        else:
            self.synced_to_idx = -1

    def on_update(self):
        '''update note visualizer, updates gui if the looper state has changed'''
        self.note_visualizer.on_update()
        # self.note_visualizer.on_update()
        if self.looper.new_state_loaded:
            self.looper.new_state_loaded = False

            self.bpm_spin_box.setValue(self.looper.bpm)
            self.bpl_spin_box.setValue(self.looper.bpl)

            # self.note_visualizer.plot_schedule(self.looper.schedule)
            self.instrument_combobox.setCurrentIndex(self.looper.synth.program)
            self.po_spin_box.setValue(self.looper.synth.midi_offset)
            self.volume_slider.setValue(self.looper.synth.volume)

            self.note_visualizer.plot_schedule()
            self.note_visualizer.repaint()
            
            





