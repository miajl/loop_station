import fluidsynth

class SynthWrapper(fluidsynth.Synth):
    '''Wrapper class for fluidsynth.Synth to include program selection
       synth_filepath(str): filepath to sf2 file
       program_filepath(str): filepath to program name file'''
    def __init__(self, synth_filepath, program_filepath):
        super(SynthWrapper, self).__init__()
        self.sfid = self.sfload(synth_filepath)
        self.volume = 60
        self.program = 0
        self.midi_offset = 60
        self.program_selector = ProgramSelector(program_filepath)
        self.start()
        self.set_instrument(0)
    
    def set_volume(self, volume):
        '''sets synth volume'''
        self.volume = volume

    def set_midi_offset(self, offset):
        '''sets synth midi offset, the pitch of the r key'''
        self.midi_offset = offset

    def set_instrument(self, program):
        '''sets synth to instrument at index specified by program'''
        banknum, presetnum = self.program_selector.get_program_from_index(program)
        self.program_select(0, self.sfid, banknum, presetnum)
        self.program = program

    def turn_off_notes(self):
        self.all_notes_off(0)

    def do_command(self, pitch, off_on):
        '''instructs synth to turn on or off a note at pitch'''
        if off_on:
            self.noteon(0, pitch + self.midi_offset, self.volume)
        else:
            self.noteoff(0, pitch + self.midi_offset)
        

class ProgramSelector(object):
    '''Used to go between the program tuples used by the synth and program 
    indexes used by looper gui to do selections'''
    def __init__(self, program_file):
        f = open(program_file)
        self.program_tuples = []
        self.program_strings = []
        strings = f.readlines()
        for s in strings:
            tmp = s.strip().split(' ', 1)
            pg_tuple = tmp[0].split('-')
            self.program_tuples.append((int(pg_tuple[0]), int(pg_tuple[1])))
            self.program_strings.append(tmp[1])

    def get_program_names(self):
        return self.program_strings
    
    def get_program_from_index(self, index):
        return self.program_tuples[index]