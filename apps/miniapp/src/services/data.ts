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
import { getTeamDisplayName, getTeamProfileById } from '@/services/teamResources'

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

type ApiGroupSummary = {
  id: string
  name: string
  matches_finished?: number
  matches_total?: number
  summary?: string
}

type ApiTeamProfile = {
  team: ApiTeam
  summary: string
  group?: {
    id?: string
    name?: string
    rank?: number
    record?: string
    points?: number
    goals?: string
    rank_1_prob?: number | null
    qualify_prob?: number | null
    expected_points?: number | null
  } | null
  probabilities: Array<{ label: string; value?: number | null; delta?: number | null; source?: string }>
  ratings: Array<{ label: string; value: number; source?: string }>
  form: {
    headline: string
    stats: Array<string | { label: string; value?: string | number | null }>
    recent?: {
      matches?: number
      wins?: number | null
      draws?: number | null
      losses?: number | null
      goals_for?: number | null
      goals_against?: number | null
    }
    evidence?: Array<{ label: string; value: string; note?: string; tone?: 'positive' | 'negative' | 'neutral'; source?: string }>
  }
  key_players: Array<{
    id?: string
    source_player_id?: string | null
    name: string
    name_en?: string | null
    role?: string
    position?: string
    form?: number
    club?: string | null
    market_value_eur?: number | null
    profile_url?: string | null
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
  coach?: {
    name?: string
    name_en?: string | null
    record?: string
    win_rate?: number | null
    quality_status?: string | null
    source_confidence?: number | null
  } | null
  related_matches?: Array<ApiMatch & {
    opponent_team?: ApiTeam
    prediction_summary?: {
      tendency?: string
      home_win_prob?: number
      draw_prob?: number
      away_win_prob?: number
      confidence?: string
    } | null
  }>
  news?: Array<{
    id: string
    source: string
    source_label?: string | null
    trust_level?: string | null
    source_url?: string | null
    title: string
    summary?: string | null
    language?: string | null
    published_at?: string | null
    fetched_at?: string | null
    relevance?: string | null
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
  id: string
  title: string
  subtitle: string
  summary: string
  teams: GroupTeam[]
  updatedAt: string
  matchesFinished?: number
  matchesTotal?: number
}

export type GroupSummary = {
  id: string
  name: string
  matchesFinished: number
  matchesTotal: number
  summary?: string
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
const homeDataCache = new Map<string, Promise<HomeData>>()
const rankingDataCache = new Map<string, Promise<RankingData>>()
const teamProfileCache = new Map<string, Promise<TeamProfile>>()

function cachedRequest<T>(cache: Map<string, Promise<T>>, key: string, factory: () => Promise<T>) {
  const existing = cache.get(key)
  if (existing) return existing

  const request = factory().catch(error => {
    cache.delete(key)
    throw error
  })
  cache.set(key, request)
  return request
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

function formatNewsTime(iso?: string | null) {
  if (!iso) return '时间待同步'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '时间待同步'
  const month = date.getMonth() + 1
  const day = date.getDate()
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${month}月${day}日 ${hour}:${minute}`
}

function formatNewsSource(source?: string | null) {
  const sourceMap: Record<string, string> = {
    dongqiudi: '懂球帝',
    bbc: 'BBC',
    guardian: 'The Guardian',
    espn: 'ESPN',
    foxsports: 'FOX Sports',
    fifa: 'FIFA'
  }
  return source ? sourceMap[source] || source : '新闻源'
}

function formatTrustLevel(value?: string | null) {
  const trustMap: Record<string, string> = {
    public_news: '公开新闻',
    public_source: '公开数据',
    public_api: '公开接口',
    official: '官方来源',
    manual_verified: '人工核验',
    internal_derived: 'AI 抽取'
  }
  return value ? trustMap[value] || value : undefined
}

function formatNewsText(value?: string | null, maxLength = 120) {
  if (!value) return undefined
  const textValue = value
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!textValue) return undefined
  return textValue.length > maxLength ? `${textValue.slice(0, maxLength)}...` : textValue
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

function formatStageLabel(value?: string | null) {
  if (!value) return '世界杯赛程'
  const normalized = value.toLowerCase()
  if (normalized.includes('dongqiudi') || normalized.includes('schedule context')) {
    return '世界杯赛程'
  }
  return value
}

function formatGroupName(id?: string, rawName?: string | null) {
  const groupLetter = id?.match(/group-([a-z])/i)?.[1]?.toUpperCase()
  if (groupLetter) return `${groupLetter}组`
  if (!rawName || /[�ÃÂäåæçèéà]/.test(rawName)) return '小组'
  return rawName
}

function groupSortValue(id: string) {
  const letter = id.match(/group-([a-z])/i)?.[1]?.toLowerCase()
  return letter ? letter.charCodeAt(0) - 97 : 99
}

function displayTeam(team: ApiTeam) {
  return getTeamDisplayName(team.name, team.name_en, team.id)
}

function formatPredictionVersion(hasPrediction: boolean, status: string) {
  if (hasPrediction) return '最终赛前版'
  if (status === 'live') return '滚动更新'
  if (status === 'finished') return '赛后复盘'
  return '赛程已同步'
}

function formatTendency(value: string | undefined, home: string, away: string) {
  if (!value) return '预测待重算'
  const key = value.toLowerCase()
  const tendencyMap: Record<string, string> = {
    home: `${home}占优`,
    away: `${away}占优`,
    draw: '平局倾向',
    low: '低信心',
    medium: '中等信心',
    high: '高信心'
  }
  if (tendencyMap[key]) return tendencyMap[key]
  if (value.includes('来源可信')) return '赛程可信'
  return value
}

function formatEvidenceLabel(value: string) {
  const labelMap: Record<string, string> = {
    elo_diff: '整体强度',
    fifa_rank_diff: 'FIFA排名',
    venue: '场地因素',
    model_mode: '模型校准',
    home_advantage: '主场因素',
    player_form: '球员状态',
    team_form: '近期状态',
    market_value: '身价深度',
    roster_value: '阵容身价',
    lineup_stability: '阵容稳定',
    coach_record: '教练战绩',
    historical_matchups: '历史交锋'
  }
  return labelMap[value] || value
}

function formatEvidenceNote(item: { label: string; note?: string }) {
  if (item.note && !/^[a-z0-9_ ./:+-]+$/i.test(item.note)) return item.note
  const noteMap: Record<string, string> = {
    elo_diff: '基于双方 Elo 评分差异',
    fifa_rank_diff: '基于 FIFA 世界排名差异',
    venue: '结合比赛场地与中立场信息',
    model_mode: '双层模型赛前校准结果',
    home_advantage: '结合主客场与场地影响',
    player_form: '来自近期球员进球、助攻与出场状态',
    team_form: '来自国家队近期战绩快照',
    market_value: '来自球员身价与阵容深度',
    roster_value: '来自球员身价与阵容深度',
    lineup_stability: '来自阵容稳定性与出勤记录',
    coach_record: '来自主教练带队战绩',
    historical_matchups: '来自双方历史交锋'
  }
  return noteMap[item.label] || item.note || '来自赛前特征快照'
}

function mapEvidenceItem(item: { label: string; value?: number; note?: string }) {
  return {
    label: formatEvidenceLabel(item.label),
    value: item.value || 0,
    note: formatEvidenceNote(item)
  }
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
  return '场地待同步'
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

function formatTeamSubtitle(team: ApiTeam, groupName: string) {
  const values = [
    team.fifa_rank ? `FIFA排名 ${team.fifa_rank}` : undefined,
    team.elo_rating ? `Elo ${Math.round(team.elo_rating)}` : undefined,
    groupName
  ].filter(Boolean)
  return values.length ? values.join(' · ') : '球队数据待同步'
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

function formatPlayerRole(value?: string | null) {
  const normalized = (value || '').trim().toUpperCase()
  const roleMap: Record<string, string> = {
    GK: '门将',
    GOALKEEPER: '门将',
    DF: '后卫',
    DEFENDER: '后卫',
    CB: '中卫',
    LB: '左后卫',
    RB: '右后卫',
    MF: '中场',
    MIDFIELDER: '中场',
    DM: '后腰',
    CM: '中场',
    AM: '前腰',
    FW: '前锋',
    FORWARD: '前锋',
    ST: '中锋',
    LW: '左边锋',
    RW: '右边锋',
    F: '前锋',
    M: '中场',
    D: '后卫'
  }
  return roleMap[normalized] || value || '-'
}

function formatProbabilityLabel(value: string) {
  const labelMap: Record<string, string> = {
    冠军概率: '模型冠军概率',
    四强概率: '模型四强概率',
    小组第一: '小组第一概率'
  }
  return labelMap[value] || value
}

function formatProfileStat(stat: string | { label: string; value?: string | number | null }) {
  if (typeof stat === 'string') {
    return stat
  }
  return `${stat.label}: ${stat.value ?? '-'}`
}

function formatOptionalNumber(value?: number | null, digits = 1) {
  if (value === undefined || value === null) return undefined
  return Number(value).toFixed(digits)
}

function formatCoachWinRate(value?: number | null) {
  if (value === undefined || value === null) return undefined
  return value > 1 ? `${value.toFixed(1)}%` : `${(value * 100).toFixed(1)}%`
}

function normalizePlayerScore(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return 0
  return Math.max(0, Math.min(10, Number(value)))
}

function formatRelatedMatch(match: ApiMatch & { opponent_team?: ApiTeam }) {
  const opponent = match.opponent_team
    ? displayTeam(match.opponent_team)
    : `${match.home_team ? displayTeam(match.home_team) : '主队'} vs ${match.away_team ? displayTeam(match.away_team) : '客队'}`
  return {
    id: match.id,
    opponent: opponent || match.away_team?.name || match.home_team?.name || '对手待同步',
    stage: match.stage || '赛程阶段待同步',
    time: formatKickoff(match.kickoff_at),
    venue: formatVenue(match),
    status: formatStatus(match.status, match.home_score, match.away_score),
    tendency: match.prediction_summary?.confidence ? formatConfidence(match.prediction_summary.confidence) : undefined
  }
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
  const homeName = displayTeam(apiMatch.home_team)
  const awayName = displayTeam(apiMatch.away_team)
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
  const evidence = prediction?.key_factors?.map(mapEvidenceItem) || report?.evidence?.map(mapEvidenceItem) || []

  return {
    id: apiMatch.id,
    home: homeName,
    away: awayName,
    time: formatKickoff(apiMatch.kickoff_at),
    stage: formatStageLabel(apiMatch.stage || featuredMatch.stage),
    venue: formatVenue(apiMatch),
    status: formatStatus(apiMatch.status, apiMatch.home_score, apiMatch.away_score),
    versionLabel: formatPredictionVersion(hasPrediction, apiMatch.status),
    score,
    confidence: hasPrediction ? report?.confidence_label || formatConfidence(prediction?.confidence || embeddedPrediction?.confidence) : '预测待重算',
    tendency: formatTendency(embeddedPrediction?.tendency || (hasPrediction ? 'high' : undefined), homeName, awayName),
    source: formatSourceConfidence(sourceConfidence),
    sourceConfidence: sourceConfidence === undefined ? undefined : percentFromApi(sourceConfidence),
    modelStatus,
    expectedGoals,
    insight: report?.content || apiMatch.ai_summary || (hasPrediction ? `${homeName} vs ${awayName} 已基于历史赛果小模型和上下文特征校准生成预测。` : `${homeName} vs ${awayName} 已从真实赛程源同步，预测、比分分布和 AI 证据等待后续任务生成。`),
    dataPoints: [
      { label: '赛程状态', value: `${formatStatus(apiMatch.status, apiMatch.home_score, apiMatch.away_score)} · ${formatSourceConfidence(sourceConfidence)}` },
      { label: homeName, value: formatTeamMeta(apiMatch.home_team) },
      { label: awayName, value: formatTeamMeta(apiMatch.away_team) },
      expectedGoals ? { label: '模型输出', value: expectedGoals } : { label: '模型输出', value: modelStatus }
    ],
    probabilities: hasPrediction && homeWin !== undefined && draw !== undefined && awayWin !== undefined ? [
      { label: `${homeName}胜`, value: percentFromApi(homeWin) },
      { label: '平', value: percentFromApi(draw) },
      { label: `${awayName}胜`, value: percentFromApi(awayWin) }
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

async function loadHomeData(): Promise<HomeData> {
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
    upcomingMatches: response.data.upcoming_matches.map(match => {
      const homeName = displayTeam(match.home_team)
      const awayName = displayTeam(match.away_team)
      return {
        id: match.id,
        home: homeName,
        away: awayName,
        time: formatKickoff(match.kickoff_at),
        status: formatStatus(match.status, match.home_score, match.away_score),
        tendency: formatTendency(match.prediction_summary?.tendency || match.prediction?.tendency, homeName, awayName),
        meta: formatStageLabel(match.stage)
      }
    }),
    championTop: response.data.champion_rankings.map(item => ({
      teamId: item.team.id,
      name: displayTeam(item.team),
      probability: percentFromApi(item.probability),
      meta: formatTeamMeta(item.team)
    })),
    updatedAt: formatUpdatedAt(response.meta?.updated_at),
    dataSourceStatus: status
  }
}

export async function getHomeData(): Promise<HomeData> {
  return cachedRequest(homeDataCache, 'home', loadHomeData)
}

export async function getMatchData(matchId = defaultMatchId): Promise<{ match: Match; updatedAt: string }> {
  if (!shouldUseApi()) {
    return {
      match: featuredMatch,
      updatedAt: '更新时间待同步'
    }
  }

  let resolvedMatchId = matchId
  if (!resolvedMatchId) {
    const homeResponse = await requestData<{ featured_match: ApiMatch }>('/api/v1/home')
    resolvedMatchId = homeResponse.data.featured_match.id
  }

  const [matchResponse, predictionResponse, reportResponse] = await Promise.all([
    requestData<ApiMatch>(`/api/v1/matches/${resolvedMatchId}`),
    optionalRequestData<ApiPrediction>(`/api/v1/matches/${resolvedMatchId}/prediction`),
    optionalRequestData<ApiReport>(`/api/v1/matches/${resolvedMatchId}/ai-report`)
  ])

  return {
    match: mapMatch(matchResponse.data, predictionResponse?.data, reportResponse?.data),
    updatedAt: formatUpdatedAt(predictionResponse?.meta?.updated_at || matchResponse.meta?.updated_at)
  }
}

async function loadRankingData(type: 'champion' | 'semifinal' | 'darkhorse'): Promise<RankingData> {
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
      name: displayTeam(item.team),
      probability: percentFromApi(item.probability),
      delta: percentFromApi(item.delta || 0),
      reason: mapReason(item.reason),
      meta: formatTeamMeta(item.team)
    })),
    updatedAt: formatUpdatedAt(response.meta?.updated_at),
    source: `基于模型快照 · ${response.meta?.count ?? response.data.length}队`
  }
}

export async function getRankingData(type: 'champion' | 'semifinal' | 'darkhorse'): Promise<RankingData> {
  return cachedRequest(rankingDataCache, type, () => loadRankingData(type))
}

export async function getGroupList(): Promise<GroupSummary[]> {
  if (!shouldUseApi()) {
    return []
  }

  const response = await requestData<ApiGroupSummary[]>('/api/v1/groups')
  return response.data
    .map(item => ({
      id: item.id,
      name: formatGroupName(item.id, item.name),
      matchesFinished: item.matches_finished || 0,
      matchesTotal: item.matches_total || 6,
      summary: item.summary
    }))
    .sort((a, b) => groupSortValue(a.id) - groupSortValue(b.id))
}

async function resolveTeamId(teamId = '') {
  if (teamId) {
    return teamId
  }

  const response = await requestData<ApiTeam[]>('/api/v1/teams')
  return response.data[0]?.id || ''
}

async function loadTeamProfile(teamId = ''): Promise<TeamProfile> {
  if (!shouldUseApi()) {
    return getTeamProfileById(teamId)
  }

  const resolvedTeamId = await resolveTeamId(teamId)
  if (!resolvedTeamId) {
    return getTeamProfileById(teamId)
  }

  const response = await requestData<ApiTeamProfile>(`/api/v1/teams/${resolvedTeamId}/profile`)
  const group = response.data.group
  const teamName = displayTeam(response.data.team)
  const groupName = group?.name ? formatGroupName(group.id, group.name) : response.data.team.confederation || '小组待同步'
  const dataChips = [
    group?.rank ? `分组排名: ${groupName} 第${group.rank}` : response.data.team.confederation ? `所属赛区: ${response.data.team.confederation}` : undefined,
    `阵容身价: ${formatMarketValue(response.data.team.market_value_eur).replace(/^身价\s*/, '')}`,
    `数据质量: ${formatQuality(response.data.team.quality_status)}`
  ].filter(Boolean) as string[]
  return {
    id: response.data.team.id,
    name: teamName,
    subtitle: formatTeamSubtitle(response.data.team, groupName),
    updatedAt: formatUpdatedAt(response.meta?.updated_at),
    summary: response.data.summary,
    group: group ? {
      name: groupName,
      rank: group.rank,
      record: group.record,
      points: group.points,
      goals: group.goals,
      groupWinnerProbability: formatOptionalPercent(group.rank_1_prob),
      qualifyProbability: formatOptionalPercent(group.qualify_prob),
      expectedPoints: formatOptionalNumber(group.expected_points, 1)
    } : undefined,
    probabilities: response.data.probabilities.map(item => ({
      label: formatProbabilityLabel(item.label),
      value: formatOptionalPercent(item.value),
      delta: item.delta === undefined || item.delta === null ? undefined : `${item.delta >= 0 ? '+' : '-'}${Math.abs(percentFromApi(item.delta))}%`
    })),
    ratings: response.data.ratings.map(item => ({
      label: item.label,
      value: item.value
    })),
    form: {
      headline: response.data.form.headline,
      stats: response.data.form.stats.map(formatProfileStat),
      recent: response.data.form.recent ? {
        matches: response.data.form.recent.matches || 0,
        wins: response.data.form.recent.wins,
        draws: response.data.form.recent.draws,
        losses: response.data.form.recent.losses,
        goalsFor: response.data.form.recent.goals_for,
        goalsAgainst: response.data.form.recent.goals_against
      } : undefined,
      evidence: response.data.form.evidence?.map(item => ({
        label: item.label,
        value: item.value,
        note: item.source,
        tone: item.tone
      })) || []
    },
    dataChips,
    players: response.data.key_players.map(player => ({
      name: player.name,
      role: formatPlayerRole(player.role || player.position),
      form: normalizePlayerScore(player.form || player.recent_form?.form_score || player.recent_form?.rating),
      meta: [
        player.club || undefined,
        player.recent_form?.matches ? `近${player.recent_form.matches}场 ${player.recent_form.goals || 0}球 ${player.recent_form.assists || 0}助` : undefined,
        formatAvailability(player.recent_form?.availability)
      ].filter(Boolean).join(' · ')
    })),
    coach: response.data.coach?.name ? {
      name: response.data.coach.name,
      record: response.data.coach.record,
      winRate: formatCoachWinRate(response.data.coach.win_rate),
      meta: [
        response.data.coach.name_en || undefined,
        formatQuality(response.data.coach.quality_status),
        response.data.coach.source_confidence ? formatSourceConfidence(response.data.coach.source_confidence) : undefined
      ].filter(Boolean).join(' · ')
    } : undefined,
    relatedMatches: (response.data.related_matches || []).map(formatRelatedMatch),
    news: (response.data.news || []).map(item => ({
      title: formatNewsText(item.title, 80) || item.title,
      summary: formatNewsText(item.summary),
      source: [
        formatNewsSource(item.source),
        formatNewsTime(item.published_at || item.fetched_at),
        item.relevance === 'latest' ? '最新新闻' : '球队相关'
      ].filter(Boolean).join(' · '),
      sourceUrl: item.source_url || undefined,
      relevance: formatTrustLevel(item.trust_level)
    })),
    risks: response.data.risks
  }
}

export async function getTeamProfile(teamId = ''): Promise<TeamProfile> {
  return cachedRequest(teamProfileCache, teamId || '__default__', () => loadTeamProfile(teamId))
}

export async function getGroupData(groupId = 'group-a'): Promise<GroupData> {
  if (!shouldUseApi()) {
    return {
      id: groupId,
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
  const qualificationByName = new Map((simulationResponse?.data.teams || []).map(item => [displayTeam(item.team), percentFromApi(item.qualify_prob)]))
  const played = detailResponse.data.standings.reduce((total, item) => {
    const values = item.record.match(/\d+/g)?.map(Number) || []
    return total + values.reduce((sum, value) => sum + value, 0)
  }, 0)
  const finished = Math.floor(played / 2)
  const groupName = formatGroupName(detailResponse.data.id, detailResponse.data.name)
  const sortedStandings = [...detailResponse.data.standings].sort((a, b) => {
    if (a.rank !== b.rank) return a.rank - b.rank
    if (b.points !== a.points) return b.points - a.points
    return displayTeam(a.team).localeCompare(displayTeam(b.team))
  })

  return {
    id: detailResponse.data.id,
    title: `${groupName}形势`,
    subtitle: `小组赛 · 已完成 ${finished}/6 场`,
    summary: simulationResponse ? '积分榜与出线模拟已同步，第三名路径取决于末轮净胜球和交叉区排名。' : '真实积分榜已同步，出线模拟等待后续模型重算。',
    teams: sortedStandings.map(item => {
      const teamName = displayTeam(item.team)
      return {
      teamId: item.team.id,
      rank: item.rank,
      name: teamName,
      record: item.record,
      points: item.points,
      goals: item.goals,
      qualification: qualificationByTeam.get(item.team.id) || qualificationByName.get(teamName) || 0
      }
    }),
    updatedAt: formatUpdatedAt(detailResponse.meta?.updated_at),
    matchesFinished: finished,
    matchesTotal: 6
  }
}
