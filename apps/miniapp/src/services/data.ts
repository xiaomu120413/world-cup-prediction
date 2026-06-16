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
    count?: number
  }
}

type ApiTeam = {
  id: string
  code?: string
  name: string
  abbr?: string
  name_en?: string
  confederation?: string | null
  fifa_rank?: number
  elo_rating?: number | null
  market_value_eur?: number | null
  quality_status?: string | null
}

type ApiMatch = {
  id: string
  stage?: string
  kickoff_at: string
  venue?: {
    name?: string
    city?: string
    country?: string
    timezone?: string
  }
  home_team: ApiTeam
  away_team: ApiTeam
  status: string
  home_score?: number | null
  away_score?: number | null
  neutral_site?: boolean
  source_confidence?: number
  prediction?: {
    home_win_prob: number
    draw_prob: number
    away_win_prob: number
    confidence?: string
    tendency?: string
  }
  prediction_summary?: {
    home_win_prob: number
    draw_prob: number
    away_win_prob: number
    confidence?: string
    tendency?: string
  } | null
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
  confidence?: string
  key_factors?: Array<{ label: string; value: number; note: string }>
  scorelines?: Array<{ score?: string; home_goals?: number; away_goals?: number; probability: number }>
  generated_at?: string
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
  probabilities: Array<{ label: string; value?: number | null; delta?: number | null; source?: string }>
  ratings: Array<{ label: string; value: number; source?: string }>
  form: {
    headline: string
    stats: Array<string | { label: string; value?: string | number | null }>
  }
  key_players: Array<{
    name: string
    role?: string
    position?: string
    form?: number
    club?: string | null
    market_value_eur?: number | null
    quality_status?: string | null
    recent_form?: {
      matches?: number | null
      goals?: number
      assists?: number
      rating?: number | null
      form_score?: number | null
      availability?: string | null
      as_of_at?: string | null
    }
  }>
  risks: Array<{ label: string; value: number }>
  data_sources?: Record<string, string>
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
  primary_source?: string
  table_counts: Record<string, number>
  real_data_audit?: {
    status?: string
    no_sample_data?: boolean
    all_canonical_data_has_source?: boolean
    unapproved_source_links?: number
  }
  latest_collector_runs: Array<{ source: string; job_type: string; status: string; records_written?: number }>
}

export type LoadState = 'idle' | 'loading' | 'ready' | 'error'

export type DataSourceStatus = {
  label: string
  detail: string
  isDatabase: boolean
  audit: string
  counts: string
  freshness: string
}

export type HomeData = {
  featuredMatch: Match
  upcomingMatches: Array<(typeof upcomingMatches)[number] & { status?: string; meta?: string }>
  championTop: Array<(typeof championTop)[number] & { teamId?: string; meta?: string }>
  updatedAt: string
  dataSourceStatus: DataSourceStatus
}

export type RankingData = {
  rankings: RankingTeam[]
  updatedAt: string
  source: string
}

export type GroupData = {
  title: string
  subtitle: string
  summary: string
  teams: GroupTeam[]
  updatedAt: string
}

const apiBaseUrl = __API_BASE_URL__.replace(/\/$/, '')
const defaultMatchId = ''
const mockDataSourceStatus: DataSourceStatus = {
  label: '离线',
  detail: '未连接后端',
  isDatabase: false,
  audit: '真实数据未同步',
  counts: '无本地比赛数据',
  freshness: '离线'
}

function shouldUseApi() {
  return Boolean(apiBaseUrl)
}

function percent(value: number) {
  return Number((value * 100).toFixed(1))
}

function percentFromApi(value?: number | null) {
  if (value === undefined || value === null) return 0
  return value > 1 ? Number(value.toFixed(1)) : percent(value)
}

function formatPercentText(value?: number | null) {
  return value === undefined || value === null ? '-' : `${percentFromApi(value)}%`
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
    return '更新时间待同步'
  }
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return '更新时间待同步'
  }
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `更新于 ${hour}:${minute}`
}

function formatConfidence(value?: string) {
  if (!value) {
    return '模型待生成'
  }
  const confidenceMap: Record<string, string> = {
    low: '低信心',
    medium: '中等信心',
    high: '高信心'
  }
  return confidenceMap[value] || value
}

function formatOptionalPercent(value?: number | null) {
  return formatPercentText(value)
}

function formatStatus(status: string, homeScore?: number | null, awayScore?: number | null) {
  const statusMap: Record<string, string> = {
    scheduled: '赛程已同步',
    live: '进行中',
    finished: '已完赛',
    postponed: '延期',
    cancelled: '取消'
  }
  if (
    (status === 'live' || status === 'finished')
    && homeScore !== undefined
    && homeScore !== null
    && awayScore !== undefined
    && awayScore !== null
  ) {
    return statusMap[status] || status
  }
  return statusMap[status] || status
}

