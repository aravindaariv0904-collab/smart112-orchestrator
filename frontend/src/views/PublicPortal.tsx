import React, { useState, useEffect } from 'react';
import { 
  Send, 
  Mic, 
  MapPin, 
  CheckCircle, 
  AlertCircle, 
  ShieldAlert, 
  HeartPulse, 
  Flame, 
  Car, 
  Shield, 
  AlertTriangle,
  Clock,
  Navigation,
  RefreshCw
} from 'lucide-react';
import { LeafletMap } from '../map/LeafletMap';

const PRESETS = [
  {
    id: 'accident',
    icon: Car,
    title: 'Traffic Collision',
    telugu: 'రోడ్డు ప్రమాదం',
    text: 'Severe multi-vehicle collision near Guntur RTC bus station with trapped passengers and potential fuel leak',
    color: 'border-rose-500/50 bg-rose-950/30 text-rose-300'
  },
  {
    id: 'cardiac',
    icon: HeartPulse,
    title: 'Cardiac Arrest',
    telugu: 'గుండెపోటు అత్యవసరం',
    text: 'Elderly individual collapsed, unresponsive and struggling to breathe, immediate CPR and ambulance needed',
    color: 'border-red-500/50 bg-red-950/30 text-red-300'
  },
  {
    id: 'fire',
    icon: Flame,
    title: 'Fire / Explosion',
    telugu: 'అగ్నిప్రమాదం',
    text: 'Commercial building ground floor fire with dense black smoke spreading rapidly, residents evacuating',
    color: 'border-orange-500/50 bg-orange-950/30 text-orange-300'
  },
  {
    id: 'assault',
    icon: ShieldAlert,
    title: 'Assault / Crime',
    telugu: 'దాడులు / నేరం',
    text: 'Armed robbery and physical altercation in progress, aggressive individuals carrying weapons',
    color: 'border-amber-500/50 bg-amber-950/30 text-amber-300'
  },
  {
    id: 'womens_sos',
    icon: Shield,
    title: "Women's Safety SOS",
    telugu: 'మహిళా రక్షణ అత్యవసరం',
    text: 'Immediate assistance required, caller is being stalked and feels in extreme danger, police unit needed',
    color: 'border-purple-500/50 bg-purple-950/30 text-purple-300'
  }
];

