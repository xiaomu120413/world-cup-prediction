import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProbabilitySummary } from '@/components/ProbabilitySummary'
import { ProgressRow } from '@/components/ProgressRow'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import { getHomeData, type HomeData, type LoadState } from '@/services/data'
import { championTop, featuredMatch, upcomingMatches } from '@/services/mock'
import { getTeamIdByName } from '@/services/teamResources'
import { goTo, routes } from '@/utils/navigation'

const fallbackHome: HomeData = {
  featuredMatch,
  upcomingMatches,
  championTop,
  dataSourceStatus: {
    label: 'Mock',
    detail: 'Local fallback',
    isDatabase: false
  },
  updatedAt: '更新于 18:00'
}

export default function MatchesPage() {
  const [homeData, setHomeData] = useState<HomeData>(fallbackHome)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const match = homeData.featuredMatch

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getHomeData()
      .then(data => {
        if (mounted) {
          setHomeData(data)
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
  }, [])

  return (
    <View className='page page--matchday'>
      <View className='app-header app-header--home'>
        <View>
          <Text className='app-title'>世界杯预测</Text>
          <View className='subline'>
            <View className='subline__bar' />
            <Text>今日赛程 · 6月13日</Text>
          </View>
        </View>
        <View className='header-ai' onClick={() => goTo(routes.matchDetail)}>
          <Icon name='ai' color='#2563eb' size={30} />
          <Text>AI 赛前报告</Text>
        </View>
      </View>

      <View className='updated-line'>
        <Icon name='clock' color='#94a3b8' size={26} />
        <Text>{homeData.updatedAt}</Text>
        <Text className={homeData.dataSourceStatus.isDatabase ? 'source-pill source-pill--db' : 'source-pill'}>
          {homeData.dataSourceStatus.label}
        </Text>
        <Text>{homeData.dataSourceStatus.detail}</Text>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新赛前数据' detail='稍后显示最新预测快照' />}
      {loadState === 'error' && <StatusView title='赛前数据暂未更新' detail='当前显示本地预测快照' />}

      <View className='focus-card' onClick={() => goTo(routes.matchDetail)}>
        <View className='focus-card__top'>
          <View>
            <Text className='card-eyebrow'>今日重点</Text>
            <Text className='card-title'>{match.stage}</Text>
          </View>
          <Text className='status-pill'>{match.status}</Text>
        </View>

        <View className='fixture'>
          <View className='fixture__team'>
            <Flag team={match.home} size='lg' />
            <Text className='fixture__name'>{match.home}</Text>
          </View>
          <View className='fixture__middle'>
            <Text className='fixture__time'>{match.time}</Text>
            <Text className='fixture__vs'>VS</Text>
            <Text className='fixture__venue'>{match.venue}</Text>
          </View>
          <View className='fixture__team fixture__team--away'>
            <Flag team={match.away} size='lg' />
            <Text className='fixture__name'>{match.away}</Text>
          </View>
        </View>

        <ProbabilitySummary probabilities={match.probabilities} />

        <View className='ai-summary-inline'>
          <AIReportCard title='AI 判断' status={match.confidence}>
            {match.insight}
          </AIReportCard>
          <View className='report-link'>
            <Text>查看 AI 赛前报告</Text>
            <Icon name='chevron' color='#2563eb' size={30} />
          </View>
        </View>
      </View>

      <Section title='即将开始'>
        {homeData.upcomingMatches.map(item => (
          <View className='list-row match-row' key={item.id} onClick={() => goTo(routes.matchDetail)}>
            <View className='match-row__teams'>
              <Flag team={item.home} size='sm' />
              <Text className='list-row__title'>{item.home}</Text>
              <Text className='muted-inline'>vs</Text>
              <Flag team={item.away} size='sm' />
              <Text className='list-row__title'>{item.away}</Text>
            </View>
            <View className='list-row__right'>
              <Text>{item.time}</Text>
              <Text className='trend-pill'>{item.tendency}</Text>
            </View>
          </View>
        ))}
      </Section>

      <Section title='冠军概率' action='全部'>
        {homeData.championTop.map((team, index) => (
          <View
            className='champion-row'
            key={team.name}
            onClick={() => goTo(`${routes.teamDetail}?teamId=${getTeamIdByName(team.name)}`)}
          >
            <View className='rank-medal'>
              <Icon name='medal' color={index === 0 ? '#f59e0b' : '#94a3b8'} size={30} />
              <Text>{index + 1}</Text>
            </View>
            <Flag team={team.name} size='sm' />
            <Text className='champion-row__name'>{team.name}</Text>
            <View className='champion-row__bar'>
              <ProgressRow label='' value={team.probability} />
            </View>
            <Text className='champion-row__value'>{team.probability}%</Text>
          </View>
        ))}
      </Section>

      <BottomNav active='matches' />
    </View>
  )
}
