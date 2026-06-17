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
    roleIcon?: 'ball' | 'defense' | 'shield' | 'stability'
    form: number
    meta?: string
    avatarUrl?: string
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
