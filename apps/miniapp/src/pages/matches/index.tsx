import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
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
      <View className='matchday-hero' onClick={() => goTo(routes.matchDetail)}>
        <View className='matchday-hero__top'>
          <View>
            <Text className='matchday-hero__eyebrow'>WORLD CUP AI BOARD</Text>
            <Text className='matchday-hero__title'>今日预测</Text>
          </View>
          <Text className='matchday-hero__status'>{match.status}</Text>
        </View>

        <View className='matchday-hero__fixture'>
          <View className='team-badge'>
            <Text className='team-badge__abbr'>USA</Text>
            <Text className='team-badge__name'>{match.home}</Text>
          </View>
          <View className='matchday-hero__center'>
            <Text className='matchday-hero__time'>{match.time}</Text>
            <Text className='matchday-hero__versus'>VS</Text>
            <Text className='matchday-hero__venue'>{match.venue}</Text>
          </View>
          <View className='team-badge team-badge--away'>
            <Text className='team-badge__abbr'>PAR</Text>
            <Text className='team-badge__name'>{match.away}</Text>
          </View>
        </View>

        <View className='prediction-strip'>
          <Text className='prediction-strip__label'>AI 倾向</Text>
          <Text className='prediction-strip__value'>{match.tendency}</Text>
          <Text className='prediction-strip__confidence'>{match.confidence}</Text>
        </View>

        <ProbabilitySummary probabilities={match.probabilities} />

        <View className='hero-insight'>
          <Text className='hero-insight__label'>赛前信号</Text>
          <Text className='hero-insight__text'>{match.insight}</Text>
        </View>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新赛前数据' detail='稍后显示最新预测快照' />}
      {loadState === 'error' && <StatusView title='赛前数据暂未更新' detail='当前显示本地预测快照' />}

      <View className='quick-grid'>
        <View className='quick-card'>
          <Text className='quick-card__value'>50k</Text>
          <Text className='quick-card__label'>模拟次数</Text>
        </View>
        <View className='quick-card'>
          <Text className='quick-card__value'>1.42</Text>
          <Text className='quick-card__label'>美国 xG</Text>
        </View>
        <View className='quick-card'>
          <Text className='quick-card__value'>1-1</Text>
          <Text className='quick-card__label'>最高比分</Text>
        </View>
      </View>

      <Section title='AI 简报'>
        <View onClick={() => goTo(routes.matchDetail)}>
          <AIReportCard title='模型结论' status='可解释预测'>
            美国胜率只领先 15 个百分点，真正的风险在巴拉圭反击效率和低比分平局。
          </AIReportCard>
          <View className='primary-link'>
            <Text>查看 AI 赛前报告</Text>
          </View>
        </View>
      </Section>

      <Section title='即将开始'>
        {homeData.upcomingMatches.map(item => (
          <View className='list-row' key={item.id} onClick={() => goTo(routes.matchDetail)}>
            <View>
              <Text className='list-row__title'>{item.home} vs {item.away}</Text>
              <Text className='list-row__meta'>{item.time} · 小组赛</Text>
            </View>
            <Text className='list-row__right'>{item.tendency}</Text>
          </View>
        ))}
      </Section>

      <Section title='冠军概率' action='查看全部'>
        {homeData.championTop.map(team => (
          <ProgressRow key={team.name} label={team.name} value={team.probability} />
        ))}
      </Section>

      <BottomNav active='matches' />
    </View>
  )
}
