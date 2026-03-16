// ── Google Maps ────────────────────────────────────────────────────
let map;
let mapOverlays = [];

function initMap() {
  map = new google.maps.Map(document.getElementById("map"), {
    center: { lat: 12.9716, lng: 77.5946 },
    zoom: 12,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false,
  });
  loadMetroStations();
}

// ── State ─────────────────────────────────────────────────────────
function clearMapOverlays() {
  mapOverlays.forEach(o => o.setMap(null));
  mapOverlays = [];
}

// ── Custom SVG markers ────────────────────────────────────────────
function makeMarkerIcon(color, symbol) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30">
    <circle cx="15" cy="15" r="13" fill="${color}" stroke="white" stroke-width="3"/>
    <text x="15" y="20" text-anchor="middle" font-size="13" font-weight="bold"
          fill="white" font-family="Arial,sans-serif">${symbol}</text>
  </svg>`;
  return {
    url: "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(svg),
    scaledSize: new google.maps.Size(30, 30),
    anchor: new google.maps.Point(15, 15),
  };
}

// ── DOM refs ──────────────────────────────────────────────────────
const form        = document.getElementById("routeForm");
const startInput  = document.getElementById("startInput");
const endInput    = document.getElementById("endInput");
const findBtn     = document.getElementById("findBtn");
const btnText     = document.getElementById("btnText");
const btnSpinner  = document.getElementById("btnSpinner");
const results     = document.getElementById("results");
const errorBanner = document.getElementById("errorBanner");
const stepsList   = document.getElementById("stepsList");
const sumFrom     = document.getElementById("sumFrom");
const sumTo       = document.getElementById("sumTo");
const sumTime     = document.getElementById("sumTime");
const modeIcons   = document.getElementById("modeIcons");
const swapBtn     = document.getElementById("swapBtn");

// ── Quick-pick chips ──────────────────────────────────────────────
document.querySelectorAll(".chip").forEach(chip => {
  chip.addEventListener("click", () => {
    startInput.value = chip.dataset.from;
    endInput.value   = chip.dataset.to;
    form.dispatchEvent(new Event("submit"));
  });
});

// ── Swap button ───────────────────────────────────────────────────
swapBtn.addEventListener("click", () => {
  [startInput.value, endInput.value] = [endInput.value, startInput.value];
});

// ── Show / hide error ─────────────────────────────────────────────
function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.remove("hidden");
  results.classList.add("hidden");
}
function clearError() {
  errorBanner.classList.add("hidden");
}

// ── Loading state ─────────────────────────────────────────────────
function setLoading(on) {
  findBtn.disabled    = on;
  btnText.textContent = on ? "Searching…" : "Find Best Route";
  btnSpinner.classList.toggle("hidden", !on);
}

// ── Mode label helpers ────────────────────────────────────────────
const MODE_META = {
  metro: { icon: "🚇", label: "Metro" },
  bus:   { icon: "🚌", label: "Bus"   },
  walk:  { icon: "🚶", label: "Walk"  },
};

function modeColor(step) {
  if (step.mode === "metro") {
    return step.line === "Green" ? "#27AE60" : "#9B59B6";
  }
  if (step.mode === "bus") return "#2980B9";
  return "#7F8C8D";
}

// ── Render results ────────────────────────────────────────────────
function renderRoute(data) {
  // Summary
  sumFrom.textContent = data.start_name || "Start";
  sumTo.textContent   = data.end_name   || "End";
  sumTime.textContent = data.total_time_fmt;

  // Mode badges
  modeIcons.innerHTML = "";
  data.modes_used.forEach(mode => {
    const m     = MODE_META[mode] || { icon: "?", label: mode };
    const badge = document.createElement("span");
    badge.className = "mode-badge";
    badge.style.background = mode === "metro" ? "#9B59B6"
                           : mode === "bus"   ? "#2980B9" : "#7F8C8D";
    badge.textContent = `${m.icon} ${m.label}`;
    modeIcons.appendChild(badge);
  });

  // Steps
  stepsList.innerHTML = "";
  data.steps.forEach(step => {
    const li    = document.createElement("li");
    li.className = "step-item";
    const m     = MODE_META[step.mode] || { icon: "?", label: step.mode };
    const color = modeColor(step);
    li.innerHTML = `
      <div class="step-icon" style="background:${color}">${m.icon}</div>
      <div class="step-body">
        <div class="step-instruction">${step.instruction}</div>
        <div class="step-time">⏱ ${step.time} min${step.mode === "metro" && step.line ? " · " + step.line + " Line" : ""}</div>
      </div>`;
    stepsList.appendChild(li);
  });

  results.classList.remove("hidden");

  // ── Map rendering ─────────────────────────────────────────────
  if (!map) return;
  clearMapOverlays();

  const bounds = new google.maps.LatLngBounds();

  // Draw polyline segments
  data.segments.forEach(seg => {
    if (!seg.coords || seg.coords.length < 2) return;
    const path = seg.coords.map(c => ({ lat: c.lat, lng: c.lon }));
    path.forEach(p => bounds.extend(p));

    const isWalk = seg.mode === "walk";
    const polyline = new google.maps.Polyline({
      path,
      geodesic: true,
      strokeColor:   seg.color,
      strokeOpacity: isWalk ? 0 : 0.9,
      strokeWeight:  isWalk ? 3 : 5,
      icons: isWalk ? [{
        icon: { path: "M 0,-1 0,1", strokeOpacity: 1, scale: 4,
                strokeColor: seg.color },
        offset: "0",
        repeat: "16px",
      }] : [],
      map,
    });
    mapOverlays.push(polyline);
  });

  // Start marker
  const startPos = { lat: data.start.lat, lng: data.start.lon };
  bounds.extend(startPos);
  const startMarker = new google.maps.Marker({
    position: startPos,
    map,
    icon:  makeMarkerIcon("#27AE60", "A"),
    title: data.start_name,
  });
  const startInfo = new google.maps.InfoWindow({
    content: `<b>Start:</b> ${data.start_name}`,
  });
  startMarker.addListener("click", () => startInfo.open(map, startMarker));
  mapOverlays.push(startMarker);

  // End marker
  const endPos = { lat: data.end.lat, lng: data.end.lon };
  bounds.extend(endPos);
  const endMarker = new google.maps.Marker({
    position: endPos,
    map,
    icon:  makeMarkerIcon("#E53E3E", "B"),
    title: data.end_name,
  });
  const endInfo = new google.maps.InfoWindow({
    content: `<b>End:</b> ${data.end_name}`,
  });
  endMarker.addListener("click", () => endInfo.open(map, endMarker));
  mapOverlays.push(endMarker);

  // Station dots along route
  const visited = new Set();
  data.segments.forEach(seg => {
    if (seg.mode === "walk") return;
    (seg.coords || []).forEach(c => {
      const key = `${c.lat},${c.lon}`;
      if (visited.has(key)) return;
      visited.add(key);
      const circle = new google.maps.Circle({
        center:       { lat: c.lat, lng: c.lon },
        radius:       50,
        strokeColor:  "#fff",
        strokeWeight: 2,
        fillColor:    seg.color,
        fillOpacity:  1,
        map,
      });
      mapOverlays.push(circle);
    });
  });

  // Fit map to route
  if (!bounds.isEmpty()) {
    map.fitBounds(bounds, { top: 40, right: 40, bottom: 40, left: 40 });
  }
}

// ── Form submit ───────────────────────────────────────────────────
form.addEventListener("submit", async e => {
  e.preventDefault();
  const start = startInput.value.trim();
  const end   = endInput.value.trim();

  if (!start || !end) {
    showError("Please enter both a start and an end location.");
    return;
  }
  if (start.toLowerCase() === end.toLowerCase()) {
    showError("Start and end locations are the same.");
    return;
  }

  clearError();
  setLoading(true);

  try {
    const resp = await fetch("/api/route", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ start, end }),
    });
    const data = await resp.json();

    if (!resp.ok) {
      showError(data.error || "Something went wrong.");
    } else {
      renderRoute(data);
    }
  } catch (err) {
    showError("Network error – please try again.");
  } finally {
    setLoading(false);
  }
});

// ── Load metro stations on map startup ───────────────────────────
function loadMetroStations() {
  fetch("/api/stations")
    .then(r => r.json())
    .then(stations => {
      stations.forEach(st => {
        const color = st.lines.includes("purple") && st.lines.includes("green")
                    ? "#E67E22"
                    : st.lines.includes("purple") ? "#9B59B6" : "#27AE60";

        const circle = new google.maps.Circle({
          center:       { lat: st.lat, lng: st.lon },
          radius:       80,
          strokeColor:  "#fff",
          strokeWeight: 1,
          fillColor:    color,
          fillOpacity:  0.7,
          map,
        });

        const lineNames = st.lines
          .map(l => l.charAt(0).toUpperCase() + l.slice(1))
          .join(" / ");
        const infoWindow = new google.maps.InfoWindow({
          content:  `<b>${st.name}</b><br>${lineNames} Line`,
          position: { lat: st.lat, lng: st.lon },
        });
        circle.addListener("click", () => infoWindow.open(map));
      });
    })
    .catch(() => {});
}
