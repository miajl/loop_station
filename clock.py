import time

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

    def get_tick(self):
        '''gets current tick number'''
        return int((time.time() - self.offset) * self.tps)
        
    def start(self):
        '''start clock'''
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

    def get_current_beat(self, looper_id, bpm):
        '''get the current beat of track looper id'''
        return (self.get_tick() - self.track_offsets[looper_id]) / self.tps / 60 * bpm

    def sync(self, track_to_sync, reference):
        '''syncs track of track_to_sync to reference track'''
        if reference in self.track_offsets.keys():
            self.track_offsets[track_to_sync] = self.track_offsets[reference]

    def on_update(self):
        if self.enabled:
            tick = self.get_tick()
            for looper_id in self.schedules.keys():
                if self.track_is_active[looper_id]:
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
                    # loop through all notes until the note tick is greater than current tick
                    while( self.counters[looper_id] < len(self.schedules[looper_id].schedule_ticks) and self.schedules[looper_id].schedule_ticks[self.counters[looper_id]][0] <= looper_tick):

                        self.synths[looper_id].do_command(self.schedules[looper_id].schedule_ticks[self.counters[looper_id]][1], self.schedules[looper_id].schedule_ticks[self.counters[looper_id]][2])
                        self.counters[looper_id] += 1
                    # update previous tick
                    self.prev_ticks[looper_id] = looper_tick                                                                
    
class AudioSchedule(object):
    '''Class used to define the schedule'''
    def __init__(self, bpm, beats_per_loop, schedule):
        super(AudioSchedule, self).__init__()
        self.bpm = bpm
        self.beats_per_loop = beats_per_loop
        self.schedule_beats = schedule # List of tuple beat, pitch
        self.schedule_ticks = []
        self.ticks_per_loop = -1

    def get_schedule_ticks(self, tps):
        self.schedule_ticks = []
        for note in self.schedule_beats:
            tick = note[0] / self.bpm * 60 * tps
            self.schedule_ticks.append((tick, note[1], note[2]))

        self.ticks_per_loop = self.beats_per_loop / self.bpm * 60 * tps

    # def __repr__(self):
    #     return "%s (bpm=%r, bpl=%r, schedule_beats=%r, schedule_ticks=%r, ticks_per_loop=%r)" % (self.__class__.__name__, self.bpm, self.beats_per_loop, self.schedule_beats, self.schedule_ticks, self.ticks_per_loop)