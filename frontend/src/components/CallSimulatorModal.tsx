import React, { useEffect, useState } from 'react';
import { X, Mic, Upload, MapPin, Sparkles, AlertCircle, CheckCircle2 } from 'lucide-react';
import { api } from '../services/api';
import { AudioTranscribeResult } from '../types';

interface CallSimulatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onIncidentCreated: () => void;
}

const PRESETS = [
  {
    title: "Critical Crash with Fuel Leak (Guntur RTC)",
    description: "Head-on collision near Guntur RTC bus station, two passengers trapped and unconscious, fuel leaking rapidly across road",
    lat: 16.3067,
    lon: 80.4365,
    address: "Near Guntur RTC Bus Complex, AP"
  },
  {
    title: "Commercial Warehouse Fire (Vijayawada)",
    description: "Major explosion and active flames in chemical warehouse near Vijayawada bypass, thick toxic smoke spreading",
    lat: 16.5180,
    lon: 80.6200,
    address: "Auto Nagar Bypass, Vijayawada"
  },
  {
    title: "Cardiac Emergency (Arundelpet)",
    description: "65-year-old patient collapsed on sidewalk, not breathing, bystanders attempting CPR",
    lat: 16.3150,
    lon: 80.4280,
    address: "Main Road, Arundelpet, Guntur"
  },
  {
    title: "Minor Traffic Bump (Kothapet)",
    description: "Rear-end collision between two auto-rickshaws, no visible injuries, traffic blockage",
    lat: 16.3050,
    lon: 80.4350,
    address: "Kothapet Traffic Circle, Guntur"
  }
];

