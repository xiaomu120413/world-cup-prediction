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
import { goTo, routes } from '@/utils/navigation'

const fallbackHome: HomeData = {
  featuredMatch,
  upcomingMatches,
  championTop,
  dataSourceStatus: {
    label: '离线',
    detail: '未连接后端',
    isDatabase: false,
    audit: '真实数据未同步',
    counts: '无本地比赛数据',
    freshness: '离线'
  },
  updatedAt: '更新时间待同步'
}

function splitKickoff(value: string) {
  const match = value.match(/^(.+)\s+(\d{2}:\d{2})$/)
  if (!match) {
    return { date: '', clock: value }
  }
  return { date: match[1], clock: match[2] }
}

export default function MatchesPage() {
  const [homeData, setHomeData] = useState<HomeData>(fallbackHome)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const match = homeData.featuredMatch
  const focusStage = match.stage === '世界杯赛程' ? '' : match.stage
  const focusVersion = match.versionLabel || match.status

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
            <Text>今日赛程</Text>
          </View>
        </View>
        <View className='header-ai' onClick={() => goTo(`${routes.matchDetail}?matchId=${match.id}`)}>
          <Icon name='ai' color='#2563eb' size={30} />
          <Text>AI 赛前报告</Text>
        </View>
      </View>

      <View className='updated-line'>
        <Icon name='clock' color='#94a3b8' size={26} />
        <Text>{homeData.updatedAt}</Text>
      </View>

      <View className='home-flow-grid'>
        <View className='home-flow-card' onClick={() => goTo(routes.groups)}>
          <Icon name='trophy' color='#2563eb' size={34} />
          <View>
            <Text className='home-flow-card__title'>小组形势</Text>
            <Text className='home-flow-card__meta'>A-L 组</Text>
          </View>
        </View>
        <View className='home-flow-card' onClick={() => goTo(routes.predictions)}>
          <Icon name='chart' color='#2563eb' size={34} />
          <View>
            <Text className='home-flow-card__title'>预测榜</Text>
            <Text className='home-flow-card__meta'>冠军/四强/黑马</Text>
          </View>
        </View>
        <View className='home-flow-card' onClick={() => goTo(routes.teamDetail)}>
          <Icon name='shield' color='#2563eb' size={34} />
          <View>
            <Text className='home-flow-card__title'>球队画像</Text>
            <Text className='home-flow-card__meta'>阵容/状态</Text>
          </View>
        </View>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新赛前数据' detail='稍后显示最新预测快照' />}
      {loadState === 'error' && <StatusView title='赛前数据暂未更新' detail='仅显示空态占位，请检查后端真实数据接口' />}

      <View className='focus-card' onClick={() => goTo(`${routes.matchDetail}?matchId=${match.id}`)}>
        <View className='focus-card__top'>
          <View>
            <Text className='card-eyebrow'>今日重点</Text>
          </View>
          {focusStage ? <Text className='card-meta'>{focusStage}</Text> : null}
        </View>

        <View className='fixture'>
          <View className='fixture__team'>
            <Flag team={match.home} size='lg' />
            <Text className='fixture__name'>{match.home}</Text>
          </View>
          <View className='fixture__middle'>
            <Text className='match-version-pill'>{focusVersion}</Text>
            <Text className={match.score ? 'fixture__score' : 'fixture__vs'}>{match.score || 'VS'}</Text>
            <Text className='fixture__time'>{match.time}</Text>
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
        {homeData.upcomingMatches.length ? homeData.upcomingMatches.map(item => {
          const kickoff = splitKickoff(item.time)
          return (
            <View className='match-row match-row--schedule' key={item.id} onClick={() => goTo(`${routes.matchDetail}?matchId=${item.id}`)}>
              <View className='match-row__time'>
                <Text>{kickoff.clock}</Text>
                {kickoff.date ? <Text>{kickoff.date}</Text> : null}
              </View>
              <View className='match-row__fixture'>
                <View className='match-row__team'>
                  <Flag team={item.home} size='sm' />
                  <Text>{item.home}</Text>
                </View>
                <Text className='match-row__vs'>VS</Text>
                <View className='match-row__team match-row__team--away'>
                  <Flag team={item.away} size='sm' />
                  <Text>{item.away}</Text>
                </View>
              </View>
              <View className='match-row__trend'>
                <Text>{item.tendency}</Text>
                <Icon name='chevron' color='#94a3b8' size={26} />
              </View>
            </View>
          )
        }) : <Text className='empty-state'>暂无真实赛程数据</Text>}
      </Section>

      <Section title='冠军概率' action='全部' onAction={() => goTo(routes.predictions)}>
        {homeData.championTop.length ? homeData.championTop.map((team, index) => (
          <View
            className='champion-row'
            key={team.name}
            onClick={() => goTo(routes.predictions)}
          >
            <View className='rank-medal'>
              <Icon name='medal' color={index === 0 ? '#f59e0b' : '#94a3b8'} size={30} />
              <Text>{index + 1}</Text>
            </View>
            <Flag team={team.name} size='sm' />
            <View className='champion-row__main'>
              <Text className='champion-row__name'>{team.name}</Text>
              {team.meta ? <Text className='champion-row__meta'>{team.meta}</Text> : null}
            </View>
            <View className='champion-row__bar'>
              <ProgressRow label='' value={team.probability} />
            </View>
            <Text className='champion-row__value'>{team.probability}%</Text>
          </View>
        )) : <Text className='empty-state'>暂无真实冠军概率数据</Text>}
      </Section>

      <BottomNav active='matches' />
    </View>
  )
}
