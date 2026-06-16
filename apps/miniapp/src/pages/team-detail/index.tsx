import { useEffect, useMemo, useState } from 'react'
import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { RatingRow } from '@/components/RatingRow'
import { Section } from '@/components/Section'
import { getTeamProfile, type LoadState } from '@/services/data'
import { championRankings, emptyTeamProfile, type TeamProfile } from '@/services/mock'
import {
  allTournamentTeams,
  getFallbackGroupSummaries,
  getTeamGroupLabel,
  type TournamentTeam
} from '@/services/tournamentStructure'
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

function shouldUseDesignTeam(team: TeamProfile) {
  return !team.probabilities.length || team.name.includes('待')
}

function evidenceValueClass(tone?: string) {
  if (tone === 'negative') return 'team-evidence-row__value text-negative'
  if (tone === 'positive') return 'team-evidence-row__value text-positive'
  return 'team-evidence-row__value'
}

function goTeam(teamId: string, source = 'direct') {
  goTo(`${routes.teamDetail}?teamId=${teamId}&source=${source}`)
}

function rankingProbability(teamId: string) {
  return championRankings.find(team => team.teamId === teamId)?.probability
}

function TeamListRow({ team, index }: { team: TournamentTeam; index: number }) {
  const probability = rankingProbability(team.id)
  return (
    <View className='team-index-row' onClick={() => goTeam(team.id)}>
      <Text className='team-index-row__rank'>{String(index + 1).padStart(2, '0')}</Text>
      <Flag team={team.name} size='sm' />
      <View className='team-index-row__main'>
        <Text className='team-index-row__name'>{team.name}</Text>
        <Text className='team-index-row__meta'>{team.nameEn} · {getTeamGroupLabel(team.id)}</Text>
      </View>
      <View className='team-index-row__right'>
        {probability ? <Text>{probability}%</Text> : <Text>{team.groupName}</Text>}
        <Icon name='chevron' color='#94a3b8' size={26} />
      </View>
    </View>
  )
}

function TeamsIndexPage() {
  const [activeGroupId, setActiveGroupId] = useState('all')
  const groupOptions = getFallbackGroupSummaries()
  const featuredTeams = championRankings
    .map(item => allTournamentTeams.find(team => team.id === item.teamId))
    .filter(Boolean) as TournamentTeam[]
  const visibleTeams = activeGroupId === 'all'
    ? allTournamentTeams
    : allTournamentTeams.filter(team => team.groupId === activeGroupId)

  return (
    <View className='page page--team-index design-page'>
      <View className='team-index-header'>
        <View>
          <Text className='app-title'>球队</Text>
          <Text className='page-head__subtitle'>48支球队画像 · 点击进入分析</Text>
        </View>
        <View className='team-index-header__icon'>
          <Icon name='team' color='#2563eb' size={42} />
        </View>
      </View>

      <View className='team-index-ai-card'>
        <View className='team-index-ai-card__icon'>
          <Icon name='ai' color='#2563eb' size={44} />
        </View>
        <View className='team-index-ai-card__main'>
          <Text className='team-index-ai-card__title'>AI 球队索引</Text>
          <Text className='team-index-ai-card__text'>从热门球队、全部小组进入单队画像，概率、评分、状态和关键球员保持同一套字段。</Text>
        </View>
      </View>

      <Section title='冠军热门' action='预测榜' onAction={() => goTo(routes.predictions)}>
        {featuredTeams.map((team, index) => (
          <View className='team-feature-row' key={team.id} onClick={() => goTeam(team.id, 'predictions')}>
            <Text className={`rank-medal rank-medal--${index + 1}`}>{index + 1}</Text>
            <Flag team={team.name} size='sm' />
            <View className='team-feature-row__main'>
              <Text className='team-feature-row__name'>{team.name}</Text>
              <Text className='team-feature-row__meta'>{team.nameEn} · {team.groupName}</Text>
            </View>
            <Text className='team-feature-row__prob'>{championRankings[index]?.probability}%</Text>
            <Icon name='chevron' color='#94a3b8' size={26} />
          </View>
        ))}
      </Section>

      <Section title='全部球队' action={activeGroupId === 'all' ? '全部小组' : '查看全部'} onAction={() => setActiveGroupId('all')}>
        <View className='team-group-filter'>
          <Text
            className={`team-group-filter__item ${activeGroupId === 'all' ? 'team-group-filter__item--active' : ''}`}
            onClick={() => setActiveGroupId('all')}
          >
            全部
          </Text>
          {groupOptions.map(group => (
            <Text
              key={group.id}
              className={`team-group-filter__item ${activeGroupId === group.id ? 'team-group-filter__item--active' : ''}`}
              onClick={() => setActiveGroupId(group.id)}
            >
              {group.name}
            </Text>
          ))}
        </View>
        <View className='team-index-list'>
          {visibleTeams.map((team, index) => <TeamListRow key={team.id} team={team} index={index} />)}
        </View>
      </Section>

      <BottomNav active='teams' />
    </View>
  )
}

