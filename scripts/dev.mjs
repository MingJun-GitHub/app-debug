import { spawn } from 'node:child_process'

const children = []
const isWindows = process.platform === 'win32'
const python = isWindows ? 'python' : 'python3'
const nuxi = isWindows ? 'npx.cmd' : 'npx'

function start(command, args, env = {}) {
  const child = spawn(command, args, {
    stdio: 'inherit',
    env: { ...process.env, ...env }
  })
  children.push(child)
  return child
}

function shutdown(signal = 'SIGTERM') {
  for (const child of children) {
    if (!child.killed) child.kill(signal)
  }
}

process.on('SIGINT', () => shutdown('SIGINT'))
process.on('SIGTERM', () => shutdown('SIGTERM'))
process.on('exit', () => shutdown())

start(python, ['server.py', '--no-browser'], { PORT: '8787' })
const ui = start(nuxi, ['nuxt', 'dev'])
ui.on('exit', code => process.exit(code ?? 0))
