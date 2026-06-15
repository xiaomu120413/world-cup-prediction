import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProgressRow } from '@/components/ProgressRow'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import { getRankingData, type LoadState } from '@/services/data'
import { championRankings, darkHorseRankings, semiFinalRankings, type RankingTeam } from '@/services/mock'
import { goTo, routes } from '@/utils/navigation'

const rankingMap = {
  champion: championRankings,
  semifinal: semiFinalRankings,
  darkhorse: darkHorseRankings
}

const tabLabels = {
  champion: '冠军',
  semifinal: '四强',
  darkhorse: '黑马'
}

type Tab = keyof typeof rankingMap

export default function PredictionsPage() {
  const [active, setActive] = useState<Tab>('champion')
  const [rankings, setRankings] = useState<RankingTeam[]>(rankingMap[active])
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setRankings(rankingMap[active])
    setLoadState('loading')
    getRankingData(active)
      .then(data => {
        if (mounted) {
          setRankings(data)
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
  }, [active])

  return (
    <View className='page'>
      <View className='page-head page-head--center'>
        <Text className='app-title app-title--sm'>预测榜</Text>
        <Text className='page-head__subtitle'>基于 50,000 次模拟 · 更新于 18:00</Text>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新预测榜' detail='稍后显示最新模拟快照' />}
      {loadState === 'error' && <StatusView title='预测榜暂未更新' detail='当前显示本地模拟快照' />}

      <View className='segmented'>
        {Object.keys(tabLabels).map(key => (
          <Text
            key={key}
            className={`segmented__item ${active === key ? 'segmented__item--active' : ''}`}
            onClick={() => setActive(key as Tab)}
          >
            {tabLabels[key as Tab]}
          </Text>
        ))}
      </View>

      <Section title='AI 榜单解读'>
        <AIReportCard title='概率变化' status={tabLabels[active]}>
          法国仍是当前榜单第一档，巴西和英格兰差距很小。今日变化主要来自阵容可用性、赛程路径和近期进攻效率。
        </AIReportCard>
      </Section>

      <Section title='概率排名'>
        {rankings.map(team => (
          <View className='ranking-row' key={team.name} onClick={() => goTo(routes.teamDetail)}>
            <View className='ranking-row__top'>
              <Text className='ranking-row__rank'>{team.rank}</Text>
              <Flag team={team.name} size='sm' />
              <Text className='ranking-row__name'>{team.name}</Text>
              <Text className='ranking-row__probability'>{team.probability}%</Text>
            </View>
            <View className='ranking-row__detail'>
              <View className='ranking-row__track'>
                <ProgressRow label='' value={team.probability} />
              </View>
              <Text className={team.delta >= 0 ? 'delta delta--up' : 'delta delta--down'}>
                {team.delta >= 0 ? '+' : '-'}{Math.abs(team.delta)}%
              </Text>
              <Text className='reason-chip'>{team.reason}</Text>
            </View>
          </View>
        ))}
      </Section>

      <View className='today-change-card' onClick={() => goTo(routes.matchDetail)}>
        <View className='today-change-card__icon'>
          <Icon name='chart' color='#2563eb' size={36} />
        </View>
        <View>
          <Text className='today-change-card__title'>今日变化</Text>
          <Text className='today-change-card__text'>美国胜率上调，主场环境和阵容完整度带来 +2.1% 的黑马概率变化。</Text>
        </View>
      </View>

      <BottomNav active='predictions' />
    </View>
  )
}
