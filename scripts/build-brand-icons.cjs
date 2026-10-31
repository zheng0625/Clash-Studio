// The Android adaptive foreground is the canonical brand mark for every platform.
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const sharp = createRequire(path.join(root, 'frontend/package.json'))('sharp');
const drawable = path.join(root, 'android/app/src/main/res/drawable');
const foreground = fs.readFileSync(path.join(drawable, 'ic_launcher_foreground.xml'), 'utf8');
const attributes = { fillColor: 'fill', strokeColor: 'stroke', strokeWidth: 'stroke-width', strokeLineCap: 'stroke-linecap', strokeLineJoin: 'stroke-linejoin', pathData: 'd' };
const paths = [...foreground.matchAll(/<path\s+([\s\S]*?)\/>/g)].map(([, text]) => {
  const attrs = [...text.matchAll(/android:(\w+)="([^"]*)"/g)].map(([, key, value]) => {
    if (!attributes[key]) throw new Error(`Unsupported vector attribute: ${key}`);
    return `${attributes[key]}="${value === '#00000000' ? 'none' : value}"`;
  });
  return `<path ${attrs.join(' ')}/>`;
});
if (paths.length !== 2 || !foreground.includes('android:viewportWidth="108"')) throw new Error('Unexpected Android brand vector');
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108"><rect width="108" height="108" fill="#FFFFFF"/>${paths.join('')}</svg>\n`;
(async () => {
  for (const name of ['src-tauri/icons/brand.svg', 'frontend/src/assets/brand.svg']) fs.writeFileSync(path.join(root, name), svg);
  const legacy = foreground.replace(/\s*<!--.*?-->/s, '').replace(/(<vector\b[^>]*>)/, '$1\n    <path android:fillColor="#FFFFFF" android:pathData="M0,0h108v108h-108z" />');
  fs.writeFileSync(path.join(drawable, 'ic_launcher.xml'), legacy);
  const source = Buffer.from(svg);
  const sizes = [16, 24, 32, 48, 64, 128, 256];
  const images = await Promise.all(sizes.map(size => sharp(source).resize(size, size).png().toBuffer()));
  const header = Buffer.alloc(6 + sizes.length * 16);
  header.writeUInt16LE(1, 2); header.writeUInt16LE(sizes.length, 4);
  let offset = header.length;
  sizes.forEach((size, index) => {
    const at = 6 + index * 16;
    header[at] = header[at + 1] = size === 256 ? 0 : size;
    header.writeUInt16LE(1, at + 4); header.writeUInt16LE(32, at + 6);
    header.writeUInt32LE(images[index].length, at + 8); header.writeUInt32LE(offset, at + 12);
    offset += images[index].length;
  });
  fs.writeFileSync(path.join(root, 'src-tauri/icons/icon.ico'), Buffer.concat([header, ...images]));
  await sharp(source).resize(512, 512).png().toFile(path.join(root, 'src-tauri/icons/icon.png'));
  const notificationFolder = path.join(drawable, '../drawable-nodpi');
  fs.mkdirSync(notificationFolder, { recursive: true });
  await sharp(source).resize(128, 128).png().toFile(path.join(notificationFolder, 'ic_brand.png'));
  console.log('Updated shared SVGs, Android fallback, multi-size ICO and 512px PNG from the Android white/black icon.');
})().catch(error => { console.error(error.message); process.exitCode = 1; });
