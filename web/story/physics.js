// Diagramas SVG de los 3 mecanismos físicos de retrodispersión SAR en Banda L (24 cm)

export function renderPhysicsDiagrams(container, lang = "es") {
  const isEn = lang === "en";
  const cards = [
    {
      title: isEn ? "1. Volume scattering" : "1. Dispersión volumétrica",
      desc: isEn
        ? "Intact forest canopy: branches bounce the 24 cm L-band wave multiple times, rotating polarization → bright HV."
        : "Bosque intacto: las ramas rebotan la onda de 24 cm en múltiples ángulos y giran el plano → HV alto.",
      svg: `
        <svg viewBox="0 0 180 110" aria-label="Dispersión volumétrica">
          <rect x="0" y="92" width="180" height="18" fill="#2b241c"/>
          <path d="M55,92 L55,58 M125,92 L125,58" stroke="#8b5e34" stroke-width="5"/>
          <circle cx="55" cy="46" r="22" fill="#2f6e49" opacity="0.88"/>
          <circle cx="125" cy="48" r="20" fill="#2f6e49" opacity="0.88"/>
          <path d="M22,12 L48,40 L62,48 L52,32 L78,12" fill="none" stroke="#39e8e0" stroke-width="2" stroke-dasharray="4 2"/>
          <path d="M98,12 L120,42 L132,52 L116,58 L145,14" fill="none" stroke="#f6c963" stroke-width="2"/>
          <text x="8" y="104" fill="#9c9284" font-size="8" font-family="monospace">HV ALTO · dosel 3D</text>
        </svg>`,
    },
    {
      title: isEn ? "2. Specular / surface drop" : "2. Superficie rasurada (caída HV)",
      desc: isEn
        ? "Burned canopy: leaves & fine twigs are gone. Microwave bounces away from the radar → sharp HV drop (≤ −1.5 dB)."
        : "Copa consumida: desaparecen hojas y ramas finas; la onda se aleja especularmente → desplome de HV.",
      svg: `
        <svg viewBox="0 0 180 110" aria-label="Superficie quemada">
          <rect x="0" y="92" width="180" height="18" fill="#1e1915"/>
          <path d="M25,14 L88,91 L154,18" fill="none" stroke="#e2793c" stroke-width="2.2" stroke-dasharray="4 3"/>
          <path d="M148,18 L156,16 L154,25" fill="none" stroke="#e2793c" stroke-width="2"/>
          <line x1="70" y1="92" x2="70" y2="74" stroke="#5c4d41" stroke-width="3"/>
          <line x1="108" y1="92" x2="108" y2="78" stroke="#5c4d41" stroke-width="3"/>
          <text x="8" y="104" fill="#9c9284" font-size="8" font-family="monospace">HV BAJO · ΔHV ≤ -1.5 dB</text>
        </svg>`,
    },
    {
      title: isEn ? "3. Double-bounce (HH)" : "3. Doble rebote (polarización HH)",
      desc: isEn
        ? "Standing charred trunks + bare ground form a 90° corner reflector returning energy in parallel HH."
        : "Tronco en pie + suelo desnudo forman esquina de 90° y devuelven pulso intenso en HH paralela.",
      svg: `
        <svg viewBox="0 0 180 110" aria-label="Doble rebote HH">
          <rect x="0" y="92" width="180" height="18" fill="#2b241c"/>
          <line x1="110" y1="92" x2="110" y2="30" stroke="#786354" stroke-width="6"/>
          <path d="M26,18 L86,91 L108,68 L44,12" fill="none" stroke="#f6c963" stroke-width="2.2"/>
          <path d="M51,12 L42,10 L45,19" fill="none" stroke="#f6c963" stroke-width="2"/>
          <text x="8" y="104" fill="#9c9284" font-size="8" font-family="monospace">HH SENSIBLE · tronco/humedad</text>
        </svg>`,
    },
  ];

  container.innerHTML = cards
    .map(
      (c) => `
      <div class="physics-card">
        ${c.svg}
        <h4>${c.title}</h4>
        <p>${c.desc}</p>
      </div>`
    )
    .join("");
}