function formatScore(homeScore?: number | null, awayScore?: number | null) {
  if (homeScore === undefined || homeScore === null || awayScore === undefined || awayScore === null) {
    return undefined
  }
  return `${homeScore}-${awayScore}`
}

function formatVenue(match: ApiMatch) {
  if (match.venue?.name) return match.venue.name
  if (match.venue?.city) return match.venue.country ? `${match.venue.city}, ${match.venue.country}` : match.venue.city
  return match.neutral_site ? '中立场地待定' : '场地待同步'
}

function formatSourceConfidence(value?: number) {
  return value === undefined ? '来源可信度待同步' : `来源可信 ${percentFromApi(value)}%`
}

function formatMarketValue(value?: number | null) {
  if (value === undefined || value === null) return '身价待同步'
  if (value >= 100000000) return `身价 €${(value / 100000000).toFixed(1)}亿`
  if (value >= 10000) return `身价 €${Math.round(value / 10000)}万`
  return `身价 €${value}`
}

function formatTeamMeta(team: ApiTeam) {
  const values = [
    team.fifa_rank ? `FIFA ${team.fifa_rank}` : undefined,
    team.elo_rating ? `Elo ${Math.round(team.elo_rating)}` : undefined,
    team.confederation || undefined
  ].filter(Boolean)
  return values.length ? values.join(' · ') : '淘汰赛席位待定'
}

function mapReason(value?: string) {
  const reasonMap: Record<string, string> = {
    baseline_strength: '模型强度',
    tournament_path_strength: '赛程路径强度',
    darkhorse_upside: '黑马上限',
    model_update: '模型更新',
    player_form: '球员状态',
    schedule_path: '赛程路径'
  }
  return value ? reasonMap[value] || value : '模型输出'
}

function formatQuality(value?: string | null) {
  const qualityMap: Record<string, string> = {
    source: '真实源',
    derived: '派生',
    manual_verified: '人工核验',
    mock: '测试样本'
  }
  return value ? qualityMap[value] || value : '质量待标注'
}

function formatAvailability(value?: string | null) {
  const availabilityMap: Record<string, string> = {
    available: '可出场',
    doubtful: '出战存疑',
    injured: '伤停',
    suspended: '停赛'
  }
  return value ? availabilityMap[value] || value : '状态待同步'
}

function formatProfileStat(stat: string | { label: string; value?: string | number | null }) {
  if (typeof stat === 'string') {
    return stat
  }
  return `${stat.label}: ${stat.value ?? '-'}`
}

