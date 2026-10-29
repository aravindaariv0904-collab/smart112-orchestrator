import React, { useEffect, useState } from 'react';
import { X, ShieldCheck, Clock, User, Cpu, AlertCircle, FileText } from 'lucide-react';
import { api } from '../services/api';
import { AuditRecord } from '../types';

interface AuditLogDrawerProps {
  incidentId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

export const AuditLogDrawer: React.FC<AuditLogDrawerProps> = ({
  incidentId,
  isOpen,
  onClose
}) => {
  const [logs, setLogs] = useState<AuditRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !incidentId) return;

    const loadAudit = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const records = await api.getAuditTrail(incidentId);
        setLogs(records);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch audit log');
      } finally {
        setIsLoading(false);
      }
    };

    loadAudit();
  }, [isOpen, incidentId]);

  // Escape closes the drawer.
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[2000] flex justify-end bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="audit-drawer-title"
        className="bg-slate-900 border-l border-slate-800 w-full max-w-lg h-full flex flex-col shadow-2xl"
      >
        {/* Drawer Header */}
        <div className="p-4 border-b border-slate-800 bg-slate-950 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-950/60 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 id="audit-drawer-title" className="text-sm font-bold text-white">Audit History</h3>
              <p className="text-[10px] text-slate-400 font-mono">Incident ID: {incidentId}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Audit Trail List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {isLoading ? (
            <div className="p-8 text-center text-xs text-slate-400 space-y-2">
              <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <p>Loading audit history...</p>
            </div>
          ) : error ? (
            <div className="p-3 rounded-lg bg-rose-950/80 border border-rose-500/50 text-rose-200 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
              <span>{error}</span>
            </div>
          ) : logs.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No audit ledger events recorded yet.
            </div>
          ) : (
            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
              {logs.map((log) => {
                const isSystem = log.actor.includes('SYSTEM') || log.actor.includes('AI');
                let parsedDetails: any = null;
                try {
                  parsedDetails = JSON.parse(log.details);
                } catch {
                  parsedDetails = log.details;
                }

                return (
                  <div key={log.id} className="relative space-y-1.5">
                    {/* Timeline Node */}
                    <div className="absolute -left-6 top-1 w-3.5 h-3.5 rounded-full bg-slate-900 border-2 border-emerald-400 shadow"></div>

                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-bold text-white tracking-wide">{log.action}</span>
                      <span className="text-[10px] text-slate-500 flex items-center gap-1 font-mono">
                        <Clock className="w-3 h-3" />
                        {log.timestamp ? new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                      {isSystem ? (
                        <Cpu className="w-3 h-3 text-purple-400" />
                      ) : (
                        <User className="w-3 h-3 text-sky-400" />
                      )}
                      <span className="font-mono text-slate-300">{log.actor}</span>
                    </div>

                    {/* Formatted Details */}
                    <div className="p-2.5 rounded bg-slate-950 border border-slate-800 text-[11px] text-slate-300 font-mono overflow-x-auto leading-relaxed">
                      {typeof parsedDetails === 'object' ? (
                        <pre className="text-[10px] text-slate-400 whitespace-pre-wrap">
                          {JSON.stringify(parsedDetails, null, 2)}
                        </pre>
                      ) : (
                        <span>{log.details}</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-slate-800 bg-slate-950 text-center text-[10px] text-slate-500 flex items-center justify-center gap-1 font-mono">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Append-only audit history (application-enforced; not cryptographically sealed)</span>
        </div>
      </div>
    </div>
  );
};

