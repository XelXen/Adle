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
 *   icon.png        512 px, for the window on Linux and as the source for other formats
 *   icon-1024.png   the largest size, as a picture
 *   icon.icns       for macOS: the same tile drawn smaller, with the margin a Mac leaves
 *                   around every icon, at the sizes the Dock and the Finder ask for
 *   linux/NxN.png   16 to 512 px, for a desktop's menus (the sizes of the "hicolor" theme)
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
const LINUX_SIZES = [16, 24, 32, 48, 64, 128, 256, 512];
/**
 * A Mac's icon is a tile of 824 on a canvas of 1024: every icon keeps the same margin, and
 * one drawn to its edges looks a size too large beside the others.
 */
const MAC_TILE_SHARE = 824 / 1024;
/** The kinds an .icns file holds as PNG, by the size of the picture in each. */
const ICNS_KINDS = [
  ['ic11', 32],
  ['ic12', 64],
  ['ic07', 128],
  ['ic13', 256],
  ['ic08', 256],
  ['ic14', 512],
  ['ic09', 512],
  ['ic10', 1024],
];

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
    `viewBox="0 0 ${GRID} ${GRID}" style="display:block"><g id="art">` +
    `<rect id="tile" width="${GRID}" height="${GRID}" fill="${BACKDROP}"/>${markBody()}</g></svg>` +
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

/** `share` is how much of the canvas the tile takes: 1 for a tile drawn to the edges. */
async function render(size, { radius, share = 1 }) {
  const margin = (GRID * (1 - share)) / 2;
  await stage.webContents.executeJavaScript(
    `(() => {
      const icon = document.getElementById('icon');
      icon.setAttribute('width', '${size}');
      icon.setAttribute('height', '${size}');
      document.getElementById('tile').setAttribute('rx', '${radius}');
      document
        .getElementById('art')
        .setAttribute('transform', 'translate(${margin} ${margin}) scale(${share})');
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

/**
 * An .icns is the word "icns", the length of the whole file, and then each picture behind
 * its kind and its own length. Since OS X 10.7 a picture may be a PNG file as it is.
 */
function icns(entries) {
  const parts = entries.map(({ kind, png }) => {
    const header = Buffer.alloc(8);
    header.write(kind, 0, 'ascii');
    header.writeUInt32BE(png.length + 8, 4);
    return Buffer.concat([header, png]);
  });
  const body = Buffer.concat(parts);
  const header = Buffer.alloc(8);
  header.write('icns', 0, 'ascii');
  header.writeUInt32BE(body.length + 8, 4);
  return Buffer.concat([header, body]);
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

  const macPictures = new Map();
  for (const [, size] of ICNS_KINDS) {
    if (!macPictures.has(size)) {
      macPictures.set(
        size,
        (await render(size, { radius: TILE_RADIUS, share: MAC_TILE_SHARE })).toPNG(),
      );
    }
  }
  fs.writeFileSync(
    path.join(iconsDir, 'icon.icns'),
    icns(ICNS_KINDS.map(([kind, size]) => ({ kind, png: macPictures.get(size) }))),
  );

  const linuxDir = path.join(iconsDir, 'linux');
  fs.mkdirSync(linuxDir, { recursive: true });
  for (const size of LINUX_SIZES) {
    fs.writeFileSync(
      path.join(linuxDir, `${size}x${size}.png`),
      (await render(size, { radius: TILE_RADIUS })).toPNG(),
    );
  }
  console.log(
    `Wrote icon.ico (${ICO_SIZES.join(', ')} px), icon.png, icon-1024.png, icon.icns, ` +
      `linux/ (${LINUX_SIZES.join(', ')} px)`,
  );
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
