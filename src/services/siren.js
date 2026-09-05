// Native Web Audio API Siren Synthesizer for Zone C Critical Evacuation Alerts
// Synthesizes a looping two-tone square-wave alarm (800Hz / 500Hz)

class SirenSynthesizer {
  constructor() {
    this.audioCtx = null;
    this.oscillator = null;
    this.gainNode = null;
    this.isPlaying = false;
    this.intervalId = null;
    this.currentPitch = 800;
  }

  init() {
    if (!this.audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass();
      }
    }
  }

  start() {
    if (this.isPlaying) return;
    this.init();

    if (!this.audioCtx) return;

    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }

    try {
      this.oscillator = this.audioCtx.createOscillator();
      this.gainNode = this.audioCtx.createGain();

      // Sharp, industrial two-tone square wave
      this.oscillator.type = 'square';
      this.oscillator.frequency.setValueAtTime(800, this.audioCtx.currentTime);

      // Volume scaling
      this.gainNode.gain.setValueAtTime(0.2, this.audioCtx.currentTime);

      this.oscillator.connect(this.gainNode);
      this.gainNode.connect(this.audioCtx.destination);

      this.oscillator.start();
      this.isPlaying = true;

      // Alternating 800Hz / 500Hz siren frequency shift every 400ms
      this.intervalId = setInterval(() => {
        if (!this.oscillator || !this.audioCtx) return;
        this.currentPitch = this.currentPitch === 800 ? 500 : 800;
        this.oscillator.frequency.setValueAtTime(this.currentPitch, this.audioCtx.currentTime);
      }, 400);
    } catch (e) {
      console.warn('AudioContext execution prevented:', e);
    }
  }

  stop() {
    if (!this.isPlaying) return;

    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }

    if (this.oscillator) {
      try {
        this.oscillator.stop();
        this.oscillator.disconnect();
      } catch (e) {
        // ignore
      }
      this.oscillator = null;
    }

    this.isPlaying = false;
  }

  speak(text) {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel(); // Stop any pending speech
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.05;
        utterance.pitch = 1.1;
        utterance.volume = 1.0;
        window.speechSynthesis.speak(utterance);
      } catch (e) {
        console.warn('SpeechSynthesis error:', e);
      }
    }
  }

  toggle() {
    if (this.isPlaying) {
      this.stop();
    } else {
      this.start();
    }
  }
}

export const sirenSynthesizer = new SirenSynthesizer();

