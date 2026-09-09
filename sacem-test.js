WA.onInit().then(() => {
  const roofLayers = ["lowerLeft", "lowerRight", "upperLeft", "upperRight", "sacem"];
  roofLayers.forEach((layerName) => {
    WA.room.area.onEnter(`roof_${layerName}`).subscribe(() => WA.room.hideLayer(`roofs/${layerName}`));
    WA.room.area.onLeave(`roof_${layerName}`).subscribe(() => WA.room.showLayer(`roofs/${layerName}`));
  });

  const outlineByTag = [
    ["admin", [128, 0, 128]],
    ["teacher", [0, 0, 255]],
    ["masterclass", [255, 255, 0]],
  ];
  const match = outlineByTag.find(([tag]) => WA.player.tags.includes(tag));
  if (match) WA.player.setOutlineColor(...match[1]);
});
