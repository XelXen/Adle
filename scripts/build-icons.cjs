/**
 * Render the app icons from the vector mark. Run with Electron, which does the drawing:
 *
 *   npm run icons            write apps/desktop/assets/icons/*
 *   npm run icons -- --verify   compare the vector mark with the original artwork
 *
 * Source: apps/desktop/assets/brand/mark.svg (the mark alone, on a 1280 grid).
 * Output: the mark on a rounded tile of the artwork's own backdrop colour, as
 *
 *   icon.ico        16 to 256 px, for Windows (window, taskbar, installer)
 *   icon.png        512 px, for Linux and as the source for other formats
 *   icon-1024.png   for macOS .icns generation at packaging time
 *
 * The outputs are committed. Re-run this only when the mark changes.
 */
const { app, BrowserWindow } = require('electron');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const brandDir = path.join(repoRoot, 'apps', 'desktop', 'assets', 'brand');
const iconsDir = path.join(repoRoot, 'apps', 'desktop', 'assets', 'icons');
const verifyOnly = process.argv.includes('--verify');

const GRID = 1280;
const BACKDROP = '#eeeeee';
/** Corner radius of the tile, on the 1280 grid. */
const TILE_RADIUS = 288;
const ICO_SIZES = [16, 24, 32, 48, 64, 128, 256];

// One device pixel per CSS pixel, whatever display this runs on.
app.commandLine.appendSwitch('force-device-scale-factor', '1');
app.disableHardwareAcceleration();

function markBody() {
  const svg = fs.readFileSync(path.join(brandDir, 'mark.svg'), 'utf8');
  const start = svg.indexOf('>', svg.indexOf('<svg')) + 1;
  return svg.slice(start, svg.lastIndexOf('</svg>')).replace(/<!--[\s\S]*?-->/g, '');
}

function page() {
  return (
    '<!doctype html><html><body style="margin:0;background:transparent;overflow:hidden">' +
    `<svg id="icon" xmlns="http://www.w3.org/2000/svg" width="${GRID}" height="${GRID}" ` +
    `viewBox="0 0 ${GRID} ${GRID}" style="display:block">` +
    `<rect id="tile" width="${GRID}" height="${GRID}" fill="${BACKDROP}"/>${markBody()}</svg>` +
    '</body></html>'
  );
}

/** One offscreen window draws every size: the page is loaded once and resized in place. */
let stage = null;

async function openStage() {
  stage = new BrowserWindow({
    width: GRID,
    height: GRID,
    show: false,
    frame: false,
    transparent: true,
    webPreferences: { offscreen: true, sandbox: true },
  });
  await stage.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(page())}`);
}

async function render(size, { radius }) {
  await stage.webContents.executeJavaScript(
    `(() => {
      const icon = document.getElementById('icon');
      icon.setAttribute('width', '${size}');
      icon.setAttribute('height', '${size}');
      document.getElementById('tile').setAttribute('rx', '${radius}');
      return new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
    })()`,
  );
  await new Promise((resolve) => setTimeout(resolve, 120));
  const image = await stage.webContents.capturePage({ x: 0, y: 0, width: size, height: size });
  const { width, height } = image.getSize();
  if (width !== size || height !== size) {
    throw new Error(`Expected a ${size} px render, got ${width}x${height}.`);
  }
  return image;
}

/** An .ico is a small directory followed by the images, which may be PNG files as they are. */
function ico(entries) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(entries.length, 4);
  const directory = Buffer.alloc(16 * entries.length);
  let offset = header.length + directory.length;
  entries.forEach(({ size, png }, index) => {
    const at = index * 16;
    directory.writeUInt8(size >= 256 ? 0 : size, at);
    directory.writeUInt8(size >= 256 ? 0 : size, at + 1);
    directory.writeUInt8(0, at + 2);
    directory.writeUInt8(0, at + 3);
    directory.writeUInt16LE(1, at + 4);
    directory.writeUInt16LE(32, at + 6);
    directory.writeUInt32LE(png.length, at + 8);
    directory.writeUInt32LE(offset, at + 12);
    offset += png.length;
  });
  return Buffer.concat([header, directory, ...entries.map((entry) => entry.png)]);
}

/** How far the vector mark is from the artwork it was drawn from. */
async function verify() {
  const { nativeImage } = require('electron');
  const original = nativeImage.createFromPath(path.join(brandDir, 'adle-logo.png'));
  const drawn = await render(GRID, { radius: 0 });
  const a = original.toBitmap();
  const b = drawn.toBitmap();
  if (a.length !== b.length) throw new Error('The artwork is not 1280 by 1280.');
  let different = 0;
  for (let index = 0; index < a.length; index += 4) {
    const delta = Math.max(
      Math.abs(a[index] - b[index]),
      Math.abs(a[index + 1] - b[index + 1]),
      Math.abs(a[index + 2] - b[index + 2]),
    );
    if (delta > 48) different += 1;
  }
  const share = (different / (a.length / 4)) * 100;
  console.log(
    `${different} of ${a.length / 4} pixels differ noticeably (${share.toFixed(3)}%). ` +
      'Edges are anti-aliased differently, so a small number is expected.',
  );
  if (share > 0.2) {
    console.error('The vector mark does not match the artwork.');
    process.exitCode = 1;
  }
}

async function build() {
  fs.mkdirSync(iconsDir, { recursive: true });
  const entries = [];
  for (const size of ICO_SIZES) {
    entries.push({ size, png: (await render(size, { radius: TILE_RADIUS })).toPNG() });
  }
  fs.writeFileSync(path.join(iconsDir, 'icon.ico'), ico(entries));
  fs.writeFileSync(
    path.join(iconsDir, 'icon.png'),
    (await render(512, { radius: TILE_RADIUS })).toPNG(),
  );
  fs.writeFileSync(
    path.join(iconsDir, 'icon-1024.png'),
    (await render(1024, { radius: TILE_RADIUS })).toPNG(),
  );
  console.log(`Wrote icon.ico (${ICO_SIZES.join(', ')} px), icon.png, icon-1024.png`);
}

app.whenReady().then(async () => {
  try {
    await openStage();
    await (verifyOnly ? verify() : build());
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  } finally {
    app.quit();
  }
});
