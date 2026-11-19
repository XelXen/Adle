// Print an HTML file to PDF with Chromium, to produce a realistic test fixture.
// Run through Electron:  npx electron scripts/fixtures/print-pdf.cjs <input.html> <output.pdf>
//
// The result is a real, text-layer PDF of the kind a learner would export from a
// browser or word processor: embedded subset fonts, ToUnicode maps, multiple pages.
const { app, BrowserWindow } = require('electron');
const fs = require('node:fs');
const path = require('node:path');

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error('usage: electron print-pdf.cjs <input.html> <output.pdf>');
  process.exit(2);
}

app.disableHardwareAcceleration();
app.whenReady().then(async () => {
  const window = new BrowserWindow({
    show: false,
    webPreferences: { sandbox: true, javascript: false },
  });
  await window.loadFile(path.resolve(input));
  const pdf = await window.webContents.printToPDF({
    pageSize: 'A4',
    printBackground: false,
    margins: { marginType: 'default' },
  });
  fs.writeFileSync(path.resolve(output), pdf);
  console.log(`wrote ${output} (${pdf.length} bytes)`);
  app.quit();
});
