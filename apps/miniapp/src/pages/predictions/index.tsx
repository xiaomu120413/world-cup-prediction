import { useState } from 'react'
import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { ProgressRow } from '@/components/ProgressRow'
import { Section } from '@/components/Section'
import { championRankings, darkHorseRankings, semiFinalRankings } from '@/services/mock'
import { goTo, routes } from '@/utils/navigation'

const rankingMap = {
  champion: championRankings,
  semifinal: semiFinalRankings,
  darkhorse: darkHorseRankings
}

type Tab = keyof typeof rankingMap

export default function PredictionsPage() {
  const [active, setActive] = useState<Tab>('champion')
  const rankings = rankingMap[active]

  return (
    <View className='page'>
      <View className='page-head'>
        <Text className='page-head__title'>预测榜</Text>
        <Text className='page-head__subtitle'>基于 50,000 次模拟</Text>
        <Text className='muted'>更新于 18:00</Text>
      </View>

      <View className='segmented'>
        <Text className={`segmented__item ${active === 'champion' ? 'segmented__item--active' : ''}`} onClick={() => setActive('champion')}>冠军</Text>
        <Text className={`segmented__item ${active === 'semifinal' ? 'segmented__item--active' : ''}`} onClick={() => setActive('semifinal')}>四强</Text>
        <Text className={`segmented__item ${active === 'darkhorse' ? 'segmented__item--active' : ''}`} onClick={() => setActive('darkhorse')}>黑马</Text>
      </View>

      <Section title='AI 榜单解读'>
        <AIReportCard title='榜单变化'>
          法国仍是冠军概率最高球队，巴西和英格兰差距很小。
        </AIReportCard>
      </Section>

      <Section title='概率排名'>
        {rankings.map(team => (
          <View className='ranking-row' key={team.name} onClick={() => goTo(routes.teamDetail)}>
            <View className='ranking-row__top'>
              <Text className='ranking-row__rank'>{team.rank}</Text>
              <Text className='ranking-row__name'>{team.name}</Text>
              <Text className='ranking-row__probability'>{team.probability}%</Text>
            </View>
            <View className='ranking-row__detail'>
              <Text className={team.delta >= 0 ? 'text-positive' : 'text-negative'}>
                {team.delta >= 0 ? '▲' : '▼'}{Math.abs(team.delta)}%
              </Text>
              <Text className='reason-chip'>{team.reason}</Text>
            </View>
            <ProgressRow label='' value={team.probability} />
          </View>
        ))}
      </Section>

      <Section title='今日变化'>
        <View className='list-row' onClick={() => goTo(routes.matchDetail)}>
          <Text className='list-row__title'>美国胜率上调</Text>
          <Text className='list-row__right'>出线概率 +18%</Text>
        </View>
      </Section>

      <BottomNav active='predictions' />
    </View>
  )
}

