import React, { useState } from 'react';
import { Send, Mic, MapPin, CheckCircle, AlertCircle, ShieldAlert } from 'lucide-react';
import { LeafletMap } from '../map/LeafletMap';

export const PublicPortal: React.FC = () => {
  const [description, setDescription] = useState<string>('');
  const [address, setAddress] = useState<string>('Guntur RTC Bus Station Complex, AP');
  const [callerPhone, setCallerPhone] = useState<string>('+91 98765 43210');
  const [coordinates, setCoordinates] = useState<[number, number]>([16.3067, 80.4365]);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submittedIncident, setSubmittedIncident] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
    <div className="h-[calc(100vh-4rem)] p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 bg-slate-950">
      {/* Left Column: Intake Form */}
      <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between overflow-y-auto">
        <div>
          <div className="flex items-center space-x-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-red-600/20 border border-red-500/40 flex items-center justify-center">
              <ShieldAlert className="w-6 h-6 text-red-500" />
            </div>
            <div>
              <h1 className="text-xl font-extrabold text-white">Citizen Emergency Portal</h1>
              <p className="text-xs text-slate-400">Direct connection to SMART 112 Triage Orchestrator</p>
            </div>
          </div>

          {submittedIncident ? (
            <div className="p-6 bg-emerald-950/40 border border-emerald-800/60 rounded-2xl text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center mx-auto text-emerald-400">
                <CheckCircle className="w-7 h-7" />
              </div>
              <h2 className="text-lg font-bold text-white">Emergency Dispatched to Queue</h2>
              <div className="text-xs font-mono text-emerald-300 bg-slate-950/80 p-3 rounded-xl border border-emerald-900/50 text-left space-y-1">
                <div>Incident ID: <span className="font-bold">{submittedIncident.incident_number}</span></div>
                <div>Assessed Category: <span className="font-bold">{submittedIncident.category}</span></div>
                <div>Severity Triage: <span className="font-bold text-red-400">{submittedIncident.severity}</span></div>
                <div>Status: <span className="font-bold text-sky-400">{submittedIncident.status}</span></div>
              </div>
              <p className="text-xs text-slate-400">
                AI evaluation completed. Dispatchers have verified your emergency coordinates. Keep your line clear.
              </p>
              <button
                onClick={() => {
                  setSubmittedIncident(null);
                  setDescription('');
                }}
                className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition-all"
              >
                Submit Another Report
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Voice Simulated Ingestion */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-white block">Emergency Call / Audio Intake</span>
                  <span className="text-[11px] text-slate-400">Simulate caller speech transcription</span>
                </div>
                <button
                  type="button"
                  onClick={handleSimulateVoiceCall}
                  disabled={isRecording}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-xs font-bold border transition-all ${
                    isRecording
                      ? 'bg-red-500 text-white animate-pulse border-red-400'
                      : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700'
                  }`}
                >
                  <Mic className="w-4 h-4" />
                  <span>{isRecording ? 'Transcribing...' : 'Record Voice'}</span>
                </button>
              </div>

              {/* Text Description */}
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Emergency Situation Description *
                </label>
                <textarea
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe the nature of the emergency, injuries, trapped persons, or fire..."
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition-all font-mono"
                  required
                />
              </div>

              {/* Location Address */}
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Nearest Landmark / Street Address
                </label>
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-red-500 transition-all"
                />
              </div>

              {/* Caller Phone */}
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Callback Telephone Number
                </label>
                <input
                  type="tel"
                  value={callerPhone}
                  onChange={(e) => setCallerPhone(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-red-500 transition-all font-mono"
                />
              </div>

              {/* Pinned Coordinates Display */}
              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2 text-slate-400">
                  <MapPin className="w-4 h-4 text-amber-400" />
                  <span>Pinned Coordinates (Click Map to Update):</span>
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
                className="w-full py-3 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-extrabold text-sm shadow-xl shadow-red-950/60 flex items-center justify-center space-x-2 transition-all cursor-pointer disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
                <span>{isSubmitting ? 'Routing to Dispatcher...' : 'Transmit Emergency Report (112)'}</span>
              </button>
            </form>
          )}
        </div>

        <div className="text-[11px] text-slate-500 border-t border-slate-800/80 pt-4 mt-6">
          Backend is single source of truth. Calls and coordinates are securely relayed to local 112 command centers.
        </div>
      </div>

      {/* Right Column: Interactive Map Picker */}
      <div className="lg:col-span-7 h-full flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <MapPin className="w-4 h-4 text-red-500" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Interactive Incident Location Pin (Click Anywhere on Map to Place Pin)
            </span>
          </div>
          <span className="text-[11px] text-slate-500">Free OpenStreetMap Engine</span>
        </div>
        <div className="flex-1">
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
