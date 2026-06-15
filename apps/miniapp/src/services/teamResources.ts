import type { TeamProfile } from '@/services/mock'

export type TeamResource = {
  id: string
  name: string
  flagCode: string
  group: string
  fifaRank: number
  elo: number
  accent: string
}

export const teamResources: TeamResource[] = [
  { id: 'france', name: '法国', flagCode: 'fr', group: 'D 组', fifaRank: 2, elo: 2104, accent: '#2563eb' },
  { id: 'brazil', name: '巴西', flagCode: 'br', group: 'E 组', fifaRank: 5, elo: 2087, accent: '#16a34a' },
  { id: 'england', name: '英格兰', flagCode: 'gb-eng', group: 'B 组', fifaRank: 4, elo: 2059, accent: '#dc2626' },
  { id: 'spain', name: '西班牙', flagCode: 'es', group: 'C 组', fifaRank: 8, elo: 2028, accent: '#ef4444' },
  { id: 'argentina', name: '阿根廷', flagCode: 'ar', group: 'F 组', fifaRank: 1, elo: 2112, accent: '#38bdf8' },
  { id: 'usa', name: '美国', flagCode: 'us', group: 'A 组', fifaRank: 11, elo: 1868, accent: '#2563eb' },
  { id: 'paraguay', name: '巴拉圭', flagCode: 'py', group: 'A 组', fifaRank: 53, elo: 1736, accent: '#dc2626' },
  { id: 'morocco', name: '摩洛哥', flagCode: 'ma', group: 'E 组', fifaRank: 12, elo: 1847, accent: '#16a34a' },
  { id: 'switzerland', name: '瑞士', flagCode: 'ch', group: 'H 组', fifaRank: 19, elo: 1816, accent: '#dc2626' },
  { id: 'korea', name: '韩国', flagCode: 'kr', group: 'A 组', fifaRank: 23, elo: 1795, accent: '#2563eb' },
  { id: 'mexico', name: '墨西哥', flagCode: 'mx', group: 'A 组', fifaRank: 14, elo: 1827, accent: '#16a34a' },
  { id: 'czech', name: '捷克', flagCode: 'cz', group: 'A 组', fifaRank: 36, elo: 1764, accent: '#2563eb' },
  { id: 'south-africa', name: '南非', flagCode: 'za', group: 'A 组', fifaRank: 58, elo: 1698, accent: '#16a34a' },
  { id: 'qatar', name: '卡塔尔', flagCode: 'qa', group: 'H 组', fifaRank: 34, elo: 1742, accent: '#7f1d1d' },
  { id: 'norway', name: '挪威', flagCode: 'no', group: 'D 组', fifaRank: 42, elo: 1778, accent: '#dc2626' },
  { id: 'senegal', name: '塞内加尔', flagCode: 'sn', group: 'G 组', fifaRank: 17, elo: 1819, accent: '#16a34a' }
]

const profile = (
  resource: TeamResource,
  summary: string,
  probabilities: TeamProfile['probabilities'],
  ratings: TeamProfile['ratings'],
  form: TeamProfile['form'],
  players: TeamProfile['players'],
  risks: TeamProfile['risks']
): TeamProfile => ({
  id: resource.id,
  name: resource.name,
  subtitle: `FIFA 排名 ${resource.fifaRank} · Elo ${resource.elo} · ${resource.group}`,
  updatedAt: '数据更新于 18:00',
  summary,
  probabilities,
  ratings,
  form,
  players,
  risks
})

