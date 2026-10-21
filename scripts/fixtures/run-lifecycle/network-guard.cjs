// Inherited by Pi and its detached Node runner. No remote sockets, including catalog traffic.
const net = require('node:net');
const tls = require('node:tls');
const fs = require('node:fs');
const audit = (event) => fs.appendFileSync(process.env.HOST_PROBE_NETWORK_LOG, `${JSON.stringify({ pid: process.pid, at: Date.now(), ...event })}\n`);
audit({ type: 'process', agentDir: process.env.PI_CODING_AGENT_DIR, home: process.env.HOME, offline: process.env.PI_OFFLINE });
const connect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function (...args) {
  const [options] = Array.isArray(args[0]) ? args[0] : net._normalizeArgs(args);
  const allowed = options.host === '127.0.0.1' && Number(options.port) === Number(process.env.HOST_PROBE_PORT) && !options.path;
  audit({ type: 'connect', host: options.host, port: options.port, path: options.path, allowed });
  if (!allowed) throw new Error(`host-probe blocked socket: ${JSON.stringify(options)}`);
  return connect.apply(this, args);
};
tls.connect = () => { audit({ type: 'tls', allowed: false }); throw new Error('host-probe blocked TLS'); };