function mapDataStatus(status: ApiDataStatus): DataSourceStatus {
  const latestRun = status.latest_collector_runs[0]
  const primarySource = status.primary_source || latestRun?.source || status.backend
  const auditPassed = status.real_data_audit?.status === 'pass'
  const teamsCount = status.table_counts.dongqiudi_roster_teams || status.table_counts.teams || 0
  const matchesCount = status.table_counts.dongqiudi_matches || status.table_counts.matches || 0
  return {
    label: status.mode === 'database' ? (auditPassed ? 'DB · 已核验' : 'DB · 待核验') : '后端离线模式',
    detail: primarySource === 'dongqiudi' ? 'dongqiudi/homepage' : latestRun ? `${latestRun.source}/${latestRun.job_type}` : status.backend,
    isDatabase: status.mode === 'database' && status.canonical_ready,
    audit: status.mode === 'database' ? (auditPassed ? '真实数据审计通过' : '数据审计需关注') : '后端未接真实库',
    counts: `${teamsCount}队 / ${matchesCount}场`,
    freshness: latestRun ? `${latestRun.source}/${latestRun.job_type} · ${latestRun.status}` : status.backend
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

async function optionalRequestData<T>(path: string): Promise<Envelope<T> | undefined> {
  try {
    return await requestData<T>(path)
  } catch {
    return undefined
  }
}

function mapMatch(apiMatch: ApiMatch, prediction?: ApiPrediction, report?: ApiReport): Match {
  const embeddedPrediction = apiMatch.prediction || apiMatch.prediction_summary || undefined
  const probabilities = prediction?.probabilities
  const hasPrediction = Boolean(probabilities || embeddedPrediction)
  const homeWin = probabilities?.home_win ?? embeddedPrediction?.home_win_prob
  const draw = probabilities?.draw ?? embeddedPrediction?.draw_prob
  const awayWin = probabilities?.away_win ?? embeddedPrediction?.away_win_prob
  const scorelines = prediction?.scorelines?.map(item => ({
    score: item.score || `${item.home_goals ?? '-'}-${item.away_goals ?? '-'}`,
    probability: item.probability > 1 ? item.probability : percent(item.probability)
  })) || []
  const score = formatScore(apiMatch.home_score, apiMatch.away_score)
  const expectedGoals = prediction?.expected_goals
    ? `预期进球 ${prediction.expected_goals.home.toFixed(2)}-${prediction.expected_goals.away.toFixed(2)}`
    : undefined
  const sourceConfidence = apiMatch.source_confidence
  const modelStatus = hasPrediction ? '模型预测已生成' : '预测待重算'
  const evidence = prediction?.key_factors || report?.evidence?.map(item => ({
    label: item.label,
    value: item.value || 0,
    note: item.note || '来自 AI 情报'
  })) || []

  return {
    id: apiMatch.id,
    home: apiMatch.home_team.name,
    away: apiMatch.away_team.name,
    time: formatKickoff(apiMatch.kickoff_at),
    stage: apiMatch.stage || featuredMatch.stage,
    venue: formatVenue(apiMatch),
    status: formatStatus(apiMatch.status, apiMatch.home_score, apiMatch.away_score),
    score,
    confidence: hasPrediction ? report?.confidence_label || formatConfidence(prediction?.confidence || embeddedPrediction?.confidence) : '预测待重算',
    tendency: embeddedPrediction?.tendency || (hasPrediction ? '模型已重算' : '真实赛程已同步'),
    source: formatSourceConfidence(sourceConfidence),
    sourceConfidence: sourceConfidence === undefined ? undefined : percentFromApi(sourceConfidence),
    modelStatus,
    expectedGoals,
    insight: report?.content || apiMatch.ai_summary || (hasPrediction ? `${apiMatch.home_team.name} vs ${apiMatch.away_team.name} 已基于历史赛果小模型和上下文特征校准生成预测。` : `${apiMatch.home_team.name} vs ${apiMatch.away_team.name} 已从真实赛程源同步，预测、比分分布和 AI 证据等待后续任务生成。`),
    dataPoints: [
      { label: '赛程状态', value: `${formatStatus(apiMatch.status, apiMatch.home_score, apiMatch.away_score)} · ${formatSourceConfidence(sourceConfidence)}` },
      { label: apiMatch.home_team.name, value: formatTeamMeta(apiMatch.home_team) },
      { label: apiMatch.away_team.name, value: formatTeamMeta(apiMatch.away_team) },
      expectedGoals ? { label: '模型输出', value: expectedGoals } : { label: '模型输出', value: modelStatus }
    ],
    probabilities: hasPrediction && homeWin !== undefined && draw !== undefined && awayWin !== undefined ? [
      { label: `${apiMatch.home_team.name}胜`, value: percentFromApi(homeWin) },
      { label: '平', value: percentFromApi(draw) },
      { label: `${apiMatch.away_team.name}胜`, value: percentFromApi(awayWin) }
    ] : [],
    scorelines,
    evidence
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
      updatedAt: '更新时间待同步'
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
      status: formatStatus(match.status, match.home_score, match.away_score),
      tendency: match.prediction_summary?.tendency || match.prediction?.tendency || (match.source_confidence ? formatSourceConfidence(match.source_confidence) : '预测待重算'),
      meta: match.stage
    })),
    championTop: response.data.champion_rankings.map(item => ({
      teamId: item.team.id,
      name: item.team.name,
      probability: percentFromApi(item.probability),
      meta: formatTeamMeta(item.team)
    })),
    updatedAt: formatUpdatedAt(response.meta?.updated_at),
    dataSourceStatus: status
  }
}

export async function getMatchData(matchId = defaultMatchId): Promise<{ match: Match; updatedAt: string }> {
  if (!shouldUseApi() || !matchId) {
    return {
      match: featuredMatch,
      updatedAt: '更新时间待同步'
    }
  }

  const [matchResponse, predictionResponse, reportResponse] = await Promise.all([
    requestData<ApiMatch>(`/api/v1/matches/${matchId}`),
    optionalRequestData<ApiPrediction>(`/api/v1/matches/${matchId}/prediction`),
    optionalRequestData<ApiReport>(`/api/v1/matches/${matchId}/ai-report`)
  ])

  return {
    match: mapMatch(matchResponse.data, predictionResponse?.data, reportResponse?.data),
    updatedAt: formatUpdatedAt(predictionResponse?.meta?.updated_at || matchResponse.meta?.updated_at)
  }
}