export const teamProfilesById: Record<string, TeamProfile> = {
  france: profile(
    teamResources[0],
    '法国阵容深度和进攻创造力领先，冠军概率保持第一档。主要变量是后防伤停与淘汰赛潜在路径。',
    [
      { label: '冠军概率', value: '15.8%', delta: '+1.2%' },
      { label: '四强概率', value: '42.6%' },
      { label: '小组第一', value: '71.4%' }
    ],
    [
      { label: '进攻', value: 8.7 },
      { label: '防守', value: 7.8 },
      { label: '阵容深度', value: 9.1 },
      { label: '稳定性', value: 8.3 }
    ],
    { headline: '近 10 场 7 胜 2 平 1 负 · 进 21 球', stats: ['对 Top30：3胜 1平 1负', '零封率：40%', '场均进球：2.1'] },
    [
      { name: '姆巴佩', role: '前锋', form: 9.2 },
      { name: '格列兹曼', role: '中场', form: 8.5 },
      { name: '迈尼昂', role: '门将', form: 8.1 }
    ],
    [
      { label: '主力中卫伤停', value: -2.4 },
      { label: '淘汰赛路径偏难', value: -1.1 }
    ]
  ),
  brazil: profile(
    teamResources[1],
    '巴西前场个人能力仍是主要优势，近期压迫质量回升。风险在于中后场转换保护和关键球员健康。',
    [
      { label: '冠军概率', value: '13.6%', delta: '+0.8%' },
      { label: '四强概率', value: '39.4%' },
      { label: '小组第一', value: '68.2%' }
    ],
    [
      { label: '进攻', value: 8.9 },
      { label: '防守', value: 7.6 },
      { label: '阵容深度', value: 8.8 },
      { label: '稳定性', value: 7.9 }
    ],
    { headline: '近 10 场 6 胜 2 平 2 负 · 进 19 球', stats: ['对 Top30：3胜 1平 2负', '场均射门：14.8', '反抢成功率：31%'] },
    [
      { name: '维尼修斯', role: '边锋', form: 9.0 },
      { name: '罗德里戈', role: '前锋', form: 8.4 },
      { name: '阿利松', role: '门将', form: 8.2 }
    ],
    [
      { label: '后腰保护波动', value: -1.8 },
      { label: '核心前锋健康', value: -1.4 }
    ]
  ),
  england: profile(
    teamResources[2],
    '英格兰中前场厚度很强，定位球和转换进攻稳定。主要不确定性来自淘汰赛路径和边后卫防守覆盖。',
    [
      { label: '冠军概率', value: '12.9%', delta: '-0.3%' },
      { label: '四强概率', value: '37.9%' },
      { label: '小组第一', value: '66.8%' }
    ],
    [
      { label: '进攻', value: 8.5 },
      { label: '防守', value: 7.9 },
      { label: '阵容深度', value: 8.7 },
      { label: '稳定性', value: 8.0 }
    ],
    { headline: '近 10 场 6 胜 3 平 1 负 · 进 18 球', stats: ['定位球进球：4', '场均失球：0.8', '领先保持率：78%'] },
    [
      { name: '凯恩', role: '前锋', form: 8.8 },
      { name: '贝林厄姆', role: '中场', form: 9.0 },
      { name: '福登', role: '前场', form: 8.3 }
    ],
    [
      { label: '强强对话效率', value: -1.5 },
      { label: '边路回防压力', value: -1.0 }
    ]
  ),
  spain: profile(
    teamResources[3],
    '西班牙控球质量和高位逼抢稳定，能持续压低对手机会。短板是禁区终结效率和替补前锋变化。',
    [
      { label: '冠军概率', value: '11.4%', delta: '+0.4%' },
      { label: '四强概率', value: '35.2%' },
      { label: '小组第一', value: '64.0%' }
    ],
    [
      { label: '进攻', value: 8.1 },
      { label: '防守', value: 8.3 },
      { label: '阵容深度', value: 8.0 },
      { label: '稳定性', value: 8.6 }
    ],
    { headline: '近 10 场 7 胜 1 平 2 负 · 进 20 球', stats: ['控球率：63%', '高位夺回：9.4次', '零封率：50%'] },
    [
      { name: '罗德里', role: '中场', form: 9.1 },
      { name: '佩德里', role: '中场', form: 8.2 },
      { name: '亚马尔', role: '边锋', form: 8.4 }
    ],
    [
      { label: '终结效率波动', value: -1.6 },
      { label: '年轻球员稳定性', value: -0.9 }
    ]
  ),
  argentina: profile(
    teamResources[4],
    '阿根廷大赛经验和中场控制力仍然突出，比赛管理能力强。年龄结构和高强度连续作战是主要风险。',
    [
      { label: '冠军概率', value: '10.7%', delta: '-0.6%' },
      { label: '四强概率', value: '32.8%' },
      { label: '小组第一', value: '62.5%' }
    ],
    [
      { label: '进攻', value: 8.2 },
      { label: '防守', value: 8.1 },
      { label: '阵容深度', value: 7.9 },
      { label: '稳定性', value: 8.7 }
    ],
    { headline: '近 10 场 8 胜 1 平 1 负 · 进 17 球', stats: ['领先保持率：84%', '场均失球：0.6', '点球效率：86%'] },
    [
      { name: '梅西', role: '前场', form: 8.5 },
      { name: '劳塔罗', role: '前锋', form: 8.3 },
      { name: '马丁内斯', role: '门将', form: 8.4 }
    ],
    [
      { label: '年龄结构偏高', value: -1.7 },
      { label: '连续高强度赛程', value: -1.2 }
    ]
  ),
  usa: profile(
    teamResources[5],
    '美国受益于主场环境和体能优势，压迫强度可观。能否把控球转化为高质量机会，是出线概率上限的关键。',
    [
      { label: '冠军概率', value: '2.8%', delta: '+0.4%' },
      { label: '四强概率', value: '12.6%' },
      { label: '小组第一', value: '44.0%' }
    ],
    [
      { label: '进攻', value: 7.4 },
      { label: '防守', value: 7.2 },
      { label: '阵容深度', value: 7.5 },
      { label: '稳定性', value: 7.0 }
    ],
    { headline: '近 10 场 5 胜 2 平 3 负 · 进 16 球', stats: ['主场胜率：62%', '场均冲刺：高', '定位球威胁：中高'] },
    [
      { name: '普利西奇', role: '边锋', form: 8.4 },
      { name: '麦肯尼', role: '中场', form: 7.8 },
      { name: '雷纳', role: '前场', form: 7.6 }
    ],
    [
      { label: '阵地战效率', value: -1.4 },
      { label: '后防经验', value: -0.8 }
    ]
  ),
  morocco: profile(
    teamResources[7],
    '摩洛哥防守组织和身体对抗稳定，适合淘汰赛低比分场景。进攻端转换效率决定黑马成色。',
    [
      { label: '冠军概率', value: '3.4%', delta: '+0.7%' },
      { label: '四强概率', value: '18.4%' },
      { label: '小组第一', value: '49.6%' }
    ],
    [
      { label: '进攻', value: 7.2 },
      { label: '防守', value: 8.4 },
      { label: '阵容深度', value: 7.4 },
      { label: '稳定性', value: 8.1 }
    ],
    { headline: '近 10 场 5 胜 4 平 1 负 · 失 7 球', stats: ['零封率：50%', '反击进球：5', '对抗成功率：54%'] },
    [
      { name: '阿什拉夫', role: '边后卫', form: 8.6 },
      { name: '齐耶赫', role: '边锋', form: 7.9 },
      { name: '阿姆拉巴特', role: '中场', form: 8.0 }
    ],
    [
      { label: '阵地进攻办法', value: -1.3 },
      { label: '替补火力', value: -0.9 }
    ]
  )
}

const teamIdByName = teamResources.reduce<Record<string, string>>((acc, team) => {
  acc[team.name] = team.id
  return acc
}, {})

export function getTeamIdByName(name: string) {
  return teamIdByName[name] || 'france'
}

export function getFlagCodeByTeamName(name: string) {
  return teamResources.find(team => team.name === name)?.flagCode
}

export function getTeamProfileById(teamId = 'france') {
  return teamProfilesById[teamId] || teamProfilesById.france
}
