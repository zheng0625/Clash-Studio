// Settings automation must never select another saved VPN's Forget action.
const assert=require('node:assert/strict');
const {DeviceSession}=require('./android-device-session.cjs');
process.env.ANDROID_SERIAL='unit-scope-check';
process.env.ANDROID_PACKAGE='studio.clash.android.validation.acceptance';
const device=new DeviceSession(),commands=[];
device.command=(...args)=>commands.push(args);
const node=(attribute,value,bounds)=>`<node ${attribute}="${value}" bounds="${bounds}">`;
device.uiNodes=()=>[
  node('text','Another VPN','[252,146][669,217]'),
  node('content-desc','设置','[1024,98][1168,265]'),
  node('text','Clash Studio · 验收','[252,346][669,417]'),
  node('content-desc','设置','[1024,298][1168,465]'),
];
device.openIsolatedVpnSettings();
assert.deepEqual(commands,[['shell','input','tap','1096','382']]);
device.uiNodes=()=>[node('content-desc','Another VPN','[0,130][1264,298]'),node('text','取消保存 VPN','[252,1032][551,1103]')];
assert.throws(()=>device.openIsolatedVpnSettings(),/isolated acceptance/);
assert.throws(()=>device.assertIsolatedVpnUi(),/another VPN/);
device.uiNodes=()=>[node('content-desc','Clash Studio · 验收','[0,130][1264,298]'),node('text','取消保存 VPN','[252,1032][551,1103]')];
device.openIsolatedVpnSettings();device.assertIsolatedVpnUi();
assert.equal(commands.length,1);
console.log('PASS Settings scope: own VPN row selected; another VPN detail/forget rejected');
