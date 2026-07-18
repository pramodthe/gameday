import { useEffect, useState } from 'react';
import { LandingPage } from './features/landing/LandingPage';
import { MirrorExperience } from './features/mirror/MirrorExperience';

function currentView() {
  return window.location.pathname.startsWith('/mirror') ? 'mirror' : 'landing';
}

export default function App() {
  const [view, setView] = useState(currentView);

  useEffect(() => {
    const handlePopState = () => setView(currentView());
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const openMirror = () => {
    window.history.pushState({}, '', '/mirror');
    setView('mirror');
    window.scrollTo({ top: 0 });
  };

  return view === 'mirror' ? <MirrorExperience /> : <LandingPage onLaunch={openMirror} />;
}
