import React, { useState } from 'react';
import { SessionSummary } from '../types';

interface SidebarProps {
  sessions: SessionSummary[];
  activeSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onCreateNewSession: () => void;
  onRenameSession: (sessionId: string, newTitle: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onClearAllSessions: () => void;
  isOpen: boolean;
  onToggleOpen: () => void;
  runningSessionIds?: Record<string, boolean>;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onCreateNewSession,
  onRenameSession,
  onDeleteSession,
  onClearAllSessions,
  isOpen,
  onToggleOpen,
  runningSessionIds = {},
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.last_preview.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const startEditing = (e: React.MouseEvent, session: SessionSummary) => {
    e.stopPropagation();
    setEditingSessionId(session.session_id);
    setEditTitle(session.title);
  };

  const saveRename = (sessionId: string) => {
    if (editTitle.trim()) {
      onRenameSession(sessionId, editTitle.trim());
    }
    setEditingSessionId(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent, sessionId: string) => {
    if (e.key === 'Enter') {
      saveRename(sessionId);
    } else if (e.key === 'Escape') {
      setEditingSessionId(null);
    }
  };

  const formatRelativeTime = (isoString: string) => {
    if (!isoString) return '';
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  if (!isOpen) {
    return (
      <div className="h-full bg-slate-900 border-r border-slate-800/80 flex flex-col items-center py-4 px-2 space-y-4 select-none z-30">
        <button
          onClick={onToggleOpen}
          title="Expand sidebar"
          className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
        </button>
        <button
          onClick={onCreateNewSession}
          title="New Analysis"
          className="p-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl shadow-lg shadow-blue-600/30 transition-all hover:scale-105"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <aside className="w-72 h-full bg-slate-900/95 backdrop-blur-md border-r border-slate-800/80 flex flex-col min-w-[280px] max-w-[320px] select-none z-30 transition-all duration-200">
      {/* Sidebar Header */}
      <div className="p-3.5 border-b border-slate-800/80 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-[#ffffff] font-bold text-sm justify-center shadow-md shadow-blue-500/20">
            📊
          </div>
          <span className="font-semibold text-slate-200 text-sm tracking-wide">Conversations</span>
        </div>
        <button
          onClick={onToggleOpen}
          title="Collapse sidebar"
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Action Controls */}
      <div className="p-3 space-y-2.5">
        <button
          onClick={onCreateNewSession}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-medium text-sm shadow-md shadow-blue-500/20 hover:shadow-blue-500/30 transition-all duration-150 active:scale-[0.98]"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
          </svg>
          <span>New Analysis</span>
        </button>

        {/* Search input */}
        <div className="relative">
          <svg
            className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search threads..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/60 text-slate-200 placeholder-slate-500 text-xs rounded-lg pl-8 pr-3 py-1.5 border border-slate-800 focus:outline-none focus:border-blue-500/50 transition-colors"
          />
        </div>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1 custom-scrollbar">
        {filteredSessions.length === 0 ? (
          <div className="text-center py-8 px-4 text-slate-500 text-xs">
            {searchQuery ? 'No matching threads' : 'No saved conversations'}
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.session_id === activeSessionId;
            const isEditing = editingSessionId === session.session_id;

            return (
              <div
                key={session.session_id}
                onClick={() => onSelectSession(session.session_id)}
                className={`group relative flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-150 text-xs border ${
                  isActive
                    ? 'bg-blue-600/15 border-blue-500/40 text-blue-100 font-medium shadow-sm'
                    : 'border-transparent text-slate-300 hover:bg-slate-800/60 hover:text-slate-100'
                }`}
              >
                <div className="flex-1 min-w-0 pr-2">
                  {isEditing ? (
                    <input
                      type="text"
                      autoFocus
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onBlur={() => saveRename(session.session_id)}
                      onKeyDown={(e) => handleKeyDown(e, session.session_id)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full bg-slate-950 text-white text-xs px-2 py-1 rounded border border-blue-500 focus:outline-none"
                    />
                  ) : (
                    <>
                      <div className="truncate font-medium flex items-center justify-between gap-1">
                        <span className="truncate">{session.title || 'Untitled Session'}</span>
                      </div>
                      <div className="flex items-center justify-between gap-2 mt-1 text-[10px] text-slate-500 group-hover:text-slate-400">
                        <span>{formatRelativeTime(session.updated_at)}</span>
                        {runningSessionIds[session.session_id] ? (
                          <span className="bg-blue-500/20 text-blue-300 border border-blue-500/40 px-1.5 py-0.5 rounded font-mono flex items-center gap-1 animate-pulse">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
                            Running
                          </span>
                        ) : session.turn_count > 0 ? (
                          <span className="bg-slate-800/80 px-1.5 py-0.5 rounded text-slate-400 font-mono">
                            {session.turn_count} turns
                          </span>
                        ) : null}
                      </div>
                    </>
                  )}
                </div>

                {/* Actions (visible on hover or active) */}
                {!isEditing && (
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {confirmDeleteId === session.session_id ? (
                      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => onDeleteSession(session.session_id)}
                          className="px-1.5 py-0.5 bg-red-600 hover:bg-red-500 text-white rounded text-[10px] font-bold"
                          title="Confirm Delete"
                        >
                          Del
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="px-1.5 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-[10px]"
                          title="Cancel"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <>
                        <button
                          onClick={(e) => startEditing(e, session)}
                          title="Rename title"
                          className="p-1 text-slate-400 hover:text-blue-400 hover:bg-slate-800 rounded transition-colors"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                          </svg>
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setConfirmDeleteId(session.session_id);
                          }}
                          title="Delete thread"
                          className="p-1 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded transition-colors"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer Info */}
      <div className="p-3 border-t border-slate-800/80 text-[11px] text-slate-500 flex items-center justify-between">
        {sessions.length > 0 ? (
          <button
            onClick={onClearAllSessions}
            className="text-slate-400 hover:text-red-400 transition-colors flex items-center gap-1"
            title="Clear all session history"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Clear All
          </button>
        ) : (
          <span>SEC EDGAR Analyst</span>
        )}
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          Ready
        </span>
      </div>
    </aside>
  );
}
