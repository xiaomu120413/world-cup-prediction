import { emptyTeamProfile, type TeamProfile } from '@/services/mock'

export type TeamResource = {
  id: string
  name: string
  flagCode: string
}

const flagCodeByTeamName: Record<string, string> = {
  阿根廷: 'ar',
  澳大利亚: 'au',
  比利时: 'be',
  巴西: 'br',
  加拿大: 'ca',
  哥伦比亚: 'co',
  克罗地亚: 'hr',
  丹麦: 'dk',
  英格兰: 'gb-eng',
  法国: 'fr',
  德国: 'de',
  意大利: 'it',
  日本: 'jp',
  墨西哥: 'mx',
  摩洛哥: 'ma',
  荷兰: 'nl',
  葡萄牙: 'pt',
  韩国: 'kr',
  西班牙: 'es',
  瑞士: 'ch',
  美国: 'us',
  乌拉圭: 'uy'
}

export const teamResources: TeamResource[] = Object.entries(flagCodeByTeamName).map(([name, flagCode]) => ({
  id: '',
  name,
  flagCode
}))

export const teamProfilesById: Record<string, TeamProfile> = {}

export function getTeamIdByName(_name?: string) {
  return ''
}

export function getFlagCodeByTeamName(name: string) {
  return flagCodeByTeamName[name]
}

export function getTeamProfileById(teamId = '') {
  return {
    ...emptyTeamProfile,
    id: teamId || emptyTeamProfile.id
  }
}
