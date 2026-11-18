// Actualiza en vivo los nombres de elemento y unidad en la tabla de leyes.
document.addEventListener("change", (event) => {
  const el = event.target;
  const pairs = [["elSelect", "el-name"], ["unitSelect", "unit-name"]];
  for (const [dataKey, target] of pairs) {
    const index = el.dataset[dataKey];
    if (index === undefined) continue;
    document.querySelectorAll(`[data-${target}="${index}"]`).forEach((span) => {
      span.textContent = el.value;
    });
  }
});
