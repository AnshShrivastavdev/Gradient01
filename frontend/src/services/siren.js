// ============================================================================
// Team Gradient - Underground Coal Mine Subsidence Monitoring System
// Web Audio API Continuous Evacuation Siren Synthesizer
// ============================================================================
// 1. Truly Continuous Dual-Tone Industrial Emergency Siren Wail (550Hz - 950Hz)
// 2. Hardware-rate LFO modulation in audio thread - zero JS timer jitter
// 3. Strict Zone-Driven: ONLY sounds when Zone C / CRITICAL is active.
//    Stops IMMEDIATELY on Zone B and Zone A!
// 4. Pre-warms AudioContext on any user gesture to satisfy browser autoplay policy.
// ============================================================================

class SirenSynthesizer {
  constructor() {
    this.audioCtx = null;
    this.carrierOsc = null;
    this.lfoOsc = null;
    this.lfoGain = null;
    this.masterGain = null;
    this.isPlaying = false;
    this.isMuted = false;
    this.stopTimeout = null;
    this.currentZone = 'Zone A';

    // Pre-warm AudioContext on user gesture
    if (typeof window !== 'undefined') {
      const warmup = () => {
        this.init();
        if (this.audioCtx && this.audioCtx.state === 'suspended') {
          this.audioCtx.resume().catch(() => {});
        }
      };
      window.addEventListener('click', warmup, { passive: true });
      window.addEventListener('touchstart', warmup, { passive: true });
      window.addEventListener('keydown', warmup, { passive: true });
    }
  }

  init() {
    if (!this.audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass();
      }
    }
    if (this.audioCtx && this.audioCtx.state === 'suspended') {
      this.audioCtx.resume().catch(() => {});
    }
  }

  setMuted(muted) {
    this.isMuted = Boolean(muted);
    if (this.isMuted) {
      this.stop();
    } else if (this._isZoneCritical(this.currentZone)) {
      this.start();
    }
  }

  _isZoneCritical(zone) {
    if (!zone) return false;
    const z = String(zone).toUpperCase();
    return z.includes('ZONE C') || z.includes('ZONE_C') || z.includes('CRITICAL');
  }

  /**
   * Report zone state.
   * If Zone C / CRITICAL -> wails continuously.
   * If Zone B or Zone A -> stops immediately.
   */
  reportZone(source, zone) {
    this.currentZone = zone || 'Zone A';

    if (this._isZoneCritical(zone)) {
      if (!this.isMuted) {
        this.start();
      }
    } else {
      // Non-critical zone (Zone B, Zone A) -> IMMEDIATELY stop siren
      this.stop();
    }
  }

  setZone(zone) {
    this.reportZone('default', zone);
  }

  start() {
    if (this.isMuted) return;

    this.init();
    if (!this.audioCtx) {
      console.warn('[SIREN] No AudioContext available');
      return;
    }

    if (this.stopTimeout) {
      clearTimeout(this.stopTimeout);
      this.stopTimeout = null;
    }

    const startAudioNodes = () => {
      // If already playing, ramp gain back up if needed
      if (this.isPlaying && this.masterGain && this.carrierOsc) {
        try {
          const now = this.audioCtx.currentTime;
          this.masterGain.gain.cancelScheduledValues(now);
          this.masterGain.gain.setValueAtTime(this.masterGain.gain.value, now);
          this.masterGain.gain.linearRampToValueAtTime(0.35, now + 0.05);
        } catch (e) {}
        return;
      }

      try {
        const now = this.audioCtx.currentTime;

        // 1. Master Output Gain
        this.masterGain = this.audioCtx.createGain();
        this.masterGain.gain.setValueAtTime(0.001, now);
        this.masterGain.gain.linearRampToValueAtTime(0.35, now + 0.10);
        this.masterGain.connect(this.audioCtx.destination);

        // 2. Carrier Oscillator: Aggressive sawtooth evacuation wail centered at 750 Hz
        this.carrierOsc = this.audioCtx.createOscillator();
        this.carrierOsc.type = 'sawtooth';
        this.carrierOsc.frequency.setValueAtTime(750, now);

        // 3. Hardware-Rate LFO: Modulates frequency smoothly between 550Hz and 950Hz
        this.lfoOsc = this.audioCtx.createOscillator();
        this.lfoGain = this.audioCtx.createGain();
        this.lfoOsc.type = 'triangle';
        this.lfoOsc.frequency.setValueAtTime(1.1, now);
        this.lfoGain.gain.setValueAtTime(200, now);

        this.lfoOsc.connect(this.lfoGain);
        this.lfoGain.connect(this.carrierOsc.frequency);
        this.carrierOsc.connect(this.masterGain);

        this.lfoOsc.start(now);
        this.carrierOsc.start(now);
        this.isPlaying = true;

        console.log('[SIREN] 🚨 EVACUATION SIREN ACTIVE (Continuous Zone C Wail)');
      } catch (e) {
        console.warn('[SIREN] Failed to start continuous audio nodes:', e);
      }
    };

    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume().then(startAudioNodes).catch(() => {});
    } else {
      startAudioNodes();
    }
  }

  stop() {
    if (!this.isPlaying) return;
    this.isPlaying = false;

    if (this.stopTimeout) {
      clearTimeout(this.stopTimeout);
      this.stopTimeout = null;
    }

    const carrier = this.carrierOsc;
    const lfo = this.lfoOsc;
    const lfoG = this.lfoGain;
    const master = this.masterGain;
    const ctx = this.audioCtx;

    this.carrierOsc = null;
    this.lfoOsc = null;
    this.lfoGain = null;
    this.masterGain = null;

    if (master && ctx) {
      try {
        const now = ctx.currentTime;
        master.gain.cancelScheduledValues(now);
        master.gain.setValueAtTime(master.gain.value, now);
        master.gain.linearRampToValueAtTime(0.0001, now + 0.10);

        this.stopTimeout = setTimeout(() => {
          try {
            carrier?.stop();
            carrier?.disconnect();
            lfo?.stop();
            lfo?.disconnect();
            lfoG?.disconnect();
            master?.disconnect();
          } catch (e) {}
          this.stopTimeout = null;
        }, 120);
      } catch (e) {
        try {
          carrier?.stop();
          lfo?.stop();
        } catch (err) {}
      }
    }

    console.log('[SIREN] Emergency siren silenced (Zone B / Zone A).');
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
export default sirenSynthesizer;
