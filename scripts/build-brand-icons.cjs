// Uses Sharp as a build tool only; the supplied SVG is the source of truth.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
const root = path.resolve(__dirname, '..');
const source = path.join(root, 'src-tauri/icons/brand.svg');
(async () => {
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
  console.log('Generated multi-size Windows icon and 512px preview from supplied SVG.');
})().catch(error => { console.error(error.message); process.exitCode = 1; });
