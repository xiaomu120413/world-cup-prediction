import Taro from '@tarojs/taro'

import {
  championRankings,
  championTop,
  darkHorseRankings,
  featuredMatch,
  groupATeams,
  semiFinalRankings,
  upcomingMatches,
  type GroupTeam,
  type Match,
  type RankingTeam,
  type TeamProfile
} from '@/services/mock'
import { getTeamProfileById } from '@/services/teamResources'

type Envelope<T> = {
  data: T
  meta?: {
    updated_at?: string
  }
}

type ApiTeam = {
  id: string
  name: string
  abbr?: string
  fifa_rank?: number
  elo_rating?: number
}

type ApiMatch = {
  id: string
  stage?: string
  kickoff_at: string
  venue?: {
    name?: string
    city?: string
  }
  home_team: ApiTeam
  away_team: ApiTeam
  status: string
  prediction?: {
    home_win_prob: number
    draw_prob: number
    away_win_prob: number
    confidence?: string
    tendency?: string
  }
  ai_summary?: string
}

type ApiPrediction = {
  probabilities: {
    home_win: number
    draw: number
    away_win: number
  }
  expected_goals?: {
    home: number
    away: number
  }
  confidence: string
  key_factors?: Array<{ label: string; value: number; note: string }>
  scorelines?: Array<{ score?: string; home_goals?: number; away_goals?: number; probability: number }>
}

type ApiReport = {
  confidence_label?: string
  content: string
  evidence?: Array<{ label: string; value?: number; note?: string }>
}

type ApiRanking = {
  rank: number
  team: ApiTeam
  probability: number
  delta?: number
  reason: string
}

type ApiTeamProfile = {
  team: ApiTeam
  summary: string
  probabilities: Array<{ label: string; value?: number | null; delta?: number | null }>
  ratings: Array<{ label: string; value: number }>
  form: {
    headline: string
    stats: Array<string | { label: string; value?: string | number | null }>
  }
  key_players: Array<{
    name: string
    role?: string
    position?: string
    form?: number
    recent_form?: {
      goals?: number
      assists?: number
      rating?: number | null
      form_score?: number | null
    }
  }>
  risks: Array<{ label: string; value: number }>
}

type ApiGroupDetail = {
  id: string
  name: string
  standings: Array<{
    rank: number
    team: ApiTeam
    record: string
    points: number
    goals: string
  }>
}

type ApiGroupSimulation = {
  teams: Array<{
    team: ApiTeam
    qualify_prob: number
  }>
}

type ApiDataStatus = {
  backend: string
  mode: 'mock' | 'database'
  canonical_ready: boolean
  player_form_ready: boolean
  table_counts: Record<string, number>
  latest_collector_runs: Array<{ source: string; job_type: string; status: string }>
}

export type LoadState = 'idle' | 'loading' | 'ready' | 'error'

export type DataSourceStatus = {
  label: string
  detail: string
  isDatabase: boolean
}

export type HomeData = {
  featuredMatch: Match
  upcomingMatches: typeof upcomingMatches
  championTop: typeof championTop
  updatedAt: string
  dataSourceStatus: DataSourceStatus
}

export type GroupData = {
  title: string
  subtitle: string
  summary: string
  teams: GroupTeam[]
  updatedAt: string
}

const apiBaseUrl = __API_BASE_URL__.replace(/\/$/, '')
const defaultMatchId = 'usa-paraguay-2026-06-13'
const mockDataSourceStatus: DataSourceStatus = {
  label: 'Mock',
  detail: 'Local fallback',
  isDatabase: false
}

function shouldUseApi() {
  return Boolean(apiBaseUrl)
}

function percent(value: number) {
  return Number((value * 100).toFixed(1))
}

