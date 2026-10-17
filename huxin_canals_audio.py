"""Two quiet encounter cues; automated reviews never open an audio device."""
from pathlib import Path
import pyray as pr
from g_audio import audio_output_muted

class EncounterAudio:
    def __init__(self,automated=False):
        self.muted=audio_output_muted(automated);self.sounds={};self.played=[];self.opened=False
        if not self.muted:
            pr.init_audio_device();self.opened=pr.is_audio_device_ready()
            if self.opened:
                for name,gain in (('bell',.34),('timber',.10)):
                    sound=pr.load_sound(str(Path(__file__).parent/'art'/'temple'/'huxin_canals'/(name+'.wav')))
                    pr.set_sound_volume(sound,gain);self.sounds[name]=sound
    def drain(self,sequence):
        for event in sequence.events:
            self.played.append(event)
            if event in self.sounds:pr.play_sound(self.sounds[event])
        sequence.events.clear()
    def close(self):
        for sound in self.sounds.values():pr.unload_sound(sound)
        if self.opened:pr.close_audio_device()

def prepare():
    """Reproducible original sound design: one distant bronze strike, one creak."""
    import numpy as np
    import wave
    root=Path(__file__).parent/'art'/'temple'/'huxin_canals';rate=44100
    t=np.arange(rate*18)/rate;bell=np.zeros_like(t)
    for frequency,amplitude,decay in ((131,.55,5.8),(202,.26,4.5),(272,.25,4.2),(354,.16,3.6),(466,.12,2.8),(613,.07,2.3),(807,.04,1.4)):
        bell+=amplitude*np.sin(2*np.pi*frequency*t+.003*np.sin(t*4))*np.exp(-t/decay)*(1-np.exp(-t*28))
    # A delayed, softer arrival gives the single strike a distant tail.
    echo=np.zeros_like(bell);delay=int(.24*rate);echo[delay:]=bell[:-delay]*.17;bell+=echo
    bell*=np.minimum(1,(18-t)/1.8);bell*=.61/max(abs(bell))
    t=np.arange(int(rate*3.2))/rate;rng=np.random.default_rng(892)
    phase=2*np.pi*(78*t+11*np.sin(t*1.3));creak=(np.sin(phase)+.30*np.sin(phase*2.03)+.13*np.sin(phase*3.07))
    noise=np.convolve(rng.normal(0,.2,len(t)),np.ones(35)/35,mode='same')
    creak=(creak*.08+noise*.17)*np.sin(np.pi*t/3.2)**2*(.4+.6*np.sin(t*8)**2)
    for name,data in (('bell',bell),('timber',creak)):
        with wave.open(str(root/(name+'.wav')),'wb') as out:
            out.setparams((1,2,rate,0,'NONE','not compressed'));out.writeframes((data*32767).astype('<i2').tobytes())
if __name__=='__main__':prepare()
