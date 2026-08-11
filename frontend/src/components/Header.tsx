'use client';

interface HeaderProps {
  isConnected: boolean;
  lastUpdated: string | null;
}

export default function Header({ isConnected, lastUpdated }: HeaderProps) {
  return (
    <header className="bg-dark-900 border-b border-dark-700 px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-drk-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">+</span>
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">DRK Troisdorf</h1>
            <p className="text-xs text-dark-400">Frühwarnsystem</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {lastUpdated && (
            <span className="text-xs text-dark-400">
              Aktualisiert: {new Date(lastUpdated).toLocaleTimeString('de-DE')}
            </span>
          )}
          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-xs text-dark-400">
              {isConnected ? 'Live' : 'Offline'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
