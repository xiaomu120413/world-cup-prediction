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
  versionLabel?: string
  score?: string
  confidence: string
  insight: string
  tendency: string
  source?: string
  sourceConfidence?: number
  modelStatus?: string
  expectedGoals?: string
  dataPoints?: Array<{ label: string; value: string }>
  probabilities: Probability[]
  scorelines: Scoreline[]
  evidence: Evidence[]
}

export type GroupTeam = {
  teamId?: string
  rank: number
  name: string
  record: string
  points: number
  goals: string
  qualification: number
}

export type RankingTeam = {
  teamId?: string
  rank: number
  name: string
  probability: number
  delta: number
  reason: string
  meta?: string
}

export type TeamProfile = {
  id: string
  name: string
  subtitle: string
  updatedAt: string
  summary: string
  group?: {
    name: string
    rank?: number
    record?: string
    points?: number
    goals?: string
    groupWinnerProbability?: string
    qualifyProbability?: string
    expectedPoints?: string
  }
  probabilities: Array<{ label: string; value: string; delta?: string }>
  ratings: Array<{ label: string; value: number }>
  form: {
    headline: string
    stats: string[]
    recent?: {
      matches: number
      wins?: number | null
      draws?: number | null
      losses?: number | null
      goalsFor?: number | null
      goalsAgainst?: number | null
    }
    evidence?: Array<{ label: string; value: string; note?: string; tone?: 'positive' | 'negative' | 'neutral' }>
  }
  dataChips?: string[]
  players: Array<{
    name: string
    role: string
    form: number
    meta?: string
    dataPoints?: Array<{ icon: string; label: string; value: string }>
  }>
  coach?: { name: string; record?: string; winRate?: string; meta?: string }
  relatedMatches?: Array<{ id: string; opponent: string; stage: string; time: string; venue?: string; status: string; tendency?: string }>
  news: Array<{ title: string; source: string; summary?: string; sourceUrl?: string; relevance?: string }>
  risks: Array<{ label: string; value: number }>
}

export type UpcomingMatch = {
  id: string
  home: string
  away: string
  time: string
  tendency: string
  status?: string
  meta?: string
}

export type ChampionTopTeam = {
  teamId?: string
  name: string
  probability: number
  delta?: number
  meta?: string
}

export const featuredMatch: Match = {
  id: 'usa-paraguay',
  home: '美国',
  away: '巴拉圭',
  time: '6月13日 01:00',
  stage: '小组赛',
  venue: '洛杉矶',
  status: '最终赛前版',
  versionLabel: '最终赛前版',
  confidence: '中等信心',
  tendency: '美国略占优',
  source: '模型快照 · 公开赛程',
  sourceConfidence: 92,
  modelStatus: '模型预测已生成',
  expectedGoals: '预期进球 1.42-1.16',
  insight: '美国整体评分略高，但巴拉圭反击效率让平局和小比分概率上升。',
  dataPoints: [
    { label: '赛程状态', value: '最终赛前版 · 来源可信 92%' },
    { label: '美国', value: 'FIFA 16 · Elo 1792 · CONCACAF' },
    { label: '巴拉圭', value: 'FIFA 48 · Elo 1694 · CONMEBOL' },
    { label: '模型输出', value: '预期进球 1.42-1.16' }
  ],
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
    { label: '阵容稳定', value: 6, note: '主力框架连续比赛，磨合度较高' },
    { label: '近期进攻', value: 4, note: '近5场场均进球 1.6，进攻状态回升' },
    { label: '伤停影响', value: -2, note: '中场轮换受限，防守替补经验不足' },
    { label: '对强队战绩', value: -1, note: '近10场对强队仅1胜，抗压能力一般' }
  ]
}

export const upcomingMatches: UpcomingMatch[] = [
  { id: 'qatar-switzerland', home: '卡塔尔', away: '瑞士', time: '6月13日 19:00', tendency: '瑞士略优', meta: '小组赛' },
  { id: 'brazil-morocco', home: '巴西', away: '摩洛哥', time: '6月13日 22:00', tendency: '巴西占优', meta: '小组赛' },
  { id: 'france-norway', home: '法国', away: '挪威', time: '6月14日 01:00', tendency: '法国占优', meta: '小组赛' }
]

export const championTop: ChampionTopTeam[] = [
  { teamId: 'france', name: '法国', probability: 15.8, delta: 1.2, meta: '阵容深度' },
  { teamId: 'brazil', name: '巴西', probability: 13.6, delta: 0.8, meta: '进攻状态' },
  { teamId: 'england', name: '英格兰', probability: 12.9, delta: -0.3, meta: '路径难度' }
]

export const groupATeams: GroupTeam[] = [
  { teamId: 'mexico', rank: 1, name: '墨西哥', record: '1/0/0', points: 3, goals: '2/0', qualification: 98.5 },
  { teamId: 'south-korea', rank: 2, name: '韩国', record: '1/0/0', points: 3, goals: '2/1', qualification: 97.7 },
  { teamId: 'czech', rank: 3, name: '捷克', record: '0/0/1', points: 0, goals: '1/2', qualification: 51.2 },
  { teamId: 'south-africa', rank: 4, name: '南非', record: '0/0/1', points: 0, goals: '0/2', qualification: 22.4 }
]

