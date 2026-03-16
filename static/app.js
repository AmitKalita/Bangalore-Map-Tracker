// ── Leaflet map ───────────────────────────────────────────────────
const map = L.map("map", { zoomControl: true }).setView([12.9716, 77.5946], 12);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
  maxZoom: 19,
}).addTo(map);

// ── State ─────────────────────────────────────────────────────────
let mapLayers = [];

function clearMapLayers() {
  mapLayers.forEach(l => map.removeLayer(l));
  mapLayers = [];
}

// ── Custom markers ────────────────────────────────────────────────
function makeIcon(color, symbol) {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:30px;height:30px;
      background:${color};
      border:3px solid #fff;
      border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      color:#fff;font-size:14px;
      box-shadow:0 2px 6px rgba(0,0,0,.3);
    ">${symbol}</div>`,
    iconSize:   [30, 30],
    iconAnchor: [15, 15],
    popupAnchor:[0, -15],
  });
}

const startIcon = makeIcon("#27AE60", "A");
const endIcon   = makeIcon("#E53E3E", "B");
const stationIcon = (color) => makeIcon(color, "●");

// ── DOM refs ──────────────────────────────────────────────────────
const form       = document.getElementById("routeForm");
const startInput = document.getElementById("startInput");
const endInput   = document.getElementById("endInput");
const findBtn    = document.getElementById("findBtn");
const btnText    = document.getElementById("btnText");
const btnSpinner = document.getElementById("btnSpinner");
const results    = document.getElementById("results");
const errorBanner= document.getElementById("errorBanner");
const stepsList  = document.getElementById("stepsList");
const sumFrom    = document.getElementById("sumFrom");
const sumTo      = document.getElementById("sumTo");
const sumTime    = document.getElementById("sumTime");
const modeIcons  = document.getElementById("modeIcons");
const swapBtn    = document.getElementById("swapBtn");

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
  findBtn.disabled = on;
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
  if (step.mode === "bus")  return "#2980B9";
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
    const m = MODE_META[mode] || { icon: "?", label: mode };
    const badge = document.createElement("span");
    badge.className = "mode-badge";
    badge.style.background = mode === "metro" ? "#9B59B6"
                           : mode === "bus"   ? "#2980B9" : "#7F8C8D";
    badge.textContent = `${m.icon} ${m.label}`;
    modeIcons.appendChild(badge);
  });

  // Steps
  stepsList.innerHTML = "";
  data.steps.forEach((step, idx) => {
    const li   = document.createElement("li");
    li.className = "step-item";

    const m    = MODE_META[step.mode] || { icon: "?", label: step.mode };
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
  clearMapLayers();

  // Draw polyline segments
  data.segments.forEach(seg => {
    if (!seg.coords || seg.coords.length < 2) return;
    const latlngs = seg.coords.map(c => [c.lat, c.lon]);
    const dashArray = seg.mode === "walk" ? "6 6" : null;
    const weight    = seg.mode === "walk" ? 3 : 5;
    const line = L.polyline(latlngs, {
      color: seg.color,
      weight,
      opacity: seg.mode === "walk" ? 0.7 : 0.9,
      dashArray,
    }).addTo(map);
    mapLayers.push(line);
  });

  // Start & end markers
  const sm = L.marker([data.start.lat, data.start.lon], { icon: startIcon })
              .bindPopup(`<b>Start:</b> ${data.start_name}`).addTo(map);
  const em = L.marker([data.end.lat,   data.end.lon],   { icon: endIcon })
              .bindPopup(`<b>End:</b> ${data.end_name}`).addTo(map);
  mapLayers.push(sm, em);

  // Station markers along route
  const visited = new Set();
  data.segments.forEach(seg => {
    if (seg.mode === "walk") return;
    (seg.coords || []).forEach(c => {
      const key = `${c.lat},${c.lon}`;
      if (visited.has(key)) return;
      visited.add(key);
      const m = L.circleMarker([c.lat, c.lon], {
        radius: 5, color: "#fff", weight: 2,
        fillColor: seg.color, fillOpacity: 1,
      }).addTo(map);
      mapLayers.push(m);
    });
  });

  // Fit map to route
  const allCoords = data.segments.flatMap(s => (s.coords || []).map(c => [c.lat, c.lon]));
  allCoords.push([data.start.lat, data.start.lon], [data.end.lat, data.end.lon]);
  if (allCoords.length) {
    map.fitBounds(L.latLngBounds(allCoords), { padding: [40, 40] });
  }
}

// ── Form submit ───────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
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
fetch("/api/stations")
  .then(r => r.json())
  .then(stations => {
    stations.forEach(st => {
      const color = st.lines.includes("purple") && st.lines.includes("green")
                  ? "#E67E22"      // interchange = orange
                  : st.lines.includes("purple") ? "#9B59B6" : "#27AE60";
      L.circleMarker([st.lat, st.lon], {
        radius: 4, color, weight: 1,
        fillColor: color, fillOpacity: 0.7,
        className: "station-dot",
      })
        .bindPopup(`<b>${st.name}</b><br>${st.lines.map(l => l.charAt(0).toUpperCase() + l.slice(1)).join(" / ")} Line`)
        .addTo(map);
    });
  })
  .catch(() => {});
