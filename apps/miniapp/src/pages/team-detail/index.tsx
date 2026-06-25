import { useEffect, useMemo, useState } from 'react'
import { Image, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon, type IconName } from '@/components/Icon'
import { RatingRow } from '@/components/RatingRow'
import { Section } from '@/components/Section'
import { getTeamList, getTeamProfile, type LoadState, type TeamListItem } from '@/services/data'
import type { TeamProfile } from '@/services/types'
import { goTo, routes } from '@/utils/navigation'

type TeamSource = 'home' | 'predictions' | 'groups' | 'direct'

type RouteContext = {
  source: TeamSource
  rankingType?: string
  groupId?: string
}

function formatPlayerScore(value: number) {
  return value > 0 ? value.toFixed(1) : '-'
}

function playerScoreWidth(value: number) {
  return `${Math.max(0, Math.min(10, value)) * 10}%`
}

function getRouteTeamId() {
  const params = Taro.getCurrentInstance().router?.params
  const value = params?.teamId
  return typeof value === 'string' && value ? value : undefined
}

function getRouteContext(): RouteContext {
  const params = Taro.getCurrentInstance().router?.params
  const source = params?.source
  return {
    source: source === 'home' || source === 'predictions' || source === 'groups' ? source : 'direct',
    rankingType: typeof params?.rankingType === 'string' ? params.rankingType : undefined,
    groupId: typeof params?.groupId === 'string' ? params.groupId : undefined
  }
}

function sourceTarget(context: RouteContext) {
  if (context.source === 'predictions') return routes.predictions
  if (context.source === 'groups') return `${routes.groups}?groupId=${context.groupId || 'group-a'}`
  return routes.matches
}

function evidenceValueClass(tone?: string) {
  if (tone === 'negative') return 'team-evidence-row__value text-negative'
  if (tone === 'positive') return 'team-evidence-row__value text-positive'
  return 'team-evidence-row__value'
}

function deltaValue(delta?: string) {
  if (!delta) return 0
  return Number(delta.replace('%', ''))
}

function deltaClass(delta?: string) {
  return deltaValue(delta) < 0 ? 'delta delta--down' : 'delta delta--up'
}

function deltaLabel(delta?: string) {
  const value = deltaValue(delta)
  if (!value) return ''
  return `${value > 0 ? '▲' : '▼'}${Math.abs(value)}%`
}

function goTeam(teamId: string, source = 'direct') {
  goTo(`${routes.teamDetail}?teamId=${teamId}&source=${source}`)
}

function PlayerAvatar({ player }: { player: TeamProfile['players'][number] }) {
  const [imageFailed, setImageFailed] = useState(false)
  const roleIcon = player.roleIcon || 'stability'

  if (player.avatarUrl && !imageFailed) {
    return (
      <View className='avatar avatar--local'>
        <Image
          className='avatar__image'
          src={player.avatarUrl}
          mode='aspectFill'
          onError={() => setImageFailed(true)}
        />
      </View>
    )
  }

  return (
    <View className='avatar avatar--local'>
      <Icon name={roleIcon} color='#2563eb' size={34} />
    </View>
  )
}

function PlayerDataChips({ player }: { player: TeamProfile['players'][number] }) {
  const chips = (player.dataPoints || []).slice(0, 4)
  if (!chips.length) return null

  return (
    <View className='player-data-points'>
      {chips.map(item => (
        <View className='player-data-chip' key={`${item.icon}-${item.label}`}>
          <Icon name={item.icon as IconName} color='#2563eb' size={20} />
          <Text>{item.value}</Text>
        </View>
      ))}
    </View>
  )
}

function TeamListRow({ team, index }: { team: TeamListItem; index: number }) {
  return (
    <View className='team-index-row' onClick={() => goTeam(team.id)}>
      <Text className='team-index-row__rank'>{String(index + 1).padStart(2, '0')}</Text>
      <Flag team={team.name} teamId={team.id} teamCode={team.code} teamEn={team.nameEn} size='sm' />
      <View className='team-index-row__main'>
        <Text className='team-index-row__name'>{team.name}</Text>
        <Text className='team-index-row__meta'>{team.nameEn || team.meta}</Text>
      </View>
      <View className='team-index-row__right'>
        {team.probability !== undefined ? <Text>{team.probability}%</Text> : <Text>待更新</Text>}
        <Icon name='chevron' color='#94a3b8' size={26} />
      </View>
    </View>
  )
}

