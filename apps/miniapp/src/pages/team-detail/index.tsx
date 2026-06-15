import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { RatingRow } from '@/components/RatingRow'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import { getTeamProfile, type LoadState } from '@/services/data'
import { getTeamProfileById } from '@/services/teamResources'
import type { TeamProfile } from '@/services/mock'

function getRouteTeamId() {
  const params = Taro.getCurrentInstance().router?.params
  const value = params?.teamId
  return typeof value === 'string' && value ? value : 'france'
}

export default function TeamDetailPage() {
  const [teamId] = useState(getRouteTeamId)
  const [team, setTeam] = useState<TeamProfile>(() => getTeamProfileById(teamId))
  const [loadState, setLoadState] = useState<LoadState>('idle')

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
    <View className='page'>
      <View className='team-hero'>
        <View className='team-hero__tools'>
          <View className='icon-button'>
            <Icon name='back' color='#0f172a' size={32} />
          </View>
          <View className='icon-button'>
            <Icon name='star' color='#2563eb' size={32} />
          </View>
        </View>
        <View className='team-hero__main'>
          <Flag team={team.name} size='lg' />
          <Text className='team-hero__name'>{team.name}</Text>
          <Text className='team-hero__subtitle'>{team.subtitle}</Text>
        </View>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新球队数据' detail='稍后显示最新球队快照' />}
      {loadState === 'error' && <StatusView title='球队数据暂未更新' detail='当前显示本地球队快照' />}

      <Section title='AI 球队判断'>
        <AIReportCard title='球队状态' status={team.updatedAt}>
          {team.summary}
        </AIReportCard>
      </Section>

      <View className='probability-mini-grid'>
        {team.probabilities.map(item => (
          <View className='probability-mini' key={item.label}>
            <Text className='probability-mini__value'>{item.value}</Text>
            <Text className='probability-mini__label'>{item.label}</Text>
            {item.delta ? <Text className='delta delta--up'>{item.delta}</Text> : null}
          </View>
        ))}
      </View>

      <Section title='核心评分'>
        {team.ratings.map(item => (
          <RatingRow key={item.label} label={item.label} value={item.value} />
        ))}
      </Section>

      <Section title='近期状态'>
        <View className='form-card'>
          <Text className='form-card__headline'>{team.form.headline}</Text>
          <View className='stat-grid'>
            {team.form.stats.map(stat => (
              <Text className='stat-chip' key={stat}>{stat}</Text>
            ))}
          </View>
        </View>
      </Section>

      <Section title='关键球员'>
        {team.players.map(player => (
          <View className='player-row' key={player.name}>
            <View className='avatar'>
              <Text>{player.name.slice(0, 1)}</Text>
            </View>
            <View className='player-row__main'>
              <Text className='list-row__title'>{player.name}</Text>
              <Text className='list-row__meta'>{player.role}</Text>
            </View>
            <Text className='player-score'>{player.form}</Text>
          </View>
        ))}
      </Section>

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

      <BottomNav active='teams' />
    </View>
  )
}