export async function getRankingData(type: 'champion' | 'semifinal' | 'darkhorse'): Promise<RankingData> {
  if (!shouldUseApi()) {
    const rankings = type === 'semifinal' ? semiFinalRankings : type === 'darkhorse' ? darkHorseRankings : championRankings
    return {
      rankings,
      updatedAt: '更新时间待同步',
      source: '等待后端真实预测'
    }
  }

  const response = await requestData<ApiRanking[]>(`/api/v1/predictions/rankings?type=${type}`)
  return {
    rankings: response.data.map((item, index) => ({
      teamId: item.team.id,
      rank: index + 1,
      name: item.team.name,
      probability: percentFromApi(item.probability),
      delta: percentFromApi(item.delta || 0),
      reason: mapReason(item.reason),
      meta: formatTeamMeta(item.team)
    })),
    updatedAt: formatUpdatedAt(response.meta?.updated_at),
    source: `ranking_predictions · ${response.meta?.count ?? response.data.length}条`
  }
}

export async function getTeamProfile(teamId = ''): Promise<TeamProfile> {
  if (!shouldUseApi() || !teamId) {
    return getTeamProfileById(teamId)
  }

  const response = await requestData<ApiTeamProfile>(`/api/v1/teams/${teamId}/profile`)
  const dataChips = [
    response.data.team.confederation || undefined,
    formatMarketValue(response.data.team.market_value_eur),
    formatQuality(response.data.team.quality_status)
  ].filter(Boolean) as string[]
  return {
    id: response.data.team.id,
    name: response.data.team.name,
    subtitle: `FIFA 排名 ${response.data.team.fifa_rank || '-'} · Elo ${response.data.team.elo_rating ? Math.round(response.data.team.elo_rating) : '-'}`,
    updatedAt: formatUpdatedAt(response.meta?.updated_at),
    summary: response.data.summary,
    probabilities: response.data.probabilities.map(item => ({
      label: item.label,
      value: formatOptionalPercent(item.value),
      delta: item.delta === undefined || item.delta === null ? undefined : `${item.delta >= 0 ? '+' : '-'}${Math.abs(percentFromApi(item.delta))}%`
    })),
    ratings: response.data.ratings.map(item => ({
      label: item.source ? `${item.label} · ${item.source}` : item.label,
      value: item.value
    })),
    form: {
      headline: response.data.form.headline,
      stats: response.data.form.stats.map(formatProfileStat)
    },
    dataChips,
    players: response.data.key_players.map(player => ({
      name: player.name,
      role: player.role || player.position || '-',
      form: player.form || player.recent_form?.form_score || player.recent_form?.rating || 0,
      meta: [
        player.club || undefined,
        player.recent_form?.matches ? `近${player.recent_form.matches}场 ${player.recent_form.goals || 0}球 ${player.recent_form.assists || 0}助` : undefined,
        formatAvailability(player.recent_form?.availability)
      ].filter(Boolean).join(' · ')
    })),
    risks: response.data.risks
  }
}

export async function getGroupData(groupId = 'group-a'): Promise<GroupData> {
  if (!shouldUseApi()) {
    return {
      title: '小组形势',
      subtitle: '真实积分榜待同步',
      summary: '连接后端后展示真实积分榜和出线模拟；当前仅显示小组数据待同步空态。',
      teams: groupATeams,
      updatedAt: '更新时间待同步'
    }
  }

  const [detailResponse, simulationResponse] = await Promise.all([
    requestData<ApiGroupDetail>(`/api/v1/groups/${groupId}`),
    optionalRequestData<ApiGroupSimulation>(`/api/v1/groups/${groupId}/simulation`)
  ])
  const qualificationByTeam = new Map((simulationResponse?.data.teams || []).map(item => [item.team.id, percentFromApi(item.qualify_prob)]))
  const qualificationByName = new Map((simulationResponse?.data.teams || []).map(item => [item.team.name, percentFromApi(item.qualify_prob)]))
  const played = detailResponse.data.standings.reduce((total, item) => {
    const values = item.record.match(/\d+/g)?.map(Number) || []
    return total + values.reduce((sum, value) => sum + value, 0)
  }, 0)
  const finished = Math.floor(played / 2)

  return {
    title: `${detailResponse.data.name}形势`,
    subtitle: `小组赛 · 已完成 ${finished}/6 场`,
    summary: simulationResponse ? '积分榜与出线模拟已同步，第三名路径取决于末轮净胜球和交叉区排名。' : '真实积分榜已同步，出线模拟等待后续模型重算。',
    teams: detailResponse.data.standings.map(item => ({
      teamId: item.team.id,
      rank: item.rank,
      name: item.team.name,
      record: item.record,
      points: item.points,
      goals: item.goals,
      qualification: qualificationByTeam.get(item.team.id) || qualificationByName.get(item.team.name) || 0
    })),
    updatedAt: formatUpdatedAt(detailResponse.meta?.updated_at)
  }
}