function TeamsIndexPage() {
  const [teams, setTeams] = useState<TeamListItem[]>([])
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getTeamList()
      .then(data => {
        if (!mounted) return
        setTeams(data)
        setLoadState('ready')
      })
      .catch(() => {
        if (!mounted) return
        setTeams([])
        setLoadState('error')
      })

    return () => {
      mounted = false
    }
  }, [])

  const featuredTeams = useMemo(
    () => teams
      .filter(team => team.probability !== undefined)
      .sort((a, b) => (b.probability || 0) - (a.probability || 0) || a.name.localeCompare(b.name))
      .slice(0, 3),
    [teams]
  )

  const rankedTeams = useMemo(
    () => [...teams].sort((a, b) => (b.probability ?? -1) - (a.probability ?? -1) || a.name.localeCompare(b.name)),
    [teams]
  )

  return (
    <View className='page page--team-index design-page'>
      <View className='team-index-header'>
        <View>
          <Text className='app-title'>球队</Text>
          <Text className='page-head__subtitle'>球队数据 · 点击进入分析</Text>
        </View>
        <View className='team-index-header__icon'>
          <Icon name='shield' color='#2563eb' size={42} />
        </View>
      </View>

      <View className='team-index-ai-card'>
        <View className='team-index-ai-card__icon'>
          <Icon name='ai' color='#2563eb' size={44} />
        </View>
        <View className='team-index-ai-card__main'>
          <Text className='team-index-ai-card__title'>AI 球队索引</Text>
          <Text className='team-index-ai-card__text'>基于最新数据快照展示球队概率和关键资料，点击球队进入完整分析。</Text>
        </View>
      </View>

      <Section title='冠军热门' action='预测榜' onAction={() => goTo(routes.predictions)}>
        {featuredTeams.length ? featuredTeams.map((team, index) => (
          <View className='team-feature-row' key={team.id} onClick={() => goTeam(team.id, 'predictions')}>
            <Text className={`rank-medal rank-medal--${index + 1}`}>{index + 1}</Text>
            <Flag team={team.name} teamId={team.id} teamCode={team.code} teamEn={team.nameEn} size='sm' />
            <View className='team-feature-row__main'>
              <Text className='team-feature-row__name'>{team.name}</Text>
              <Text className='team-feature-row__meta'>{team.nameEn || team.meta}</Text>
            </View>
            <Text className='team-feature-row__prob'>{team.probability}%</Text>
            <Icon name='chevron' color='#94a3b8' size={26} />
          </View>
        )) : <View className='empty-state'><Text>暂无冠军热门数据</Text></View>}
      </Section>

      <Section title='全部球队' action='已同步'>
        <View className='team-index-list'>
          {rankedTeams.length ? rankedTeams.map((team, index) => <TeamListRow key={team.id} team={team} index={index} />) : (
            <View className='empty-state'>
              <Text>{loadState === 'loading' ? '正在加载球队数据' : '暂无球队数据'}</Text>
            </View>
          )}
        </View>
      </Section>

      {loadState === 'error' ? <Text className='data-note'>数据连接异常，请稍后重试。</Text> : null}
      <BottomNav active='teams' />
    </View>
  )
}

