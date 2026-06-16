import { useEffect, useState } from 'react'
import { Image, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { getLocalFlagAsset } from '@/assets/flags'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { RatingRow } from '@/components/RatingRow'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import { getTeamProfile, type LoadState } from '@/services/data'
import { getFlagCodeByTeamName, getTeamProfileById } from '@/services/teamResources'
import type { TeamProfile } from '@/services/mock'
import { goTo, routes } from '@/utils/navigation'

type TeamSource = 'home' | 'predictions' | 'groups' | 'direct'

type RouteContext = {
  source: TeamSource
  rankingType?: string
  groupId?: string
}

function toneClass(tone?: string) {
  if (tone === 'positive') return 'team-evidence-row__value text-positive'
  if (tone === 'negative') return 'team-evidence-row__value text-negative'
  return 'team-evidence-row__value'
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

function rankingLabel(value?: string) {
  const labels: Record<string, string> = {
    champion: '冠军榜',
    semifinal: '四强榜',
    darkhorse: '黑马榜'
  }
  return value ? labels[value] || '预测榜' : '预测榜'
}

function groupLabel(value?: string) {
  const letter = value?.match(/group-([a-z])/i)?.[1]?.toUpperCase()
  return letter ? `${letter}组` : '小组页'
}

function sourceLabel(context: RouteContext) {
  if (context.source === 'home') return '来自首页 · 冠军概率'
  if (context.source === 'predictions') return `来自预测榜 · ${rankingLabel(context.rankingType)}`
  if (context.source === 'groups') return `来自小组页 · ${groupLabel(context.groupId)}`
  return '球队画像'
}

function sourceMeta(context: RouteContext) {
  if (context.source === 'predictions') return '榜单概率、球队画像和关联赛程联动'
  if (context.source === 'groups') return '积分榜、出线概率和球队画像联动'
  if (context.source === 'home') return '首页冠军概率进入球队画像'
  return '球队画像默认入口'
}

function sourceTarget(context: RouteContext) {
  if (context.source === 'predictions') return routes.predictions
  if (context.source === 'groups') return `${routes.groups}?groupId=${context.groupId || 'group-a'}`
  return routes.matches
}

function getCircleFlagUrl(teamName: string) {
  const code = getFlagCodeByTeamName(teamName)
  return getLocalFlagAsset(code)
}

function contextRows(chips?: string[]) {
  return (chips || []).map(chip => {
    const separator = chip.indexOf(':')
    if (separator < 0) {
      return { label: '数据项', value: chip }
    }
    return {
      label: chip.slice(0, separator).trim(),
      value: chip.slice(separator + 1).trim()
    }
  })
}

export default function TeamDetailPage() {
  const [teamId] = useState<string | undefined>(getRouteTeamId)
  const [routeContext] = useState<RouteContext>(getRouteContext)
  const [team, setTeam] = useState<TeamProfile>(() => getTeamProfileById(teamId))
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const circleFlagUrl = getCircleFlagUrl(team.name)

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getTeamProfile(teamId)
      .then(data => {
        if (mounted) {
          setTeam(data)
          setLoadState('ready')
        }
      })
      .catch(() => {
        if (mounted) {
          setLoadState('error')
        }
      })

    return () => {
      mounted = false
    }
  }, [teamId])

  return (
    <View className='page page--team-report'>
      <View className='team-report-hero'>
        <View className='team-report-header'>
          <View className='icon-button icon-button--plain' onClick={() => goTo(sourceTarget(routeContext))}>
            <Icon name='back' color='#0f172a' size={32} />
          </View>
          <View className='team-report-hero__main'>
            <Text className='team-report-hero__name'>{team.name}</Text>
            <Text className='team-report-hero__subtitle'>{team.subtitle}</Text>
            <View className='team-report-hero__updated'>
              <Icon name='clock' color='#64748b' size={26} />
              <Text>{loadState === 'loading' ? '同步最新数据中' : team.updatedAt}</Text>
            </View>
          </View>
          <View className='icon-button icon-button--plain'>
            <Icon name='star' color='#0f172a' size={32} />
          </View>
        </View>

        <View className='team-report-hero__identity'>
          <View className='team-report-emblem'>
            <Flag team={team.name} size='lg' />
            <View className='team-report-badge'>
              {circleFlagUrl ? (
                <Image className='team-circle-flag' src={circleFlagUrl} mode='aspectFill' />
              ) : (
                <Icon name='shield' color='#2563eb' size={42} />
              )}
            </View>
          </View>
          <View className='team-ai-panel'>
            <View className='team-ai-panel__head'>
              <Icon name='ai' color='#2563eb' size={38} />
              <Text>AI 球队判断</Text>
            </View>
            <Text className='team-ai-panel__text'>{team.summary}</Text>
          </View>
        </View>
      </View>

      {loadState === 'error' && <StatusView title='球队数据暂未更新' detail='仅显示空态占位，请检查球队画像接口' />}

      <View className='team-source-strip' onClick={() => goTo(sourceTarget(routeContext))}>
        <View className='team-source-strip__icon'>
          <Icon name={routeContext.source === 'groups' ? 'trophy' : routeContext.source === 'predictions' ? 'chart' : 'ball'} color='#2563eb' size={34} />
        </View>
        <View className='team-source-strip__main'>
          <Text className='team-source-strip__title'>{sourceLabel(routeContext)}</Text>
          <Text className='team-source-strip__meta'>{sourceMeta(routeContext)}</Text>
        </View>
        <Text className='team-source-strip__action'>返回</Text>
      </View>

      <View className='probability-mini-grid team-probability-strip'>
        {team.probabilities.length ? team.probabilities.map(item => (
          <View className='probability-mini' key={item.label}>
            <Text className='probability-mini__value'>{item.value}</Text>
            <Text className='probability-mini__label'>{item.label}</Text>
            {item.delta ? <Text className='delta delta--up'>{item.delta}</Text> : null}
          </View>
        )) : <Text className='empty-state'>暂无真实球队概率数据</Text>}
      </View>

      <Section title='核心评分' action='满分 10 分'>
        {team.ratings.length ? team.ratings.map(item => (
          <RatingRow key={item.label} label={item.label} value={item.value} />
        )) : <Text className='empty-state'>暂无真实评分数据</Text>}
      </Section>

      <Section title='近期状态'>
        <View className='team-form-report'>
          <View className='team-form-summary'>
            <Text className='team-form-summary__label'>{team.form.recent?.matches ? `近${team.form.recent.matches}场` : '近期战绩'}</Text>
            {team.form.recent?.wins !== undefined && team.form.recent?.wins !== null ? (
              <View className='team-form-summary__record'>
                <Text className='text-positive'>{team.form.recent.wins}胜</Text>
                <Text>{team.form.recent.draws ?? 0}平</Text>
                <Text className='text-negative'>{team.form.recent.losses ?? 0}负</Text>
              </View>
            ) : (
              <Text className='team-form-summary__fallback'>{team.form.headline}</Text>
            )}
            {team.form.recent?.goalsFor !== undefined && team.form.recent?.goalsFor !== null ? (
              <Text className='team-form-summary__goals'>进{team.form.recent.goalsFor}失{team.form.recent.goalsAgainst ?? '-'}</Text>
            ) : null}
          </View>
          <View className='team-evidence-list'>
            {team.form.evidence?.length ? team.form.evidence.map(item => (
              <View className='team-evidence-row' key={item.label}>
                <Text className='team-evidence-row__label'>{item.label}</Text>
                <Text className={toneClass(item.tone)}>{item.value}</Text>
              </View>
            )) : <Text className='empty-state'>暂无真实近期状态数据</Text>}
          </View>
        </View>
      </Section>

      <Section title='关键球员' action='状态评分'>
        {team.players.length ? (
          <View className='player-list-head'>
            <Text>球员</Text>
            <Text>位置</Text>
            <Text>状态评分</Text>
          </View>
        ) : null}
        {team.players.length ? team.players.map(player => (
          <View className='player-row' key={player.name}>
            <View className='avatar'>
              <View className='avatar__fallback'>
                <Icon name='team' color='#2563eb' size={30} />
              </View>
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
        )) : <Text className='empty-state'>暂无真实关键球员数据</Text>}
      </Section>

      <Section title='阵容与教练'>
        <View className='team-context-list'>
          {contextRows(team.dataChips).map(item => (
            <View className='team-context-row' key={`${item.label}-${item.value}`}>
              <Text className='team-context-row__label'>{item.label}</Text>
              <Text className='team-context-row__value'>{item.value}</Text>
            </View>
          ))}
          {team.group ? (
            <View className='team-context-row'>
              <Text className='team-context-row__label'>小组形势</Text>
              <Text className='team-context-row__value'>{team.group.name} 第{team.group.rank ?? '-'} · {team.group.goals || '进失球待同步'}</Text>
            </View>
          ) : null}
          {team.coach ? (
            <View className='team-context-row team-context-row--coach'>
              <View>
                <Text className='team-context-row__label'>{team.coach.name}</Text>
                <Text className='list-row__meta'>{team.coach.record || '战绩待同步'}{team.coach.winRate ? ` · 胜率 ${team.coach.winRate}` : ''}</Text>
              </View>
              <Text className='team-context-row__value'>主教练</Text>
            </View>
          ) : <Text className='empty-state'>主教练信息待同步</Text>}
        </View>
      </Section>

      <Section title='关联比赛'>
        {team.relatedMatches?.length ? team.relatedMatches.map(match => (
          <View className='related-match-row' key={match.id} onClick={() => goTo(`${routes.matchDetail}?matchId=${match.id}`)}>
            <View>
              <Text className='list-row__title'>vs {match.opponent}</Text>
              <Text className='list-row__meta'>{match.stage} · {match.time}</Text>
              {match.venue ? <Text className='list-row__meta'>{match.venue}</Text> : null}
            </View>
            <Text className='related-match-row__status'>{match.tendency || match.status}</Text>
          </View>
        )) : <Text className='empty-state'>关联赛程待同步</Text>}
      </Section>

      <Section title='相关新闻'>
        {team.news.length ? team.news.map(item => (
          <View className='news-card' key={item.sourceUrl || item.title}>
            <View className='news-card__head'>
              <Text className='news-card__source'>{item.source}</Text>
              {item.relevance ? <Text className='news-card__badge'>{item.relevance}</Text> : null}
            </View>
            <Text className='news-card__title'>{item.title}</Text>
            {item.summary ? <Text className='news-card__summary'>{item.summary}</Text> : null}
          </View>
        )) : <Text className='empty-state'>暂无相关新闻</Text>}
      </Section>

      {team.risks.length ? (
        <View className='risk-card'>
          <View className='risk-card__head'>
            <Icon name='shield' color='#dc2626' size={34} />
            <Text>风险提醒</Text>
          </View>
          {team.risks.map(risk => (
            <View className='risk-card__row' key={risk.label}>
              <Text>{risk.label}</Text>
              <Text className='text-negative'>{risk.value}</Text>
            </View>
          ))}
        </View>
      ) : null}

      <BottomNav active='teams' />
    </View>
  )
}
