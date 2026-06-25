import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const args = new Set(process.argv.slice(2))
const isRelease = args.has('--release')
const writeDistConfig = args.has('--dist')
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const appRoot = path.resolve(__dirname, '..')
const configPath = path.join(appRoot, 'project.config.json')
const privateConfigPath = path.join(appRoot, 'project.private.config.json')
const distConfigPath = path.join(appRoot, 'dist-weapp', 'project.config.json')

const apiBaseUrl = (process.env.TARO_APP_API_BASE_URL || '').trim()
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
const privateConfig = fs.existsSync(privateConfigPath)
  ? JSON.parse(fs.readFileSync(privateConfigPath, 'utf8'))
  : {}
const localAppid = (
  process.env.TARO_APP_WEAPP_APPID ||
  process.env.WEAPP_APPID ||
  privateConfig.appid ||
  ''
).trim()

function fail(message) {
  console.error(`[weapp config] ${message}`)
  process.exit(1)
}

function validateReleaseApiBaseUrl(value) {
  if (!value) {
    fail('TARO_APP_API_BASE_URL is required for release builds.')
  }

  let parsed
  try {
    parsed = new URL(value)
  } catch {
    fail(`TARO_APP_API_BASE_URL is not a valid URL: ${value}`)
  }

  if (parsed.protocol !== 'https:') {
    fail('TARO_APP_API_BASE_URL must use https:// for WeChat release builds.')
  }

  const hostname = parsed.hostname.toLowerCase()
  const blockedHosts = new Set(['localhost', '127.0.0.1', '0.0.0.0', '[::1]', '::1'])
  if (blockedHosts.has(hostname) || hostname.endsWith('.local')) {
    fail('TARO_APP_API_BASE_URL must be a public HTTPS domain, not a local host.')
  }
}

function mergePackIgnore(existing = [], entries = []) {
  const merged = [...existing]
  const seen = new Set(
    merged.map((item) => `${item.type || ''}:${item.value || ''}`)
  )

  for (const entry of entries) {
    const key = `${entry.type}:${entry.value}`
    if (!seen.has(key)) {
      merged.push(entry)
      seen.add(key)
    }
  }

  return merged
}

function applyRootPackOptions(targetConfig) {
  targetConfig.packOptions = {
    ...(targetConfig.packOptions || {}),
    ignore: mergePackIgnore(targetConfig.packOptions?.ignore, [
      { type: 'folder', value: 'node_modules' },
      { type: 'folder', value: '.swc' },
      { type: 'folder', value: '.preview' },
      { type: 'folder', value: 'dist' },
      { type: 'folder', value: 'screenshots' },
      { type: 'folder', value: 'src' },
      { type: 'folder', value: 'scripts' },
      { type: 'folder', value: 'types' },
    ]),
  }
}

function applyDistPackOptions(targetConfig) {
  targetConfig.packOptions = {
    ...(targetConfig.packOptions || {}),
    ignore: mergePackIgnore(targetConfig.packOptions?.ignore, [
      { type: 'suffix', value: '.map' },
      { type: 'folder', value: 'node_modules' },
      { type: 'folder', value: '.swc' },
    ]),
  }
}

if (isRelease) {
  validateReleaseApiBaseUrl(apiBaseUrl)
  if (!localAppid || localAppid === 'touristappid') {
    fail('TARO_APP_WEAPP_APPID, WEAPP_APPID, or project.private.config.json must provide the real mini program AppID.')
  }
}

config.miniprogramRoot = './dist-weapp'
config.appid = 'touristappid'
applyRootPackOptions(config)

const next = `${JSON.stringify(config, null, 2)}\n`
if (fs.readFileSync(configPath, 'utf8') !== next) {
  fs.writeFileSync(configPath, next)
}

if (writeDistConfig) {
  if (!fs.existsSync(distConfigPath)) {
    fail('dist-weapp/project.config.json was not found. Run the Taro weapp build first.')
  }
  const distConfig = JSON.parse(fs.readFileSync(distConfigPath, 'utf8'))
  distConfig.miniprogramRoot = './'
  distConfig.appid = localAppid || 'touristappid'
  distConfig.setting = {
    ...(distConfig.setting || {}),
    minified: Boolean(isRelease),
  }
  applyDistPackOptions(distConfig)
  fs.writeFileSync(distConfigPath, `${JSON.stringify(distConfig, null, 2)}\n`)
}

const appidSource = localAppid && localAppid !== 'touristappid' ? 'local' : 'touristappid'
console.log(
  `[weapp config] miniprogramRoot=${config.miniprogramRoot}, appid=${appidSource}, dist=${writeDistConfig ? 'yes' : 'no'}, release=${isRelease ? 'yes' : 'no'}`
)