export const championRankings: RankingTeam[] = [
  { teamId: 'france', rank: 1, name: '法国', probability: 15.8, delta: 1.2, reason: '阵容深度', meta: 'FIFA 2 · Elo 2104' },
  { teamId: 'brazil', rank: 2, name: '巴西', probability: 13.6, delta: 0.8, reason: '进攻状态', meta: 'FIFA 5 · Elo 2078' },
  { teamId: 'england', rank: 3, name: '英格兰', probability: 12.9, delta: -0.3, reason: '路径难度', meta: 'FIFA 4 · Elo 2046' },
  { teamId: 'spain', rank: 4, name: '西班牙', probability: 11.4, delta: 0.4, reason: '控球稳定', meta: 'FIFA 1 · Elo 2092' },
  { teamId: 'argentina', rank: 5, name: '阿根廷', probability: 10.7, delta: -0.6, reason: '防守稳定', meta: 'FIFA 3 · Elo 2082' }
]

export const semiFinalRankings: RankingTeam[] = [
  { teamId: 'france', rank: 1, name: '法国', probability: 42.6, delta: 1.1, reason: '阵容深度', meta: 'FIFA 2 · Elo 2104' },
  { teamId: 'brazil', rank: 2, name: '巴西', probability: 39.4, delta: 0.6, reason: '进攻状态', meta: 'FIFA 5 · Elo 2078' },
  { teamId: 'england', rank: 3, name: '英格兰', probability: 36.2, delta: -0.2, reason: '路径难度', meta: 'FIFA 4 · Elo 2046' },
  { teamId: 'spain', rank: 4, name: '西班牙', probability: 34.8, delta: 0.5, reason: '控球稳定', meta: 'FIFA 1 · Elo 2092' },
  { teamId: 'argentina', rank: 5, name: '阿根廷', probability: 32.6, delta: -0.4, reason: '防守稳定', meta: 'FIFA 3 · Elo 2082' }
]

export const darkHorseRankings: RankingTeam[] = [
  { teamId: 'morocco', rank: 1, name: '摩洛哥', probability: 18.4, delta: 1.6, reason: '反击效率', meta: '淘汰赛上限' },
  { teamId: 'usa', rank: 2, name: '美国', probability: 16.2, delta: 1.1, reason: '主场加成', meta: '出线路径改善' },
  { teamId: 'senegal', rank: 3, name: '塞内加尔', probability: 14.9, delta: 0.4, reason: '身体对抗', meta: '防守强度' },
  { teamId: 'japan', rank: 4, name: '日本', probability: 13.1, delta: -0.2, reason: '转换速度', meta: '小组难度' },
  { teamId: 'south-korea', rank: 5, name: '韩国', probability: 11.8, delta: 0.3, reason: '团队稳定', meta: '晋级机会' }
]

export const emptyTeamProfile: TeamProfile = {
  id: 'france',
  name: '法国',
  subtitle: 'FIFA排名 2 · Elo 2104 · A组',
  updatedAt: '数据更新于 18:00',
  summary: '法国阵容深度和进攻创造力领先，但后防伤停让淘汰赛稳定性略受影响。',
  group: {
    name: 'A组',
    rank: 1,
    record: '1/0/0',
    points: 3,
    goals: '2/0',
    groupWinnerProbability: '71.4%',
    qualifyProbability: '96.8%',
    expectedPoints: '6.4'
  },
  probabilities: [
    { label: '冠军概率', value: '15.8%', delta: '+1.2%' },
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
    headline: '近10场 7胜2平1负，进21失8',
    stats: ['对Top30 3胜1平1负', '零封率 40%', '场均进球 2.1'],
    recent: {
      matches: 10,
      wins: 7,
      draws: 2,
      losses: 1,
      goalsFor: 21,
      goalsAgainst: 8
    },
    evidence: [
      { label: '对Top30', value: '3胜 1平 1负', tone: 'positive' },
      { label: '零封率', value: '40%', tone: 'positive' },
      { label: '场均进球', value: '2.1', tone: 'positive' }
    ]
  },
  dataChips: ['FIFA排名: 2', 'Elo: 2104', '分组: A组'],
  players: [
    { name: '姆巴佩', role: '前锋', form: 9.2, meta: '巴黎圣日耳曼 · 可出场' },
    { name: '格列兹曼', role: '中场', form: 8.5, meta: '马德里竞技 · 可出场' },
    { name: '迈尼昂', role: '门将', form: 8.1, meta: 'AC米兰 · 可出场' }
  ],
  coach: { name: '德尚', record: '近10场 7胜2平1负', winRate: '70.0%', meta: '主教练' },
  relatedMatches: [
    { id: 'france-norway', opponent: '挪威', stage: '小组赛', time: '6月14日 01:00', venue: '洛杉矶', status: '赛前', tendency: '法国占优' }
  ],
  news: [],
  risks: [
    { label: '主力中卫伤停', value: -2.4 }
  ]
}

export const franceProfile: TeamProfile = emptyTeamProfile