export default function TeamDetailPage() {
  const [teamId] = useState<string | undefined>(getRouteTeamId)
  const [routeContext] = useState<RouteContext>(getRouteContext)
  const [team, setTeam] = useState<TeamProfile | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const isTeamListMode = !teamId && routeContext.source === 'direct'

  useEffect(() => {
    if (isTeamListMode) return
    let mounted = true
    setLoadState('loading')
    getTeamProfile(teamId)
      .then(data => {
        if (!mounted) return
        setTeam(data)
        setLoadState('ready')
      })
      .catch(() => {
        if (!mounted) return
        setTeam(null)
        setLoadState('error')
      })

    return () => {
      mounted = false
    }
  }, [isTeamListMode, teamId])

  const displayTeam = useMemo(() => team, [team])

  if (isTeamListMode) {
    return <TeamsIndexPage />
  }

  if (!displayTeam) {
    return (
      <View className='page page--team-report design-page'>
        <View className='team-report-topbar'>
          <View className='icon-button icon-button--plain' onClick={() => goTo(sourceTarget(routeContext))}>
            <Icon name='back' color='#0f172a' size={34} />
          </View>
          <View className='team-report-title'>
            <Text className='team-report-title__name'>球队数据</Text>
            <Text className='team-report-title__meta'>{loadState === 'loading' ? '正在加载球队数据' : '球队数据暂不可用'}</Text>
          </View>
        </View>
        <View className='empty-state'>
          <Text>{loadState === 'loading' ? '正在加载球队数据' : '球队数据暂不可用'}</Text>
        </View>
        <BottomNav active='teams' />
      </View>
    )
  }

  const recent = displayTeam.form.recent

  return (
    <View className='page page--team-report design-page'>
      <View className='team-report-topbar'>
        <View className='icon-button icon-button--plain' onClick={() => goTo(sourceTarget(routeContext))}>
          <Icon name='back' color='#0f172a' size={34} />
        </View>
        <View className='team-report-title'>
          <Text className='team-report-title__name'>{displayTeam.name}</Text>
          <Text className='team-report-title__meta'>{displayTeam.subtitle}</Text>
          <View className='team-report-title__updated'>
            <Icon name='clock' color='#64748b' size={26} />
            <Text>{displayTeam.updatedAt}</Text>
          </View>
        </View>
        <View className='icon-button icon-button--plain team-report-topbar__flag'>
          <Flag team={displayTeam.name} teamId={displayTeam.id} teamCode={displayTeam.code} teamEn={displayTeam.nameEn} size='sm' />
        </View>
      </View>

      <View className='team-identity-layout'>
        <View className='team-identity-assets'>
          <Flag team={displayTeam.name} teamId={displayTeam.id} teamCode={displayTeam.code} teamEn={displayTeam.nameEn} size='lg' />
          <View className='team-crest-local'>
            <Icon name='shield' color='#2563eb' size={58} />
          </View>
        </View>
        <View className='team-ai-panel team-ai-panel--design'>
          <View className='team-ai-panel__head'>
            <Icon name='ai' color='#2563eb' size={40} />
            <Text>AI 球队判断</Text>
          </View>
          <Text className='team-ai-panel__text'>{displayTeam.summary}</Text>
        </View>
      </View>

      <View className='probability-mini-grid team-probability-strip'>
        {displayTeam.probabilities.length ? displayTeam.probabilities.map(item => (
          <View className='probability-mini' key={item.label}>
            <Text className='probability-mini__label'>{item.label}</Text>
            <Text className='probability-mini__value'>{item.value}</Text>
            {deltaLabel(item.delta) ? <Text className={deltaClass(item.delta)}>{deltaLabel(item.delta)}</Text> : null}
          </View>
        )) : <View className='empty-state'><Text>暂无概率数据</Text></View>}
      </View>

      <Section title='核心评分' action='满分 10 分'>
        {displayTeam.ratings.length ? displayTeam.ratings.map(item => (
          <RatingRow key={item.label} label={item.label} value={item.value} />
        )) : <View className='empty-state'><Text>暂无评分数据</Text></View>}
      </Section>

      <Section title='近期状态'>
        <View className='team-form-report'>
          <View className='team-form-summary'>
            <Text className='team-form-summary__label'>{recent ? `近${recent.matches}场` : '暂无近期记录'}</Text>
            <View className='team-form-summary__record'>
              <Text className='text-positive'>{recent?.wins ?? '-'}胜</Text>
              <Text>{recent?.draws ?? '-'}平</Text>
              <Text className='text-negative'>{recent?.losses ?? '-'}负</Text>
            </View>
            <Text className='team-form-summary__goals'>进{recent?.goalsFor ?? '-'} 失{recent?.goalsAgainst ?? '-'}</Text>
          </View>
          <View className='team-evidence-list'>
            {(displayTeam.form.evidence || []).length ? (displayTeam.form.evidence || []).map(item => (
              <View className='team-evidence-row' key={item.label}>
                <Text className='team-evidence-row__label'>{item.label}</Text>
                <Text className={evidenceValueClass(item.tone)}>{item.value}</Text>
              </View>
            )) : <View className='empty-state'><Text>暂无状态证据</Text></View>}
          </View>
        </View>
      </Section>

      <Section title='关键球员' action='状态评分'>
        <View className='player-list-head'>
          <Text>球员</Text>
          <Text>位置</Text>
          <Text>状态评分</Text>
        </View>
        {displayTeam.players.length ? displayTeam.players.map(player => (
          <View className='player-row player-row--design' key={player.name}>
            <PlayerAvatar player={player} />
            <View className='player-row__main'>
              <Text className='list-row__title'>{player.name}</Text>
              {player.meta ? <Text className='list-row__meta'>{player.meta}</Text> : null}
              <PlayerDataChips player={player} />
            </View>
            <Text className='player-row__position'>{player.role}</Text>
            <View className='player-score-box'>
              <Text className='player-score'>{formatPlayerScore(player.form)}</Text>
              <View className='player-score-track'>
                <View className='player-score-track__bar' style={{ width: playerScoreWidth(player.form) }} />
              </View>
            </View>
          </View>
        )) : <View className='empty-state'><Text>暂无关键球员数据</Text></View>}
      </Section>

      {displayTeam.risks.length ? (
        <View className='risk-card risk-card--design'>
          <View className='risk-card__icon'>
            <Icon name='shield' color='#dc2626' size={42} />
          </View>
          <View className='risk-card__main'>
            <Text className='risk-card__title'>风险提醒</Text>
            <Text className='risk-card__text'>{displayTeam.risks[0].label}</Text>
            <Text className='risk-card__meta'>来自最新风险信号。</Text>
          </View>
          <View className='risk-card__score'>
            <Text>{displayTeam.risks[0].value}</Text>
            <Text>影响评分</Text>
          </View>
          <Icon name='chevron' color='#94a3b8' size={30} />
        </View>
      ) : null}

      {loadState === 'error' ? <Text className='data-note'>数据连接异常，请稍后重试。</Text> : null}
      <BottomNav active='teams' />
    </View>
  )
}
