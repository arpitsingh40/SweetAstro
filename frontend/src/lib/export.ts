/**
 * Client-side SVG -> PNG export (no server render, no external deps).
 * Used for kundli share cards (WhatsApp-friendly).
 */
export async function downloadSvgAsPng(
  svg: SVGSVGElement,
  filename: string,
  scale = 2,
): Promise<void> {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const viewBox = (svg.getAttribute("viewBox") || "0 0 320 320").trim().split(/\s+/).map(Number);
  const width = viewBox[2] || 320;
  const height = viewBox[3] || 320;

  const svgBlob = new Blob([new XMLSerializer().serializeToString(clone)],
    { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(svgBlob);
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("Could not render the chart image."));
      image.src = svgUrl;
    });
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas is unavailable in this browser.");
    ctx.fillStyle = "#020617";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("PNG encoding failed.");
    const pngUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = pngUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(pngUrl);
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
}