export default function TeamDetailPage() {
  const [teamId] = useState<string | undefined>(getRouteTeamId)
  const [routeContext] = useState<RouteContext>(getRouteContext)
  const [team, setTeam] = useState<TeamProfile>(emptyTeamProfile)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const isTeamListMode = !teamId && routeContext.source === 'direct'

  useEffect(() => {
    if (isTeamListMode) return
    let mounted = true
    setLoadState('loading')
    getTeamProfile(teamId)
      .then(data => {
        if (!mounted) return
        setTeam(shouldUseDesignTeam(data) ? emptyTeamProfile : data)
        setLoadState('ready')
      })
      .catch(() => {
        if (!mounted) return
        setTeam(emptyTeamProfile)
        setLoadState('error')
      })

    return () => {
      mounted = false
    }
  }, [isTeamListMode, teamId])

  const displayTeam = useMemo(() => shouldUseDesignTeam(team) ? emptyTeamProfile : team, [team])

  if (isTeamListMode) {
    return <TeamsIndexPage />
  }

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
        <View className='icon-button icon-button--plain'>
          <Icon name='star' color='#0f172a' size={34} />
        </View>
      </View>

      <View className='team-identity-layout'>
        <View className='team-identity-assets'>
          <Flag team={displayTeam.name} size='lg' />
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
        {displayTeam.probabilities.map(item => (
          <View className='probability-mini' key={item.label}>
            <Text className='probability-mini__label'>{item.label}</Text>
            <Text className='probability-mini__value'>{item.value}</Text>
            {item.delta ? <Text className='delta delta--up'>▲ {item.delta.replace('+', '')}</Text> : null}
          </View>
        ))}
      </View>

      <Section title='核心评分' action='满分 10 分'>
        {displayTeam.ratings.map(item => (
          <RatingRow key={item.label} label={item.label} value={item.value} />
        ))}
      </Section>

      <Section title='近期状态'>
        <View className='team-form-report'>
          <View className='team-form-summary'>
            <Text className='team-form-summary__label'>近{displayTeam.form.recent?.matches || 10}场</Text>
            <View className='team-form-summary__record'>
              <Text className='text-positive'>{displayTeam.form.recent?.wins ?? 7}胜</Text>
              <Text>{displayTeam.form.recent?.draws ?? 2}平</Text>
              <Text className='text-negative'>{displayTeam.form.recent?.losses ?? 1}负</Text>
            </View>
            <Text className='team-form-summary__goals'>进{displayTeam.form.recent?.goalsFor ?? 21}失{displayTeam.form.recent?.goalsAgainst ?? 8}</Text>
          </View>
          <View className='team-evidence-list'>
            {(displayTeam.form.evidence || []).map(item => (
              <View className='team-evidence-row' key={item.label}>
                <Text className='team-evidence-row__label'>{item.label}</Text>
                <Text className={evidenceValueClass(item.tone)}>{item.value}</Text>
              </View>
            ))}
          </View>
        </View>
      </Section>

      <Section title='关键球员' action='状态评分'>
        <View className='player-list-head'>
          <Text>球员</Text>
          <Text>位置</Text>
          <Text>状态评分</Text>
        </View>
        {displayTeam.players.map(player => (
          <View className='player-row player-row--design' key={player.name}>
            <View className='avatar avatar--local'>
              <Icon name='team' color='#2563eb' size={34} />
            </View>
            <View className='player-row__main'>
              <Text className='list-row__title'>{player.name}</Text>
              {player.meta ? <Text className='list-row__meta'>{player.meta}</Text> : null}
            </View>
            <Text className='player-row__position'>{player.role}</Text>
            <View className='player-score-box'>
              <Text className='player-score'>{formatPlayerScore(player.form)}</Text>
              <View className='player-score-track'>
                <View className='player-score-track__bar' style={{ width: playerScoreWidth(player.form) }} />
              </View>
            </View>
          </View>
        ))}
      </Section>

      <View className='risk-card risk-card--design'>
        <View className='risk-card__icon'>
          <Icon name='shield' color='#dc2626' size={42} />
        </View>
        <View className='risk-card__main'>
          <Text className='risk-card__title'>风险提醒</Text>
          <Text className='risk-card__text'>{displayTeam.risks[0]?.label || '主力中卫伤停'}</Text>
          <Text className='risk-card__meta'>后防稳定性下降，淘汰赛风险上升。</Text>
        </View>
        <View className='risk-card__score'>
          <Text>{displayTeam.risks[0]?.value ?? -2.4}</Text>
          <Text>影响评分</Text>
        </View>
        <Icon name='chevron' color='#94a3b8' size={30} />
      </View>

      {loadState === 'error' ? <Text className='data-note'>后端未连接，当前使用设计稿样例数据。</Text> : null}
      <BottomNav active='teams' />
    </View>
  )
}