export const CallSimulatorModal: React.FC<CallSimulatorModalProps> = ({
  isOpen,
  onClose,
  onIncidentCreated
}) => {
  const [mode, setMode] = useState<'TEXT' | 'AUDIO'>('TEXT');
  const [description, setDescription] = useState(PRESETS[0].description);
  const [latitude, setLatitude] = useState(PRESETS[0].lat);
  const [longitude, setLongitude] = useState(PRESETS[0].lon);
  const [address, setAddress] = useState(PRESETS[0].address);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcribeResult, setTranscribeResult] = useState<AudioTranscribeResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Escape closes the modal unless a request is in flight.
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isSubmitting && !isTranscribing) {
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, isSubmitting, isTranscribing, onClose]);

  if (!isOpen) return null;

  const handleApplyPreset = (p: typeof PRESETS[0]) => {
    setDescription(p.description);
    setLatitude(p.lat);
    setLongitude(p.lon);
    setAddress(p.address);
  };

  const handleAudioUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setErrorMessage(null);
    setIsTranscribing(true);
    setTranscribeResult(null);

    try {
      const result = await api.transcribeAudio(file);
      setTranscribeResult(result);
      setDescription(result.transcript);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to transcribe audio file');
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await api.createIncident({
        description,
        latitude: Number(latitude),
        longitude: Number(longitude),
        address
      });
      onIncidentCreated();
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to register incident');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="call-simulator-title"
        className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]"
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-rose-600/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <Mic className="w-4 h-4" />
            </div>
            <div>
              <h3 id="call-simulator-title" className="text-sm font-bold text-white">Emergency Call Ingestion Simulator</h3>
              <p className="text-[11px] text-slate-400">Test real-time NLU triage &amp; Whisper speech-to-text</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4">
          {/* Mode Switcher */}
          <div className="flex rounded-lg bg-slate-950 p-1 border border-slate-800">
            <button
              type="button"
              onClick={() => setMode('TEXT')}
              className={`flex-1 py-1.5 rounded-md text-xs font-semibold transition ${
                mode === 'TEXT'
                  ? 'bg-rose-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Emergency Presets &amp; Text
            </button>
            <button
              type="button"
              onClick={() => setMode('AUDIO')}
              className={`flex-1 py-1.5 rounded-md text-xs font-semibold transition flex items-center justify-center gap-1.5 ${
                mode === 'AUDIO'
                  ? 'bg-rose-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Upload className="w-3.5 h-3.5" />
              Upload Audio (.wav, .mp3)
            </button>
          </div>

          {errorMessage && (
            <div className="p-3 rounded-lg bg-rose-950/80 border border-rose-500/50 text-rose-200 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {mode === 'AUDIO' ? (
            <div className="space-y-4">
              <div className="border-2 border-dashed border-slate-700 hover:border-rose-500/60 rounded-xl p-6 text-center space-y-2 bg-slate-950/40 transition">
                <Upload className="w-8 h-8 text-rose-400 mx-auto" />
                <p className="text-xs font-semibold text-slate-200">
                  Select 112 Voice Recording
                </p>
                <p className="text-[11px] text-slate-500">
                  Supported formats: .wav, .mp3, .ogg (Max 15 MB)
                </p>
                <label className="inline-block mt-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold cursor-pointer border border-slate-700 transition">
                  Browse Audio File
                  <input
                    type="file"
                    accept="audio/wav,audio/mpeg,audio/mp3,audio/ogg"
                    onChange={handleAudioUpload}
                    className="hidden"
                  />
                </label>
              </div>

              {isTranscribing && (
                <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 text-center space-y-2 text-xs text-slate-400">
                  <div className="w-5 h-5 border-2 border-rose-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                  <p>Processing speech audio with faster-whisper...</p>
                </div>
              )}

              {transcribeResult && (
                <div className="p-3 rounded-lg bg-slate-950 border border-emerald-500/30 space-y-2 text-xs">
                  <div className="flex items-center justify-between text-emerald-400 font-bold">
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="w-4 h-4" />
                      Transcription Complete
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">
                      Confidence: {(transcribeResult.stt_confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-slate-300 italic bg-slate-900 p-2.5 rounded border border-slate-800">
                    "{transcribeResult.transcript}"
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <label className="text-[11px] font-semibold text-slate-400 uppercase">Emergency Scenario Presets</label>
              <div className="grid grid-cols-2 gap-2">
                {PRESETS.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleApplyPreset(p)}
                    className="p-2.5 text-left rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 transition space-y-1"
                  >
                    <div className="text-xs font-bold text-slate-200 line-clamp-1">{p.title}</div>
                    <div className="text-[10px] text-slate-500 line-clamp-1">{p.address}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Incident Fields Form */}
          <form onSubmit={handleSubmit} className="space-y-3 pt-2 border-t border-slate-800">
            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase">Caller Narrative / Transcript</label>
              <textarea
                rows={3}
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full mt-1 bg-slate-950 text-xs text-slate-200 p-3 rounded-lg border border-slate-800 focus:outline-none focus:border-rose-500"
                placeholder="Describe caller details, injuries, hazards..."
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-slate-400 uppercase">Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  required
                  value={latitude}
                  onChange={(e) => setLatitude(parseFloat(e.target.value))}
                  className="w-full mt-1 bg-slate-950 text-xs text-slate-200 px-3 py-2 rounded-lg border border-slate-800 focus:outline-none focus:border-rose-500 font-mono"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-slate-400 uppercase">Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  required
                  value={longitude}
                  onChange={(e) => setLongitude(parseFloat(e.target.value))}
                  className="w-full mt-1 bg-slate-950 text-xs text-slate-200 px-3 py-2 rounded-lg border border-slate-800 focus:outline-none focus:border-rose-500 font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase">Address / Landmarks</label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full mt-1 bg-slate-950 text-xs text-slate-200 px-3 py-2 rounded-lg border border-slate-800 focus:outline-none focus:border-rose-500"
                placeholder="Street name, landmark, cross junction"
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting || !description.trim()}
              className="w-full mt-4 py-2.5 rounded-lg bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white font-bold text-xs shadow-lg shadow-rose-950/40 transition disabled:opacity-50"
            >
              {isSubmitting ? 'Ingesting Emergency...' : 'Submit & Execute Triage Engine'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

