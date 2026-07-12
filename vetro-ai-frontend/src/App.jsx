import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "./components/shell/AppShell";
import ChatApp from "./components/ChatApp";
import NetworkGraphView from "./components/network/NetworkGraphView";
import HotspotMapView from "./components/map/HotspotMapView";
import TrendsView from "./components/trends/TrendsView";
import OffenderProfilingView from "./components/offenders/OffenderProfilingView";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<ChatApp />} />
          <Route path="/network" element={<NetworkGraphView />} />
          <Route path="/map" element={<HotspotMapView />} />
          <Route path="/trends" element={<TrendsView />} />
          <Route path="/offenders" element={<OffenderProfilingView />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
