import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const args = new Set(process.argv.slice(2))
const isRelease = args.has('--release')
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const appRoot = path.resolve(__dirname, '..')
const configPath = path.join(appRoot, 'project.config.json')

const apiBaseUrl = (process.env.TARO_APP_API_BASE_URL || '').trim()
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
const appid = (
  process.env.TARO_APP_WEAPP_APPID ||
  process.env.WEAPP_APPID ||
  config.appid ||
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

if (isRelease) {
  validateReleaseApiBaseUrl(apiBaseUrl)
  if (!appid || appid === 'touristappid') {
    fail('TARO_APP_WEAPP_APPID or WEAPP_APPID must be set to the real mini program AppID.')
  }
}

config.miniprogramRoot = './dist-weapp'
if (appid) {
  config.appid = appid
}

const next = `${JSON.stringify(config, null, 2)}\n`
if (fs.readFileSync(configPath, 'utf8') !== next) {
  fs.writeFileSync(configPath, next)
}

console.log(
  `[weapp config] miniprogramRoot=${config.miniprogramRoot}, appid=${config.appid}, release=${isRelease ? 'yes' : 'no'}`
)
