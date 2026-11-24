// Make scanned-notes.pdf: pages that are pictures with no text layer, as a scanner or a
// phone makes them, and one page of ordinary text.
// Run through Electron, on Windows (the handwriting is drawn in its "Ink Free" font):
//
//   npx electron scripts/fixtures/print-scans.cjs scripts/fixtures/scanned-notes.html \
//       fixtures/sample-documents/scanned-notes.pdf
//
// Each `.sheet` of the page is photographed (`capturePage`), slightly gray and soft, as a
// scan is. The photographs, and the last sheet as text, are then printed to one PDF.
const { app, BrowserWindow } = require('electron');
const fs = require('node:fs');
const path = require('node:path');

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error('usage: electron print-scans.cjs <input.html> <output.pdf>');
  process.exit(2);
}

const PICTURES = ['typed', 'hand'];
const TEXT = 'text';

app.disableHardwareAcceleration();
app.whenReady().then(async () => {
  const window = new BrowserWindow({
    width: 794,
    height: 1123,
    show: false,
    useContentSize: true,
    webPreferences: { sandbox: true, offscreen: true },
  });
  await window.loadFile(path.resolve(input));
  window.webContents.setZoomFactor(1);

  const photographs = [];
  for (const id of PICTURES) {
    // One sheet at a time, filling the window, then photographed at twice the size: about
    // 190 dots to the inch on A4, as a scanner set for documents makes.
    await window.webContents.executeJavaScript(`
      for (const sheet of document.querySelectorAll('.sheet')) {
        sheet.style.display = sheet.id === ${JSON.stringify(id)} ? 'block' : 'none';
      }
      document.body.style.filter = 'grayscale(0.35) blur(0.35px) contrast(1.08)';
      document.documentElement.style.overflow = 'hidden';
      new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
    `);
    window.webContents.setZoomFactor(2);
    window.setContentSize(794 * 2, 1123 * 2);
    await new Promise((done) => setTimeout(done, 300));
    const image = await window.webContents.capturePage();
    photographs.push(image.toJPEG(82).toString('base64'));
    window.webContents.setZoomFactor(1);
    window.setContentSize(794, 1123);
  }

  const text = await window.webContents.executeJavaScript(`
    const sheet = document.getElementById(${JSON.stringify(TEXT)});
    sheet.style.display = '';
    sheet.outerHTML;
  `);
  const style = await window.webContents.executeJavaScript(
    `document.querySelector('style').textContent`,
  );
  const pages = photographs
    .map((jpeg) => `<div class="page"><img src="data:image/jpeg;base64,${jpeg}" alt=""></div>`)
    .join('');
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
    @page { size: A4; margin: 0; }
    body { margin: 0; }
    ${style}
    .page { width: 210mm; height: 297mm; break-after: page; overflow: hidden; }
    .page img { width: 210mm; height: 297mm; display: block; }
    .sheet { width: 210mm; height: 297mm; }
  </style></head><body>${pages}${text}</body></html>`;
  const sheetFile = path.resolve(output) + '.html';
  fs.writeFileSync(sheetFile, html);
  const printer = new BrowserWindow({ show: false, webPreferences: { sandbox: true } });
  await printer.loadFile(sheetFile);
  const pdf = await printer.webContents.printToPDF({
    pageSize: 'A4',
    printBackground: true,
    margins: { marginType: 'none' },
  });
  fs.rmSync(sheetFile);
  fs.writeFileSync(path.resolve(output), pdf);
  console.log(`wrote ${output} (${pdf.length} bytes)`);
  app.quit();
});
