WA.onInit().then(() => {
  const roofLayers = ["lowerLeft", "lowerRight", "upperLeft", "upperRight"];
  roofLayers.forEach((layerName) => {
    WA.room.area.onEnter(`roof_${layerName}`).subscribe(() => WA.room.hideLayer(`roofs/${layerName}`));
    WA.room.area.onLeave(`roof_${layerName}`).subscribe(() => WA.room.showLayer(`roofs/${layerName}`));
  });

  // Toit SACEM : l'intérieur du bâtiment est couvert par plusieurs rectangles (roof_sacem, roof_sacem_2, …),
  // atteignables uniquement par la porte. On compte dans combien on se trouve : le toit ne réapparaît
  // qu'une fois sorti de tous, avec un court délai pour éviter un clignotement en passant de l'un à l'autre.
  const sacemAreas = ["roof_sacem", "roof_sacem_2", "roof_sacem_3", "roof_sacem_4", "roof_sacem_5", "roof_sacem_6", "roof_sacem_7", "roof_sacem_8", "roof_sacem_9"];
  let insideSacem = 0;
  let showTimer = null;
  sacemAreas.forEach((name) => {
    WA.room.area.onEnter(name).subscribe(() => {
      insideSacem++;
      if (showTimer) { clearTimeout(showTimer); showTimer = null; }
      WA.room.hideLayer("roofs/sacem");
    });
    WA.room.area.onLeave(name).subscribe(() => {
      insideSacem = Math.max(0, insideSacem - 1);
      if (insideSacem === 0) {
        if (showTimer) clearTimeout(showTimer);
        showTimer = setTimeout(() => { if (insideSacem === 0) WA.room.showLayer("roofs/sacem"); showTimer = null; }, 150);
      }
    });
  });

  const outlineByTag = [["admin", [128, 0, 128]], ["teacher", [0, 0, 255]], ["masterclass", [255, 255, 0]]];
  const match = outlineByTag.find(([tag]) => WA.player.tags.includes(tag));
  if (match) WA.player.setOutlineColor(...match[1]);
});
