import time
from synth_wrapper import SynthWrapper

class Clock(object):
    '''Clock object keeps track of schedules from all the tracks and plays them when needed'''
    def __init__(self, n_tracks, synths, tps):
        super(Clock, self).__init__()
        self.offset = 0
        self.n_tracks = n_tracks
        self.synths = synths
        self.tps = tps
        self.tick_length = 1/tps
        self.schedules = {}
        self.counters = {} # index of next note to be played
        self.prev_ticks = {} # previous tick in each loop used to track when we've crossed a loop
        self.enabled = False
        self.track_is_active = {}
        self.track_offsets = {}
        self.use_metronome = False
        self.metro_track_idx = -1
        self.metro_synth = SynthWrapper("./data/FluidR3_GM.sf2",
                                             "./data/fluid_synth_programs.txt")
        self.metro_synth.set_instrument(115) # wood block
        self.metro_synth.set_volume(100)
        self.metro_bpm = 60
        self.prev_metro_beat = 0
        self.metro_noteon = False
        

    def get_tick(self):
        '''gets current tick number'''
        return int((time.time() - self.offset) * self.tps)
        
    def start(self):
        '''start clock'''
        if not self.enabled:
            self.offset = time.time()
            self.enabled = True
    
    def disable_track(self, looper_id):
        '''disable track with number looper_id'''
        self.track_is_active[looper_id] = False

    def enable_track(self, looper_id, keep_offset):
        '''enable track with number looper id, if keep_offset is False, update the offset'''
        if not self.enabled:
            self.start()
        self.track_is_active[looper_id] = True
        self.prev_ticks[looper_id] = 0
        self.counters[looper_id] = 0

        if (not keep_offset):
            self.reset_track_offset(looper_id)

    def post_schedule(self, looper_id, schedule):
        '''called by loopers to post their new schedules'''
        # sort schedule by command beats
        schedule.sort()
        self.schedules[looper_id] = schedule
        self.schedules[looper_id].get_schedule_ticks(self.tps)

    def reset_track_offset(self, looper_id):
        '''resets the track offset of track with number looper_id'''
        self.track_offsets[looper_id] = self.get_tick()

    def sync_track_starts(self):
        '''resets track offsets of all tracks'''
        new_start_tick = self.get_tick()
        for looper_id in self.track_offsets.keys():
            self.track_offsets[looper_id] = new_start_tick

    def get_current_beat(self, looper_id, bpm, bpl):
        '''get the current beat of track looper id'''
        return ((self.get_tick() - self.track_offsets[looper_id]) / self.tps / 60 * bpm) % bpl

    def sync(self, track_to_sync, reference):
        '''syncs track of track_to_sync to reference track'''
        if reference in self.track_offsets.keys():
            self.track_offsets[track_to_sync] = self.track_offsets[reference]

    def set_metronome(self, index, bpm):
        '''Sets metronome to follow track at index, with bpm'''
        self.metro_track_idx = index
        self.metro_bpm = bpm
        self.prev_metro_beat = 0

    def release_metronome(self, index):
        '''release metronome at track index'''
        if index == self.metro_track_idx:
            self.metro_track_idx = -1

    def on_update(self):
        if self.enabled:
            tick = self.get_tick()
            # look at all current schedules
            for looper_id in self.schedules.keys():
                if looper_id in self.track_is_active.keys() and self.track_is_active[looper_id]:
                    # tick of loop
                    looper_tick = (tick - self.track_offsets[looper_id]) % \
                        self.schedules[looper_id].ticks_per_loop
                    # if we've looped around, do any remaining noteoffs in the schedule
                    if looper_tick < self.prev_ticks[looper_id]:
                        for i in range(self.counters[looper_id], len(self.schedules[looper_id].schedule_ticks)):
                            # only do noteoffs
                            if not self.schedules[looper_id].schedule_ticks[i][2]:
                                self.synths[looper_id].do_command(self.schedules[looper_id].schedule_ticks[i][1], self.schedules[looper_id].schedule_ticks[i][2])
                        self.counters[looper_id] = 0
                    # loop through all notes until the note tick is greater than current tick, only play noteons if we do not get the noteoff
                    note_ons = []
                    while( self.counters[looper_id] < len(self.schedules[looper_id].schedule_ticks) and self.schedules[looper_id].schedule_ticks[self.counters[looper_id]][0] <= looper_tick):
                        current_note = self.schedules[looper_id].schedule_ticks[self.counters[looper_id]]
                        # keep track of all noteons to be played
                        if current_note[2]:
                            note_ons.append(self.schedules[looper_id].schedule_ticks[self.counters[looper_id]][1])
                        else:
                            self.synths[looper_id].do_command(current_note[1], current_note[2])
                            if current_note[1] in note_ons:
                                note_ons.remove(current_note[1])
                        self.counters[looper_id] += 1
                    
                    # do all note ons
                    for note in note_ons:
                        self.synths[looper_id].do_command(note, 1)
                    # update previous tick
                    self.prev_ticks[looper_id] = looper_tick 
            # play metronome
            if self.use_metronome and self.metro_track_idx >= 0:
                metro_tick = (tick - self.track_offsets[self.metro_track_idx])
                metro_beat = (metro_tick / self.tps / 60 * self.metro_bpm)
                if metro_beat - self.prev_metro_beat >= 1:
                    self.metro_synth.do_command(60, 1)
                    self.prev_metro_beat = int(metro_beat)
                    self.metro_noteon = True
                # turn off metronome note 0.2 beats later
                if metro_beat - self.prev_metro_beat >= 0.2 and self.metro_noteon:
                    self.metro_synth.do_command(60, 0)
                    self.metro_noteon = False

    
class AudioSchedule(object):
    '''Class used to define the schedule'''
    def __init__(self, bpm, beats_per_loop, schedule):
        super(AudioSchedule, self).__init__()
        self.bpm = bpm
        self.beats_per_loop = beats_per_loop
        self.schedule_beats = schedule # List of tuple beat, pitch, off
        self.schedule_ticks = []
        self.ticks_per_loop = -1

    def get_schedule_ticks(self, tps):
        self.schedule_ticks = []
        for note in self.schedule_beats:
            tick = note[0] / self.bpm * 60 * tps
            self.schedule_ticks.append((tick, note[1], note[2]))

        self.ticks_per_loop = self.beats_per_loop / self.bpm * 60 * tps

    def sort(self):
        tmp = sorted(self.schedule_beats, key=lambda x: x[0])
        self.schedule_beats = tmp
        