function formatKickoff(iso: string) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return featuredMatch.time
  }
  const month = date.getMonth() + 1
  const day = date.getDate()
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${month}月${day}日 ${hour}:${minute}`
}

function formatUpdatedAt(iso?: string) {
  if (!iso) {
    return '更新于 18:00'
  }
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return '更新于 18:00'
  }
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `更新于 ${hour}:${minute}`
}

function formatConfidence(value?: string) {
  if (!value) {
    return featuredMatch.confidence
  }
  const confidenceMap: Record<string, string> = {
    low: '低信心',
    medium: '中等信心',
    high: '高信心'
  }
  return confidenceMap[value] || value
}

function formatOptionalPercent(value?: number | null) {
  return value === undefined || value === null ? '-' : `${percent(value)}%`
}

function formatProfileStat(stat: string | { label: string; value?: string | number | null }) {
  if (typeof stat === 'string') {
    return stat
  }
  return `${stat.label}: ${stat.value ?? '-'}`
}

function mapDataStatus(status: ApiDataStatus): DataSourceStatus {
  const latestRun = status.latest_collector_runs[0]
  return {
    label: status.mode === 'database' ? 'DB' : 'Mock',
    detail: latestRun ? `${latestRun.source}/${latestRun.job_type}` : status.backend,
    isDatabase: status.mode === 'database' && status.canonical_ready
  }
}

async function requestData<T>(path: string): Promise<Envelope<T>> {
  const response = await Taro.request<Envelope<T>>({
    url: `${apiBaseUrl}${path}`,
    method: 'GET',
    timeout: 8000
  })

  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new Error(`API request failed: ${response.statusCode}`)
  }

  return response.data
}

function mapMatch(apiMatch: ApiMatch, prediction?: ApiPrediction, report?: ApiReport): Match {
  const probabilities = prediction?.probabilities
  const homeWin = probabilities?.home_win ?? apiMatch.prediction?.home_win_prob ?? featuredMatch.probabilities[0].value / 100
  const draw = probabilities?.draw ?? apiMatch.prediction?.draw_prob ?? featuredMatch.probabilities[1].value / 100
  const awayWin = probabilities?.away_win ?? apiMatch.prediction?.away_win_prob ?? featuredMatch.probabilities[2].value / 100
  const scorelines = prediction?.scorelines?.map(item => ({
    score: item.score || `${item.home_goals}-${item.away_goals}`,
    probability: item.probability > 1 ? item.probability : percent(item.probability)
  })) || featuredMatch.scorelines

  return {
    id: apiMatch.id,
    home: apiMatch.home_team.name,
    away: apiMatch.away_team.name,
    time: formatKickoff(apiMatch.kickoff_at),
    stage: apiMatch.stage || featuredMatch.stage,
    venue: apiMatch.venue?.name || apiMatch.venue?.city || featuredMatch.venue,
    status: apiMatch.status === 'scheduled' ? '最终赛前版' : apiMatch.status,
    confidence: report?.confidence_label || formatConfidence(prediction?.confidence || apiMatch.prediction?.confidence),
    tendency: apiMatch.prediction?.tendency || featuredMatch.tendency,
    insight: report?.content || apiMatch.ai_summary || featuredMatch.insight,
    probabilities: [
      { label: `${apiMatch.home_team.name}胜`, value: percent(homeWin) },
      { label: '平', value: percent(draw) },
      { label: `${apiMatch.away_team.name}胜`, value: percent(awayWin) }
    ],
    scorelines,
    evidence: prediction?.key_factors || report?.evidence?.map(item => ({
      label: item.label,
      value: item.value || 0,
      note: item.note || '来自 AI 情报'
    })) || featuredMatch.evidence
  }
}

export async function getDataStatus(): Promise<DataSourceStatus> {
  if (!shouldUseApi()) {
    return mockDataSourceStatus
  }

  const response = await requestData<ApiDataStatus>('/api/v1/data-status')
  return mapDataStatus(response.data)
}

export async function getHomeData(): Promise<HomeData> {
  if (!shouldUseApi()) {
    return {
      featuredMatch,
      upcomingMatches,
      championTop,
      dataSourceStatus: mockDataSourceStatus,
      updatedAt: '更新于 18:00'
    }
  }

  const [response, status] = await Promise.all([
    requestData<{
      featured_match: ApiMatch
      upcoming_matches: ApiMatch[]
      champion_rankings: ApiRanking[]
    }>('/api/v1/home'),
    getDataStatus()
  ])

  return {
    featuredMatch: mapMatch(response.data.featured_match),
    upcomingMatches: response.data.upcoming_matches.map(match => ({
      id: match.id,
      home: match.home_team.name,
      away: match.away_team.name,
      time: formatKickoff(match.kickoff_at),
      tendency: match.prediction?.tendency || '待更新'
    })),
    championTop: response.data.champion_rankings.map(item => ({
      name: item.team.name,
      probability: percent(item.probability)
    })),
    updatedAt: formatUpdatedAt(response.meta?.updated_at),
    dataSourceStatus: status
  }
}

export async function getMatchData(matchId = defaultMatchId): Promise<{ match: Match; updatedAt: string }> {
  if (!shouldUseApi()) {
    return {
      match: featuredMatch,
      updatedAt: '更新于 18:00'
    }
  }

  const [matchResponse, predictionResponse, reportResponse] = await Promise.all([
    requestData<ApiMatch>(`/api/v1/matches/${matchId}`),
    requestData<ApiPrediction>(`/api/v1/matches/${matchId}/prediction`),
    requestData<ApiReport>(`/api/v1/matches/${matchId}/ai-report`)
  ])

  return {
    match: mapMatch(matchResponse.data, predictionResponse.data, reportResponse.data),
    updatedAt: formatUpdatedAt(predictionResponse.meta?.updated_at || matchResponse.meta?.updated_at)
  }
}

export async function getRankingData(type: 'champion' | 'semifinal' | 'darkhorse'): Promise<RankingTeam[]> {
  if (!shouldUseApi()) {
    if (type === 'semifinal') return semiFinalRankings
    if (type === 'darkhorse') return darkHorseRankings
    return championRankings
  }

  const response = await requestData<ApiRanking[]>(`/api/v1/predictions/rankings?type=${type}`)
  return response.data.map(item => ({
    rank: item.rank,
    name: item.team.name,
    probability: percent(item.probability),
    delta: percent(item.delta || 0),
    reason: item.reason
  }))
}

export async function getTeamProfile(teamId = 'france'): Promise<TeamProfile> {
  if (!shouldUseApi()) {
    return getTeamProfileById(teamId)
  }

  const response = await requestData<ApiTeamProfile>(`/api/v1/teams/${teamId}/profile`)
  return {
    id: response.data.team.id,
    name: response.data.team.name,
    subtitle: `FIFA 排名 ${response.data.team.fifa_rank || '-'} · Elo ${response.data.team.elo_rating || '-'}`,
    updatedAt: formatUpdatedAt(response.meta?.updated_at),
    summary: response.data.summary,
    probabilities: response.data.probabilities.map(item => ({
      label: item.label,
      value: formatOptionalPercent(item.value),
      delta: item.delta === undefined || item.delta === null ? undefined : `${item.delta >= 0 ? '+' : '-'}${Math.abs(percent(item.delta))}%`
    })),
    ratings: response.data.ratings,
    form: {
      headline: response.data.form.headline,
      stats: response.data.form.stats.map(formatProfileStat)
    },
    players: response.data.key_players.map(player => ({
      name: player.name,
      role: player.role || player.position || '-',
      form: player.form || player.recent_form?.form_score || player.recent_form?.rating || 0
    })),
    risks: response.data.risks
  }
}

export async function getGroupData(groupId = 'group-a'): Promise<GroupData> {
  if (!shouldUseApi()) {
    return {
      title: 'A组形势',
      subtitle: '小组赛 · 已完成 2/6 场',
      summary: '墨西哥和韩国出线优势明显，捷克仍保留第三名晋级机会。南非需要下一场拿分才能避免提前进入低概率区。',
      teams: groupATeams,
      updatedAt: '模拟更新于 18:00'
    }
  }

  const [detailResponse, simulationResponse] = await Promise.all([
    requestData<ApiGroupDetail>(`/api/v1/groups/${groupId}`),
    requestData<ApiGroupSimulation>(`/api/v1/groups/${groupId}/simulation`)
  ])
  const qualificationByTeam = new Map(
    simulationResponse.data.teams.map(item => [item.team.id, percent(item.qualify_prob)])
  )

  return {
    title: `${detailResponse.data.name}形势`,
    subtitle: `小组赛 · 已完成 ${detailResponse.data.standings.filter(item => item.points > 0).length}/6 场`,
    summary: '小组前两名优势扩大，但第三名路径仍取决于末轮净胜球和交叉区排名。',
    teams: detailResponse.data.standings.map(item => ({
      rank: item.rank,
      name: item.team.name,
      record: item.record,
      points: item.points,
      goals: item.goals,
      qualification: qualificationByTeam.get(item.team.id) || 0
    })),
    updatedAt: formatUpdatedAt(detailResponse.meta?.updated_at)
  }
}
