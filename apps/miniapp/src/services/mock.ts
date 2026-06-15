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
  probabilities: Array<{ label: string; value: string; delta?: string }>
  ratings: Array<{ label: string; value: number }>
  form: {
    headline: string
    stats: string[]
  }
  dataChips?: string[]
  players: Array<{ name: string; role: string; form: number; meta?: string }>
  risks: Array<{ label: string; value: number }>
}

export type UpcomingMatch = {
  id: string
  home: string
  away: string
  time: string
  tendency: string
}

export type ChampionTopTeam = {
  name: string
  probability: number
}

export const featuredMatch: Match = {
  id: 'pending-match',
  home: '主队待同步',
  away: '客队待同步',
  time: '赛程待同步',
  stage: '真实赛程待同步',
  venue: '场地待同步',
  status: '等待数据',
  confidence: '模型待生成',
  tendency: '等待真实赛程',
  insight: '连接后端后展示真实赛程、预测概率和 AI 证据；当前仅显示真实数据待同步空态。',
  modelStatus: '等待真实数据',
  dataPoints: [
    { label: '数据来源', value: '等待后端接口' }
  ],
  probabilities: [],
  scorelines: [],
  evidence: []
}

export const upcomingMatches: UpcomingMatch[] = []

export const championTop: ChampionTopTeam[] = []

export const groupATeams: GroupTeam[] = []

export const championRankings: RankingTeam[] = []

export const semiFinalRankings: RankingTeam[] = []

export const darkHorseRankings: RankingTeam[] = []

export const emptyTeamProfile: TeamProfile = {
  id: 'pending-team',
  name: '球队待同步',
  subtitle: '真实球队数据待同步',
  updatedAt: '更新时间待同步',
  summary: '连接后端后展示真实球队画像、概率、评分、球员状态和风险项；当前仅显示球队数据待同步空态。',
  probabilities: [],
  ratings: [],
  form: {
    headline: '近期状态待同步',
    stats: []
  },
  dataChips: ['真实数据待同步'],
  players: [],
  risks: []
}

export const franceProfile: TeamProfile = emptyTeamProfile
