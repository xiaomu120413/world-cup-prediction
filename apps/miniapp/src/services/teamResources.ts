export type TeamResource = {
  id: string
  name: string
  nameEn: string
  flagCode: string
  aliases?: string[]
}

export const teamResources: TeamResource[] = [
  { id: 'argentina', name: '阿根廷', nameEn: 'Argentina', flagCode: 'ar' },
  { id: 'spain', name: '西班牙', nameEn: 'Spain', flagCode: 'es' },
  { id: 'france', name: '法国', nameEn: 'France', flagCode: 'fr' },
  { id: 'england', name: '英格兰', nameEn: 'England', flagCode: 'gb-eng' },
  { id: 'portugal', name: '葡萄牙', nameEn: 'Portugal', flagCode: 'pt' },
  { id: 'brazil', name: '巴西', nameEn: 'Brazil', flagCode: 'br' },
  { id: 'morocco', name: '摩洛哥', nameEn: 'Morocco', flagCode: 'ma' },
  { id: 'netherlands', name: '荷兰', nameEn: 'Netherlands', flagCode: 'nl' },
  { id: 'belgium', name: '比利时', nameEn: 'Belgium', flagCode: 'be' },
  { id: 'germany', name: '德国', nameEn: 'Germany', flagCode: 'de' },
  { id: 'croatia', name: '克罗地亚', nameEn: 'Croatia', flagCode: 'hr' },
  { id: 'colombia', name: '哥伦比亚', nameEn: 'Colombia', flagCode: 'co' },
  { id: 'mexico', name: '墨西哥', nameEn: 'Mexico', flagCode: 'mx' },
  { id: 'senegal', name: '塞内加尔', nameEn: 'Senegal', flagCode: 'sn' },
  { id: 'uruguay', name: '乌拉圭', nameEn: 'Uruguay', flagCode: 'uy' },
  { id: 'usa', name: '美国', nameEn: 'United States', flagCode: 'us', aliases: ['USA', 'United States of America'] },
  { id: 'japan', name: '日本', nameEn: 'Japan', flagCode: 'jp' },
  { id: 'switzerland', name: '瑞士', nameEn: 'Switzerland', flagCode: 'ch' },
  { id: 'iran', name: '伊朗', nameEn: 'Iran', flagCode: 'ir', aliases: ['IR Iran', 'IR-IRAN'] },
  { id: 'turkey', name: '土耳其', nameEn: 'Turkey', flagCode: 'tr', aliases: ['Turkiye', 'Türkiye'] },
  { id: 'ecuador', name: '厄瓜多尔', nameEn: 'Ecuador', flagCode: 'ec' },
  { id: 'austria', name: '奥地利', nameEn: 'Austria', flagCode: 'at' },
  { id: 'south-korea', name: '韩国', nameEn: 'South Korea', flagCode: 'kr', aliases: ['Korea Republic', 'KOREA-REPUBLIC'] },
  { id: 'australia', name: '澳大利亚', nameEn: 'Australia', flagCode: 'au' },
  { id: 'algeria', name: '阿尔及利亚', nameEn: 'Algeria', flagCode: 'dz' },
  { id: 'egypt', name: '埃及', nameEn: 'Egypt', flagCode: 'eg' },
  { id: 'canada', name: '加拿大', nameEn: 'Canada', flagCode: 'ca' },
  { id: 'norway', name: '挪威', nameEn: 'Norway', flagCode: 'no' },
  { id: 'ivory-coast', name: '科特迪瓦', nameEn: 'Ivory Coast', flagCode: 'ci', aliases: ["Cote d'Ivoire", "Cote D Ivoire", "COTE-D-IVOIRE"] },
  { id: 'panama', name: '巴拿马', nameEn: 'Panama', flagCode: 'pa' },
  { id: 'sweden', name: '瑞典', nameEn: 'Sweden', flagCode: 'se' },
  { id: 'czech', name: '捷克', nameEn: 'Czech', flagCode: 'cz', aliases: ['Czechia'] },
  { id: 'paraguay', name: '巴拉圭', nameEn: 'Paraguay', flagCode: 'py' },
  { id: 'scotland', name: '苏格兰', nameEn: 'Scotland', flagCode: 'gb-sct' },
  { id: 'tunisia', name: '突尼斯', nameEn: 'Tunisia', flagCode: 'tn' },
  { id: 'congo-dr', name: '刚果民主共和国', nameEn: 'Congo DR', flagCode: 'cd', aliases: ['DR Congo', 'CONGO-DR'] },
  { id: 'uzbekistan', name: '乌兹别克斯坦', nameEn: 'Uzbekistan', flagCode: 'uz' },
  { id: 'qatar', name: '卡塔尔', nameEn: 'Qatar', flagCode: 'qa' },
  { id: 'iraq', name: '伊拉克', nameEn: 'Iraq', flagCode: 'iq' },
  { id: 'south-africa', name: '南非', nameEn: 'South Africa', flagCode: 'za' },
  { id: 'saudi-arabia', name: '沙特阿拉伯', nameEn: 'Saudi Arabia', flagCode: 'sa' },
  { id: 'jordan', name: '约旦', nameEn: 'Jordan', flagCode: 'jo' },
  { id: 'bosnia-herzegovina', name: '波黑', nameEn: 'Bosnia-Herzegovina', flagCode: 'ba', aliases: ['Bosnia and Herzegovina', 'Bosnia-Herzegovina'] },
  { id: 'cape-verde', name: '佛得角', nameEn: 'Cape Verde', flagCode: 'cv', aliases: ['Cabo Verde'] },
  { id: 'ghana', name: '加纳', nameEn: 'Ghana', flagCode: 'gh' },
  { id: 'curacao', name: '库拉索', nameEn: 'Curacao', flagCode: 'cw', aliases: ['Curaçao'] },
  { id: 'haiti', name: '海地', nameEn: 'Haiti', flagCode: 'ht' },
  { id: 'new-zealand', name: '新西兰', nameEn: 'New Zealand', flagCode: 'nz' },
  { id: 'denmark', name: '丹麦', nameEn: 'Denmark', flagCode: 'dk' },
  { id: 'italy', name: '意大利', nameEn: 'Italy', flagCode: 'it' }
]

function normalizeTeamKey(value?: string | null) {
  return (value || '').trim().toLowerCase().replace(/\s+/g, '-')
}

function looksGarbled(value?: string | null) {
  return Boolean(value && /[�ÃÂäåæçèéà]/.test(value))
}

const teamByLookupKey = teamResources.reduce<Record<string, TeamResource>>((map, team) => {
  const keys = [team.id, team.name, team.nameEn, ...(team.aliases || [])]
  keys.forEach(key => {
    map[normalizeTeamKey(key)] = team
  })
  return map
}, {})

export function getFlagCodeByTeamName(name: string) {
  return teamByLookupKey[normalizeTeamKey(name)]?.flagCode
}

export function getTeamDisplayName(name?: string | null, nameEn?: string | null, id?: string | null) {
  const direct = teamByLookupKey[normalizeTeamKey(name)]
  if (direct && !looksGarbled(name)) return direct.name

  const byEnglish = teamByLookupKey[normalizeTeamKey(nameEn)]
  if (byEnglish) return byEnglish.name

  const byId = teamByLookupKey[normalizeTeamKey(id)]
  if (byId) return byId.name

  return looksGarbled(name) ? nameEn || id || '球队待同步' : name || nameEn || id || '球队待同步'
}