export const PublicPortal: React.FC = () => {
  const [description, setDescription] = useState<string>('');
  const [address, setAddress] = useState<string>('Guntur RTC Bus Station Complex, AP');
  const [callerPhone, setCallerPhone] = useState<string>('+91 98765 43210');
  const [coordinates, setCoordinates] = useState<[number, number]>([16.3067, 80.4365]);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submittedIncident, setSubmittedIncident] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [language, setLanguage] = useState<'EN' | 'TE'>('EN');

  // Live polling for submitted incident tracking status
  useEffect(() => {
    if (!submittedIncident?.id) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/incidents/${submittedIncident.id}`);
        if (res.ok) {
          const fresh = await res.json();
          setSubmittedIncident(fresh);
        }
      } catch {}
    }, 4000);
    return () => clearInterval(interval);
  }, [submittedIncident?.id]);

  const handleMapClick = (lat: number, lng: number) => {
    setCoordinates([lat, lng]);
  };

  const handleSimulateVoiceCall = () => {
    setIsRecording(true);
    setTimeout(() => {
      setDescription(
        "Head-on collision near Guntur RTC bus station, two passengers trapped and unconscious, fuel leaking"
      );
      setIsRecording(false);
    }, 1200);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) {
      setErrorMsg('Please describe the emergency incident.');
      return;
    }
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const response = await fetch('/api/v1/incidents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description,
          latitude: coordinates[0],
          longitude: coordinates[1],
          address,
          caller_phone: callerPhone
        })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to submit report');
      }

      const data = await response.json();
      setSubmittedIncident(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Submission failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="h-full p-4 lg:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 bg-slate-950 overflow-y-auto">
      {/* Left Column: Intake Form & Live Status Tracking Ticket (6 cols) */}
      <div className="lg:col-span-6 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between overflow-y-auto">
        <div>
          {/* Header */}
          <div className="flex items-center justify-between mb-5 border-b border-slate-800 pb-4">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 rounded-xl bg-red-600/20 border border-red-500/40 flex items-center justify-center">
                <ShieldAlert className="w-7 h-7 text-red-500 animate-pulse" />
              </div>
              <div>
                <h1 className="text-xl font-black text-white tracking-tight">112 EMERGENCY PORTAL</h1>
                <p className="text-xs text-slate-400">Government of Andhra Pradesh • Public Safety Ingestion</p>
              </div>
            </div>

            {/* Language Switcher */}
            <div className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-bold">
              <button
                type="button"
                onClick={() => setLanguage('EN')}
                className={`px-2.5 py-1 rounded transition ${language === 'EN' ? 'bg-red-600 text-white' : 'text-slate-400'}`}
              >
                EN
              </button>
              <button
                type="button"
                onClick={() => setLanguage('TE')}
                className={`px-2.5 py-1 rounded transition ${language === 'TE' ? 'bg-red-600 text-white' : 'text-slate-400'}`}
              >
                తెలుగు
              </button>
            </div>
          </div>

          {submittedIncident ? (
            /* Live Emergency Status Ticket Stepper */
            <div className="p-6 bg-slate-950 border border-slate-800 rounded-2xl space-y-5 animate-in fade-in duration-300">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-emerald-500 animate-ping" />
                  <span className="font-bold text-sm text-white">Live Emergency Dispatch Ticket</span>
                </div>
                <span className="font-mono text-xs font-bold text-rose-400 bg-rose-950/60 px-2 py-0.5 rounded border border-rose-800">
                  {submittedIncident.incident_number}
                </span>
              </div>

              {/* Status Stepper Progression */}
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-6 h-6 rounded-full bg-emerald-500 text-white flex items-center justify-center text-xs font-bold">✓</div>
                  <div>
                    <div className="text-xs font-bold text-white">1. Emergency Report Transmitted &amp; Triaged</div>
                    <div className="text-[11px] text-slate-400">Classified as <span className="text-rose-400 font-bold">{submittedIncident.severity}</span> ({submittedIncident.category})</div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    ['RECOMMENDED', 'DISPATCHED', 'ON_SCENE', 'RESOLVED'].includes(submittedIncident.status)
                      ? 'bg-emerald-500 text-white'
                      : 'bg-slate-800 text-slate-400 animate-pulse'
                  }`}>
                    {['RECOMMENDED', 'DISPATCHED', 'ON_SCENE', 'RESOLVED'].includes(submittedIncident.status) ? '✓' : '2'}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white">2. Spatial PostGIS Matching</div>
                    <div className="text-[11px] text-slate-400">Nearest available units identified by GPS proximity</div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    ['DISPATCHED', 'ON_SCENE', 'RESOLVED'].includes(submittedIncident.status)
                      ? 'bg-rose-600 text-white animate-pulse'
                      : 'bg-slate-800 text-slate-400'
                  }`}>
                    {['ON_SCENE', 'RESOLVED'].includes(submittedIncident.status) ? '✓' : '3'}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white">3. Dispatch Authorized by Lead Dispatcher</div>
                    <div className="text-[11px] text-slate-400">
                      {['DISPATCHED', 'ON_SCENE', 'RESOLVED'].includes(submittedIncident.status)
                        ? 'Emergency unit en route with active siren and priority lights'
                        : 'Awaiting human authorization gate...'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    ['ON_SCENE', 'RESOLVED'].includes(submittedIncident.status)
                      ? 'bg-purple-600 text-white'
                      : 'bg-slate-800 text-slate-400'
                  }`}>
                    {submittedIncident.status === 'RESOLVED' ? '✓' : '4'}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white">4. Responders On Scene / Incident Mitigated</div>
                    <div className="text-[11px] text-slate-400">
                      Current Status: <span className="font-mono font-bold text-sky-400 uppercase">{submittedIncident.status}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-300 font-mono">
                Caller Transcript: "{submittedIncident.description}"
              </div>

              <div className="pt-2 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setSubmittedIncident(null);
                    setDescription('');
                  }}
                  className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition"
                >
                  File Another Incident
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Quick 1-Click SOS Presets */}
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                  {language === 'EN' ? 'Quick Emergency Presets (1-Click Fill)' : 'తక్షణ అత్యవసర ఎంపికలు'}
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {PRESETS.map((preset) => {
                    const Icon = preset.icon;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => setDescription(preset.text)}
                        className={`p-2.5 rounded-xl border text-left flex flex-col justify-between transition hover:scale-[1.02] cursor-pointer ${preset.color}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-xs">{language === 'EN' ? preset.title : preset.telugu}</span>
                          <Icon className="w-4 h-4" />
                        </div>
                        <span className="text-[10px] opacity-80 line-clamp-1">{preset.text}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Voice Simulated Ingestion */}
              <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-white block">
                    {language === 'EN' ? 'Simulate 112 Voice Call Intake' : 'వాయిస్ కాల్ అనుకరణ'}
                  </span>
                  <span className="text-[11px] text-slate-400">Audio Speech-to-Text Transcriber</span>
                </div>
                <button
                  type="button"
                  onClick={handleSimulateVoiceCall}
                  disabled={isRecording}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-xs font-bold border transition ${
                    isRecording
                      ? 'bg-red-500 text-white animate-pulse border-red-400'
                      : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700 cursor-pointer'
                  }`}
                >
                  <Mic className="w-4 h-4" />
                  <span>{isRecording ? 'Transcribing...' : 'Record Speech'}</span>
                </button>
              </div>

              {/* Text Description */}
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  {language === 'EN' ? 'Emergency Incident Narrative *' : 'అత్యవసర వివరాలు *'}
                </label>
                <textarea
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={language === 'EN' ? 'Specify injuries, collision, fire, weapons or trapped victims...' : 'గాయాలు, ప్రమాద వివరాలు ఇక్కడ రాయండి...'}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition font-mono"
                  required
                />
              </div>

              {/* Location Address */}
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  {language === 'EN' ? 'Street Address / Landmark' : 'చిరునామా / ల్యాండ్‌మార్క్'}
                </label>
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-red-500 transition"
                />
              </div>

              {/* Pinned Coordinates Display */}
              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2 text-slate-400">
                  <MapPin className="w-4 h-4 text-amber-400" />
                  <span>GPS Coordinates (Click Map to Update):</span>
                </div>
                <span className="font-mono font-bold text-amber-300">
                  {coordinates[0].toFixed(4)}, {coordinates[1].toFixed(4)}
                </span>
              </div>

              {errorMsg && (
                <div className="p-3 rounded-xl bg-red-950/50 border border-red-800/80 text-xs text-red-200">
                  {errorMsg}
                </div>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-black text-sm shadow-xl shadow-red-950 flex items-center justify-center space-x-2 transition cursor-pointer disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
                <span>{isSubmitting ? 'Transmitting to 112 Dispatch...' : 'TRANSMIT 112 EMERGENCY CALL'}</span>
              </button>
            </form>
          )}
        </div>

        <div className="text-[11px] text-slate-500 border-t border-slate-800 pt-3 mt-4">
          SMART 112: Backend Single Source of Truth. Emergency telemetry transmitted via secure authenticated channels.
        </div>
      </div>

      {/* Right Column: Interactive Map Picker (6 cols) */}
      <div className="lg:col-span-6 h-full flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <MapPin className="w-4 h-4 text-red-500" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Interactive Incident Location Pin (Click Map to Place Pin)
            </span>
          </div>
          <span className="text-[11px] text-slate-500">Free OpenStreetMap Engine</span>
        </div>
        <div className="flex-1 min-h-[400px]">
          <LeafletMap
            center={coordinates}
            selectedCoordinates={coordinates}
            onMapClick={handleMapClick}
          />
        </div>
      </div>
    </div>
  );
};
