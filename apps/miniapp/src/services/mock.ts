export type Probability = {
  label: string
  value: number
}

export type Evidence = {
  label: string
  value: number
  note: string
}

export type Scoreline = {
  score: string
  probability: number
}

export type Match = {
  id: string
  home: string
  away: string
  time: string
  stage: string
  venue: string
  status: string
  confidence: string
  insight: string
  tendency: string
  probabilities: Probability[]
  scorelines: Scoreline[]
  evidence: Evidence[]
}

export type GroupTeam = {
  rank: number
  name: string
  record: string
  points: number
  goals: string
  qualification: number
}

export type RankingTeam = {
  rank: number
  name: string
  probability: number
  delta: number
  reason: string
}

export type TeamProfile = {
  id: string
  name: string
  subtitle: string
  updatedAt: string
  summary: string
  probabilities: Array<{ label: string; value: string; delta?: string }>
  ratings: Array<{ label: string; value: number }>
  form: {
    headline: string
    stats: string[]
  }
  players: Array<{ name: string; role: string; form: number }>
  risks: Array<{ label: string; value: number }>
}

export const featuredMatch: Match = {
  id: 'usa-paraguay',
  home: '美国',
  away: '巴拉圭',
  time: '6月13日 01:00',
  stage: '小组赛',
  venue: '洛杉矶',
  status: '最终赛前版',
  confidence: '中等信心',
  tendency: '美国略占优',
  insight: '美国整体评分略高，但巴拉圭反击效率让平局和小比分概率上升。',
  probabilities: [
    { label: '美国胜', value: 44 },
    { label: '平', value: 27 },
    { label: '巴拉圭胜', value: 29 }
  ],
  scorelines: [
    { score: '1-1', probability: 12 },
    { score: '2-1', probability: 10 },
    { score: '1-0', probability: 9 },
    { score: '0-0', probability: 8 }
  ],
  evidence: [
    { label: '阵容稳定', value: 6, note: '近 5 场首发重复率更高' },
    { label: '近期进攻', value: 4, note: '前场创造力略优' },
    { label: '伤停影响', value: -2, note: '边路轮换深度下降' },
    { label: '对强队战绩', value: -1, note: '硬仗表现仍需观察' }
  ]
}

export const upcomingMatches = [
  { id: 'qatar-switzerland', home: '卡塔尔', away: '瑞士', time: '19:00', tendency: '瑞士略优' },
  { id: 'brazil-morocco', home: '巴西', away: '摩洛哥', time: '22:00', tendency: '巴西占优' },
  { id: 'france-norway', home: '法国', away: '挪威', time: '01:00', tendency: '法国占优' }
]

export const championTop = [
  { name: '法国', probability: 15.8 },
  { name: '巴西', probability: 13.6 },
  { name: '英格兰', probability: 12.9 }
]

export const groupATeams: GroupTeam[] = [
  { rank: 1, name: '墨西哥', record: '1胜0平0负', points: 3, goals: '进2失0', qualification: 98.5 },
  { rank: 2, name: '韩国', record: '1胜0平0负', points: 3, goals: '进2失1', qualification: 97.7 },
  { rank: 3, name: '捷克', record: '0胜0平1负', points: 0, goals: '进1失2', qualification: 51.2 },
  { rank: 4, name: '南非', record: '0胜0平1负', points: 0, goals: '进0失2', qualification: 22.4 }
]

export const championRankings: RankingTeam[] = [
  { rank: 1, name: '法国', probability: 15.8, delta: 1.2, reason: '阵容深度' },
  { rank: 2, name: '巴西', probability: 13.6, delta: 0.8, reason: '进攻状态' },
  { rank: 3, name: '英格兰', probability: 12.9, delta: -0.3, reason: '路径难度' },
  { rank: 4, name: '西班牙', probability: 11.4, delta: 0.4, reason: '防守稳定' },
  { rank: 5, name: '阿根廷', probability: 10.7, delta: -0.6, reason: '伤停影响' }
]

export const semiFinalRankings: RankingTeam[] = [
  { rank: 1, name: '法国', probability: 42.6, delta: 2.3, reason: '阵容深度' },
  { rank: 2, name: '巴西', probability: 39.4, delta: 1.1, reason: '进攻状态' },
  { rank: 3, name: '英格兰', probability: 37.9, delta: -0.7, reason: '路径难度' },
  { rank: 4, name: '西班牙', probability: 35.2, delta: 1.0, reason: '控球稳定' },
  { rank: 5, name: '阿根廷', probability: 32.8, delta: -1.2, reason: '淘汰赛路径' }
]

export const darkHorseRankings: RankingTeam[] = [
  { rank: 1, name: '摩洛哥', probability: 18.4, delta: 3.6, reason: '防守韧性' },
  { rank: 2, name: '韩国', probability: 14.8, delta: 2.9, reason: '小组路径' },
  { rank: 3, name: '瑞士', probability: 13.2, delta: 1.8, reason: '阵容稳定' },
  { rank: 4, name: '美国', probability: 12.6, delta: 2.1, reason: '主场环境' },
  { rank: 5, name: '塞内加尔', probability: 11.7, delta: 0.9, reason: '身体对抗' }
]

export const franceProfile: TeamProfile = {
  id: 'france',
  name: '法国',
  subtitle: 'FIFA排名 2 · Elo 2104 · A组',
  updatedAt: '数据更新于 18:00',
  summary: '法国阵容深度和进攻创造力领先，但后防伤停让淘汰赛稳定性略受影响。',
  probabilities: [
    { label: '冠军概率', value: '15.8%', delta: '▲1.2%' },
    { label: '四强概率', value: '42.6%' },
    { label: '小组第一', value: '71.4%' }
  ],
  ratings: [
    { label: '进攻', value: 8.7 },
    { label: '防守', value: 7.8 },
    { label: '阵容深度', value: 9.1 },
    { label: '稳定性', value: 8.3 }
  ],
  form: {
    headline: '近10场 7胜2平1负 · 进21失8',
    stats: ['对Top30 3胜1平1负', '零封率 40%', '场均进球 2.1']
  },
  players: [
    { name: '姆巴佩', role: '前锋', form: 9.2 },
    { name: '格列兹曼', role: '中场', form: 8.5 },
    { name: '迈尼昂', role: '门将', form: 8.1 }
  ],
  risks: [
    { label: '主力中卫伤停', value: -2.4 },
    { label: '淘汰赛路径偏难', value: -1.1 }
  ]
}

